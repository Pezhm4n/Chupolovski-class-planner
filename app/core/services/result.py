from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class Result:
    """A standard result object returned by services to decouple them from UI"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
