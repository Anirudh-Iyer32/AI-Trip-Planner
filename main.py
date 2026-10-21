"""FastAPI entry point for the trip planner and public analytics configuration."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.responses import FileResponse

from agent.agentic_workflow import GraphBuilder
from utils.save_to_document import save_to_pdf

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
logger = logging.getLogger(__name__)

app = FastAPI(title="Voyage Trip Planner")
app.mount("/output", StaticFiles(directory=OUTPUT), name="output")


@app.get("/")
def get_index():
    return FileResponse(ROOT / "index.html")


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
        "amplitude_api_key": os.getenv("AMPLITUDE_API_KEY", ""),
        "posthog_project_token": os.getenv("POSTHOG_PROJECT_TOKEN", ""),
        "posthog_host": os.getenv("POSTHOG_HOST", "https://us.i.posthog.com"),
    }


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
