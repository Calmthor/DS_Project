"""核心数据结构测试：墙位、打通、连通性、渲染与序列化。"""

from __future__ import annotations

import pytest

from mazelab.core.maze import E, N, S, W, Maze


def test_new_maze_starts_fully_walled() -> None:
    maze = Maze(3, 4)
    assert maze.size == 12
    assert all(cell.walls == (N | E | S | W) for row in maze.cells for cell in row)


def test_carve_clears_both_sides() -> None:
    maze = Maze(2, 3)
    maze.carve((0, 0), (0, 1))
    assert (maze.cells[0][0].walls & E) == 0
    assert (maze.cells[0][1].walls & W) == 0
    assert maze.is_open((0, 1), (0, 0))
    # 其余三面墙不应被牵连
    assert maze.cells[0][0].walls & N
    assert maze.cells[0][0].walls & S


def test_carve_is_idempotent() -> None:
    maze = Maze(2, 2)
    maze.carve((0, 0), (1, 0))
    before = maze.to_dict()
    maze.carve((0, 0), (1, 0))
    assert maze.to_dict() == before


def test_carve_rejects_non_adjacent_cells() -> None:
    maze = Maze(3, 3)
    with pytest.raises(ValueError, match="不相邻"):
        maze.carve((0, 0), (1, 1))


def test_carve_rejects_out_of_bounds() -> None:
    maze = Maze(2, 2)
    with pytest.raises(ValueError, match="越界"):
        maze.carve((0, 0), (2, 0))


def test_neighbors_only_through_open_walls() -> None:
    maze = Maze(2, 2)
    assert maze.neighbors((0, 0)) == []
    maze.carve((0, 0), (0, 1))
    assert maze.neighbors((0, 0)) == [(0, 1)]
    assert maze.neighbors((0, 1)) == [(0, 0)]


def test_adjacent_ignores_walls() -> None:
    maze = Maze(3, 3)
    assert set(maze.adjacent((1, 1))) == {(0, 1), (1, 2), (2, 1), (1, 0)}
    assert set(maze.adjacent((0, 0))) == {(0, 1), (1, 0)}


def test_connectivity_follows_carved_passages() -> None:
    maze = Maze(1, 3)
    maze.carve((0, 0), (0, 1))
    assert maze.is_connected((0, 0), (0, 1))
    assert not maze.is_connected((0, 0), (0, 2))
    assert maze.is_connected((0, 2), (0, 2))
    assert maze.reachable_from((0, 0)) == {(0, 0), (0, 1)}


def test_passages_lists_each_edge_once() -> None:
    maze = Maze(2, 2)
    maze.carve((0, 0), (0, 1))
    maze.carve((0, 0), (1, 0))
    assert len(maze.passages()) == 2


def test_is_perfect_matrix() -> None:
    perfect = Maze(1, 3)
    perfect.carve((0, 0), (0, 1))
    perfect.carve((0, 1), (0, 2))
    assert perfect.is_perfect()

    looped = Maze(2, 2)
    for a, b in [((0, 0), (0, 1)), ((0, 0), (1, 0)), ((0, 1), (1, 1)), ((1, 0), (1, 1))]:
        looped.carve(a, b)
    assert not looped.is_perfect()


def test_single_cell_maze() -> None:
    maze = Maze(1, 1)
    assert maze.size == 1
    assert maze.is_perfect()
    assert maze.neighbors((0, 0)) == []
    assert "S" in maze.to_ascii(marks={(0, 0): "S"})


def test_ascii_has_expected_shape() -> None:
    maze = Maze(2, 3)
    lines = maze.to_ascii().splitlines()
    assert len(lines) == 2 * 2 + 1  # 每行一条上边框 + 一条内容行，末尾再补一条
    assert all(len(line) == 4 * 3 + 1 for line in lines)
    assert lines[0].startswith("+")


def test_ascii_marks_and_path() -> None:
    maze = Maze(1, 2)
    maze.carve((0, 0), (0, 1))
    text = maze.to_ascii(path=[(0, 0), (0, 1)], marks={(0, 0): "S"})
    assert " S " in text


def test_json_roundtrip() -> None:
    maze = Maze(3, 3)
    maze.carve((0, 0), (0, 1))
    maze.carve((1, 1), (2, 1))
    restored = Maze.from_json(maze.to_json())
    assert restored.to_dict() == maze.to_dict()
    assert restored.to_ascii() == maze.to_ascii()


def test_from_dict_ignores_unknown_keys() -> None:
    maze = Maze.from_dict({"rows": 1, "cols": 2, "walls": [[3, 12]], "algorithm": "dfs"})
    assert maze.rows == 1 and maze.cols == 2


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"rows": 1, "cols": 1},
        {"rows": 0, "cols": 1, "walls": []},
        {"rows": 2, "cols": 2, "walls": [[15, 15]]},
        {"rows": 1, "cols": 2, "walls": [[15, 16]]},
        {"rows": 1, "cols": 2, "walls": [[15, 15.0]]},
        {"rows": "1", "cols": 2, "walls": [[15, 15]]},
    ],
)
def test_from_dict_rejects_bad_data(payload: dict) -> None:
    with pytest.raises(ValueError):
        Maze.from_dict(payload)


def test_from_json_rejects_broken_json() -> None:
    with pytest.raises(ValueError, match="JSON"):
        Maze.from_json("{not json")


def test_load_missing_file(tmp_path) -> None:
    with pytest.raises(ValueError, match="无法读取"):
        Maze.load(tmp_path / "nope.json")


def test_save_and_load(tmp_path) -> None:
    maze = Maze(2, 2)
    maze.carve((0, 0), (1, 0))
    target = tmp_path / "maze.json"
    maze.save(target)
    assert Maze.load(target).to_dict() == maze.to_dict()
