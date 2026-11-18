"""生成器共享的样板逻辑。

三个生成算法在"准备迷宫"和"只要结果、不要快照"这两件事上完全一样，
抽到这里是为了让算法本身留在各自的模块里，样板只有一份。
"""

from __future__ import annotations

import random
from collections.abc import Callable, Iterator

from mazelab.core.maze import Maze
from mazelab.core.snapshot import StepSnapshot

# 生成器模块里 generate_steps 的统一签名：(rows, cols, rng, maze, *, capture)
StepFn = Callable[..., Iterator[StepSnapshot]]


def resolve_maze(rows: int, cols: int, maze: Maze | None) -> Maze:
    """确定要雕刻的迷宫：没传就新建；传了就必须和 rows×cols 一致。

    尺寸不符时立刻报错，而不是在雕刻到越界格时才发现。
    """
    if maze is None:
        return Maze(rows, cols)
    if (maze.rows, maze.cols) != (rows, cols):
        raise ValueError(f"传入的迷宫尺寸 {maze.rows}×{maze.cols} 与参数 {rows}×{cols} 不一致")
    return maze


def drain(step_fn: StepFn, rows: int, cols: int, rng: random.Random) -> Maze:
    """以 ``capture=False`` 跑完生成过程，只返回最终迷宫。

    这样 ``generate()`` 与 ``generate_steps()`` 共用同一份算法实现，
    却不用为每一帧复制 visited/frontier —— 否则全部走完会退化成 O(n²)。
    """
    maze = Maze(rows, cols)
    for _ in step_fn(rows, cols, rng, maze, capture=False):
        pass
    return maze
