"""BFS 求解器：保证最短路，逐步产出 StepSnapshot。

算法：队列 + 父指针表。起点入队；每次出队一格，把未访问的相邻格登记父节点
并入队。因为 BFS 按"层"推进，**第一次发现终点**时它的层数就是最少步数，
此时沿父指针回溯即得最短路径。

课堂对应：队列、无权图上的最短路径。
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator

from mazelab.core.maze import Maze
from mazelab.core.path import reconstruct_path
from mazelab.core.snapshot import Point, StepSnapshot


def solve_steps(maze: Maze, start: Point, goal: Point) -> Iterator[StepSnapshot]:
    """逐步求解：每次出队一个格子并扩展其未访问邻居。"""
    maze.cell(start)
    maze.cell(goal)

    visited: set[Point] = {start}
    parent: dict[Point, Point | None] = {start: None}

    if start == goal:
        yield StepSnapshot(
            action="起点即终点",
            current=start,
            visited=set(visited),
            path=[start],
            done=True,
            extra={"expanded": 0},
        )
        return

    queue: deque[Point] = deque([start])
    yield StepSnapshot(
        action=f"起点 {start} 入队",
        current=start,
        structure=list(queue),
        visited=set(visited),
        frontier=set(queue),
        extra={"expanded": 0},
    )

    expanded = 0
    while queue:
        cur = queue.popleft()
        expanded += 1
        for nb in maze.neighbors(cur):
            if nb in visited:
                continue
            visited.add(nb)
            parent[nb] = cur
            queue.append(nb)
            if nb == goal:
                path = reconstruct_path(parent, goal)
                yield StepSnapshot(
                    action=f"发现终点 {goal}，路径长度 {len(path)}",
                    current=goal,
                    structure=list(queue),
                    visited=set(visited),
                    frontier=set(queue),
                    path=path,
                    done=True,
                    extra={"expanded": expanded, "distance": len(path) - 1},
                )
                return
            yield StepSnapshot(
                action=f"由 {cur} 发现 {nb}",
                current=nb,
                structure=list(queue),
                visited=set(visited),
                frontier=set(queue),
                extra={"expanded": expanded, "parent": cur},
            )

    yield StepSnapshot(
        action="队列为空，终点不可达",
        structure=[],
        visited=set(visited),
        done=True,
        path=[],
        extra={"expanded": expanded, "reachable": len(visited)},
    )


def solve(maze: Maze, start: Point, goal: Point) -> list[Point] | None:
    """返回最短路径（起点在前），不可达时返回 ``None``。"""
    path: list[Point] | None = None
    for snapshot in solve_steps(maze, start, goal):
        if snapshot.done:
            path = snapshot.path or None
    return path
