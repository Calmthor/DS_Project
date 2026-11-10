"""Kruskal + 并查集迷宫生成器，逐步产出 StepSnapshot。

算法：把所有相邻格之间的墙看成候选边，随机打乱后依次尝试：
若两端还不连通（并查集判断），就打通这条边并合并两个集合；
否则丢弃（否则会形成环路）。当连通分量降到 1 时，得到的必然是一棵生成树，
也就是完美迷宫。

课堂对应：并查集、最小生成树、按权重排序的贪心选择。

性能说明：``generate()`` 用 ``capture=False`` 跳过快照构造，
每条边只做一次并查集操作，整体 O(E·α(E))。
"""

from __future__ import annotations

import random
from collections.abc import Iterator

from mazelab.core.disjoint_set import DisjointSet
from mazelab.core.maze import Maze
from mazelab.core.snapshot import Point, StepSnapshot


def _edges(maze: Maze) -> list[tuple[Point, Point]]:
    """枚举所有"内部墙"对应的候选边，每对相邻格只出现一次。"""
    result: list[tuple[Point, Point]] = []
    for r in range(maze.rows):
        for c in range(maze.cols):
            if c + 1 < maze.cols:
                result.append(((r, c), (r, c + 1)))
            if r + 1 < maze.rows:
                result.append(((r, c), (r + 1, c)))
    return result


def generate_steps(
    rows: int,
    cols: int,
    rng: random.Random,
    maze: Maze | None = None,
    *,
    capture: bool = True,
) -> Iterator[StepSnapshot]:
    """逐步生成迷宫：按随机顺序考察每条候选边，用并查集决定是否打通。

    ``capture=False`` 时不产出快照，只推进算法状态。
    """
    if maze is None:
        maze = Maze(rows, cols)
    elif (maze.rows, maze.cols) != (rows, cols):
        raise ValueError(f"传入的迷宫尺寸 {maze.rows}×{maze.cols} 与参数 {rows}×{cols} 不一致")

    def index(pos: Point) -> int:
        return pos[0] * maze.cols + pos[1]

    edges = _edges(maze)
    rng.shuffle(edges)
    dsu = DisjointSet(maze.size)
    accepted = rejected = 0

    if capture:
        yield StepSnapshot(
            action=f"打乱 {len(edges)} 条候选边",
            structure=[],
            extra={"edges": len(edges), "components": dsu.components, "carve": None},
        )

    for a, b in edges:
        if dsu.union(index(a), index(b)):
            maze.carve(a, b)
            accepted += 1
            if capture:
                yield StepSnapshot(
                    action=f"接通 {a} — {b}",
                    current=b,
                    structure=[],
                    extra={
                        "accepted": accepted,
                        "rejected": rejected,
                        "components": dsu.components,
                        "carve": (a, b),
                    },
                )
            if dsu.components == 1:
                break
        else:
            rejected += 1
            if capture:
                yield StepSnapshot(
                    action=f"丢弃 {a} — {b}（已连通，会成环）",
                    current=b,
                    structure=[],
                    extra={
                        "accepted": accepted,
                        "rejected": rejected,
                        "components": dsu.components,
                        "carve": None,
                    },
                )

    if capture:
        yield StepSnapshot(
            action="生成完成",
            structure=[],
            visited={(r, c) for r in range(rows) for c in range(cols)},
            done=True,
            extra={
                "accepted": accepted,
                "rejected": rejected,
                "components": dsu.components,
                "passages": len(maze.passages()),
            },
        )


def generate(rows: int, cols: int, rng: random.Random) -> Maze:
    """一次性生成并返回迷宫。"""
    maze = Maze(rows, cols)
    for _ in generate_steps(rows, cols, rng, maze, capture=False):
        pass
    return maze
