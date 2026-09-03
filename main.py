from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import JSONResponse, FileResponse
from agent.agentic_workflow import GraphBuilder
from utils.save_to_document import save_document, save_to_pdf
import os
import datetime
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # set specific origins in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure output directory exists and mount static files for PDF downloads
os.makedirs("output", exist_ok=True)
app.mount("/output", StaticFiles(directory="output"), name="output")


@app.get("/")
async def get_index():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"message": "AI Trip Planner API is running"}


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
async def query_travel_agent(query: QueryRequest):
    try:
        print(query)
        graph = GraphBuilder(model_provider="google")
        react_app = graph()

        png_graph = react_app.get_graph().draw_mermaid_png()
        with open("my_graph.png", "wb") as f:
            f.write(png_graph)

        print(f"Graph saved as 'my_graph.png' in {os.getcwd()}")
        messages = {"messages": [query.question]}
        output = react_app.invoke(messages)
        print("invoking success")

        if isinstance(output, dict) and "messages" in output:
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

        # Save markdown and PDF outputs
        save_document(response_text=final_output)
        pdf_filename = save_to_pdf(response_text=final_output)

        pdf_url = f"/output/{pdf_filename}" if pdf_filename else None

        return {"answer": final_output, "pdf_url": pdf_url}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})