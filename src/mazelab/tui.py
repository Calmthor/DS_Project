"""交互式终端演示：选尺寸 → 生成迷宫 → 选算法 → 逐帧展示求解过程。

视觉约定：
- 当前格用方向箭头表示（从父节点指向当前格），比一个静止的标记更能看出"往哪走"；
- 颜色按状态区分：起点/终点、当前分支、走过的岔路、候选、最终路径各一色，
  所以"既是当前分支又是旧岔路"的格子会按当前分支着色——它未必是错的；
- 关掉颜色（``--no-color``）或用 ASCII 箭头（``--ascii``）时，字符和排版完全不变，
  只是少了转义序列，方便在不支持 ANSI 的终端或重定向场景里使用。
"""

from __future__ import annotations

import os
import random
import shutil
import sys
import time

from mazelab.core.maze import E, N, S, W, Maze
from mazelab.core.snapshot import Point, StepSnapshot
from mazelab.generators import GENERATORS, NAMES as GENERATOR_NAMES
from mazelab.solvers import NAMES as SOLVER_NAMES, SOLVERS

DEFAULT_DELAY = 1.0
MAX_SIZE = 40

RESET = "\x1b[0m"

# 256 色：墙面压暗，让内容跳出来
PALETTE = {
    "wall": "\x1b[38;5;240m",
    "visited": "\x1b[38;5;245m",   # 走过的岔路
    "route": "\x1b[38;5;51m",      # 当前这条分支
    "frontier": "\x1b[38;5;220m",  # 候选
    "path": "\x1b[1;38;5;46m",     # 最终路径
    "head": "\x1b[1;38;5;213m",    # 当前格
    "start": "\x1b[1;38;5;46m",
    "goal": "\x1b[1;38;5;196m",
}

_ARROWS = {(1, 0): "↓", (-1, 0): "↑", (0, 1): "→", (0, -1): "←"}
_ARROWS_ASCII = {(1, 0): "v", (-1, 0): "^", (0, 1): ">", (0, -1): "<"}

_ansi_ready: bool | None = None


# ---------- 终端能力探测 ----------


def _probe_ansi() -> bool:
    """判断当前终端能否用 ANSI 转义（颜色 + 原地重绘）。"""
    if not sys.stdout.isatty():
        return False
    if os.name != "nt":
        return True
    try:  # Windows 10+ 需要显式打开 VT 处理
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def _ansi_supported() -> bool:
    global _ansi_ready
    if _ansi_ready is None:
        _ansi_ready = _probe_ansi()
    return _ansi_ready


def _fits(lines: int) -> bool:
    """终端高度是否放得下一整帧（放不下就别原地重绘）。"""
    try:
        height = shutil.get_terminal_size().lines
    except OSError:
        return False
    return height <= 0 or lines < height


def color_enabled(requested: bool) -> bool:
    """是否真的上色：用户没关、没有 NO_COLOR、终端支持 ANSI。"""
    return bool(requested) and not os.environ.get("NO_COLOR") and _ansi_supported()


# ---------- 渲染 ----------


def head_char(snapshot: StepSnapshot, ascii_arrows: bool = False) -> str:
    """当前格的方向箭头：由父节点指向当前格；还没有父节点时用 o。"""
    route = snapshot.extra.get("route") or []
    if len(route) >= 2:
        dr = route[-1][0] - route[-2][0]
        dc = route[-1][1] - route[-2][1]
        table = _ARROWS_ASCII if ascii_arrows else _ARROWS
        return table.get((dr, dc), "o")
    return "o"


def cell_mark(
    snapshot: StepSnapshot,
    pos: Point,
    start: Point,
    goal: Point,
    head: str,
) -> tuple[str, str]:
    """返回 (字符, 调色板键)。

    叠加顺序即优先级：起终点 > 当前格 > 最终路径 > 当前分支 > 候选 > 已访问。
    当前分支排在已访问之前，是为了让"既在分支上又走过"的格子仍按分支显示。
    """
    if pos == start:
        return "S", "start"
    if pos == goal:
        return "G", "goal"
    if pos == snapshot.current:
        return head, "head"
    if pos in snapshot.path:
        return "*", "path"
    if pos in (snapshot.extra.get("route") or ()):
        return "+", "route"
    if pos in snapshot.frontier:
        return ",", "frontier"
    if pos in snapshot.visited:
        return ".", "visited"
    return " ", ""


def render(
    maze: Maze,
    snapshot: StepSnapshot,
    start: Point,
    goal: Point,
    *,
    color: bool = True,
    ascii_arrows: bool = False,
) -> str:
    """渲染一帧。排版与 ``Maze.to_ascii()`` 完全一致，只是可能多了颜色转义。"""
    head = head_char(snapshot, ascii_arrows)

    def paint(text: str, key: str) -> str:
        code = PALETTE.get(key, "") if color else ""
        return f"{code}{text}{RESET}" if code else text

    lines: list[str] = []
    for r in range(maze.rows):
        border = ["+"]
        for c in range(maze.cols):
            border.append("---" if maze.cells[r][c].walls & N else "   ")
            border.append("+")
        lines.append(paint("".join(border), "wall"))

        body: list[str] = []
        for c in range(maze.cols):
            cell = maze.cells[r][c]
            body.append(paint("|" if cell.walls & W else " ", "wall"))
            ch, key = cell_mark(snapshot, (r, c), start, goal, head)
            body.append(paint(f" {ch} ", key))
        body.append(paint("|" if maze.cells[r][maze.cols - 1].walls & E else " ", "wall"))
        lines.append("".join(body))

    lines.append(paint("+" + "---+" * maze.cols, "wall"))
    return "\n".join(lines)


def legend(color: bool = True, ascii_arrows: bool = False) -> str:
    """图例：颜色开启时，每个符号也按对应颜色显示。"""
    arrow = _ARROWS_ASCII[(0, 1)] if ascii_arrows else _ARROWS[(0, 1)]
    parts = [
        ("S", "start", "起点"),
        ("G", "goal", "终点"),
        (arrow, "head", "当前格"),
        ("*", "path", "最终路径"),
        ("+", "route", "当前探索分支"),
        (",", "frontier", "候选"),
        (".", "visited", "走过的岔路"),
    ]
    pieces = []
    for ch, key, label in parts:
        code = PALETTE.get(key, "") if color else ""
        pieces.append(f"{code}{ch}{RESET} {label}" if code else f"{ch} {label}")
    return "   ".join(pieces)


class _Screen:
    """原地重绘：每帧覆盖上一帧，避免刷屏。

    只有当终端够高、且支持 ANSI 时才原地重绘；否则退化为逐帧追加，
    这样帧比窗口高的时候不会因为换行导致光标回不到正确位置。
    """

    def __init__(self, min_lines: int = 0) -> None:
        self._lines = 0
        self._live = _ansi_supported() and _fits(min_lines)

    @property
    def live(self) -> bool:
        return self._live

    def paint(self, text: str) -> None:
        if self._live:
            if self._lines:
                sys.stdout.write(f"\x1b[{self._lines}A")  # 光标回到上一帧开头
            sys.stdout.write("\x1b[J")  # 清掉旧内容
        sys.stdout.write(text)
        sys.stdout.flush()
        self._lines = text.count("\n")


# ---------- 交互 ----------


def ask_int(prompt: str, default: int, lo: int, hi: int) -> int:
    """读一个整数，空输入用默认值，非法输入重新问。"""
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(f"  请输入 {lo}–{hi} 之间的整数")
            continue
        if not lo <= value <= hi:
            print(f"  超出范围，请输入 {lo}–{hi}")
            continue
        return value


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    """从固定选项里选一个，空输入用默认值。"""
    joined = "/".join(options)
    while True:
        raw = input(f"{prompt} ({joined}) [{default}]: ").strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"  可选：{joined}")


def run_demo(
    rows: int,
    cols: int,
    generator: str,
    solver: str,
    seed: int,
    delay: float = DEFAULT_DELAY,
    *,
    color: bool = True,
    ascii_arrows: bool = False,
) -> int:
    """跑一次完整演示：生成、逐帧求解、输出总结。"""
    if not 1 <= rows <= MAX_SIZE or not 1 <= cols <= MAX_SIZE:
        print(f"尺寸需在 1–{MAX_SIZE} 之间，收到 {rows}×{cols}", file=sys.stderr)
        return 2

    use_color = color_enabled(color) and not ascii_arrows
    maze = GENERATORS[generator].generate(rows, cols, random.Random(seed))
    start, goal = (0, 0), (rows - 1, cols - 1)

    print(f"MazeLab 演示：{rows}×{cols}｜生成 {generator}｜求解 {solver}｜seed={seed}")
    print(legend(use_color, ascii_arrows))
    print(f"按 Ctrl+C 可随时中断；用 --delay 0.2 可加快（当前每步 {delay:g}s）")
    print()

    screen = _Screen(min_lines=2 * rows + 3)
    if not screen.live:
        print("（终端放不下整帧或未启用 ANSI，改为逐帧追加输出）")
    final: StepSnapshot | None = None
    step_no = 0
    try:
        for step_no, snapshot in enumerate(SOLVERS[solver].solve_steps(maze, start, goal), 1):
            picture = render(maze, snapshot, start, goal, color=use_color, ascii_arrows=ascii_arrows)
            screen.paint(f"{picture}\n步骤 {step_no:3d}  {snapshot.action}\n")
            final = snapshot
            if delay > 0:
                time.sleep(delay)
    except KeyboardInterrupt:
        print()
        print("已中断（未完成求解）")
        return 130

    if final is None:
        print("没有任何可展示的步骤")
        return 1

    path = final.path
    if not path:
        print("\n结果：起点与终点不连通，无解")
        return 0

    print()
    print(f"结果：最短路径 {len(path) - 1} 步，共展示 {step_no} 帧，扩展 {final.extra.get('expanded', '?')} 格")
    return 0


def interactive(
    rows: int | None = None,
    cols: int | None = None,
    generator: str | None = None,
    solver: str | None = None,
    delay: float = DEFAULT_DELAY,
    seed: int | None = None,
    *,
    color: bool = True,
    ascii_arrows: bool = False,
) -> int:
    """交互入口：缺什么问什么，全给了就直接跑。"""
    print("=== MazeLab 交互演示 ===")
    try:
        if rows is None:
            rows = ask_int("迷宫行数", 10, 1, MAX_SIZE)
        if cols is None:
            cols = ask_int("迷宫列数", 10, 1, MAX_SIZE)
        if generator is None:
            generator = ask_choice("生成算法", list(GENERATOR_NAMES), "dfs")
        if solver is None:
            solver = ask_choice("求解算法", list(SOLVER_NAMES), "bfs")
    except EOFError:
        print("没有可用的标准输入（可能是在管道或重定向里运行）。", file=sys.stderr)
        print(
            "改用参数直接指定：mazelab play --rows 10 --cols 10 "
            "--algorithm dfs --solver bfs --delay 0.2",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\n已取消", file=sys.stderr)
        return 130

    if seed is None:
        seed = random.randrange(1, 1_000_000)
    print()
    return run_demo(
        rows, cols, generator, solver, seed, delay, color=color, ascii_arrows=ascii_arrows
    )
