from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth_context import WorkflowRequestContext, bind_command_context, get_admin_request_context
from ..database import get_db
from ..services import outbox_admin
from ..workflow_schemas import (
    DeadLetterEventV1,
    DeadLetterQueueV1,
    ReplayDeadLetterCommandV1,
    ReviewDeadLetterCommandV1,
)

router = APIRouter(prefix="/admin/outbox", tags=["admin outbox review"])


def _admin_error(error: ValueError) -> HTTPException:
    status_code = 404 if isinstance(error, outbox_admin.OutboxAdminNotFoundError) else 409
    return HTTPException(status_code=status_code, detail=str(error))


@router.get("/dead-letters", response_model=DeadLetterQueueV1)
def get_dead_letter_queue(
    limit: int = Query(default=100, ge=1, le=250),
    offset: int = Query(default=0, ge=0),
    _admin: WorkflowRequestContext = Depends(get_admin_request_context),
    db: Session = Depends(get_db),
):
    return outbox_admin.list_dead_letters(db, limit=limit, offset=offset)


@router.post("/dead-letters/{event_id}/review", response_model=DeadLetterEventV1)
def review_dead_letter(
    event_id: str,
    command: ReviewDeadLetterCommandV1,
    admin: WorkflowRequestContext = Depends(get_admin_request_context),
    db: Session = Depends(get_db),
):
    bound = bind_command_context(command, admin)
    try:
        return outbox_admin.review_dead_letter(
            db,
            event_id=event_id,
            admin_actor_id=bound.actor_id,
            correlation_id=bound.correlation_id,
            idempotency_key=bound.idempotency_key,
            review_note=bound.review_note,
        )
    except ValueError as error:
        raise _admin_error(error) from error


@router.post("/dead-letters/{event_id}/replay", response_model=DeadLetterEventV1)
def replay_dead_letter(
    event_id: str,
    command: ReplayDeadLetterCommandV1,
    admin: WorkflowRequestContext = Depends(get_admin_request_context),
    db: Session = Depends(get_db),
):
    bound = bind_command_context(command, admin)
    try:
        return outbox_admin.replay_dead_letter(
            db,
            event_id=event_id,
            admin_actor_id=bound.actor_id,
            correlation_id=bound.correlation_id,
            idempotency_key=bound.idempotency_key,
            review_note=bound.review_note,
        )
    except ValueError as error:
        raise _admin_error(error) from error
