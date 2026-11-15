"""The background worker: takes queued model runs and executes them.

    python web/manage.py run_worker

The web process only writes Job rows; this command is what actually calls the
recognition and the grading model. Several runs go at once (QUEUE_WORKERS),
because one at a time would make the last student in a class of 25 wait about
ten minutes.

Stops cleanly on Ctrl+C: the threads finish the run they are on, and nothing
is left marked as running.
"""

import logging
import signal
import socket
import threading
import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from courses.services import sync_lesson_states
from submissions import jobs, queue

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Runs the queued recognition and evaluation jobs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--interval",
            type=float,
            default=2.0,
            help="how often to look for new work, in seconds (default: 2)",
        )
        parser.add_argument(
            "--workers",
            type=int,
            default=None,
            help="how many jobs may run at once (default: the QUEUE_WORKERS setting)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="work through what is in the queue, then stop (useful in tests and scripts)",
        )

    def handle(self, *args, **options):
        worker_count = options["workers"] or queue.workers()
        interval = options["interval"]
        host = socket.gethostname()

        stopping = threading.Event()

        def stop(signum, frame):
            if not stopping.is_set():
                self.stdout.write("\nStopping; the runs in progress are being finished…")
                stopping.set()

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        self.stdout.write(
            f"The worker has started: {worker_count} at a time, "
            f"checking every {interval:g}s. Quit with Ctrl+C."
        )

        threads = [
            threading.Thread(
                target=self._loop,
                args=(f"{host}#{number + 1}", interval, stopping, options["once"]),
                daemon=True,
                name=f"worker-{number + 1}",
            )
            for number in range(worker_count)
        ]

        try:
            sync_lesson_states()
        except Exception:
            logger.exception("Could not sync the lesson states")

        if not options["once"]:
            threads.append(
                threading.Thread(
                    target=self._sync_lessons,
                    args=(stopping,),
                    daemon=True,
                    name="lesson-sync",
                )
            )

        for thread in threads:
            thread.start()

        try:
            while any(thread.is_alive() for thread in threads):
                for thread in threads:
                    thread.join(timeout=0.2)
        except KeyboardInterrupt:
            stopping.set()

        for thread in threads:
            thread.join()

        self.stdout.write("The worker has stopped.")

    def _loop(self, worker_name, interval, stopping, once):
        while not stopping.is_set():
            close_old_connections()

            try:
                job = queue.claim(worker_name)
            except Exception:
                logger.exception("Could not take a job from the queue: worker=%s", worker_name)
                time.sleep(interval)
                continue

            if job is None:
                if once:
                    return

                stopping.wait(interval)
                continue

            self._run(job, worker_name)

    def _sync_lessons(self, stopping, interval=60):
        """Percenként hozzáigazítja az órák állapotát az időpontjaikhoz."""
        while not stopping.is_set():
            close_old_connections()

            try:
                sync_lesson_states()
            except Exception:
                logger.exception("Could not sync the lesson states")

            stopping.wait(interval)

    def _run(self, job, worker_name):
        started = time.monotonic()

        self.stdout.write(f"[{worker_name}] {job.get_kind_display()} – submission {job.submission_id}")

        try:
            jobs.run(job)
        except Exception as error:
            logger.exception("The job failed: job=%s kind=%s", job.id, job.kind)
            queue.finish(job, error=f"{type(error).__name__}: {error}")
            self.stderr.write(f"[{worker_name}] failed after {time.monotonic() - started:.1f}s: {error}")
            return

        queue.finish(job)
        self.stdout.write(f"[{worker_name}] done in {time.monotonic() - started:.1f}s")
