import io
import os
import secrets
from pathlib import Path
from typing import Any, Literal

import segno
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .p0 import P0Service
from .service import DemoError, DemoService

app = FastAPI(title="HUSH Demo API", version="0.2.0")
service = DemoService()
p0_service = P0Service()
frontend = Path(
    os.getenv("HUSH_FRONTEND_DIR", str(Path(__file__).resolve().parents[2] / "frontend"))
)
app.mount("/static", StaticFiles(directory=frontend), name="static")


class JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite_code: str = Field(min_length=6, max_length=100)


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_text: str = Field(min_length=1, max_length=500)


class ConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft_id: str = Field(min_length=8, max_length=100)


class RoomCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    required_participant_count: int = Field(ge=2, le=20)
    candidate_dataset_version: str = "demo-candidates-v1"


class P0JoinRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    invite_token: str = Field(min_length=16, max_length=200)


class P0ConstraintRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    constraint_type: Literal[
        "max_price", "excluded_category", "accessibility_required",
        "max_travel_minutes", "latest_end_time"
    ]
    priority: Literal["HARD", "SOFT"]
    constraint_value: dict[str, Any]
    source_text: str | None = Field(default=None, max_length=500)


class InputConfirmationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_mode: Literal["CONSTRAINED", "EMPTY"]


class ProposalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    constraint_version_id: str = Field(min_length=8, max_length=128)


def participant_session(request: Request, participant: str) -> str:
    return service.validate_session(
        participant,
        request.headers.get("x-participant-session"),
    )


def p0_session(request: Request) -> str | None:
    return request.headers.get("x-participant-session")


def idempotency_key(request: Request) -> str | None:
    return request.headers.get("idempotency-key")


def require_admin(request: Request) -> None:
    admin_key = os.getenv("HUSH_DEMO_ADMIN_KEY")
    supplied = request.headers.get("x-demo-admin-key", "")
    if not admin_key or not secrets.compare_digest(supplied, admin_key):
        raise DemoError(404, "NOT_FOUND", "관리자 기능을 찾을 수 없습니다.")


@app.exception_handler(DemoError)
async def handle_demo_error(request: Request, exc: DemoError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "request_id": request.state.request_id},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(request: Request, _: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "요청 형식이나 값이 올바르지 않습니다.",
            "request_id": request.state.request_id,
        },
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id") or secrets.token_hex(12)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(frontend / "index.html")


@app.get("/participant", include_in_schema=False)
def participant_page() -> FileResponse:
    return FileResponse(frontend / "participant.html")


@app.get("/invite", include_in_schema=False)
def invite_page() -> FileResponse:
    return FileResponse(frontend / "invite.html")


@app.get("/p0", include_in_schema=False)
def p0_page() -> FileResponse:
    return FileResponse(frontend / "p0.html")


@app.get("/p0-room", include_in_schema=False)
def p0_room_page() -> FileResponse:
    return FileResponse(frontend / "p0-room.html")


@app.get("/p0-verify", include_in_schema=False)
def p0_verify_page() -> FileResponse:
    return FileResponse(frontend / "p0-verify.html")


@app.get("/api/demo/invites")
def invites(request: Request) -> dict:
    """Join URLs for the four demo participants (invite codes are demo fixtures)."""
    base = str(request.base_url)
    return {
        "participants": [
            {
                "participant": key,
                "invite_code": code,
                "join_url": f"{base}participant?p={key}&code={code}",
            }
            for key, code in service.invite_codes.items()
        ]
    }


@app.get("/api/demo/invite-qr/{participant}", include_in_schema=False)
def invite_qr(participant: str, request: Request) -> Response:
    key = participant.upper()
    code = service.invite_codes.get(key)
    if code is None:
        raise DemoError(404, "NOT_FOUND", "참가자를 찾을 수 없습니다.")
    join_url = f"{request.base_url}participant?p={key}&code={code}"
    buffer = io.BytesIO()
    segno.make(join_url, error="m").save(buffer, kind="svg", scale=6, border=2, dark="#07100d", light="#ffffff")
    return Response(content=buffer.getvalue(), media_type="image/svg+xml")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", **service.store_info()}


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


# -- Canonical multi-room P0 API -----------------------------------------------


@app.post("/rooms", status_code=201)
def create_room(body: RoomCreateRequest, request: Request) -> dict:
    return p0_service.create_room(
        body.title, body.required_participant_count,
        body.candidate_dataset_version, idempotency_key(request),
    )


@app.post("/rooms/{room_id}/participants", status_code=201)
def join_room(room_id: str, body: P0JoinRequest, request: Request) -> dict:
    return p0_service.join(room_id, body.invite_token, idempotency_key(request))


@app.get("/rooms/{room_id}")
def get_room(room_id: str) -> dict:
    return p0_service.shared(room_id)


@app.get("/rooms/{room_id}/participants/me")
def get_me(room_id: str, request: Request) -> dict:
    return p0_service.me(room_id, p0_session(request))


@app.post("/rooms/{room_id}/participants/{participant_id}/revoke")
def revoke_room_participant(room_id: str, participant_id: str, request: Request) -> dict:
    return p0_service.revoke_participant(
        room_id, request.headers.get("x-creator-session"), participant_id,
        idempotency_key(request),
    )


@app.post("/rooms/{room_id}/private-inputs", status_code=201)
def submit_private_input(room_id: str, body: ParseRequest, request: Request) -> dict:
    return p0_service.submit_private_input(
        room_id, p0_session(request), body.source_text, idempotency_key(request)
    )


@app.post("/rooms/{room_id}/private-inputs/{private_input_id}/parse")
def parse_private_input(room_id: str, private_input_id: str, request: Request) -> dict:
    return p0_service.parse_private_input(
        room_id, p0_session(request), private_input_id, idempotency_key(request)
    )


@app.get("/rooms/{room_id}/constraints/drafts")
def get_constraint_drafts(room_id: str, request: Request) -> dict:
    return p0_service.drafts(room_id, p0_session(request))


@app.post("/rooms/{room_id}/constraints", status_code=201)
def create_constraint(room_id: str, body: P0ConstraintRequest, request: Request) -> dict:
    return p0_service.confirm_constraint(
        room_id, p0_session(request), body.model_dump(), idempotency_key(request)
    )


@app.get("/rooms/{room_id}/constraints/me")
def get_constraints_me(room_id: str, request: Request) -> dict:
    return p0_service.constraints_me(room_id, p0_session(request))


@app.post("/rooms/{room_id}/constraints/{version_id}/retire")
def retire_room_constraint(room_id: str, version_id: str, request: Request) -> dict:
    return p0_service.retire_constraint(
        room_id, p0_session(request), version_id, idempotency_key(request)
    )


@app.post("/rooms/{room_id}/constraints/{version_id}/commitments/retry")
def retry_room_constraint_commitment(
    room_id: str, version_id: str, request: Request
) -> dict:
    return p0_service.retry_constraint_commitment(
        room_id, p0_session(request), version_id, idempotency_key(request)
    )


@app.post("/rooms/{room_id}/input-confirmations")
def confirm_room_input(room_id: str, body: InputConfirmationRequest, request: Request) -> dict:
    return p0_service.confirm_input(
        room_id, p0_session(request), body.input_mode, idempotency_key(request)
    )


@app.post("/rooms/{room_id}/decision-runs", status_code=201)
def create_decision_run(room_id: str, request: Request) -> dict:
    return p0_service.run_decision(room_id, p0_session(request), idempotency_key(request))


@app.get("/rooms/{room_id}/decision-runs/{run_id}")
def get_decision_run(room_id: str, run_id: str) -> dict:
    return p0_service.decision_run(room_id, run_id)


@app.get("/rooms/{room_id}/relaxation-proposals/me")
def get_proposals_me(room_id: str, request: Request) -> dict:
    return p0_service.proposals_me(room_id, p0_session(request))


@app.post("/rooms/{room_id}/relaxation-proposals/{proposal_id}/accept")
def accept_p0_proposal(
    room_id: str, proposal_id: str, body: ProposalDecisionRequest, request: Request
) -> dict:
    return p0_service.decide_proposal(
        room_id, p0_session(request), proposal_id,
        body.constraint_version_id, "ACCEPTED", idempotency_key(request),
    )


@app.post("/rooms/{room_id}/relaxation-proposals/{proposal_id}/reject")
def reject_p0_proposal(
    room_id: str, proposal_id: str, body: ProposalDecisionRequest, request: Request
) -> dict:
    return p0_service.decide_proposal(
        room_id, p0_session(request), proposal_id,
        body.constraint_version_id, "REJECTED", idempotency_key(request),
    )


@app.get("/rooms/{room_id}/final-decision")
def get_final_decision(room_id: str) -> dict:
    return p0_service.final_decision(room_id)


@app.post("/rooms/{room_id}/final-decision/commitment/retry")
def retry_room_final_commitment(room_id: str, request: Request) -> dict:
    return p0_service.retry_final_commitment(
        room_id, p0_session(request), idempotency_key(request)
    )


@app.get("/rooms/{room_id}/receipts/me")
def get_receipt_me(room_id: str, request: Request) -> dict:
    return p0_service.receipt(room_id, p0_session(request))


@app.get("/rooms/{room_id}/verification-data/me")
def get_verification_data_me(room_id: str, request: Request) -> dict:
    return p0_service.receipt(room_id, p0_session(request))


@app.post("/rooms/{room_id}/verify")
def verify_p0_receipt(room_id: str, request: Request) -> dict:
    return p0_service.verify(room_id, p0_session(request))
