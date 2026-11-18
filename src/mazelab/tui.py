"""交互式终端演示：选尺寸 → 生成迷宫 → 选算法 → 逐帧展示求解过程。

设计要点：
- 渲染复用 ``Maze.to_ascii()``，只通过 ``marks`` 叠加状态标记，
  保证动画帧和静态输出的排版完全一致；
- 重绘优先用 ANSI 转义（光标上移 + 清屏），终端不支持时退化为顺序输出，
  所以重定向到文件或管道里不会混进乱码；
- 动画与业务逻辑分离：``run_demo()`` 不读键盘，方便测试用 ``delay=0`` 直接跑完。
"""

from __future__ import annotations

import os
import random
import shutil
import sys
import time

from mazelab.core.maze import Maze
from mazelab.core.snapshot import Point, StepSnapshot
from mazelab.generators import GENERATORS, NAMES as GENERATOR_NAMES
from mazelab.solvers import NAMES as SOLVER_NAMES, SOLVERS

DEFAULT_DELAY = 1.0
MAX_SIZE = 40

# 图例：一个字符占一格，正好塞进 to_ascii 的 " X " 三字符单元
LEGEND = "S 起点   G 终点   @ 当前   * 最终路径   , 候选(frontier)   . 已访问"

_ansi_ready: bool | None = None


def _probe_ansi() -> bool:
    """判断当前终端能否用 ANSI 转义在原地重绘。"""
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


def frame(maze: Maze, snapshot: StepSnapshot, start: Point, goal: Point) -> str:
    """把一帧快照渲染成字符画。

    叠加顺序决定了谁盖住谁：已访问 < 候选 < 路径 < 当前格 < 起终点。
    """
    marks: dict[Point, str] = {}
    for cell in snapshot.visited:
        marks[cell] = "."
    for cell in snapshot.frontier:
        marks[cell] = ","
    for cell in snapshot.path:
        marks[cell] = "*"
    if snapshot.current is not None:
        marks[snapshot.current] = "@"
    marks[start] = "S"
    marks[goal] = "G"
    return maze.to_ascii(marks=marks)


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
) -> int:
    """跑一次完整演示：生成、逐帧求解、输出总结。"""
    if not 1 <= rows <= MAX_SIZE or not 1 <= cols <= MAX_SIZE:
        print(f"尺寸需在 1–{MAX_SIZE} 之间，收到 {rows}×{cols}", file=sys.stderr)
        return 2

    maze = GENERATORS[generator].generate(rows, cols, random.Random(seed))
    start, goal = (0, 0), (rows - 1, cols - 1)

    print(f"MazeLab 演示：{rows}×{cols}｜生成 {generator}｜求解 {solver}｜seed={seed}")
    print(LEGEND)
    print(f"按 Ctrl+C 可随时中断；用 --delay 0.2 可加快（当前每步 {delay:g}s）")
    print()

    screen = _Screen(min_lines=2 * rows + 3)
    if not screen.live:
        print("（终端放不下整帧或未启用 ANSI，改为逐帧追加输出）")
    final: StepSnapshot | None = None
    step_no = 0
    try:
        for step_no, snapshot in enumerate(SOLVERS[solver].solve_steps(maze, start, goal), 1):
            screen.paint(f"{frame(maze, snapshot, start, goal)}\n步骤 {step_no:3d}  {snapshot.action}\n")
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
    return run_demo(rows, cols, generator, solver, seed, delay)
