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

from ._common import check_endpoints, collect_path, retire_dead


def solve_steps(maze: Maze, start: Point, goal: Point) -> Iterator[StepSnapshot]:
    """逐步求解：每次出队一个格子并扩展其未访问邻居。"""
    check_endpoints(maze, start, goal)

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
    closed: set[Point] = set()          # 已经扩展过的格子
    children: dict[Point, int] = {}     # 每个格子还有几个"没被判定为死路"的子节点
    dead: set[Point] = set()            # 确定走不通的格子（只增不减）
    yield StepSnapshot(
        action=f"起点 {start} 入队",
        current=start,
        structure=list(queue),
        visited=set(visited),
        frontier=set(queue),
        extra={"expanded": 0, "route": [start], "dead": set(dead)},
    )

    expanded = 0
    while queue:
        cur = queue.popleft()
        closed.add(cur)
        expanded += 1
        for nb in maze.neighbors(cur):
            if nb in visited:
                continue
            visited.add(nb)
            parent[nb] = cur
            children[cur] = children.get(cur, 0) + 1
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
                    extra={
                        "expanded": expanded,
                        "distance": len(path) - 1,
                        "route": path,
                        "dead": set(dead),
                    },
                )
                return

        # 扩展完再判断：这一格若没有存活子节点，就确定是死路，并向上传递
        retire_dead(cur, parent=parent, children=children, closed=closed, dead=dead)
        yield StepSnapshot(
            action=f"扩展 {cur}（队列 {len(queue)}）",
            current=cur,
            structure=list(queue),
            visited=set(visited),
            frontier=set(queue),
            extra={
                "expanded": expanded,
                # 从起点到当前格的父指针链：可视化里用它区分"正在走的分支"和"走过的岔路"
                "route": reconstruct_path(parent, cur),
                "dead": set(dead),
            },
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
    return collect_path(solve_steps, maze, start, goal)
