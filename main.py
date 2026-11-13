"""FastAPI entry point for the trip planner and public analytics configuration."""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pydantic import ValidationError
from starlette.responses import FileResponse, RedirectResponse

from agent.agentic_workflow import GraphBuilder
from utils.save_to_document import save_to_pdf
from version_b_service import (PlanRequest, EditRequest, AskRequest, RecommendRequest,
                               TripPlan, create_plan, edit_plan, ask_about_trip,
                               recommend, weather, model_configured, ProviderUnavailable)
from place_enrichment import enrich_plan
from version_b_pdf import save_v2_pdf
from booking_service import BookingFile, BookingList, extract_booking, check_bookings
from offer_check import OfferRequest, check_offer

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voyage Trip Planner")
app.mount("/output", StaticFiles(directory=OUTPUT), name="output")
app.mount("/assets", StaticFiles(directory=ROOT / "assets"), name="assets")


@app.middleware("http")
async def require_account(request: Request, call_next):
    """Validate the Supabase access token before running paid Version B tools."""
    if request.url.path.startswith("/api/v2/"):
        url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_ANON_KEY", "")
        if not url or not key:
            return JSONResponse({"detail": "Account sign-in is not configured yet."}, status_code=503)
        token = request.headers.get("authorization", "")
        if not token.startswith("Bearer "):
            return JSONResponse({"detail": "Sign in to use Voyage."}, status_code=401)
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                response = await client.get(
                    f"{url}/auth/v1/user",
                    headers={"apikey": key, "Authorization": token},
                )
            if response.status_code != 200 or not response.json().get("id"):
                return JSONResponse({"detail": "Your session expired. Sign in again."}, status_code=401)
        except (httpx.HTTPError, ValueError):
            return JSONResponse({"detail": "Could not verify your session. Try again."}, status_code=503)
    return await call_next(request)


@app.get("/")
def get_index():
    return FileResponse(ROOT / "index.html")


@app.get("/experiment")
def enter_experiment(request: Request):
    """Assign a stable variant without altering the two direct page URLs."""
    variant = request.cookies.get("voyage_ab_v1")
    if variant not in {"A", "B"}:
        variant = "B" if secrets.randbelow(2) else "A"
    destination = "/version-b" if variant == "B" else "/"
    response = RedirectResponse(f"{destination}?experiment=voyage_ab_v1", status_code=302)
    response.set_cookie("voyage_ab_v1", variant, max_age=60 * 60 * 24 * 30,
                        httponly=False, secure=request.url.scheme == "https",
                        samesite="lax", path="/")
    return response


@app.get("/version-b")
def get_version_b():
    return FileResponse(ROOT / "version-b.html")


@app.get("/version-b.css")
def get_version_b_css():
    return FileResponse(ROOT / "version-b.css", media_type="text/css")


@app.get("/version-b.js")
def get_version_b_js():
    return FileResponse(ROOT / "version-b.js", media_type="text/javascript")


@app.get("/version-b-live.js")
def get_version_b_live_js():
    return FileResponse(ROOT / "version-b-live.js", media_type="text/javascript")


@app.get("/bookings.js")
def get_bookings_js():
    return FileResponse(ROOT / "bookings.js", media_type="text/javascript")


@app.get("/before-you-book.js")
def get_before_you_book_js():
    return FileResponse(ROOT / "before-you-book.js", media_type="text/javascript")


@app.get("/analytics.js")
def get_analytics_script():
    return FileResponse(ROOT / "analytics.js", media_type="text/javascript")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/analytics-config")
def analytics_config():
    """Only publish browser-side project IDs. Never expose LLM or service keys."""
    return {
        "ga_measurement_id": os.getenv("GA_MEASUREMENT_ID", ""),
        "mixpanel_token": os.getenv("MIXPANEL_TOKEN", ""),
        "mixpanel_api_host": os.getenv("MIXPANEL_API_HOST", ""),
        "amplitude_api_key": os.getenv("AMPLITUDE_API_KEY", ""),
        "posthog_project_token": os.getenv("POSTHOG_PROJECT_TOKEN", ""),
        "posthog_host": os.getenv("POSTHOG_HOST", "https://us.i.posthog.com"),
    }


@app.get("/auth-config")
def auth_config():
    """The publishable key is safe for browser use; RLS protects user data."""
    return {"url": os.getenv("SUPABASE_URL", ""),
            "anon_key": os.getenv("SUPABASE_ANON_KEY", "")}


@app.get("/auth.js")
def get_auth_script():
    return FileResponse(ROOT / "auth.js", media_type="text/javascript")


def _v2_ai_available():
    if not model_configured():
        raise HTTPException(status_code=503, detail="Add GROQ_API_KEY or GOOGLE_API_KEY to enable AI planning")


@app.post("/api/v2/plan")
async def v2_plan(request: PlanRequest):
    _v2_ai_available()
    try:
        return await run_in_threadpool(create_plan, request)
    except ProviderUnavailable as exc:
        logger.warning("Version B model quota reached")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        logger.warning("Version B plan validation failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The planner returned an incomplete trip. Please try again.") from exc
    except Exception as exc:
        logger.error("Version B plan failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="The planner is temporarily unavailable. Please try again.") from exc


@app.post("/api/v2/edit")
async def v2_edit(request: EditRequest):
    _v2_ai_available()
    try:
        return await run_in_threadpool(edit_plan, request)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Version B edit failed")
        raise HTTPException(status_code=502, detail="Could not create an alternative. Please try again.") from exc


@app.post("/api/v2/ask")
async def v2_ask(request: AskRequest):
    _v2_ai_available()
    try:
        return {"answer": await run_in_threadpool(ask_about_trip, request)}
    except Exception as exc:
        logger.exception("Version B assistant failed")
        raise HTTPException(status_code=502, detail="The assistant could not answer. Please try again.") from exc


@app.post("/api/v2/recommend")
async def v2_recommend(request: RecommendRequest):
    _v2_ai_available()
    try:
        return await run_in_threadpool(recommend, request)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Version B recommendation failed")
        raise HTTPException(status_code=502, detail="Could not recommend a place. Please try again.") from exc


@app.get("/api/v2/weather")
async def v2_weather(city: str):
    if not 2 <= len(city) <= 80:
        raise HTTPException(status_code=422, detail="Enter a valid destination")
    try:
        return await run_in_threadpool(weather, city)
    except Exception as exc:
        logger.warning("Version B weather lookup failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Weather is temporarily unavailable") from exc


class PdfRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=80)
    plan: TripPlan


class EnrichRequest(BaseModel):
    plan: TripPlan


@app.post("/api/v2/enrich")
async def v2_enrich(request: EnrichRequest):
    return await run_in_threadpool(enrich_plan, request.plan)


@app.post("/api/v2/pdf")
async def v2_pdf(request: PdfRequest):
    filename = await run_in_threadpool(save_v2_pdf, request.destination, request.plan, str(OUTPUT))
    if not filename:
        raise HTTPException(status_code=502, detail="Could not create the PDF")
    return {"pdf_url": f"/output/{filename}"}


@app.post("/api/v2/bookings/extract")
async def v2_booking_extract(request: BookingFile):
    try:
        return await run_in_threadpool(extract_booking, request)
    except ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Booking extraction failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not read this confirmation. Enter its details manually or try another file.") from exc


@app.post("/api/v2/bookings/check")
async def v2_booking_check(request: BookingList):
    return {"issues": check_bookings(request.bookings)}


@app.post("/api/v2/offers/check")
async def v2_offer_check(request: OfferRequest):
    try:
        return await run_in_threadpool(check_offer, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.warning("Offer check failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not check this offer. Please try again.") from exc


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)


def generate_plan(question: str) -> str:
    graph = GraphBuilder(model_provider=os.getenv("MODEL_PROVIDER", "google"))()
    output = graph.invoke({"messages": [("user", question)]}, config={"recursion_limit": 8})
    if not isinstance(output, dict) or not output.get("messages"):
        raise RuntimeError("The planner returned no messages")
    for message in reversed(output["messages"]):
        content = getattr(message, "content", "")
        if isinstance(content, str) and content.strip():
            return content.strip()
    raise RuntimeError("The planner returned no itinerary")


@app.post("/query")
async def query_travel_agent(query: QueryRequest):
    provider = os.getenv("MODEL_PROVIDER", "google")
    if not os.getenv("GROQ_API_KEY" if provider == "groq" else "GOOGLE_API_KEY"):
        raise HTTPException(status_code=503, detail="Planner is not configured yet")
    try:
        answer = await run_in_threadpool(generate_plan, query.question.strip())
    except Exception:
        logger.exception("Trip generation failed")
        raise HTTPException(status_code=502, detail="The planner could not generate this trip. Please try again.")

    pdf_filename = await run_in_threadpool(save_to_pdf, answer, str(OUTPUT))
    return {"answer": answer, "pdf_url": f"/output/{pdf_filename}" if pdf_filename else None}
