"""交互式终端演示：选尺寸 → 生成迷宫 → 选算法 → 逐帧展示求解过程。

视觉约定：
- 当前格用方向箭头表示（由父节点指向当前格），看出搜索往哪走；
- 走过的岔路用红色 ``x``，最终路径用绿色 ``√``，候选是白色圆点 ``·``；
- 当前探索分支用白色连成一条线：格子内按邻接方向选 ``│─┌┐└┘├┤┬┴┼``，
  格子之间的空隙也补上连接符，所以整条分支看起来是连续的白线；
- 一个格子既在当前分支上、又走过一次时，按分支显示——它未必是错的。

关掉颜色（``--no-color``）或用 ASCII 模式（``--ascii``）时，排版完全不变，
只是少了颜色转义、并把特殊符号换成纯 ASCII，方便在不支持 Unicode 的终端里用。
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

# 256 色：墙面压暗，让内容跳出来；岔路用暗红，避免和亮红的终点抢眼
PALETTE = {
    "wall": "\x1b[38;5;238m",
    "dead": "\x1b[38;5;124m",      # 确定走不通：暗红 x
    "visited": "\x1b[38;5;240m",   # 走过但还没定论：灰 o
    "route": "\x1b[38;5;255m",     # 当前分支：白线
    "frontier": "\x1b[38;5;250m",  # 候选：白点
    "path": "\x1b[1;38;5;46m",     # 最终路径：亮绿 √
    "head": "\x1b[1;38;5;231m",    # 当前格：白色加粗箭头
    "start": "\x1b[1;38;5;46m",
    "goal": "\x1b[1;38;5;196m",
}

_ARROWS = {(1, 0): "↓", (-1, 0): "↑", (0, 1): "→", (0, -1): "←"}
_ARROWS_ASCII = {(1, 0): "v", (-1, 0): "^", (0, 1): ">", (0, -1): "<"}

# 当前分支的连线符号：按"这条分支连向了哪几个方向"决定用哪个字符
_LINE = {
    frozenset({"N", "S"}): "│",
    frozenset({"E", "W"}): "─",
    frozenset({"S", "E"}): "┌",
    frozenset({"S", "W"}): "┐",
    frozenset({"N", "E"}): "└",
    frozenset({"N", "W"}): "┘",
    frozenset({"N", "S", "E"}): "├",
    frozenset({"N", "S", "W"}): "┤",
    frozenset({"N", "E", "W"}): "┴",
    frozenset({"S", "E", "W"}): "┬",
    frozenset({"N", "S", "E", "W"}): "┼",
    frozenset({"N"}): "│",
    frozenset({"S"}): "│",
    frozenset({"E"}): "─",
    frozenset({"W"}): "─",
    frozenset(): "·",
}

_ansi_ready: bool | None = None

# 一格是三个字符宽（" X "），横向穿越时要把两边的空格也画成横线，
# 竖线则保持在中间一格，才能和边框行里的 " │ " 对齐
_WIDE = {
    "─": "───",
    "│": " │ ",
    "┌": " ┌─",
    "┐": "─┐ ",
    "└": " └─",
    "┘": "─┘ ",
    "├": " ├─",
    "┤": "─┤ ",
    "┬": "─┬─",
    "┴": "─┴─",
    "┼": "─┼─",
}


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


# ---------- 键盘 ----------


class _Keyboard:
    """非阻塞读一个键，用来支持"空格暂停"。

    Windows 用 msvcrt，其余平台用 select + cbreak；标准输入不是终端时直接禁用，
    这样重定向/管道场景不会卡住。
    """

    def __init__(self) -> None:
        try:
            self.enabled = sys.stdin is not None and sys.stdin.isatty()
        except Exception:  # 某些测试替身没有 isatty()
            self.enabled = False

    def read(self, timeout: float | None) -> str | None:
        """读一个按键；返回 None 表示超时（或键盘不可用）。"""
        if not self.enabled:
            if timeout:
                time.sleep(timeout)
            return None
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            ch = self._poll()
            if ch is not None:
                if ch == "\x03":  # Ctrl+C 在原始模式下不会自动抛异常
                    raise KeyboardInterrupt
                return ch
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(0.02)

    def _poll(self) -> str | None:
        if os.name == "nt":
            import msvcrt

            if msvcrt.kbhit():
                return msvcrt.getwch()
            return None
        try:
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setcbreak(fd)
                ready, _, _ = select.select([fd], [], [], 0)
                if not ready:
                    return None
                return sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            return None


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


def _step_dir(a: Point, b: Point) -> str:
    """从 a 走到 b 的方向。"""
    dr, dc = b[0] - a[0], b[1] - a[1]
    if dr == -1:
        return "N"
    if dr == 1:
        return "S"
    if dc == 1:
        return "E"
    return "W"


def route_dirs(route: list[Point]) -> dict[Point, set[str]]:
    """按路径顺序算出每格连向哪几个方向。

    必须用顺序而不是"邻格是否也在路径上"：迷宫里两条走廊常常并排贴在一起，
    按邻接判断会凭空连出一条不存在的支路，还会冒出 ├、┤ 这类三向岔口。
    """
    shapes: dict[Point, set[str]] = {}
    for i, pos in enumerate(route):
        dirs: set[str] = set()
        if i > 0:
            dirs.add(_step_dir(pos, route[i - 1]))  # 手臂朝向上一个格子
        if i + 1 < len(route):
            dirs.add(_step_dir(pos, route[i + 1]))  # 手臂朝向下一个格子
        shapes[pos] = dirs
    return shapes


def route_links(route: list[Point]) -> set[frozenset[Point]]:
    """路径上真正相邻的两格，只有它们之间才该补连接符。"""
    return {frozenset(pair) for pair in zip(route, route[1:])}


def route_glyph(dirs: set[str], ascii_mode: bool = False) -> str:
    """当前分支的连线字符：直行只有横线或竖线，转角用 ┌┐└┘。"""
    if not dirs:
        return "*" if ascii_mode else "·"
    if ascii_mode:
        if dirs == {"E", "W"}:
            return "-"
        if dirs == {"N", "S"}:
            return "|"
        if len(dirs) >= 2:
            return "+"
        return "|" if dirs & {"N", "S"} else "-"
    return _LINE.get(frozenset(dirs), "·")


def cell_mark(
    snapshot: StepSnapshot,
    pos: Point,
    start: Point,
    goal: Point,
    head: str,
    shapes: dict[Point, set[str]] | None = None,
    ascii_mode: bool = False,
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
        return ("*" if ascii_mode else "√"), "path"
    if shapes is None:
        shapes = route_dirs(list(snapshot.extra.get("route") or ()))
    if pos in shapes:
        return route_glyph(shapes[pos], ascii_mode), "route"
    if pos in (snapshot.extra.get("dead") or ()):
        return "x", "dead"  # 只有整棵子树都探完、确定走不通的格子才标红
    if pos in snapshot.frontier:
        return ("." if ascii_mode else "·"), "frontier"
    if pos in snapshot.visited:
        return ("." if ascii_mode else "o"), "visited"
    return " ", ""


def render(
    maze: Maze,
    snapshot: StepSnapshot,
    start: Point,
    goal: Point,
    *,
    color: bool = True,
    ascii_arrows: bool = False,
    ascii_mode: bool | None = None,
) -> str:
    """渲染一帧。排版与 ``Maze.to_ascii()`` 等宽，只是字符和颜色更丰富。"""
    if ascii_mode is None:
        ascii_mode = ascii_arrows
    head = head_char(snapshot, ascii_arrows)
    route = list(snapshot.extra.get("route") or ())
    shapes = route_dirs(route)
    links = route_links(route)
    v_link = "|" if ascii_mode else "│"
    h_link = "-" if ascii_mode else "─"

    def paint(text: str, key: str) -> str:
        code = PALETTE.get(key, "") if color else ""
        return f"{code}{text}{RESET}" if code else text

    lines: list[str] = []
    for r in range(maze.rows):
        seg = [paint("+", "wall")]
        for c in range(maze.cols):
            if maze.cells[r][c].walls & N:
                seg.append(paint("---", "wall"))
            elif r > 0 and frozenset({(r, c), (r - 1, c)}) in links:
                seg.append(paint(f" {v_link} ", "route"))  # 路径连续穿过这里，补一段竖线
            else:
                seg.append(paint("   ", "wall"))
            seg.append(paint("+", "wall"))
        lines.append("".join(seg))

        body: list[str] = []
        for c in range(maze.cols):
            cell = maze.cells[r][c]
            if cell.walls & W:
                body.append(paint("|", "wall"))
            elif c > 0 and frozenset({(r, c), (r, c - 1)}) in links:
                body.append(paint(h_link, "route"))  # 路径连续穿过这里，补一段横线
            else:
                body.append(paint(" ", "wall"))
            ch, key = cell_mark(
                snapshot, (r, c), start, goal, head, shapes, ascii_mode
            )
            body.append(paint(_WIDE.get(ch, f" {ch} ") if key == "route" else f" {ch} ", key))
        last = maze.cells[r][maze.cols - 1]
        body.append(paint("|" if last.walls & E else " ", "wall"))
        lines.append("".join(body))

    lines.append(paint("+" + "---+" * maze.cols, "wall"))
    return "\n".join(lines)


def legend(color: bool = True, ascii_arrows: bool = False) -> str:
    """图例：颜色开启时，每个符号也按对应颜色显示。"""
    arrow = _ARROWS_ASCII[(0, 1)] if ascii_arrows else _ARROWS[(0, 1)]
    path = "*" if ascii_arrows else "√"
    dot = "." if ascii_arrows else "·"
    line = "+" if ascii_arrows else "│─"
    parts = [
        ("S", "start", "起点"),
        ("G", "goal", "终点"),
        (arrow, "head", "当前格"),
        (path, "path", "最终路径"),
        (line, "route", "当前分支"),
        (dot, "frontier", "候选"),
        ("x", "dead", "确定死路"),
        ("o", "visited", "走过未定"),
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
    """读一个整数：提示里写明回车即用默认值，其余不合法的输入一律要求重输。"""
    while True:
        raw = input(f"{prompt}（回车=默认 {default}）: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            print(f"  输入不合法，请输入 {lo}–{hi} 的数字")
            continue
        if not lo <= value <= hi:
            print(f"  输入不合法，请输入 {lo}–{hi} 的数字")
            continue
        return value


def ask_choice(prompt: str, options: list[str], default: str) -> str:
    """从固定选项里选一个：提示里写明回车即用默认值，非法输入要求重输。"""
    joined = "/".join(options)
    while True:
        raw = input(f"{prompt} ({joined})（回车=默认 {default}）: ").strip().lower()
        if not raw:
            return default
        if raw in options:
            return raw
        print(f"  输入不合法，可选：{joined}")


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
    keyboard: _Keyboard | None = None,
) -> int:
    """跑一次完整演示：生成、逐帧求解、输出总结。"""
    if not 1 <= rows <= MAX_SIZE or not 1 <= cols <= MAX_SIZE:
        print(f"尺寸需在 1–{MAX_SIZE} 之间，收到 {rows}×{cols}", file=sys.stderr)
        return 2
    if delay < 0:
        print(f"--delay 不能为负数，收到 {delay}", file=sys.stderr)
        return 2

    use_color = color_enabled(color) and not ascii_arrows
    keyboard = keyboard if keyboard is not None else _Keyboard()
    maze = GENERATORS[generator].generate(rows, cols, random.Random(seed))
    start, goal = (0, 0), (rows - 1, cols - 1)

    print(f"MazeLab 演示：{rows}×{cols}｜生成 {generator}｜求解 {solver}｜seed={seed}")
    print(legend(use_color, ascii_arrows))
    hint = "按 Ctrl+C 可随时中断"
    if keyboard.enabled:
        hint += "，空格暂停/继续"
    print(f"{hint}；用 --delay 0.2 可加快（当前每步 {delay:g}s）")
    print()

    screen = _Screen(min_lines=2 * rows + 3)
    if not screen.live:
        print("（终端放不下整帧或未启用 ANSI，改为逐帧追加输出）")
    final: StepSnapshot | None = None
    step_no = 0
    try:
        for step_no, snapshot in enumerate(SOLVERS[solver].solve_steps(maze, start, goal), 1):
            picture = render(
                maze, snapshot, start, goal, color=use_color, ascii_arrows=ascii_arrows
            )
            status = f"步骤 {step_no:3d}  {snapshot.action}"
            screen.paint(f"{picture}\n{status}\n")
            final = snapshot

            if keyboard.enabled:
                if keyboard.read(delay) == " ":
                    screen.paint(f"{picture}\n{status}\n⏸  已暂停，按空格继续\n")
                    while True:
                        key = keyboard.read(None)
                        if key is None or key == " ":
                            break
            elif delay > 0:
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
