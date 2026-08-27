from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import uuid4

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel


class AuthenticationContextError(ValueError):
    pass


@dataclass(frozen=True)
class WorkflowRequestContext:
    actor_id: int | None
    tenant_id: str | None
    correlation_id: str | None
    idempotency_key: str | None
    auth_mode: str
    roles: frozenset[str] = frozenset()


def _demo_mode() -> bool:
    return os.getenv("AI_STYLIST_DEMO_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}


def _auth_mode() -> str:
    configured = os.getenv("WORKFLOW_AUTH_MODE")
    if configured:
        return configured.strip().lower()
    return "legacy_body" if _demo_mode() else "jwt"


def _parse_positive_int(value: object, claim_name: str) -> int:
    try:
        actor_id = int(value)
    except (TypeError, ValueError) as error:
        raise AuthenticationContextError(f"JWT claim {claim_name!r} must be a positive integer") from error
    if actor_id <= 0:
        raise AuthenticationContextError(f"JWT claim {claim_name!r} must be a positive integer")
    return actor_id


def _jwt_actor(authorization: str | None) -> tuple[int, str | None, frozenset[str]]:
    if not authorization or not authorization.startswith("Bearer "):
        raise AuthenticationContextError("Authorization Bearer token is required")
    secret = os.getenv("WORKFLOW_JWT_SIGNING_KEY")
    if not secret:
        raise AuthenticationContextError("WORKFLOW_JWT_SIGNING_KEY must be configured when WORKFLOW_AUTH_MODE=jwt")
    token = authorization.removeprefix("Bearer ").strip()
    options: dict[str, object] = {"algorithms": [os.getenv("WORKFLOW_JWT_ALGORITHM", "HS256")]}
    audience = os.getenv("WORKFLOW_JWT_AUDIENCE")
    if audience:
        options["audience"] = audience
    else:
        options["options"] = {"verify_aud": False}
    try:
        claims = jwt.decode(token, secret, **options)
    except jwt.PyJWTError as error:
        raise AuthenticationContextError("Invalid or expired workflow access token") from error
    actor_id = _parse_positive_int(claims.get("sub"), "sub")
    tenant_value = claims.get("tenant_id")
    tenant_id = str(tenant_value) if tenant_value is not None else None
    raw_roles = claims.get("roles", claims.get("role", []))
    if isinstance(raw_roles, str):
        raw_roles = [raw_roles]
    if not isinstance(raw_roles, (list, tuple, set)):
        raise AuthenticationContextError("JWT role claim must be a string or list of strings")
    roles = frozenset(str(role).strip().lower() for role in raw_roles if str(role).strip())
    return actor_id, tenant_id, roles


def get_workflow_request_context(
    authorization: str | None = Header(default=None),
    x_correlation_id: str | None = Header(default=None, alias="X-Correlation-ID"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> WorkflowRequestContext:
    """Return authenticated actor metadata. legacy_body exists only for deterministic local-demo compatibility."""
    mode = _auth_mode()
    if mode == "jwt":
        try:
            actor_id, tenant_id, roles = _jwt_actor(authorization)
        except AuthenticationContextError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error), headers={"WWW-Authenticate": "Bearer"}) from error
        return WorkflowRequestContext(actor_id, tenant_id, x_correlation_id, idempotency_key, mode, roles)
    if mode == "legacy_body" and _demo_mode():
        return WorkflowRequestContext(None, None, x_correlation_id, idempotency_key, mode, frozenset())
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Workflow authentication is not configured")


def get_reviewer_request_context(
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    x_demo_reviewer_actor_id: int | None = Header(default=None, alias="X-Demo-Reviewer-Actor-ID"),
) -> WorkflowRequestContext:
    """Require reviewer/admin role in JWT mode; local demo requires an explicit allow-list."""
    if context.auth_mode == "jwt":
        if not ({"reviewer", "admin"} & context.roles):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer or admin role is required")
        return context
    configured_ids = {value.strip() for value in os.getenv("WORKFLOW_REVIEWER_ACTOR_IDS", "").split(",") if value.strip()}
    configured_ids |= {value.strip() for value in os.getenv("WORKFLOW_ADMIN_ACTOR_IDS", "").split(",") if value.strip()}
    if context.auth_mode == "legacy_body" and x_demo_reviewer_actor_id is not None and str(x_demo_reviewer_actor_id) in configured_ids:
        return WorkflowRequestContext(
            x_demo_reviewer_actor_id,
            None,
            context.correlation_id,
            context.idempotency_key,
            context.auth_mode,
            frozenset({"reviewer"}),
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer or admin role is required")


def get_admin_request_context(
    context: WorkflowRequestContext = Depends(get_workflow_request_context),
    x_demo_admin_actor_id: int | None = Header(default=None, alias="X-Demo-Admin-Actor-ID"),
) -> WorkflowRequestContext:
    """Require a JWT admin role in production; permit named local-demo admin IDs only for local validation."""
    if context.auth_mode == "jwt":
        if "admin" not in context.roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role is required")
        return context
    configured_ids = {value.strip() for value in os.getenv("WORKFLOW_ADMIN_ACTOR_IDS", "").split(",") if value.strip()}
    if context.auth_mode == "legacy_body" and x_demo_admin_actor_id is not None and str(x_demo_admin_actor_id) in configured_ids:
        return WorkflowRequestContext(
            x_demo_admin_actor_id,
            None,
            context.correlation_id,
            context.idempotency_key,
            context.auth_mode,
            frozenset({"admin"}),
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role is required")


def bind_command_context[T: BaseModel](
    command: T,
    context: WorkflowRequestContext,
    *,
    require_idempotency_header: bool = True,
) -> T:
    """Overwrite transport metadata with authenticated/header context while retaining only demo legacy fallback."""
    command_actor = getattr(command, "actor_id", None)
    command_idempotency = getattr(command, "idempotency_key", None)
    command_correlation = getattr(command, "correlation_id", None)

    actor_id = context.actor_id if context.actor_id is not None else command_actor
    if actor_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated workflow actor is required")
    if context.actor_id is not None and command_actor is not None and command_actor != context.actor_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Command actor_id does not match authenticated actor")

    if context.idempotency_key and command_idempotency and context.idempotency_key != command_idempotency:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header does not match command idempotency_key")
    resolved_key = context.idempotency_key or command_idempotency
    if require_idempotency_header and context.auth_mode == "jwt" and not context.idempotency_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency-Key header is required")
    if not resolved_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Idempotency key is required")

    if context.correlation_id and command_correlation and context.correlation_id != command_correlation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Correlation-ID header does not match command correlation_id")
    resolved_correlation = context.correlation_id or command_correlation or f"corr_{uuid4().hex[:12]}"
    return command.model_copy(update={
        "actor_id": actor_id,
        "idempotency_key": resolved_key,
        "correlation_id": resolved_correlation,
    })


def resolve_read_actor(context: WorkflowRequestContext, legacy_actor_id: int | None) -> int:
    if context.actor_id is not None:
        if legacy_actor_id is not None and legacy_actor_id != context.actor_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Query actor_id does not match authenticated actor")
        return context.actor_id
    if context.auth_mode == "legacy_body" and legacy_actor_id is not None and legacy_actor_id > 0:
        return legacy_actor_id
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated workflow actor is required")
