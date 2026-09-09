import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .service import DemoError, DemoService

app = FastAPI(title="HUSH Demo API", version="0.2.0")
service = DemoService()
frontend = Path(
    os.getenv("HUSH_FRONTEND_DIR", str(Path(__file__).resolve().parents[2] / "frontend"))
)
app.mount("/static", StaticFiles(directory=frontend), name="static")
DEMO_ADMIN_KEY = os.getenv("HUSH_DEMO_ADMIN_KEY")


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite_code: str = Field(min_length=6, max_length=100)


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_text: str = Field(min_length=1, max_length=500)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str = Field(min_length=8, max_length=100)


def participant_session(request: Request, participant: str) -> str:
    return service.validate_session(
        participant,
        request.headers.get("x-participant-session"),
    )


def require_admin(request: Request) -> None:
    supplied = request.headers.get("x-demo-admin-key", "")
    if not DEMO_ADMIN_KEY or not secrets.compare_digest(supplied, DEMO_ADMIN_KEY):
        raise DemoError(404, "NOT_FOUND", "관리자 기능을 찾을 수 없습니다.")


@app.exception_handler(DemoError)
async def handle_demo_error(_: Request, exc: DemoError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(frontend / "index.html")


@app.get("/participant", include_in_schema=False)
def participant_page() -> FileResponse:
    return FileResponse(frontend / "participant.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/demo/state")
def shared_state() -> dict:
    return service.shared_state()


@app.post("/api/demo/participants/{participant}/join")
def join(participant: str, body: JoinRequest) -> dict:
    return service.join(participant.upper(), body.invite_code)


@app.get("/api/demo/participants/{participant}")
def private_state(participant: str, request: Request) -> dict:
    return service.private_state(participant_session(request, participant))


@app.post("/api/demo/participants/{participant}/private-inputs/parse")
def parse_input(participant: str, body: ParseRequest, request: Request) -> dict:
    owner = participant_session(request, participant)
    return service.parse_input(owner, body.source_text)


@app.post("/api/demo/participants/{participant}/constraints/confirm")
def confirm_input(participant: str, body: ConfirmRequest, request: Request) -> dict:
    owner = participant_session(request, participant)
    return service.confirm_draft(owner, body.draft_id)


@app.post("/api/demo/participants/{participant}/decision-runs")
def run_decision(participant: str, request: Request) -> dict:
    participant_session(request, participant)
    return service.run_decision()


@app.post("/api/demo/participants/{participant}/proposal/accept")
def accept(participant: str, request: Request) -> dict:
    return service.accept_proposal(participant_session(request, participant))


@app.post("/api/demo/participants/{participant}/proposal/reject")
def reject(participant: str, request: Request) -> dict:
    return service.reject_proposal(participant_session(request, participant))


@app.get("/api/demo/participants/{participant}/receipt")
def receipt(participant: str, request: Request) -> dict:
    return service.receipt(participant_session(request, participant))


@app.get("/api/demo/participants/{participant}/receipt/export")
def receipt_export(participant: str, request: Request) -> dict:
    return service.receipt(
        participant_session(request, participant),
        include_private=True,
    )


@app.post("/api/demo/participants/{participant}/verify")
def verify(participant: str, request: Request) -> dict:
    return service.verify(participant_session(request, participant))


@app.post("/api/demo/admin/reset")
def reset(request: Request) -> dict:
    require_admin(request)
    return service.reset()


@app.post("/api/demo/admin/seed-confirmed-inputs")
def seed_inputs(request: Request) -> dict:
    require_admin(request)
    return service.seed_confirmed_inputs()
