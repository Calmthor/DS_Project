"""迷宫求解算法：BFS（队列）与 A*（优先队列 + 曼哈顿距离）。

两种算法都提供 ``solve``（直接拿路径）与 ``solve_steps``（拿逐帧快照），
``SOLVERS`` 供命令行按名字选取。
"""

from __future__ import annotations

from mazelab.core.maze import Maze, Point

from . import astar, bfs

SOLVERS = {
    "bfs": bfs,
    "astar": astar,
}

NAMES = tuple(SOLVERS)


def solve(name: str, maze: Maze, start: Point, goal: Point) -> list[Point] | None:
    """按名字求解；不可达时返回 ``None``。"""
    try:
        module = SOLVERS[name]
    except KeyError:
        raise ValueError(f"未知的求解算法 {name!r}，可选：{', '.join(NAMES)}") from None
    return module.solve(maze, start, goal)
