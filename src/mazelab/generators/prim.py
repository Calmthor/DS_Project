"""随机 Prim 迷宫生成器，逐步产出 StepSnapshot。"""

from __future__ import annotations

import random
from collections.abc import Iterator

from mazelab.core.snapshot import StepSnapshot


def generate_steps(rows: int, cols: int, rng: random.Random) -> Iterator[StepSnapshot]:
    """逐步生成迷宫：每次从 frontier 中取一格，与已访问邻格连通并扩展。"""
    raise NotImplementedError