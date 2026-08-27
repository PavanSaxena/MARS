from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.master_agent import run_graph, save_graph_visualization
from app.api.routes import router
from app.api.openai_compat import router as openai_router
from app.core.config import settings

app = FastAPI(
    title="MARS Multi-Agent Decision System",
    description="A multi-agent AI system for strategic decision-making across Finance, R&D, Legal, and Operations.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(openai_router)


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
