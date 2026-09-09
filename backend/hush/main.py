from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .service import DemoError, DemoService

app = FastAPI(title="HUSH Demo API", version="0.1.0")
service = DemoService()
frontend = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/static", StaticFiles(directory=frontend), name="static")


def authorize_demo_session(request: Request, participant: str) -> str:
    normalized = participant.upper()
    expected = f"demo-session-{normalized.lower()}"
    if request.headers.get("x-participant-session") != expected:
        raise DemoError(404, "NOT_FOUND", "참가자 전용 정보를 찾을 수 없습니다.")
    return normalized


@app.exception_handler(DemoError)
async def handle_demo_error(_: Request, exc: DemoError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(frontend / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo/state")
def shared_state() -> dict:
    return service.shared_state()


@app.get("/api/demo/participants/{participant}")
def private_state(participant: str, request: Request) -> dict:
    return service.private_state(authorize_demo_session(request, participant))


@app.post("/api/demo/reset")
def reset() -> dict:
    return service.reset()


@app.post("/api/demo/seed-confirmed-inputs")
def seed_inputs() -> dict:
    return service.seed_confirmed_inputs()


@app.post("/api/demo/decision-runs")
def run_decision() -> dict:
    return service.run_decision()


@app.post("/api/demo/participants/{participant}/proposal/accept")
def accept(participant: str, request: Request) -> dict:
    return service.accept_proposal(authorize_demo_session(request, participant))


@app.post("/api/demo/participants/{participant}/proposal/reject")
def reject(participant: str, request: Request) -> dict:
    return service.reject_proposal(authorize_demo_session(request, participant))


@app.get("/api/demo/participants/{participant}/receipt")
def receipt(participant: str, request: Request) -> dict:
    return service.receipt(authorize_demo_session(request, participant))


@app.post("/api/demo/participants/{participant}/verify")
def verify(participant: str, request: Request) -> dict:
    return service.verify(authorize_demo_session(request, participant))
