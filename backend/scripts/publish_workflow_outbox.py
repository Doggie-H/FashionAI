from __future__ import annotations

import argparse
import os
import socket

from app.database import SessionLocal
from app.services.outbox_relay import OutboxRelay


def build_relay(worker_id: str, batch_size: int, poll_seconds: float) -> OutboxRelay:
    return OutboxRelay(
        SessionLocal,
        worker_id=worker_id,
        batch_size=batch_size,
        poll_seconds=poll_seconds,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish committed workflow outbox events to Celery with durable retry.")
    parser.add_argument("--once", action="store_true", help="Process at most one relay cycle, then exit.")
    parser.add_argument("--worker-id", default=f"outbox-publisher@{socket.gethostname()}")
    parser.add_argument("--batch-size", type=int, default=int(os.getenv("WORKFLOW_OUTBOX_BATCH_SIZE", "50")))
    parser.add_argument("--poll-seconds", type=float, default=float(os.getenv("WORKFLOW_OUTBOX_POLL_SECONDS", "2")))
    args = parser.parse_args()

    relay = build_relay(args.worker_id, args.batch_size, args.poll_seconds)
    reports = relay.run_forever(max_cycles=1 if args.once else None)
    if reports:
        report = reports[-1]
        print(
            f"outbox_worker={args.worker_id} claimed={report.claimed} published={report.published} "
            f"publish_failed={report.publish_failed} database_error={report.database_error}",
            flush=True,
        )


if __name__ == "__main__":
    main()
