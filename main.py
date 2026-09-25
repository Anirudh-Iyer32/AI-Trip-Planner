from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, FileResponse
from agent.agentic_workflow import GraphBuilder
from agent.features import (
    optimize_itinerary,
    companion_chat,
    replan_weather,
    calculate_budget_breakdown
)
from agent.itinerary_structurer import structure_and_validate_itinerary
from utils.save_to_document import save_document, save_to_pdf
import os
import json
import uuid
import datetime
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

app = FastAPI(title="VOYAGE AI Travel Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure output directory exists and mount static files for PDF downloads
os.makedirs("output", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")

# Ephemeral in-memory store for saved trips with persistent JSON file backup
SAVED_TRIPS_FILE = os.path.join("output", "saved_trips.json")
SAVED_TRIPS: Dict[str, Any] = {}

def load_saved_trips():
    global SAVED_TRIPS
    if os.path.exists(SAVED_TRIPS_FILE):
        try:
            with open(SAVED_TRIPS_FILE, "r", encoding="utf-8") as f:
                SAVED_TRIPS = json.load(f)
        except Exception as e:
            print(f"[Warning] Could not load saved trips: {e}")

def persist_saved_trips():
    try:
        with open(SAVED_TRIPS_FILE, "w", encoding="utf-8") as f:
            json.dump(SAVED_TRIPS, f, indent=2)
    except Exception as e:
        print(f"[Warning] Could not persist saved trips: {e}")

load_saved_trips()


# ----------------------------------------------------
# 0. ROOT & CONFIG ENDPOINTS
# ----------------------------------------------------
@app.get("/")
async def get_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "VOYAGE AI Trip Planner API is running"}


@app.get("/api/config")
async def get_client_config():
    """Returns public runtime configuration such as GA4 Measurement ID."""
    return {
        "ga_measurement_id": os.getenv("GA_MEASUREMENT_ID", ""),
        "app_env": os.getenv("ENVIRONMENT", "pilot"),
        "features": {
            "optimizer": True,
            "companion": True,
            "weather_replan": True,
            "budget_planner": True,
            "save_share": True
        }
    }


# ----------------------------------------------------
# 1. CORE ITINERARY QUERY (PRESERVED & STRUCTURED)
# ----------------------------------------------------
class QueryRequest(BaseModel):
    question: str


@app.post("/query")
def query_travel_agent(query: QueryRequest):
    """Core Agent Query with primary Google Gemini and automated Groq fallback."""
    try:
        print(f"[Query Received]: {query.question}")
        output = None
        
        # Try Primary Model (Google)
        try:
            graph = GraphBuilder(model_provider="google")
            react_app = graph()
            messages = {"messages": [query.question]}
            output = react_app.invoke(messages)
            print("[Google LangGraph execution successful]")
        except Exception as google_err:
            print(f"[LangGraph Fallback] Google provider failed: {google_err}. Trying Groq provider...")
            graph = GraphBuilder(model_provider="groq")
            react_app = graph()
            messages = {"messages": [query.question]}
            output = react_app.invoke(messages)
            print("[Groq LangGraph execution successful]")

        final_output = ""
        if isinstance(output, dict) and "messages" in output:
            # Prioritize AIMessage containing the comprehensive synthesized itinerary
            ai_messages = [
                m for m in output["messages"]
                if type(m).__name__ == "AIMessage" and getattr(m, "content", "") and len(str(m.content).strip()) > 100
            ]
            if ai_messages:
                final_output = ai_messages[-1].content
            else:
                for m in reversed(output["messages"]):
                    content = getattr(m, "content", "")
                    if content and isinstance(content, str) and content.strip():
                        final_output = content
                        break
                else:
                    last_m = output["messages"][-1]
                    final_output = getattr(last_m, "content", str(last_m))
        else:
            final_output = str(output)

        # Normalize & validate structured representation without redundant LLM call
        structured_data = structure_and_validate_itinerary(final_output, query.question)

        # Save markdown and styled ReportLab PDF outputs
        save_document(response_text=final_output)
        pdf_filename = save_to_pdf(response_text=final_output, structured_data=structured_data)
        pdf_url = f"/output/{pdf_filename}" if pdf_filename else None

        return {
            "answer": final_output,
            "structured_itinerary": structured_data,
            "pdf_url": pdf_url
        }
    except Exception as e:
        print(f"[Query Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ----------------------------------------------------
# 2. FEATURE 1: AI TRIP OPTIMIZER
# ----------------------------------------------------
class OptimizeRequest(BaseModel):
    itinerary: str
    optimization_type: str = "cost"  # cost | time | experiences | relaxed | food
    destination: Optional[str] = ""
    current_cost: Optional[float] = None
    current_hours: Optional[float] = None


@app.post("/api/optimize")
def optimize_trip_endpoint(req: OptimizeRequest):
    try:
        result = optimize_itinerary(
            itinerary=req.itinerary,
            optimization_type=req.optimization_type,
            destination=req.destination or "",
            current_cost=req.current_cost,
            current_hours=req.current_hours
        )
        return result
    except Exception as e:
        print(f"[Optimize Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ----------------------------------------------------
# 3. FEATURE 2: AI TRIP COMPANION
# ----------------------------------------------------
class CompanionRequest(BaseModel):
    question: Optional[str] = None
    message: Optional[str] = None
    trip_context: Optional[str] = ""
    history: Optional[List[Dict[str, str]]] = []


@app.post("/api/companion")
def companion_chat_endpoint(req: CompanionRequest):
    try:
        user_msg = req.question or req.message or ""
        answer = companion_chat(
            question=user_msg,
            trip_context=req.trip_context or "",
            history=req.history or []
        )
        return {"answer": answer}
    except Exception as e:
        print(f"[Companion Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ----------------------------------------------------
# 4. FEATURE 3: WEATHER-AWARE REPLANNING
# ----------------------------------------------------
class WeatherReplanRequest(BaseModel):
    itinerary: str
    destination: str
    day_number: Optional[int] = 3
    weather_condition: Optional[str] = "Rain / Storm"


@app.post("/api/replan-weather")
def replan_weather_endpoint(req: WeatherReplanRequest):
    try:
        result = replan_weather(
            itinerary=req.itinerary,
            destination=req.destination,
            day_number=req.day_number or 3,
            weather_condition=req.weather_condition or "Rain / Storm"
        )
        return result
    except Exception as e:
        print(f"[Weather Replan Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ----------------------------------------------------
# 5. FEATURE 4: SMART BUDGET PLANNER
# ----------------------------------------------------
class BudgetRequest(BaseModel):
    itinerary: Optional[str] = ""
    destination: Optional[str] = ""
    currency: Optional[str] = "INR"


@app.post("/api/budget-breakdown")
def budget_breakdown_endpoint(req: BudgetRequest):
    try:
        result = calculate_budget_breakdown(
            itinerary=req.itinerary or "",
            currency=req.currency or "INR",
            destination=req.destination or ""
        )
        return result
    except Exception as e:
        print(f"[Budget Breakdown Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


# ----------------------------------------------------
# 6. FEATURE 5: SAVE & SHARE TRIP
# ----------------------------------------------------
class SaveTripRequest(BaseModel):
    title: Optional[str] = "My AI Trip"
    destination: Optional[str] = "Curated Trip"
    itinerary: str
    structured_itinerary: Optional[Dict[str, Any]] = None
    budget_summary: Optional[Dict[str, Any]] = None
    optimization_info: Optional[Dict[str, Any]] = None


@app.post("/api/trips/save")
async def save_trip_endpoint(req: SaveTripRequest):
    try:
        trip_id = f"VY-{uuid.uuid4().hex[:6].upper()}"
        timestamp = datetime.datetime.now().isoformat()
        
        trip_record = {
            "trip_id": trip_id,
            "created_at": timestamp,
            "title": req.title,
            "destination": req.destination,
            "itinerary": req.itinerary,
            "structured_itinerary": req.structured_itinerary,
            "budget_summary": req.budget_summary,
            "optimization_info": req.optimization_info
        }
        
        SAVED_TRIPS[trip_id] = trip_record
        persist_saved_trips()
        
        return {
            "status": "success",
            "trip_id": trip_id,
            "share_url": f"/?trip={trip_id}",
            "trip": trip_record
        }
    except Exception as e:
        print(f"[Save Trip Error]: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/api/trips/{trip_id}")
async def get_saved_trip_endpoint(trip_id: str):
    trip = SAVED_TRIPS.get(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@app.get("/api/trips")
async def list_saved_trips_endpoint():
    return list(SAVED_TRIPS.values())