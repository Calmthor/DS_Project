"""DFS 回溯迷宫生成器，逐步产出 StepSnapshot。"""

from __future__ import annotations

import random
from collections.abc import Iterator

from mazelab.core.snapshot import StepSnapshot


def generate_steps(rows: int, cols: int, rng: random.Random) -> Iterator[StepSnapshot]:
    """逐步生成迷宫。

    每步代表一次有教学意义的状态变化：
    - 前进：随机选一个未访问邻居，打通墙并压栈；
    - 回溯：连续弹栈直到找到仍有未访问邻居的格子。
    """
    raise NotImplementedError