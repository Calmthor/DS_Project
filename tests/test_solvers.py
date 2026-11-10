"""求解算法测试：路径合法性、最短路性质、BFS 与 A* 的一致性、无解情形。"""

from __future__ import annotations

import pytest

from mazelab.core.maze import Maze
from mazelab.core.path import check_path
from mazelab.generators import GENERATORS, generate
from mazelab.solvers import SOLVERS, solve

ALGORITHMS = list(SOLVERS)
SOLVER_MODULES = [SOLVERS[name] for name in ALGORITHMS]


def fully_open(rows: int, cols: int) -> Maze:
    """全部内墙都打通的网格，用于验证"最短路"结论。"""
    maze = Maze(rows, cols)
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                maze.carve((r, c), (r, c + 1))
            if r + 1 < rows:
                maze.carve((r, c), (r + 1, c))
    return maze


@pytest.fixture
def open_3x3() -> Maze:
    return fully_open(3, 3)


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_shortest_path_length_on_open_grid(algorithm: str, open_3x3: Maze) -> None:
    path = solve(algorithm, open_3x3, (0, 0), (2, 2))
    assert path is not None
    assert len(path) - 1 == 4  # 曼哈顿距离，必须是最短
    assert check_path(open_3x3, (0, 0), (2, 2), path) == []


@pytest.mark.parametrize("generator", list(GENERATORS))
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_path_valid_and_optimal_on_generated_mazes(generator: str, algorithm: str) -> None:
    maze = generate(generator, 7, 9, seed=5)
    start, goal = (0, 0), (6, 8)
    path = solve(algorithm, maze, start, goal)
    assert path is not None and path[0] == start and path[-1] == goal
    assert check_path(maze, start, goal, path) == []


@pytest.mark.parametrize("generator", list(GENERATORS))
def test_bfs_and_astar_return_same_distance(generator: str) -> None:
    maze = generate(generator, 10, 10, seed=8)
    start, goal = (0, 0), (9, 9)
    bfs_path = solve("bfs", maze, start, goal)
    astar_path = solve("astar", maze, start, goal)
    assert bfs_path is not None and astar_path is not None
    assert len(bfs_path) == len(astar_path)


def test_single_corridor() -> None:
    maze = Maze(1, 5)
    for c in range(4):
        maze.carve((0, c), (0, c + 1))
    for algorithm in ALGORITHMS:
        assert solve(algorithm, maze, (0, 0), (0, 4)) == [(0, 0), (0, 1), (0, 2), (0, 3), (0, 4)]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_unreachable_goal_returns_none(algorithm: str) -> None:
    maze = Maze(3, 3)
    maze.carve((0, 0), (0, 1))
    assert solve(algorithm, maze, (0, 0), (2, 2)) is None


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_start_equals_goal(algorithm: str) -> None:
    maze = Maze(4, 4)
    assert solve(algorithm, maze, (1, 1), (1, 1)) == [(1, 1)]


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_out_of_bounds_start_raises(algorithm: str) -> None:
    maze = Maze(3, 3)
    with pytest.raises(ValueError, match="越界"):
        solve(algorithm, maze, (0, 0), (3, 0))


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_steps_end_with_done_snapshot(algorithm: str) -> None:
    module = SOLVERS[algorithm]
    maze = generate("dfs", 6, 6, seed=2)
    steps = list(module.solve_steps(maze, (0, 0), (5, 5)))
    assert steps[-1].done is True
    assert steps[-1].path[0] == (0, 0) and steps[-1].path[-1] == (5, 5)
    assert all(step.done is False for step in steps[:-1])


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_unreachable_steps_report_empty_path(algorithm: str) -> None:
    module = SOLVERS[algorithm]
    maze = Maze(2, 2)
    final = list(module.solve_steps(maze, (0, 0), (1, 1)))[-1]
    assert final.done and final.path == []


def test_astar_tie_break_beats_bfs_on_open_grid(open_3x3: Maze) -> None:
    """f 值并列时优先弹出更深的节点，A* 不再扫完整个等高区。

    改平局策略前这里扩展 9 格（= 全部格子，比 BFS 的 7 格还多）；
    改后只扩展 5 格。这条断言同时锁住了"不能退化成扫全区"。
    """

    def expanded(module) -> int:
        return list(module.solve_steps(open_3x3, (0, 0), (2, 2)))[-1].extra["expanded"]

    astar, bfs = expanded(SOLVERS["astar"]), expanded(SOLVERS["bfs"])
    assert astar == 5
    assert astar < bfs < 9


def test_astar_never_expands_the_same_cell_twice() -> None:
    """closed 集合 + 过期条目跳过，保证每格最多扩展一次。"""
    maze = generate("dfs", 8, 8, seed=4)
    expanded = [
        step.current
        for step in SOLVERS["astar"].solve_steps(maze, (0, 0), (7, 7))
        if step.extra.get("g") is not None
    ]
    assert len(expanded) == len(set(expanded))


def test_manhattan_heuristic() -> None:
    from mazelab.solvers.astar import manhattan

    assert manhattan((0, 0), (2, 3)) == 5
    assert manhattan((4, 4), (4, 4)) == 0


def test_unknown_solver_raises() -> None:
    with pytest.raises(ValueError, match="未知的求解算法"):
        solve("dfs", Maze(2, 2), (0, 0), (1, 1))
