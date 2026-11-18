"""交互演示测试：排版、符号、连线、分支优先级、空格暂停。

动画本身不好断言，所以只验证可观察的结果：
去色后排版等宽、符号与颜色键对应、当前分支优先于已访问、按键能暂停。
"""

from __future__ import annotations

import re

import pytest

from mazelab.cli import main
from mazelab.core.snapshot import StepSnapshot
from mazelab.generators import generate
from mazelab.solvers import SOLVERS
from mazelab.tui import (
    _Keyboard,
    ask_choice,
    ask_int,
    cell_mark,
    head_char,
    render,
    route_dirs,
    route_glyph,
    route_links,
    run_demo,
)

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI.sub("", text)


class _FakeKeyboard:
    """按脚本返回按键；脚本用完后返回 None（视为未按键）。"""

    enabled = True

    def __init__(self, keys: list[str]) -> None:
        self.keys = list(keys)

    def read(self, timeout: float | None = None) -> str | None:
        return self.keys.pop(0) if self.keys else None


# ---------- 排版 ----------


def test_render_matches_static_layout() -> None:
    maze = generate("dfs", 5, 7, seed=1)
    start, goal = (0, 0), (4, 6)
    snapshot = next(SOLVERS["bfs"].solve_steps(maze, start, goal))

    text = render(maze, snapshot, start, goal, color=False)
    static = maze.to_ascii()
    assert len(text.splitlines()) == len(static.splitlines())
    assert all(len(line) == 4 * 7 + 1 for line in text.splitlines())
    assert text.splitlines()[0] == static.splitlines()[0]


def test_color_adds_ansi_without_breaking_width() -> None:
    maze = generate("prim", 4, 6, seed=2)
    snapshot = next(SOLVERS["astar"].solve_steps(maze, (0, 0), (3, 5)))

    plain = render(maze, snapshot, (0, 0), (3, 5), color=False)
    colored = render(maze, snapshot, (0, 0), (3, 5), color=True)

    assert "\x1b[" in colored
    assert strip_ansi(colored) == plain  # 上色不改变任何字符
    assert all(len(line) == 4 * 6 + 1 for line in strip_ansi(colored).splitlines())


def test_render_marks_start_and_goal() -> None:
    maze = generate("prim", 3, 3, seed=2)
    start, goal = (0, 0), (2, 2)
    snapshot = next(SOLVERS["bfs"].solve_steps(maze, start, goal))
    text = render(maze, snapshot, start, goal, color=False)
    assert " S " in text
    assert " G " in text


# ---------- 符号 ----------


def test_head_char_follows_direction() -> None:
    down = StepSnapshot(action="", current=(1, 1), extra={"route": [(0, 1), (1, 1)]})
    right = StepSnapshot(action="", current=(1, 1), extra={"route": [(1, 0), (1, 1)]})
    assert head_char(down) == "↓"
    assert head_char(right) == "→"
    assert head_char(down, ascii_arrows=True) == "v"
    assert head_char(right, ascii_arrows=True) == ">"


def test_head_char_without_parent() -> None:
    solo = StepSnapshot(action="", current=(0, 0), extra={"route": [(0, 0)]})
    assert head_char(solo) == "o"


def test_dead_end_and_frontier_symbols() -> None:
    snapshot = StepSnapshot(
        action="",
        current=(0, 0),
        visited={(1, 1)},
        frontier={(2, 2)},
        extra={"route": [(0, 0)]},
    )
    assert cell_mark(snapshot, (1, 1), (0, 0), (3, 3), "→") == ("x", "visited")
    assert cell_mark(snapshot, (2, 2), (0, 0), (3, 3), "→") == ("·", "frontier")


def test_final_path_uses_check_mark() -> None:
    snapshot = StepSnapshot(action="", path=[(1, 1)], extra={"route": []})
    assert cell_mark(snapshot, (1, 1), (0, 0), (3, 3), "→") == ("√", "path")
    assert cell_mark(snapshot, (1, 1), (0, 0), (3, 3), "→", ascii_mode=True) == ("*", "path")


def test_route_beats_visited_but_not_current() -> None:
    """既在当前分支、又走过一次的格子，应按当前分支显示。"""
    snapshot = StepSnapshot(
        action="",
        current=(0, 2),
        visited={(0, 1), (1, 1), (0, 2)},
        extra={"route": [(0, 0), (0, 1), (0, 2)]},
    )
    start, goal = (0, 0), (3, 3)

    # (0,1) 左右都是分支 → 横线；当前格优先显示箭头；纯已访问格显示 x
    assert cell_mark(snapshot, (0, 1), start, goal, "→") == ("─", "route")
    assert cell_mark(snapshot, (0, 2), start, goal, "→") == ("→", "head")
    assert cell_mark(snapshot, (1, 1), start, goal, "→") == ("x", "visited")


def test_path_beats_route() -> None:
    snapshot = StepSnapshot(
        action="",
        current=(2, 2),
        path=[(0, 0), (0, 1)],
        extra={"route": [(0, 0), (0, 1)]},
    )
    assert cell_mark(snapshot, (0, 1), (0, 0), (2, 2), "→") == ("√", "path")


def test_route_glyph_shapes() -> None:
    assert route_glyph({"E", "W"}) == "─"
    assert route_glyph({"N", "S"}) == "│"
    assert route_glyph({"S", "E"}) == "┌"   # 转角
    assert route_glyph({"N", "W"}) == "┘"
    assert route_glyph({"N"}) == "│"        # 路径端点
    assert route_glyph(set()) == "·"


def test_route_glyph_ascii() -> None:
    assert route_glyph({"S", "E"}, ascii_mode=True) == "+"
    assert route_glyph({"E", "W"}, ascii_mode=True) == "-"
    assert route_glyph({"N", "S"}, ascii_mode=True) == "|"
    assert route_glyph(set(), ascii_mode=True) == "*"


def test_route_dirs_follows_path_order_not_adjacency() -> None:
    """U 形路径：两条走廊并排相邻，只有顺序上连续的两格才算连接。

    按邻接判断会把 (0,1)-(1,1) 连起来，凭空多出一条支路并冒出 ├ ┤ 岔口，
    这正是之前画面里出现 "-|" 的原因。
    """
    route = [(0, 0), (0, 1), (0, 2), (1, 2), (1, 1), (1, 0)]
    shapes = route_dirs(route)

    assert shapes[(0, 1)] == {"W", "E"}  # 上下相邻但不连续，不产生竖线
    assert shapes[(1, 1)] == {"W", "E"}
    assert shapes[(0, 2)] == {"W", "S"}  # 这里是真正的转角

    links = route_links(route)
    assert frozenset({(0, 1), (1, 1)}) not in links
    assert frozenset({(0, 2), (1, 2)}) in links


def test_render_never_draws_junction_glyphs() -> None:
    """一帧里不应出现 ├ ┤ ┬ ┴ ┼ 这类三向/四向岔口。"""
    maze = generate("dfs", 9, 9, seed=3)
    steps = list(SOLVERS["bfs"].solve_steps(maze, (0, 0), (8, 8)))
    for snapshot in steps[::5]:
        text = render(maze, snapshot, (0, 0), (8, 8), color=False)
        for glyph in "├┤┬┴┼":
            assert glyph not in text


def test_render_ascii_mode_has_no_unicode_glyphs() -> None:
    maze = generate("dfs", 6, 6, seed=4)
    start, goal = (0, 0), (5, 5)
    steps = list(SOLVERS["bfs"].solve_steps(maze, start, goal))
    text = render(maze, steps[len(steps) // 2], start, goal, color=False, ascii_arrows=True)
    for ch in "│─┌┐└┘√·↑↓←→":
        assert ch not in text


def test_solver_snapshots_expose_route() -> None:
    """当前分支来自求解器的 extra["route"]，必须以起点开头、当前格结尾。"""
    maze = generate("dfs", 5, 5, seed=1)
    for name in ("bfs", "astar"):
        for snapshot in SOLVERS[name].solve_steps(maze, (0, 0), (4, 4)):
            route = snapshot.extra.get("route")
            assert route, f"{name} 的快照缺少 route"
            assert route[0] == (0, 0)
            assert snapshot.current is None or route[-1] == snapshot.current


# ---------- 交互与暂停 ----------


def test_run_demo_completes(capsys) -> None:
    assert run_demo(4, 5, "dfs", "bfs", seed=1, delay=0) == 0
    out = capsys.readouterr().out
    assert "MazeLab 演示" in out
    assert "当前分支" in out
    assert "最短路径" in out


def test_space_pauses_and_resumes(capsys) -> None:
    keyboard = _FakeKeyboard([" ", " "])
    assert run_demo(3, 3, "dfs", "bfs", seed=1, delay=0, keyboard=keyboard) == 0
    out = capsys.readouterr().out
    assert "已暂停" in out
    assert "最短路径" in out


def test_keyboard_disabled_when_stdin_is_not_tty() -> None:
    assert _Keyboard().enabled is False
    assert _Keyboard().read(0) is None


def test_run_demo_supports_single_row_maze() -> None:
    assert run_demo(1, 5, "kruskal", "astar", seed=1, delay=0) == 0


def test_run_demo_rejects_out_of_range_size(capsys) -> None:
    assert run_demo(0, 5, "dfs", "bfs", seed=1, delay=0) == 2
    assert "1–40" in capsys.readouterr().err


def test_run_demo_rejects_negative_delay(capsys) -> None:
    assert run_demo(3, 3, "dfs", "bfs", seed=1, delay=-1) == 2
    assert "--delay" in capsys.readouterr().err


def test_ask_int_retries_on_bad_input(monkeypatch) -> None:
    answers = iter(["abc", "999", "12"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert ask_int("行数", 10, 1, 40) == 12


def test_ask_int_empty_uses_default(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt="": "   ")
    assert ask_int("行数", 10, 1, 40) == 10


def test_ask_choice_retries_on_bad_input(monkeypatch) -> None:
    answers = iter(["xxx", "prim"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert ask_choice("生成算法", ["dfs", "prim", "kruskal"], "dfs") == "prim"


def test_ask_choice_empty_uses_default(monkeypatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert ask_choice("求解算法", ["bfs", "astar"], "bfs") == "bfs"


def test_cli_play_runs_without_prompts(capsys) -> None:
    assert main(
        ["play", "--rows", "3", "--cols", "4", "--algorithm", "dfs",
         "--solver", "astar", "--delay", "0", "--seed", "5"]
    ) == 0
    out = capsys.readouterr().out
    assert "MazeLab 演示" in out
    assert "最短路径" in out


def test_cli_play_accepts_no_color_and_ascii(capsys) -> None:
    assert main(
        ["play", "--rows", "3", "--cols", "3", "--algorithm", "prim",
         "--solver", "bfs", "--delay", "0", "--seed", "2", "--no-color", "--ascii"]
    ) == 0
    capsys.readouterr()


def test_cli_play_rejects_oversized_maze(capsys) -> None:
    assert main(
        ["play", "--rows", "100", "--cols", "3", "--algorithm", "dfs",
         "--solver", "bfs", "--delay", "0", "--seed", "1"]
    ) == 2
    assert "1–40" in capsys.readouterr().err


def test_interactive_handles_closed_stdin(monkeypatch, capsys) -> None:
    """没有标准输入时不能崩出 traceback，要提示改用参数。"""

    def boom(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", boom)
    assert main(["play"]) == 1
    err = capsys.readouterr().err
    assert "标准输入" in err
    assert "--rows" in err


def test_cli_help_lists_play(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    assert "play" in capsys.readouterr().out
