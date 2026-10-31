"""生成算法测试：完美性、可复现性、逐步快照的一致性。"""

from __future__ import annotations

import random

import pytest

from mazelab.core.maze import Maze
from mazelab.core.validate import validate
from mazelab.generators import GENERATORS, generate

ALGORITHMS = list(GENERATORS)

# 覆盖退化尺寸（1×1、单行、单列）与常见尺寸
SIZES = [(1, 1), (1, 6), (6, 1), (2, 2), (3, 7), (8, 8)]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
@pytest.mark.parametrize("rows,cols", SIZES)
def test_generated_maze_is_perfect(algorithm: str, rows: int, cols: int) -> None:
    maze = generate(algorithm, rows, cols, seed=2026)
    report = validate(maze)
    assert report.ok, f"{algorithm} {rows}×{cols} 未通过自检：\n{report.render()}"
    assert maze.is_perfect()
    assert len(maze.reachable_from((0, 0))) == rows * cols


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_same_seed_reproduces_same_maze(algorithm: str) -> None:
    first = generate(algorithm, 9, 7, seed=42)
    second = generate(algorithm, 9, 7, seed=42)
    assert first.to_dict() == second.to_dict()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_different_seeds_produce_different_mazes(algorithm: str) -> None:
    shapes = {str(generate(algorithm, 8, 8, seed=seed).to_dict()["walls"]) for seed in range(5)}
    assert len(shapes) > 1, f"{algorithm} 在 5 个不同种子下生成了完全相同的迷宫"


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_steps_replay_to_the_same_maze(algorithm: str) -> None:
    """逐步快照里记录的每一条 carve，重放后必须还原出 generate() 的结果。"""
    module = GENERATORS[algorithm]
    final = module.generate(6, 6, random.Random(7))

    replayed = Maze(6, 6)
    steps = list(module.generate_steps(6, 6, random.Random(7), replayed))
    assert steps[-1].done is True
    assert all(step.done is False for step in steps[:-1])
    assert replayed.to_dict() == final.to_dict()


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_steps_record_adjacent_carves(algorithm: str) -> None:
    module = GENERATORS[algorithm]
    for step in module.generate_steps(5, 5, random.Random(11)):
        edge = step.extra.get("carve")
        if edge is not None:
            a, b = edge
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_step_count_is_positive(algorithm: str) -> None:
    module = GENERATORS[algorithm]
    assert len(list(module.generate_steps(4, 4, random.Random(1)))) > 0


def test_unknown_algorithm_raises() -> None:
    with pytest.raises(ValueError, match="未知的生成算法"):
        generate("backtracking", 3, 3, seed=1)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_injected_maze_size_must_match(algorithm: str) -> None:
    module = GENERATORS[algorithm]
    with pytest.raises(ValueError, match="尺寸"):
        list(module.generate_steps(3, 3, random.Random(0), Maze(2, 5)))


def test_dfs_has_fewer_dead_ends_than_prim() -> None:
    """定性对比：DFS 倾向长走廊、死路少；Prim 分支短而多。

    单个种子偶然性太大，这里对 5 个种子取总数再比较，并用 12×12 让差异稳定。
    """

    def dead_ends(maze: Maze) -> int:
        # 只有一条通道的格子就是死路：四面墙里恰好三面存在
        return sum(1 for row in maze.cells for cell in row if bin(cell.walls).count("1") == 3)

    dfs_total = sum(dead_ends(generate("dfs", 12, 12, seed=s)) for s in range(5))
    prim_total = sum(dead_ends(generate("prim", 12, 12, seed=s)) for s in range(5))
    assert dfs_total < prim_total
