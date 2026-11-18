"""求解器共享的样板逻辑。

BFS 与 A* 只是容器和取点规则不同，"检查起终点"和"从最后一帧取路径"
这段包装是完全一样的，抽出来免得两处各写一遍。
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

from mazelab.core.maze import Maze, Point
from mazelab.core.snapshot import StepSnapshot

# 求解器模块里 solve_steps 的统一签名：(maze, start, goal)
StepFn = Callable[[Maze, Point, Point], Iterator[StepSnapshot]]


def check_endpoints(maze: Maze, start: Point, goal: Point) -> None:
    """起终点必须在界内，越界直接抛 ``ValueError``。"""
    maze.cell(start)
    maze.cell(goal)


def collect_path(step_fn: StepFn, maze: Maze, start: Point, goal: Point) -> list[Point] | None:
    """跑完整个搜索，取最后一帧记录的路径；不可达时返回 ``None``。

    约定：``solve_steps()`` 结束时一定产出 ``done=True`` 的快照，
    且该快照的 ``path`` 就是最终结果（无解时为空列表）。
    """
    path: list[Point] | None = None
    for snapshot in step_fn(maze, start, goal):
        if snapshot.done:
            path = snapshot.path or None
    return path
