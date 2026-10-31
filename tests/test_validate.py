"""校验器测试：四类问题都要能被抓到，正常迷宫要能通过。"""

from __future__ import annotations

from mazelab.core.maze import E, N, Maze
from mazelab.core.validate import validate
from mazelab.generators import GENERATORS, generate


def failing_names(maze: Maze) -> set[str]:
    return {check.name for check in validate(maze).failures}


def test_generated_maze_passes_every_check() -> None:
    for algorithm in GENERATORS:
        report = validate(generate(algorithm, 6, 6, seed=1))
        assert report.ok, report.render()
        assert "PASS" in report.render()


def test_detects_open_border() -> None:
    maze = generate("dfs", 3, 3, seed=1)  # 先拿一个合法迷宫，再人为在最外圈开个洞
    maze.cells[0][0].walls &= ~N
    report = validate(maze)
    assert not report.ok
    assert failing_names(maze) == {"边界封闭"}


def test_detects_asymmetric_walls() -> None:
    maze = Maze(2, 2)
    maze.cells[0][0].walls &= ~E  # 只清一侧，另一侧仍认为有墙
    assert "墙位对称" in failing_names(maze)


def test_detects_disconnected_maze() -> None:
    maze = Maze(2, 2)
    maze.carve((0, 0), (0, 1))
    assert "全连通" in failing_names(maze)


def test_detects_cycle() -> None:
    maze = Maze(2, 2)
    for a, b in [((0, 0), (0, 1)), ((0, 1), (1, 1)), ((1, 1), (1, 0)), ((1, 0), (0, 0))]:
        maze.carve(a, b)
    assert "无环" in failing_names(maze)
    assert "全连通" not in failing_names(maze)


def test_report_renders_every_check() -> None:
    text = validate(generate("dfs", 3, 3, seed=1)).render()
    for name in ("边界封闭", "墙位对称", "全连通", "无环"):
        assert name in text


def test_wall_bits_are_untouched_by_validation() -> None:
    maze = generate("prim", 5, 5, seed=3)
    before = maze.to_dict()
    validate(maze)
    assert maze.to_dict() == before
