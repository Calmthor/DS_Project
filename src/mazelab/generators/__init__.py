"""迷宫生成算法：DFS 回溯、随机 Prim、Kruskal + 并查集。

三个模块暴露同样的接口，``GENERATORS`` 把它们按名字登记起来，
命令行和测试都从这张表取算法，新增算法只需在这里加一行。
"""

from __future__ import annotations

import random

from mazelab.core.maze import Maze

from . import dfs, kruskal, prim

GENERATORS = {
    "dfs": dfs,
    "prim": prim,
    "kruskal": kruskal,
}

NAMES = tuple(GENERATORS)


def generate(name: str, rows: int, cols: int, seed: int | None = None) -> Maze:
    """按名字生成迷宫；``seed`` 相同则结果完全相同。"""
    try:
        module = GENERATORS[name]
    except KeyError:
        raise ValueError(f"未知的生成算法 {name!r}，可选：{', '.join(NAMES)}") from None
    return module.generate(rows, cols, random.Random(seed))
