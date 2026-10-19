"""A* 求解器：使用曼哈顿距离启发式，逐步产出 StepSnapshot。"""

from __future__ import annotations

from collections.abc import Iterator

from mazelab.core.maze import Maze
from mazelab.core.snapshot import StepSnapshot


def solve_steps(maze: Maze, start: tuple[int, int], goal: tuple[int, int]) -> Iterator[StepSnapshot]:
    """逐步求解：每次从优先队列取 f 值最小的格子并扩展。"""
    raise NotImplementedError