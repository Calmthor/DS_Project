"""交互演示测试：帧渲染、输入解析、完整跑完。

动画本身不好断言，所以这里只验证可观察的结果：
帧的排版与静态输出一致、起终点标记到位、参数非法时给提示、整段跑完不抛异常。
"""

from __future__ import annotations

import pytest

from mazelab.cli import main
from mazelab.generators import generate
from mazelab.solvers import SOLVERS
from mazelab.tui import ask_choice, ask_int, frame, run_demo


def test_frame_keeps_the_same_layout_as_static_output() -> None:
    maze = generate("dfs", 5, 7, seed=1)
    start, goal = (0, 0), (4, 6)
    snapshot = next(SOLVERS["bfs"].solve_steps(maze, start, goal))

    text = frame(maze, snapshot, start, goal)
    static = maze.to_ascii()
    assert text.splitlines()[0] == static.splitlines()[0]  # 上边框不受标记影响
    assert len(text.splitlines()) == len(static.splitlines())
    assert all(len(line) == 4 * 7 + 1 for line in text.splitlines())


def test_frame_marks_start_and_goal() -> None:
    maze = generate("prim", 3, 3, seed=2)
    start, goal = (0, 0), (2, 2)
    steps = list(SOLVERS["bfs"].solve_steps(maze, start, goal))

    first = frame(maze, steps[0], start, goal)
    assert " S " in first and " G " in first

    # 起点在第一帧就是当前格，会被 S 覆盖；找一帧当前格不在起终点上，才看得到 @
    mid = next(s for s in steps if s.current not in (None, start, goal))
    assert " @ " in frame(maze, mid, start, goal)


def test_frame_path_overrides_visited() -> None:
    maze = generate("dfs", 6, 6, seed=4)
    final = list(SOLVERS["astar"].solve_steps(maze, (0, 0), (5, 5)))[-1]
    text = frame(maze, final, (0, 0), (5, 5))
    assert " * " in text


def test_run_demo_completes(capsys) -> None:
    assert run_demo(4, 5, "dfs", "bfs", seed=1, delay=0) == 0
    out = capsys.readouterr().out
    assert "MazeLab 演示" in out
    assert "步骤" in out
    assert "最短路径" in out


def test_run_demo_supports_single_row_maze() -> None:
    assert run_demo(1, 5, "kruskal", "astar", seed=1, delay=0) == 0


def test_run_demo_rejects_out_of_range_size(capsys) -> None:
    assert run_demo(0, 5, "dfs", "bfs", seed=1, delay=0) == 2
    assert "1–40" in capsys.readouterr().err


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
