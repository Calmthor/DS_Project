"""BFS 求解器：保证最短路，逐步产出 StepSnapshot。"""

from __future__ import annotations

from collections.abc import Iterator

from mazelab.core.maze import Maze
from mazelab.core.snapshot import StepSnapshot


def solve_steps(maze: Maze, start: tuple[int, int], goal: tuple[int, int]) -> Iterator[StepSnapshot]:
    """逐步求解：每次出队一个格子并扩展其未访问邻居。"""
    raise NotImplementedError