"""Asynchronous speech jobs.

Synchronous `POST /v1/speech` is the right shape when generation is fast. On a
small CPU-only instance it is not: a 60-second passage can take minutes, which
outlives most client timeouts. So the same generation is also offered as a job:

    POST /v1/speech/jobs   -> 202 + run_id, returns immediately
    GET  /v1/jobs/{id}     -> status and progress
    GET  /v1/jobs/{id}/audio -> the audio, once completed

Design notes:

* Jobs are scoped to the API key that created them; another client gets 404.
* Work is split into sentences so progress is real rather than a spinner, and so
  a long job does not monopolise the model slot between chunks.
* Results are held in memory with a TTL and a total byte budget. A free-tier
  instance has ~150MB of headroom, and jobs are lost on restart by design:
  this is a queue for slow generation, not durable storage.
"""

from __future__ import annotations

import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from app.errors import APIError, ErrorCode
from app.logging_config import get_logger
from app.providers.base import AudioResult
from app.services.audio import encode

logger = get_logger(__name__)

QUEUED = "queued"
RUNNING = "running"
COMPLETED = "completed"
FAILED = "failed"

TERMINAL_STATES = {COMPLETED, FAILED}

# Queue tuning. Hardcoded on purpose: the same values are correct on a laptop
# and on Render's free tier, so there is nothing for a deployment to configure.
# Raise WORKERS only alongside MAX_CONCURRENCY - each worker needs the model.
WORKERS = 1
MAX_CHUNKS = 40          # sentences per job; more are merged, not dropped
TTL_SECONDS = 3600       # finished jobs are dropped an hour later
MAX_PENDING = 50         # across all clients
MAX_PENDING_PER_CLIENT = 5
MAX_STORED_BYTES = 64_000_000  # keep well inside a 512MB instance's RAM

# Split on sentence punctuation, keeping the delimiter with its sentence.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|\n+")


def split_sentences(text: str, max_chunks: int) -> list[str]:
    """Split into speakable chunks. Falls back to the whole text if unsplittable."""
    parts = [p.strip() for p in _SENTENCE_SPLIT.split(text.strip()) if p.strip()]
    if not parts:
        return [text.strip()]
    if len(parts) > max_chunks:
        # Too many tiny sentences: merge so each inference call stays worthwhile.
        merged: list[str] = []
        for part in parts:
            if merged and len(merged[-1]) < 200:
                merged[-1] = f"{merged[-1]} {part}"
            else:
                merged.append(part)
        parts = merged
    return parts[:max_chunks]


@dataclass
class Job:
    id: str
    client_id: str
    status: str
    text_chars: int
    voice: str
    language: str
    output_format: str
    speed: float
    total_chunks: int
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    done_chunks: int = 0
    audio: bytes | None = None
    media_type: str | None = None
    audio_seconds: float | None = None
    generation_seconds: float | None = None
    error: str | None = None
    error_message: str | None = None
    voice_id: str = ""

    @property
    def progress(self) -> float:
        if self.status == COMPLETED:
            return 1.0
        if self.status != RUNNING or not self.total_chunks:
            return 0.0
        return round(self.done_chunks / self.total_chunks, 3)

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATES

    def public(self) -> dict:
        """Client-facing view. Never includes the audio bytes."""
        return {
            "run_id": self.id,
            "status": self.status,
            "progress": self.progress,
            "chunks": {"done": self.done_chunks, "total": self.total_chunks},
            "text_characters": self.text_chars,
            "voice": self.voice,
            "language": self.language,
            "format": self.output_format,
            "speed": self.speed,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "audio_seconds": self.audio_seconds,
            "generation_seconds": self.generation_seconds,
            "error": self.error,
            "message": self.error_message,
            "audio_url": f"/v1/jobs/{self.id}/audio" if self.status == COMPLETED else None,
        }


@dataclass
class _JobRecord:
    job: Job
    chunks: list[str] = field(default_factory=list)
    bytes: int = 0


class JobQueue:
    """In-process job queue with N worker threads."""

    def __init__(self, service) -> None:
        self._service = service
        self._queue: queue.Queue[str] = queue.Queue()
        self._records: dict[str, _JobRecord] = {}
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._stored_bytes = 0

    # ------------------------------------------------------------- lifecycle

    def start(self) -> None:
        if self._threads:
            return
        for index in range(WORKERS):
            thread = threading.Thread(
                target=self._worker, name=f"tts-job-{index}", daemon=True
            )
            thread.start()
            self._threads.append(thread)
        logger.info(
            "job queue started workers=%d ttl=%ds budget=%d bytes",
            len(self._threads), TTL_SECONDS, MAX_STORED_BYTES,
        )

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=2.0)
        self._threads.clear()

    # --------------------------------------------------------------- intake

    def submit(
        self,
        *,
        client_id: str,
        text: str,
        voice: str,
        language: str,
        output_format: str,
        speed: float,
    ) -> Job:
        self._evict_expired()
        with self._lock:
            pending = sum(
                1
                for record in self._records.values()
                if not record.job.is_terminal
            )
            mine = sum(
                1
                for record in self._records.values()
                if record.job.client_id == client_id and not record.job.is_terminal
            )
            if pending >= MAX_PENDING:
                raise APIError(
                    ErrorCode.SERVER_BUSY,
                    "Job queue is full, retry later.",
                    status_code=503,
                )
            if mine >= MAX_PENDING_PER_CLIENT:
                raise APIError(
                    ErrorCode.RATE_LIMITED,
                    f"Too many pending jobs for this API key (max "
                    f"{MAX_PENDING_PER_CLIENT}).",
                    status_code=429,
                )
            chunks = split_sentences(text, MAX_CHUNKS)
            job = Job(
                id=uuid.uuid4().hex,
                client_id=client_id,
                status=QUEUED,
                text_chars=len(text),
                voice=voice,
                voice_id=voice,
                language=language,
                output_format=output_format,
                speed=speed,
                total_chunks=len(chunks),
                created_at=time.time(),
            )
            self._records[job.id] = _JobRecord(job=job, chunks=chunks)
        self._queue.put(job.id)
        logger.info(
            "job queued run_id=%s client=%s chunks=%d chars=%d",
            job.id, client_id, job.total_chunks, job.text_chars,
        )
        return job

    def get(self, run_id: str, client_id: str) -> Job:
        record = self._find(run_id, client_id)
        if record is None:
            raise APIError(
                ErrorCode.INVALID_REQUEST,
                "Unknown run_id.",
                status_code=404,
            )
        return record.job

    def list(self, client_id: str, limit: int = 20) -> list[Job]:
        self._evict_expired()
        with self._lock:
            jobs = [
                record.job
                for record in self._records.values()
                if record.job.client_id == client_id
            ]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def delete(self, run_id: str, client_id: str) -> None:
        record = self._find(run_id, client_id)
        if record is None:
            raise APIError(ErrorCode.INVALID_REQUEST, "Unknown run_id.", status_code=404)
        with self._lock:
            self._stored_bytes -= record.bytes
            self._records.pop(run_id, None)
        logger.info("job deleted run_id=%s client=%s", run_id, client_id)

    def stats(self) -> dict[str, int]:
        with self._lock:
            states = {QUEUED: 0, RUNNING: 0, COMPLETED: 0, FAILED: 0}
            for record in self._records.values():
                states[record.job.status] = states.get(record.job.status, 0) + 1
            return {
                **states,
                "stored_bytes": self._stored_bytes,
                "workers": len(self._threads),
            }

    def _find(self, run_id: str, client_id: str) -> _JobRecord | None:
        with self._lock:
            record = self._records.get(run_id)
        if record is None or record.job.client_id != client_id:
            # Deliberately identical for "does not exist" and "not yours", so a
            # client cannot probe for other clients' run ids.
            return None
        return record

    # --------------------------------------------------------------- worker

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                run_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._process(run_id)
            except Exception:  # noqa: BLE001 - a bad job must not kill the worker
                logger.exception("job worker crashed on run_id=%s", run_id)
            finally:
                self._queue.task_done()

    def _process(self, run_id: str) -> None:
        record = self._find_any(run_id)
        if record is None:
            return
        job = record.job
        if not self._service.is_ready():
            job.status = FAILED
            job.error = ErrorCode.MODEL_NOT_READY
            job.error_message = "TTS model is not loaded."
            job.finished_at = time.time()
            return

        job.status = RUNNING
        job.started_at = time.time()
        started = time.perf_counter()
        collected: list[np.ndarray] = []
        sample_rate = self._service.sample_rate
        voices: set[str] = set()

        try:
            for index, chunk in enumerate(record.chunks):
                # Re-acquire the slot per chunk so one long job cannot starve
                # a short synchronous request.
                result: AudioResult = self._service.run_exclusive(
                    lambda c=chunk: self._service.provider.synthesize(
                        c, voice=job.voice_id, language=job.language, speed=job.speed
                    )
                )
                collected.append(result.samples)
                sample_rate = result.sample_rate
                voices.add(result.voice)
                job.done_chunks = index + 1
                logger.info(
                    "job progress run_id=%s chunk=%d/%d", run_id, index + 1, job.total_chunks
                )
        except Exception as exc:  # noqa: BLE001
            job.status = FAILED
            job.error = (
                exc.code if isinstance(exc, APIError) else ErrorCode.TTS_GENERATION_FAILED
            )
            job.error_message = (
                exc.message if isinstance(exc, APIError) else "Speech generation failed."
            )
            job.finished_at = time.time()
            logger.exception("job failed run_id=%s", run_id)
            return

        audio = np.concatenate(collected).astype(np.float32, copy=False)
        payload, media_type = encode(audio, sample_rate, job.output_format)
        generation_seconds = time.perf_counter() - started

        job.status = COMPLETED
        job.audio = payload
        job.media_type = media_type
        job.audio_seconds = round(len(audio) / sample_rate, 3)
        job.generation_seconds = round(generation_seconds, 3)
        job.finished_at = time.time()
        record.bytes = len(payload)
        with self._lock:
            self._stored_bytes += record.bytes
        self._enforce_budget()
        logger.info(
            "job completed run_id=%s audio_s=%s gen_s=%s bytes=%d",
            run_id, job.audio_seconds, job.generation_seconds, record.bytes,
        )

    def _find_any(self, run_id: str) -> _JobRecord | None:
        with self._lock:
            return self._records.get(run_id)

    # ----------------------------------------------------------- housekeeping

    def _evict_expired(self) -> None:
        cutoff = time.time() - TTL_SECONDS
        with self._lock:
            stale = [
                run_id
                for run_id, record in self._records.items()
                if record.job.finished_at and record.job.finished_at < cutoff
            ]
            for run_id in stale:
                self._stored_bytes -= self._records[run_id].bytes
                self._records.pop(run_id, None)
        if stale:
            logger.info("evicted %d expired job(s)", len(stale))

    def _enforce_budget(self) -> None:
        """Drop the oldest finished results until back inside the byte budget."""
        if MAX_STORED_BYTES <= 0:
            return
        while self._stored_bytes > MAX_STORED_BYTES:
            with self._lock:
                candidates = [
                    (record.job.finished_at or 0, run_id)
                    for run_id, record in self._records.items()
                    if record.job.status == COMPLETED
                ]
                if not candidates:
                    return
                _, oldest = min(candidates)
                self._stored_bytes -= self._records[oldest].bytes
                self._records.pop(oldest, None)
            logger.info("evicted job %s to stay inside the memory budget", oldest)
