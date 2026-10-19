"""迷宫核心数据结构：单元格、墙位掩码、迷宫容器。"""

from __future__ import annotations

from dataclasses import dataclass, field

N, E, S, W = 1, 2, 4, 8
DIRS = {
    N: (-1, 0),
    E: (0, 1),
    S: (1, 0),
    W: (0, -1),
}
OPPOSITE = {N: S, S: N, E: W, W: E}


@dataclass
class Cell:
    row: int
    col: int
    walls: int = N | E | S | W


@dataclass
class Maze:
    rows: int
    cols: int
    cells: list[list[Cell]] = field(init=False)

    def __post_init__(self) -> None:
        self.cells = [[Cell(r, c) for c in range(self.cols)] for r in range(self.rows)]

    def carve(self, a: tuple[int, int], b: tuple[int, int]) -> None:
        """打通相邻两格 a、b 之间的墙。"""
        raise NotImplementedError

    def neighbors(self, pos: tuple[int, int]) -> list[tuple[int, int]]:
        """返回从 pos 可以走到的相邻格。"""
        raise NotImplementedError

    def is_connected(self, start: tuple[int, int], goal: tuple[int, int]) -> bool:
        """判断 start 与 goal 是否连通。"""
        raise NotImplementedError