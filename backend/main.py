import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging_config import setup_logging, get_logger
from app.agents.master_agent import run_graph, save_graph_visualization
from app.api.routes import router
from app.api.openai_compat import router as openai_router

# Initialize application-wide logging
setup_logging(settings.LOG_LEVEL)
logger = get_logger("server")

app = FastAPI(
    title="MARS Multi-Agent Decision System",
    description="A multi-agent AI system for strategic decision-making across Finance, R&D, Legal, and Operations.",
    version="0.1.0",
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    path = request.url.path
    method = request.method
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"{method} {path} - incoming from {client_ip}")
    try:
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"{method} {path} - completed {response.status_code} ({duration_ms:.1f}ms)")
        return response
    except Exception as exc:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"{method} {path} - failed after {duration_ms:.1f}ms: {exc}", exc_info=True)
        raise exc


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
