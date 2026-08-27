from __future__ import annotations

import os
from uuid import uuid4

from locust import HttpUser, between, task


BODY_PROFILE_ID = os.getenv("LOCUST_BODY_PROFILE_ID", "").strip()
JWT_TOKEN = os.getenv("LOCUST_JWT", "").strip()
LEGACY_ACTOR_ID = os.getenv("LOCUST_LEGACY_ACTOR_ID", "").strip()
RAW_ASSET_IDS = os.getenv("LOCUST_WARDROBE_ASSET_IDS", "").strip()
WARDROBE_ASSET_IDS = [item.strip() for item in RAW_ASSET_IDS.split(",") if item.strip()]

STYLE_CONTEXT = {
    "occasion": os.getenv("LOCUST_OCCASION", "work"),
    "preferred_styles": [item.strip() for item in os.getenv("LOCUST_STYLES", "business,classic").split(",") if item.strip()],
    "season": os.getenv("LOCUST_SEASON", "autumn"),
    "fit_preference": os.getenv("LOCUST_FIT_PREFERENCE", "tailored"),
    "required_slots": [item.strip() for item in os.getenv("LOCUST_REQUIRED_SLOTS", "base_top,bottom").split(",") if item.strip()],
}


class StylingSessionLoadUser(HttpUser):
    """One synthetic user repeatedly creates distinct StylingSession commands against a pre-seeded active profile."""

    wait_time = between(float(os.getenv("LOCUST_WAIT_MIN_SECONDS", "0.2")), float(os.getenv("LOCUST_WAIT_MAX_SECONDS", "1.0")))

    def on_start(self) -> None:
        if not BODY_PROFILE_ID:
            raise RuntimeError("Set LOCUST_BODY_PROFILE_ID to an active pre-seeded body profile")
        if not JWT_TOKEN and not LEGACY_ACTOR_ID:
            raise RuntimeError("Set LOCUST_JWT for production-like JWT mode or LOCUST_LEGACY_ACTOR_ID only for local demo")

    @task
    def create_styling_session(self) -> None:
        request_id = uuid4().hex
        idempotency_key = f"locust-session-{request_id}"
        correlation_id = f"corr-locust-{request_id[:16]}"
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotency_key,
            "X-Correlation-ID": correlation_id,
        }
        payload: dict[str, object] = {
            "body_profile_id": BODY_PROFILE_ID,
            "context": STYLE_CONTEXT,
            "wardrobe_asset_ids": WARDROBE_ASSET_IDS,
        }
        if JWT_TOKEN:
            headers["Authorization"] = f"Bearer {JWT_TOKEN}"
        else:
            payload["actor_id"] = int(LEGACY_ACTOR_ID)
            payload["idempotency_key"] = idempotency_key
            payload["correlation_id"] = correlation_id

        with self.client.post("/workflow/styling-sessions", json=payload, headers=headers, name="POST /workflow/styling-sessions", catch_response=True) as response:
            if response.status_code != 201:
                response.failure(f"Expected 201, received {response.status_code}: {response.text[:300]}")
                return
            try:
                data = response.json()
                if data.get("status") != "inputs_resolved" or not data.get("session_id"):
                    response.failure("Response did not return inputs_resolved StylingSession")
                    return
            except ValueError:
                response.failure("Response was not valid JSON")
                return
            response.success()
