"""Dead-letter queue — stores permanently failed jobs for investigation."""

from __future__ import annotations

import time

from omnirag.intake.models import DeadLetter, SyncJob


class DeadLetterQueue:
    """Stores jobs that failed after max retries."""

    def __init__(self) -> None:
        self._letters: dict[str, DeadLetter] = {}

    def insert(self, job: SyncJob) -> DeadLetter:
        letter = DeadLetter(
            job_id=job.id,
            connector_id=job.connector_id,
            error=job.error_message or "max retries exceeded",
            payload={
                "source": job.source,
                "config": job.config,
                "attempts": job.attempt,
                "errors": job.errors,
            },
        )
        self._letters[letter.id] = letter
        return letter

    def get(self, letter_id: str) -> DeadLetter | None:
        return self._letters.get(letter_id)

    def list(self) -> list[dict]:
        return [
            {
                "id": l.id,
                "job_id": l.job_id,
                "connector_id": l.connector_id,
                "error": l.error,
                "created_at": l.created_at,
            }
            for l in sorted(self._letters.values(), key=lambda x: x.created_at, reverse=True)
        ]

    def delete(self, letter_id: str) -> bool:
        if letter_id in self._letters:
            del self._letters[letter_id]
            return True
        return False

    def replay(self, letter_id: str) -> DeadLetter | None:
        """Remove from dead-letter (caller should re-submit the job)."""
        return self._letters.pop(letter_id, None)

    def count(self) -> int:
        return len(self._letters)


_queue = DeadLetterQueue()


def get_dead_letter_queue() -> DeadLetterQueue:
    return _queue
