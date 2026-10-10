"""Progress callback type for streaming progress updates."""

from typing import Callable, Optional

# (stage: str, message: str) -> None
ProgressCallback = Callable[[str, str], None]
