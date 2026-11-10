"""随机 Prim 迷宫生成器，逐步产出 StepSnapshot。

算法：维护最小堆作为 frontier，堆里是 (随机权重, 目标格, 来源格)。
每次弹出权重最小的边：若目标格未访问则打通、标记访问，并把它的新候选边
压堆；已访问的边直接丢弃。随机权重让"先挑哪条边"等价于随机挑选，
但用堆实现，正好对应课堂上的优先队列。

与 DFS 的差别：Prim 从边界均匀扩张，迷宫分支短而多；DFS 则倾向长走廊。

性能说明：快照里包含 visited 与 frontier 的副本，堆的大小随规模线性增长，
因此逐帧全部走完是 O(n²)。``generate()`` 用 ``capture=False`` 跳过这些副本，
生成回到 O(n log n)（每条边一次堆操作）。
"""

from __future__ import annotations

import heapq
import itertools
import random
from collections.abc import Iterator

from mazelab.core.maze import Maze
from mazelab.core.snapshot import Point, StepSnapshot


def generate_steps(
    rows: int,
    cols: int,
    rng: random.Random,
    maze: Maze | None = None,
    *,
    capture: bool = True,
) -> Iterator[StepSnapshot]:
    """逐步生成迷宫：每次从 frontier 中取权重最小的一格，与已访问邻格连通并扩展。

    ``capture=False`` 时不产出快照，只推进算法状态。
    """
    if maze is None:
        maze = Maze(rows, cols)
    elif (maze.rows, maze.cols) != (rows, cols):
        raise ValueError(f"传入的迷宫尺寸 {maze.rows}×{maze.cols} 与参数 {rows}×{cols} 不一致")

    start = (rng.randrange(rows), rng.randrange(cols))
    visited: set[Point] = {start}
    tie = itertools.count()  # 权重相同时的稳定次序，避免比较坐标元组
    heap: list[tuple[float, int, Point, Point]] = []
    frontier: set[Point] = set()  # 候选格，增量维护，免去每帧扫描整个堆

    def push_candidates(source: Point) -> None:
        for nb in maze.adjacent(source):
            if nb not in visited:
                heapq.heappush(heap, (rng.random(), next(tie), nb, source))
                frontier.add(nb)

    push_candidates(start)
    if capture:
        yield StepSnapshot(
            action=f"从 {start} 出发",
            current=start,
            structure=[],
            visited=set(visited),
            frontier=set(frontier),
            extra={"heap_size": len(heap), "carve": None},
        )

    while heap:
        weight, _, target, source = heapq.heappop(heap)
        if target in visited:
            if capture:
                yield StepSnapshot(
                    action=f"跳过 {target}（已访问）",
                    current=target,
                    structure=[],
                    visited=set(visited),
                    frontier=set(frontier),
                    extra={"heap_size": len(heap), "carve": None},
                )
            continue

        maze.carve(source, target)
        visited.add(target)
        frontier.discard(target)
        push_candidates(target)
        if capture:
            yield StepSnapshot(
                action=f"接入 {target}（来自 {source}，权重 {weight:.3f}）",
                current=target,
                structure=[],
                visited=set(visited),
                frontier=set(frontier),
                extra={"heap_size": len(heap), "carve": (source, target)},
            )

    if capture:
        yield StepSnapshot(
            action="生成完成",
            structure=[],
            visited=set(visited),
            frontier=set(),
            done=True,
            extra={"visited": len(visited), "passages": len(maze.passages())},
        )


def generate(rows: int, cols: int, rng: random.Random) -> Maze:
    """一次性生成并返回迷宫。"""
    maze = Maze(rows, cols)
    for _ in generate_steps(rows, cols, rng, maze, capture=False):
        pass
    return maze
