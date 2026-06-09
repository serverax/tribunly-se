"""
Outbox worker — drains pending ``outbox_events`` and drives the durable
event lifecycle:  pending → processed  (on handler success)
                  pending → pending (retry) → dead_letter (at max_retries)

This is the consumer side of the transactional outbox (see ``outbox.py`` and
order §17 Event Bus / Queue / Outbox). The Brain publishes events inside the
same workflow (``brain.py`` Step 18b); this worker delivers them out-of-band so
a user answer is never blocked by downstream side effects.

Run as a long-lived process:
    python -m backend.core.outbox_worker

Drain a single batch (used by tests and one-shot jobs):
    from backend.core.outbox_worker import run_once
    run_once()
"""

from __future__ import annotations

import logging
import os
import signal
import time
from typing import Callable

from backend.core import outbox

logger = logging.getLogger(__name__)

# Handler contract: (payload: dict, trace_id: str|None) -> bool
# Raise to signal failure (triggers retry / dead-letter). Return value is
# advisory. Handlers MUST be idempotent: the same event may be delivered more
# than once after a crash between side-effect and status update.
Handler = Callable[[dict, object], bool]


def _handle_assessment_complete(payload: dict, trace_id: object) -> bool:
    """Post-assessment fan-out point. The durable effect is the status
    transition itself; notification / evaluation / reindex hooks attach here.
    Idempotent and free of PII (payload carries IDs only)."""
    if not payload.get("trace_id"):
        raise ValueError("assessment_complete event missing trace_id")
    logger.info("outbox: assessment_complete processed trace_id=%s", trace_id)
    return True


def _handle_ack(payload: dict, trace_id: object) -> bool:
    """Default acknowledgement handler for event types whose downstream
    side effect is not yet wired. Records delivery; safe to extend."""
    logger.info("outbox: event acknowledged trace_id=%s", trace_id)
    return True


# Registry — tests monkeypatch this to exercise the failure path.
HANDLERS: dict[str, Handler] = {
    "assessment_complete":    _handle_assessment_complete,
    "legal_source_reindex":   _handle_ack,
    "payment_received":       _handle_ack,
    "account_delete_request": _handle_ack,
    "evaluation_job":         _handle_ack,
    "audit_export":           _handle_ack,
    "human_review_created":   _handle_ack,
    "evidence_parsed":        _handle_ack,
}


# Stable per-process worker id, recorded on each claimed event.
WORKER_ID = f"worker-{os.getpid()}"


def _dispatch(event: dict) -> None:
    handler = HANDLERS.get(event["event_type"])
    if handler is None:
        logger.warning("outbox: no handler for type=%s — failing event=%s",
                       event["event_type"], event["event_id"])
        outbox.mark_failed(event["event_id"], f"no handler for {event['event_type']}")
        return
    try:
        handler(event["payload"], event["trace_id"])
        outbox.mark_processed(event["event_id"])
    except Exception as exc:  # handler failure → retry / dead-letter
        # Log/record exception class + message only — never the payload (no PII).
        err = f"{type(exc).__name__}: {exc}"
        logger.warning("outbox: handler failed event=%s type=%s: %s",
                       event["event_id"], event["event_type"], err)
        outbox.mark_failed(event["event_id"], err)


def run_once(limit: int = 50, worker_id: str = WORKER_ID) -> int:
    """Atomically claim up to ``limit`` pending events (pending → processing)
    and process each (→ processed, or retry/dead_letter on failure).
    Returns the number of events claimed in this batch."""
    events = outbox.claim_batch(worker_id, limit=limit)
    for ev in events:
        _dispatch(ev)
    return len(events)


def process_forever(interval: float = 2.0) -> None:
    """Long-lived loop. Sleeps ``interval`` seconds only when the queue is
    empty so a backlog is drained promptly. Stops cleanly on SIGTERM/SIGINT."""
    stop = {"flag": False}

    def _signal(_signum, _frame):
        stop["flag"] = True
        logger.info("outbox worker: shutdown signal received")

    signal.signal(signal.SIGTERM, _signal)
    signal.signal(signal.SIGINT, _signal)

    logger.info("outbox worker started id=%s interval=%ss", WORKER_ID, interval)
    while not stop["flag"]:
        drained = run_once()
        if drained == 0:
            time.sleep(interval)
    logger.info("outbox worker stopped")


if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="lawapp outbox worker")
    parser.add_argument("--once", action="store_true",
                        help="drain one batch and exit (for cron / proof / tests)")
    args = parser.parse_args()
    if args.once:
        count = run_once()
        logger.info("outbox worker --once drained %d event(s)", count)
    else:
        process_forever()
