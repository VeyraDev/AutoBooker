"""Request-scoped temporary file workspace."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def materialize_bytes(content: bytes, suffix: str) -> Iterator[Path]:
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        path = Path(tmp.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


class TemporaryWorkspace:
    @contextmanager
    def materialize(self, content: bytes, suffix: str) -> Iterator[Path]:
        with materialize_bytes(content, suffix) as path:
            yield path
