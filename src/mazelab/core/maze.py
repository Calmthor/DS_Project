"""迷宫核心数据结构：单元格、墙位掩码、迷宫容器。

墙位掩码把一格的四面墙编码进一个整数：``N=1, E=2, S=4, W=8``。
某一位为 1 表示该方向有墙。打通相邻两格时必须同时清除双方的墙，
这条不变式由 :meth:`Maze.carve` 维护，:mod:`mazelab.core.validate` 会复查。
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

N, E, S, W = 1, 2, 4, 8
ALL_WALLS = N | E | S | W

DIRS: dict[int, tuple[int, int]] = {N: (-1, 0), E: (0, 1), S: (1, 0), W: (0, -1)}
OPPOSITE: dict[int, int] = {N: S, S: N, E: W, W: E}
DIR_NAMES: dict[int, str] = {N: "N", E: "E", S: "S", W: "W"}

Point = tuple[int, int]


def _check_pos(pos: Point) -> Point:
    if (
        not isinstance(pos, tuple)
        or len(pos) != 2
        or not all(isinstance(v, int) for v in pos)
    ):
        raise ValueError(f"坐标必须是 (row, col) 整数对，收到 {pos!r}")
    return pos


@dataclass
class Cell:
    """单个格子，``walls`` 记录四面墙的位掩码。"""

    row: int
    col: int
    walls: int = ALL_WALLS

    @property
    def pos(self) -> Point:
        return (self.row, self.col)


@dataclass
class Maze:
    """``rows × cols`` 的网格迷宫，每个格子维护自己的四面墙。"""

    rows: int
    cols: int
    cells: list[list[Cell]] = field(init=False)

    def __post_init__(self) -> None:
        if self.rows < 1 or self.cols < 1:
            raise ValueError(f"迷宫尺寸必须为正整数，收到 {self.rows}×{self.cols}")
        self.cells = [[Cell(r, c) for c in range(self.cols)] for r in range(self.rows)]

    # ---------- 基本查询 ----------

    @property
    def size(self) -> int:
        """格子总数。"""
        return self.rows * self.cols

    def in_bounds(self, pos: Point) -> bool:
        row, col = _check_pos(pos)
        return 0 <= row < self.rows and 0 <= col < self.cols

    def cell(self, pos: Point) -> Cell:
        """取出格子，越界时抛 ``ValueError`` 而不是静默返回。"""
        row, col = _check_pos(pos)
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise ValueError(f"坐标 {pos} 越界（迷宫 {self.rows}×{self.cols}）")
        return self.cells[row][col]

    def adjacent(self, pos: Point) -> list[Point]:
        """返回边界内的全部相邻格，**不看墙**。生成算法用它枚举候选。"""
        row, col = self.cell(pos).pos
        result: list[Point] = []
        for d, (dr, dc) in DIRS.items():
            nr, nc = row + dr, col + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                result.append((nr, nc))
        return result

    def direction(self, a: Point, b: Point) -> int:
        """从 a 指向 b 的方向位；两格不相邻时抛 ``ValueError``。"""
        self.cell(a)
        self.cell(b)
        delta = (b[0] - a[0], b[1] - a[1])
        for d, step in DIRS.items():
            if step == delta:
                return d
        raise ValueError(f"{a} 与 {b} 不相邻，不能打通")

    def is_open(self, a: Point, b: Point) -> bool:
        """a、b 之间是否已经打通（两格必须相邻）。"""
        return not self.cell(a).walls & self.direction(a, b)

    # ---------- 修改 ----------

    def carve(self, a: Point, b: Point) -> None:
        """打通相邻两格：同时清除双方的墙，保持墙位对称。

        对已经打通的相邻格重复调用是安全的（幂等）。
        """
        d = self.direction(a, b)
        self.cell(a).walls &= ~d
        self.cell(b).walls &= ~OPPOSITE[d]

    # ---------- 图查询 ----------

    def neighbors(self, pos: Point) -> list[Point]:
        """返回从 pos **能走到**的相邻格（边界内且中间无墙），顺序为 N/E/S/W。"""
        cell = self.cell(pos)
        result: list[Point] = []
        for d, (dr, dc) in DIRS.items():
            if cell.walls & d:
                continue
            nr, nc = cell.row + dr, cell.col + dc
            if 0 <= nr < self.rows and 0 <= nc < self.cols:
                result.append((nr, nc))
        return result

    def passages(self) -> list[tuple[Point, Point]]:
        """列出所有已打通的通道边，每条边只出现一次（取东、南两个方向）。"""
        edges: list[tuple[Point, Point]] = []
        for r in range(self.rows):
            for c in range(self.cols):
                if c + 1 < self.cols and not self.cells[r][c].walls & E:
                    edges.append(((r, c), (r, c + 1)))
                if r + 1 < self.rows and not self.cells[r][c].walls & S:
                    edges.append(((r, c), (r + 1, c)))
        return edges

    def reachable_from(self, start: Point) -> set[Point]:
        """从 start 出发 BFS 能到达的全部格子（含 start 自身）。"""
        seen = {self.cell(start).pos}
        queue = deque(seen)
        while queue:
            cur = queue.popleft()
            for nb in self.neighbors(cur):
                if nb not in seen:
                    seen.add(nb)
                    queue.append(nb)
        return seen

    def is_connected(self, start: Point, goal: Point) -> bool:
        """判断 start 与 goal 是否连通。"""
        if not self.in_bounds(start) or not self.in_bounds(goal):
            raise ValueError(f"起点或终点越界：{start} → {goal}")
        if start == goal:
            return True
        return goal in self.reachable_from(start)

    def is_perfect(self) -> bool:
        """是否为完美迷宫：全连通且通道数 = 格数 − 1（无环的生成树）。"""
        if len(self.reachable_from((0, 0))) != self.size:
            return False
        return len(self.passages()) == self.size - 1

    # ---------- 展示 ----------

    def to_ascii(
        self,
        path: list[Point] | None = None,
        marks: dict[Point, str] | None = None,
    ) -> str:
        """渲染为字符画。

        ``path`` 中的格子标 ``*``；``marks`` 可以覆盖单格字符（如起终点 ``S``/``G``）。
        """
        path_set = set(path or ())
        labels = dict(marks or {})

        lines: list[str] = []
        for r in range(self.rows):
            top = ["+"]
            for c in range(self.cols):
                top.append("---" if self.cells[r][c].walls & N else "   ")
                top.append("+")
            lines.append("".join(top))

            body = []
            for c in range(self.cols):
                cell = self.cells[r][c]
                body.append("|" if cell.walls & W else " ")
                if (r, c) in labels:
                    body.append(f" {labels[(r, c)][0]} ")
                elif (r, c) in path_set:
                    body.append(" * ")
                else:
                    body.append("   ")
            body.append("|" if self.cells[r][self.cols - 1].walls & E else " ")
            lines.append("".join(body))

        lines.append("+" + "---+" * self.cols)
        return "\n".join(lines)

    # ---------- 序列化 ----------

    def to_dict(self) -> dict[str, Any]:
        """导出为可 JSON 序列化的字典：每格只存一个墙位整数。"""
        return {
            "rows": self.rows,
            "cols": self.cols,
            "walls": [[cell.walls for cell in row] for row in self.cells],
        }

    @classmethod
    def from_dict(cls, data: Any) -> Maze:
        """从 :meth:`to_dict` 的结构还原，数据不合法时抛 ``ValueError``。"""
        if not isinstance(data, dict):
            raise ValueError("迷宫数据必须是一个对象")
        for key in ("rows", "cols", "walls"):
            if key not in data:
                raise ValueError(f"迷宫数据缺少字段 {key!r}")

        rows, cols = data["rows"], data["cols"]
        if not isinstance(rows, int) or not isinstance(cols, int) or rows < 1 or cols < 1:
            raise ValueError(f"rows/cols 必须是正整数，收到 {rows!r}×{cols!r}")

        walls = data["walls"]
        if not isinstance(walls, list) or len(walls) != rows:
            raise ValueError(f"walls 必须有 {rows} 行")
        maze = cls(rows, cols)
        for r, row in enumerate(walls):
            if not isinstance(row, list) or len(row) != cols:
                raise ValueError(f"walls 第 {r} 行必须有 {cols} 个格子")
            for c, value in enumerate(row):
                if not isinstance(value, int) or isinstance(value, bool) or value & ~ALL_WALLS:
                    raise ValueError(f"({r}, {c}) 的墙位 {value!r} 不在 0..15 内")
                maze.cells[r][c].walls = value
        return maze

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> Maze:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"不是合法 JSON：{exc}") from exc
        return cls.from_dict(data)

    def save(self, path: str | Path, *, indent: int | None = 2) -> None:
        Path(path).write_text(self.to_json(indent=indent), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Maze:
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"无法读取迷宫文件 {path}：{exc}") from exc
        return cls.from_json(text)
