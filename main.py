from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from app.api.routes import router
from app.agents.master_agent import run_graph, save_graph_visualization


app = FastAPI(
    title="MARS Multi-Agent Decision System",
    description="A multi-agent AI system for strategic decision-making across Finance, R&D, Legal, and Operations.",
    version="0.1.0",
)

app.include_router(router, prefix="/api")

load_dotenv(Path(__file__).resolve().parent / ".env")

@app.get("/")
def root():
    return {"status": "ok", "message": "Welcome to the MARS Multi-Agent Decision System!"}


if __name__ == "__main__":
    output_file = save_graph_visualization("graph.png")
    print("System initialized. Ready to process queries.")
    print(f"Graph visualization saved to {output_file}")
    print("Enter query: ")
    input_query = input().strip()
    result = run_graph(user_input=input_query, thread_id="cli-session")
    print("Final Output:")
    print(result)