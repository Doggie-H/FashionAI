from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth_context import WorkflowRequestContext, bind_command_context, get_reviewer_request_context
from ..database import get_db
from ..services import review_tasks
from ..workflow_schemas import (
    AuditEventV1,
    ClaimReviewTaskCommandV1,
    CreateReviewTaskCommandV1,
    ReleaseReviewTaskCommandV1,
    ReviewTaskListV1,
    ReviewTaskV1,
    SubmitReviewDecisionCommandV1,
)


router = APIRouter(prefix="/review-tasks", tags=["P1 reviewer queue"])


def _error(error: ValueError) -> HTTPException:
    if isinstance(error, review_tasks.ReviewTaskNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


def _command(command, context: WorkflowRequestContext):
    return bind_command_context(command, context)


@router.get("", response_model=ReviewTaskListV1)
def list_tasks(
    status: str | None = Query(default=None),
    review_type: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    _: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    return review_tasks.list_review_tasks(db, status=status, review_type=review_type, cursor=cursor, limit=limit)


@router.post("", response_model=ReviewTaskV1, status_code=201)
def create_task(
    command: CreateReviewTaskCommandV1,
    context: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        return review_tasks.create_review_task(db, _command(command, context), tenant_id=context.tenant_id)
    except ValueError as error:
        raise _error(error) from error


@router.get("/{task_id}", response_model=ReviewTaskV1)
def get_task(
    task_id: str,
    _: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        return review_tasks.get_review_task(db, task_id)
    except ValueError as error:
        raise _error(error) from error


@router.post("/{task_id}/claim", response_model=ReviewTaskV1)
def claim_task(
    task_id: str,
    command: ClaimReviewTaskCommandV1,
    context: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        return review_tasks.claim_review_task(db, task_id, _command(command, context))
    except ValueError as error:
        raise _error(error) from error


@router.post("/{task_id}/submit-decision", response_model=ReviewTaskV1)
def submit_task_decision(
    task_id: str,
    command: SubmitReviewDecisionCommandV1,
    context: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        return review_tasks.submit_review_decision(db, task_id, _command(command, context), is_admin="admin" in context.roles)
    except ValueError as error:
        raise _error(error) from error


@router.post("/{task_id}/release", response_model=ReviewTaskV1)
def release_task(
    task_id: str,
    command: ReleaseReviewTaskCommandV1,
    context: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        return review_tasks.release_review_task(db, task_id, _command(command, context), is_admin="admin" in context.roles)
    except ValueError as error:
        raise _error(error) from error


@router.get("/{task_id}/audit-events", response_model=list[AuditEventV1])
def task_audit_events(
    task_id: str,
    _: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    try:
        events = review_tasks.list_review_task_audit_events(db, task_id)
    except ValueError as error:
        raise _error(error) from error
    return [AuditEventV1(
        event_id=event.event_id,
        aggregate_type=event.aggregate_type,
        aggregate_id=event.aggregate_id,
        event_type=event.event_type,
        actor_id=event.actor_id,
        correlation_id=event.correlation_id,
        payload=event.payload or {},
        created_at=event.created_at,
    ) for event in events]
