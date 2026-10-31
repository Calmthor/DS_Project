"""DFS 回溯迷宫生成器，逐步产出 StepSnapshot。

算法：维护一个显式栈，栈里是"当前这条挖掘路径"。每步随机挑一个未访问
邻居打通并压栈；无路可走时弹栈回退。栈空即生成结束。

课堂对应：栈、图遍历、回溯。生成结果的通道数恰好为 格数 − 1，
因此必然是完美迷宫（连通、无环）。
"""

from __future__ import annotations

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
    """逐步生成迷宫，每步代表一次有教学意义的状态变化。

    - 前进：随机选一个未访问邻居，打通墙并压栈；
    - 回溯：连续弹栈直到找到仍有未访问邻居的格子。

    传入 ``maze`` 时就地雕刻它（调用方可以随时看到最新状态），
    否则内部新建一个只在这个生成器里可见的迷宫。
    """
    if maze is None:
        maze = Maze(rows, cols)
    elif (maze.rows, maze.cols) != (rows, cols):
        raise ValueError(f"传入的迷宫尺寸 {maze.rows}×{maze.cols} 与参数 {rows}×{cols} 不一致")

    start = (rng.randrange(rows), rng.randrange(cols))
    visited: set[Point] = {start}
    stack: list[Point] = [start]

    yield StepSnapshot(
        action=f"从 {start} 出发",
        current=start,
        structure=list(stack),
        visited=set(visited),
        extra={"depth": len(stack), "carve": None},
    )

    while stack:
        cur = stack[-1]
        candidates = [nb for nb in maze.adjacent(cur) if nb not in visited]
        if candidates:
            nxt = rng.choice(candidates)
            maze.carve(cur, nxt)
            visited.add(nxt)
            stack.append(nxt)
            yield StepSnapshot(
                action=f"前进 {cur} → {nxt}",
                current=nxt,
                structure=list(stack),
                visited=set(visited),
                extra={"depth": len(stack), "carve": (cur, nxt)},
            )
        else:
            stack.pop()
            yield StepSnapshot(
                action=f"回溯，离开 {cur}",
                current=stack[-1] if stack else None,
                structure=list(stack),
                visited=set(visited),
                extra={"depth": len(stack), "carve": None},
            )

    yield StepSnapshot(
        action="生成完成",
        structure=[],
        visited=set(visited),
        done=True,
        extra={"visited": len(visited), "passages": len(maze.passages())},
    )


def generate(rows: int, cols: int, rng: random.Random) -> Maze:
    """一次性生成并返回迷宫（内部消费 :func:`generate_steps`，逻辑只有一份）。"""
    maze = Maze(rows, cols)
    for _ in generate_steps(rows, cols, rng, maze):
        pass
    return maze
