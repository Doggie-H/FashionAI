from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth_context import WorkflowRequestContext, bind_command_context, get_reviewer_request_context
from ..database import get_db
from ..services import taxonomy_learning
from ..workflow_schemas import (
    DecideTaxonomyLearningProposalCommandV1,
    TaxonomyLearningProposalListV1,
    TaxonomyLearningProposalV1,
)


router = APIRouter(prefix="/taxonomy-learning", tags=["governed taxonomy learning"])


def _command(command, context: WorkflowRequestContext):
    return bind_command_context(command, context)


def _error(error: ValueError) -> HTTPException:
    if isinstance(error, taxonomy_learning.TaxonomyLearningProposalNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    return HTTPException(status_code=409, detail=str(error))


@router.get("/proposals", response_model=TaxonomyLearningProposalListV1)
def list_taxonomy_proposals(
    status: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    _: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    return taxonomy_learning.list_proposals(db, status=status, cursor=cursor, limit=limit)


@router.post("/proposals/{proposal_id}/decision", response_model=TaxonomyLearningProposalV1)
def decide_taxonomy_proposal(
    proposal_id: str,
    command: DecideTaxonomyLearningProposalCommandV1,
    context: WorkflowRequestContext = Depends(get_reviewer_request_context),
    db: Session = Depends(get_db),
):
    if "admin" not in context.roles:
        raise HTTPException(status_code=403, detail="Only an admin can decide taxonomy learning proposals")
    try:
        return taxonomy_learning.decide_proposal(db, proposal_id, _command(command, context))
    except ValueError as error:
        raise _error(error) from error
