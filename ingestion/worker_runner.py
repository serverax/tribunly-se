"""Multi-queue ingestion worker runner for Docker profile `ingestion`."""

from __future__ import annotations

import logging
import os
import sys
import threading

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s  -  %(message)s",
)
logger = logging.getLogger(__name__)


def _worker_thread(worker_cls, name: str) -> None:
    worker = worker_cls()
    logger.info("Thread %s started on queue %s", name, worker.queue_name)
    worker.run_forever()


def main() -> None:
    from ingestion.workers.legislation_worker import LegislationWorker
    from ingestion.workers.case_law_worker import CaseLawWorker
    from ingestion.workers.acas_worker import AcasWorker
    from ingestion.workers.rules_compiler_worker import RulesCompilerWorker

    workers = [
        (LegislationWorker, "legislation"),
        (CaseLawWorker, "case_law"),
        (AcasWorker, "acas"),
        (RulesCompilerWorker, "rules_compiler"),
    ]

    if os.getenv("WORKER_ONCE", "").lower() in ("1", "true", "yes"):
        for cls, _ in workers:
            cls().run_once()
        return

    threads = []
    for cls, name in workers:
        t = threading.Thread(target=_worker_thread, args=(cls, name), daemon=True)
        t.start()
        threads.append(t)

    logger.info("Ingestion worker runner active (%d queues)", len(threads))
    for t in threads:
        t.join()


if __name__ == "__main__":
    main()
