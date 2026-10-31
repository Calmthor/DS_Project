"""随机 Prim 迷宫生成器，逐步产出 StepSnapshot。

算法：维护最小堆作为 frontier，堆里是 (随机权重, 目标格, 来源格)。
每次弹出权重最小的边：若目标格未访问则打通、标记访问，并把它的新候选边
压堆；已访问的边直接丢弃。随机权重让"先挑哪条边"等价于随机挑选，
但用堆实现，正好对应课堂上的优先队列。

与 DFS 的差别：Prim 从边界均匀扩张，迷宫分支短而多；DFS 则倾向长走廊。
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
) -> Iterator[StepSnapshot]:
    """逐步生成迷宫：每次从 frontier 中取权重最小的一格，与已访问邻格连通并扩展。"""
    if maze is None:
        maze = Maze(rows, cols)
    elif (maze.rows, maze.cols) != (rows, cols):
        raise ValueError(f"传入的迷宫尺寸 {maze.rows}×{maze.cols} 与参数 {rows}×{cols} 不一致")

    start = (rng.randrange(rows), rng.randrange(cols))
    visited: set[Point] = {start}
    tie = itertools.count()  # 权重相同时的稳定次序，避免比较坐标元组
    heap: list[tuple[float, int, Point, Point]] = []

    def push_candidates(source: Point) -> None:
        for nb in maze.adjacent(source):
            if nb not in visited:
                heapq.heappush(heap, (rng.random(), next(tie), nb, source))

    push_candidates(start)
    yield StepSnapshot(
        action=f"从 {start} 出发",
        current=start,
        structure=[],
        visited=set(visited),
        frontier={item[2] for item in heap},
        extra={"heap_size": len(heap), "carve": None},
    )

    while heap:
        weight, _, target, source = heapq.heappop(heap)
        if target in visited:
            yield StepSnapshot(
                action=f"跳过 {target}（已访问）",
                current=target,
                structure=[(round(w, 3), t) for w, _, t, _ in heap],
                visited=set(visited),
                frontier={item[2] for item in heap},
                extra={"heap_size": len(heap), "carve": None},
            )
            continue

        maze.carve(source, target)
        visited.add(target)
        push_candidates(target)
        yield StepSnapshot(
            action=f"接入 {target}（来自 {source}，权重 {weight:.3f}）",
            current=target,
            structure=[(round(w, 3), t) for w, _, t, _ in heap],
            visited=set(visited),
            frontier={item[2] for item in heap},
            extra={"heap_size": len(heap), "carve": (source, target)},
        )

    yield StepSnapshot(
        action="生成完成",
        structure=[],
        visited=set(visited),
        done=True,
        extra={"visited": len(visited), "passages": len(maze.passages())},
    )


def generate(rows: int, cols: int, rng: random.Random) -> Maze:
    """一次性生成并返回迷宫。"""
    maze = Maze(rows, cols)
    for _ in generate_steps(rows, cols, rng, maze):
        pass
    return maze
