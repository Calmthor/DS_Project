"""A* 求解器：使用曼哈顿距离启发式，逐步产出 StepSnapshot。

算法：优先队列按 f = g + h 取最小；g 是起点到该格的实际步数，h 是曼哈顿
距离下界。曼哈顿距离在四方向移动、每步代价 1 的无权网格上可采纳且一致，
因此 A* 找到的路径与 BFS 一样短，但扩展的格子通常更少。

若把堆里的格子记成 (f, 序号, 坐标)，同一格可能被 push 多次；
弹出时用 ``closed`` 集合跳过过期条目，保证每格只扩展一次。

课堂对应：优先队列、启发式搜索、可采纳性。
"""

from __future__ import annotations

import heapq
import itertools
from collections.abc import Iterator

from mazelab.core.maze import Maze
from mazelab.core.path import reconstruct_path
from mazelab.core.snapshot import Point, StepSnapshot


def manhattan(a: Point, b: Point) -> int:
    """两格之间的曼哈顿距离，作为 A* 的启发函数 h。"""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def solve_steps(maze: Maze, start: Point, goal: Point) -> Iterator[StepSnapshot]:
    """逐步求解：每次从优先队列取 f 值最小的格子并扩展。"""
    maze.cell(start)
    maze.cell(goal)

    if start == goal:
        yield StepSnapshot(
            action="起点即终点",
            current=start,
            visited={start},
            path=[start],
            done=True,
            extra={"expanded": 0},
        )
        return

    g_score: dict[Point, int] = {start: 0}
    parent: dict[Point, Point | None] = {start: None}
    closed: set[Point] = set()
    tie = itertools.count()  # f 相同时的稳定次序
    heap: list[tuple[int, int, Point]] = [(manhattan(start, goal), next(tie), start)]

    yield StepSnapshot(
        action=f"起点 {start} 入堆，h={manhattan(start, goal)}",
        current=start,
        structure=[(manhattan(start, goal), start)],
        visited=set(),
        frontier={start},
        extra={"expanded": 0},
    )

    expanded = 0
    while heap:
        f, _, cur = heapq.heappop(heap)
        if cur in closed:  # 过期条目：该格已用更优的 g 扩展过
            continue
        closed.add(cur)
        expanded += 1

        if cur == goal:
            path = reconstruct_path(parent, goal)
            yield StepSnapshot(
                action=f"扩展到终点 {goal}，路径长度 {len(path)}",
                current=goal,
                structure=[],
                visited=closed,
                path=path,
                done=True,
                extra={"expanded": expanded, "distance": len(path) - 1, "f": f},
            )
            return

        for nb in maze.neighbors(cur):
            if nb in closed:
                continue
            tentative = g_score[cur] + 1
            if tentative < g_score.get(nb, 1 << 30):
                g_score[nb] = tentative
                parent[nb] = cur
                heapq.heappush(heap, (tentative + manhattan(nb, goal), next(tie), nb))

        yield StepSnapshot(
            action=f"扩展 {cur}（g={g_score[cur]}, f={f}）",
            current=cur,
            structure=sorted((item[0], item[2]) for item in heap),
            visited=set(closed),
            frontier={item[2] for item in heap},
            extra={"expanded": expanded, "g": g_score[cur], "f": f},
        )

    yield StepSnapshot(
        action="优先队列为空，终点不可达",
        structure=[],
        visited=set(closed),
        done=True,
        path=[],
        extra={"expanded": expanded},
    )


def solve(maze: Maze, start: Point, goal: Point) -> list[Point] | None:
    """返回最短路径（起点在前），不可达时返回 ``None``。"""
    path: list[Point] | None = None
    for snapshot in solve_steps(maze, start, goal):
        if snapshot.done:
            path = snapshot.path or None
    return path
