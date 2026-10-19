"""单步快照：统一生成器与求解器的逐步输出格式。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Point = tuple[int, int]


@dataclass
class StepSnapshot:
    action: str
    current: Point | None = None
    structure: list[Any] = field(default_factory=list)
    visited: set[Point] = field(default_factory=set)
    frontier: set[Point] = field(default_factory=set)
    path: list[Point] = field(default_factory=list)
    done: bool = False
    extra: dict[str, Any] = field(default_factory=dict)