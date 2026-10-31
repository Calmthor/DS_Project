"""迷宫合法性检查：边界封闭、墙位对称、连通性、无环性。

命令行 ``mazelab validate`` 与测试共用这里的检查，保证"演示的结论"
和"测试的断言"是同一套判据。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mazelab.core.maze import E, N, S, W, Maze


@dataclass
class Check:
    """单项检查结果。"""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    """全部检查结果，``ok`` 为真表示迷宫通过。"""

    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    def render(self) -> str:
        lines = []
        for check in self.checks:
            flag = "PASS" if check.ok else "FAIL"
            lines.append(f"[{flag}] {check.name}: {check.detail}")
        return "\n".join(lines)


def _check_border_closed(maze: Maze) -> Check:
    """最外圈必须保持封闭，否则迷宫"漏到外面"。"""
    leaks: list[str] = []
    for c in range(maze.cols):
        if not maze.cells[0][c].walls & N:
            leaks.append(f"({0}, {c}) 北侧开口")
        if not maze.cells[maze.rows - 1][c].walls & S:
            leaks.append(f"({maze.rows - 1}, {c}) 南侧开口")
    for r in range(maze.rows):
        if not maze.cells[r][0].walls & W:
            leaks.append(f"({r}, {0}) 西侧开口")
        if not maze.cells[r][maze.cols - 1].walls & E:
            leaks.append(f"({r}, {maze.cols - 1}) 东侧开口")
    detail = "外圈封闭" if not leaks else "；".join(leaks[:5])
    return Check("边界封闭", not leaks, detail)


def _check_wall_symmetry(maze: Maze) -> Check:
    """A 与 B 之间的墙必须同时存在于双方，否则两格对"能否通过"的判断会矛盾。"""
    broken: list[str] = []
    for r in range(maze.rows):
        for c in range(maze.cols):
            cell = maze.cells[r][c]
            for d, (dr, dc) in ((N, (-1, 0)), (E, (0, 1)), (S, (1, 0)), (W, (0, -1))):
                if cell.walls & d:
                    continue
                nr, nc = r + dr, c + dc
                if not (0 <= nr < maze.rows and 0 <= nc < maze.cols):
                    continue
                other = maze.cells[nr][nc]
                opposite = {N: S, E: W, S: N, W: E}[d]
                if other.walls & opposite:
                    broken.append(f"({r}, {c}) 与 ({nr}, {nc}) 之间墙位不对称")
    detail = "通道两侧墙位一致" if not broken else "；".join(broken[:5])
    return Check("墙位对称", not broken, detail)


def _check_connectivity(maze: Maze) -> Check:
    reached = maze.reachable_from((0, 0))
    missing = maze.size - len(reached)
    detail = f"从 (0, 0) 可达 {len(reached)}/{maze.size} 格"
    return Check("全连通", missing == 0, detail)


def _check_acyclic(maze: Maze) -> Check:
    """无环 ⇔ 通道数 = 格数 − 1（此时连通图必然是一棵树）。"""
    passages = len(maze.passages())
    expected = maze.size - 1
    detail = f"通道 {passages} 条，期望 {expected} 条（格数 − 1）"
    return Check("无环", passages == expected, detail)


def validate(maze: Maze) -> Report:
    """跑完全部检查并返回报告。"""
    return Report(
        checks=[
            _check_border_closed(maze),
            _check_wall_symmetry(maze),
            _check_connectivity(maze),
            _check_acyclic(maze),
        ]
    )
