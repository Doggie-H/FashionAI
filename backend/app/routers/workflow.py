from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth_context import (
    WorkflowRequestContext,
    bind_command_context,
    get_workflow_request_context,
    resolve_read_actor,
)
from ..database import get_db
from ..services import workflow_service
from ..workflow_schemas import (
    ApproveWardrobeAssetCommandV1,
    AuditEventV1,
    BodyProfileListV1,
    BodyProfileRevisionV1,
    ConfirmBodyProfileCommandV1,
    CreateBodyProfileCommandV1,
    CreateStylingSessionCommandV1,
    CreateWardrobeAssetCommandV1,
    FeedbackListV1,
    OutfitDecisionRunV1,
    RequestTryOnCommandV1,
    RunOutfitDecisionCommandV1,
    SelectOutfitCandidateCommandV1,
    StylingSessionV1,
    StylingSessionListV1,
    StylingSessionFeedbackV1,
    SubmitFeedbackCommandV1,
    TryOnRunV1,
    WardrobeAssetListV1,
    WorkflowActorV1,
    WardrobeAssetRevisionV1,
)


router = APIRouter(prefix="/workflow", tags=["styling workflow foundation"])


def _workflow_error(error: ValueError) -> HTTPException:
    status_code = 404 if isinstance(error, workflow_service.WorkflowNotFoundError) else 409
    return HTTPException(status_code=status_code, detail=str(error))


def _command(command, context: WorkflowRequestContext):
    return bind_command_context(command, context)


@router.post("/body-profiles", response_model=BodyProfileRevisionV1, status_code=201)
def create_body_profile(
    command: CreateBodyProfileCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.create_body_profile(db, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/body-profiles/{profile_id}", response_model=BodyProfileRevisionV1)
def get_body_profile(
    profile_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.get_body_profile(db, profile_id, resolve_read_actor(context, actor_id))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/body-profiles/{profile_id}/confirm", response_model=BodyProfileRevisionV1)
def confirm_body_profile(
    profile_id: str,
    command: ConfirmBodyProfileCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.confirm_body_profile(db, profile_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/wardrobe-assets", response_model=WardrobeAssetRevisionV1, status_code=201)
def create_wardrobe_asset(
    command: CreateWardrobeAssetCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.create_wardrobe_asset(db, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/wardrobe-assets/{asset_id}", response_model=WardrobeAssetRevisionV1)
def get_wardrobe_asset(
    asset_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.get_wardrobe_asset(db, asset_id, resolve_read_actor(context, actor_id))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/wardrobe-assets/{asset_id}/approve", response_model=WardrobeAssetRevisionV1)
def approve_wardrobe_asset(
    asset_id: str,
    command: ApproveWardrobeAssetCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.approve_wardrobe_asset(db, asset_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/styling-sessions", response_model=StylingSessionV1, status_code=201)
def create_styling_session(
    command: CreateStylingSessionCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.create_styling_session(db, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/styling-sessions/{session_id}", response_model=StylingSessionV1)
def get_styling_session(
    session_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.get_styling_session(db, session_id, resolve_read_actor(context, actor_id))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/styling-sessions/{session_id}/outfit-decisions", response_model=OutfitDecisionRunV1)
def run_outfit_decision(
    session_id: str,
    command: RunOutfitDecisionCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.run_outfit_decision(db, session_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/styling-sessions/{session_id}/select-outfit", response_model=StylingSessionV1)
def select_outfit(
    session_id: str,
    command: SelectOutfitCandidateCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.select_outfit_candidate(db, session_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/styling-sessions/{session_id}/try-on", response_model=TryOnRunV1, status_code=201)
def create_try_on_run(
    session_id: str,
    command: RequestTryOnCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.request_try_on(db, session_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/audit-events/{aggregate_id}", response_model=list[AuditEventV1])
def get_audit_events(
    aggregate_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        resolved_actor = (
            resolve_read_actor(context, actor_id)
            if context.actor_id is not None or actor_id is not None
            else None
        )
        return workflow_service.list_audit_events(db, aggregate_id, resolved_actor)
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/me", response_model=WorkflowActorV1)
def get_current_actor(context: WorkflowRequestContext = Depends(get_workflow_request_context)):
    actor_id = resolve_read_actor(context, None)
    return WorkflowActorV1(actor_id=actor_id, tenant_id=context.tenant_id, roles=sorted(context.roles), auth_mode=context.auth_mode)


@router.get("/body-profiles", response_model=BodyProfileListV1)
def list_body_profiles(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    return workflow_service.list_body_profiles(db, resolve_read_actor(context, actor_id), cursor, limit)


@router.get("/wardrobe-assets", response_model=WardrobeAssetListV1)
def list_wardrobe_assets(
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    return workflow_service.list_wardrobe_assets(db, resolve_read_actor(context, actor_id), status, cursor, limit)


@router.get("/styling-sessions", response_model=StylingSessionListV1)
def list_styling_sessions(
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    return workflow_service.list_styling_sessions(db, resolve_read_actor(context, actor_id), status, cursor, limit)


@router.get("/try-on-runs/{try_on_run_id}", response_model=TryOnRunV1)
def get_try_on_run(
    try_on_run_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.get_try_on_run(db, try_on_run_id, resolve_read_actor(context, actor_id))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.post("/styling-sessions/{session_id}/feedback", response_model=StylingSessionFeedbackV1, status_code=201)
def submit_session_feedback(
    session_id: str,
    command: SubmitFeedbackCommandV1,
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.submit_feedback(db, session_id, _command(command, context))
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/styling-sessions/{session_id}/feedback", response_model=FeedbackListV1)
def list_session_feedback(
    session_id: str,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.list_feedback(db, session_id, resolve_read_actor(context, actor_id), cursor, limit)
    except ValueError as error:
        raise _workflow_error(error) from error


@router.get("/styling-sessions/{session_id}/outfit-decisions/{decision_run_id}", response_model=OutfitDecisionRunV1)
def get_outfit_decision_run(
    session_id: str,
    decision_run_id: str,
    actor_id: int | None = Query(default=None, gt=0, description="Legacy demo-only actor selector"),
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    db: Session = Depends(get_db),
):
    try:
        return workflow_service.get_outfit_decision_run(db, session_id, decision_run_id, resolve_read_actor(context, actor_id))
    except ValueError as error:
        raise _workflow_error(error) from error
