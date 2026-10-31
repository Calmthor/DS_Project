"""路径工具：从父指针表回溯路径，并校验路径合法性。"""

from __future__ import annotations

from mazelab.core.maze import Maze, Point


def reconstruct_path(parent: dict[Point, Point | None], goal: Point) -> list[Point]:
    """沿父指针从 goal 回溯到起点，返回起点在前、终点在后的路径。

    ``parent[start]`` 约定为 ``None``；goal 不在表中时抛 ``ValueError``。
    """
    if goal not in parent:
        raise ValueError(f"{goal} 不在搜索记录中，无法回溯路径")
    path: list[Point] = []
    cur: Point | None = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def check_path(maze: Maze, start: Point, goal: Point, path: list[Point]) -> list[str]:
    """检查一条路径是否合法，返回问题列表（空列表表示通过）。

    逐项检查：非空、起点终点吻合、每一步相邻、相邻两步之间确实没有墙。
    """
    problems: list[str] = []
    if not path:
        return ["路径为空"]
    if path[0] != start:
        problems.append(f"路径起点 {path[0]} 与给定起点 {start} 不符")
    if path[-1] != goal:
        problems.append(f"路径终点 {path[-1]} 与给定终点 {goal} 不符")
    for prev, cur in zip(path, path[1:]):
        if prev == cur:
            problems.append(f"路径在 {cur} 处原地踏步")
            continue
        try:
            d = maze.direction(prev, cur)
        except ValueError:
            problems.append(f"{prev} 与 {cur} 不相邻")
            continue
        if maze.cell(prev).walls & d:
            problems.append(f"{prev} 与 {cur} 之间有墙，却出现在路径中")
    return problems
