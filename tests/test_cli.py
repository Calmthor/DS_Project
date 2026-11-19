"""命令行测试：generate → solve → validate 的完整链路，以及错误输入的退出码。"""

from __future__ import annotations

import json

import pytest

from mazelab.cli import main
from mazelab.core.maze import W, Maze


def test_generate_writes_json_that_validate_accepts(tmp_path, capsys) -> None:
    maze_file = tmp_path / "maze.json"
    assert main(["generate", "--rows", "5", "--cols", "6", "--seed", "3",
                 "--format", "json", "--output", str(maze_file)]) == 0

    data = json.loads(maze_file.read_text(encoding="utf-8"))
    assert data["algorithm"] == "dfs" and data["seed"] == 3
    assert len(data["walls"]) == 5 and len(data["walls"][0]) == 6

    capsys.readouterr()
    assert main(["validate", "--input", str(maze_file)]) == 0
    out = capsys.readouterr().out
    assert "[PASS]" in out and "FAIL" not in out


def test_solve_generated_maze(tmp_path, capsys) -> None:
    maze_file = tmp_path / "maze.json"
    main(["generate", "--rows", "7", "--cols", "7", "--seed", "9",
          "--format", "json", "--output", str(maze_file)])
    capsys.readouterr()

    result = tmp_path / "solution.json"
    assert main(["solve", "--input", str(maze_file), "--algorithm", "astar",
                 "--format", "json", "--output", str(result)]) == 0

    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["start"] == [0, 0] and payload["goal"] == [6, 6]
    assert payload["path"][0] == [0, 0] and payload["path"][-1] == [6, 6]
    assert payload["distance"] == len(payload["path"]) - 1


def test_solve_ascii_overlay(tmp_path, capsys) -> None:
    maze = Maze(1, 3)
    maze.carve((0, 0), (0, 1))
    maze.carve((0, 1), (0, 2))
    maze_file = tmp_path / "line.json"
    maze.save(maze_file)

    assert main(["solve", "--input", str(maze_file)]) == 0
    out = capsys.readouterr().out
    assert "S" in out and "G" in out and "最短路径 2 步" in out


def test_solve_rejects_inconsistent_maze(tmp_path, capsys) -> None:
    """墙位不对称的坏数据必须被拒，而不是解出一条穿墙的"正常"路径。"""
    maze = Maze(2, 2)
    maze.carve((0, 0), (0, 1))
    maze.cells[0][1].walls |= W  # 制造不对称：左边说通，右边说墙
    target = tmp_path / "bad.json"
    maze.save(target)

    assert main(["solve", "--input", str(target)]) == 1
    err = capsys.readouterr().err
    assert "结构不自洽" in err
    assert "墙位对称" in err


def test_algorithm_name_is_case_insensitive(tmp_path, capsys) -> None:
    """命令行和交互模式对大小写的态度要一致，不能一个接受一个报错。"""
    maze_file = tmp_path / "m.json"
    main(["generate", "--rows", "4", "--cols", "4", "--seed", "1",
          "--format", "json", "--output", str(maze_file)])
    capsys.readouterr()

    assert main(["solve", "--input", str(maze_file), "--algorithm", "BFS"]) == 0
    assert "最短路径" in capsys.readouterr().out


def test_module_entrypoint_runs() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "mazelab", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "mazelab" in result.stdout


def test_unsolvable_maze_exits_with_code_2(tmp_path, capsys) -> None:
    maze = Maze(2, 2)  # 一格都不通
    maze_file = tmp_path / "closed.json"
    maze.save(maze_file)
    assert main(["solve", "--input", str(maze_file)]) == 2
    assert "无解" in capsys.readouterr().err


def test_broken_json_file_reports_error(tmp_path) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("{oops", encoding="utf-8")
    with pytest.raises(SystemExit) as excinfo:
        main(["validate", "--input", str(broken)])
    assert "读取失败" in str(excinfo.value.code)


def test_validate_reports_failure_for_bad_maze(tmp_path, capsys) -> None:
    maze = Maze(2, 2)
    maze.carve((0, 0), (0, 1))
    maze_file = tmp_path / "partial.json"
    maze.save(maze_file)
    assert main(["validate", "--input", str(maze_file)]) == 1
    assert "[FAIL]" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [
    ["generate", "--algorithm", "nope"],
    ["solve", "--input", "x.json", "--start", "1;2"],
    ["solve", "--input", "x.json", "--start", "-1,0"],
])
def test_bad_arguments_exit_with_usage(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2


def test_missing_required_input_argument() -> None:
    with pytest.raises(SystemExit):
        main(["solve"])


def test_version_flag(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert "mazelab" in capsys.readouterr().out
