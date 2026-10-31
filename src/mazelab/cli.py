"""命令行入口：generate / solve / validate 三个子命令。

设计原则：核心逻辑留在 core / generators / solvers 里，CLI 只负责解析参数、
调用库函数、把结果打印或落盘。因此同一套行为既能在命令行演示，也能被测试直接调用。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from pathlib import Path

from mazelab import __version__
from mazelab.core.maze import Maze, Point
from mazelab.core.validate import validate
from mazelab.generators import GENERATORS, NAMES as GENERATOR_NAMES
from mazelab.solvers import NAMES as SOLVER_NAMES, SOLVERS


def _point(text: str) -> Point:
    """解析 ``行,列`` 形式的坐标，顺带做格式校验。"""
    try:
        row, col = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"坐标应形如 '1,2'，收到 {text!r}") from None
    if row < 0 or col < 0:
        raise argparse.ArgumentTypeError(f"坐标不能为负：{text!r}")
    return (row, col)


def _load(path: str) -> Maze:
    try:
        return Maze.load(path)
    except ValueError as exc:
        raise SystemExit(f"读取失败：{exc}") from None


def _dump_json(payload: dict) -> str:
    """缩进输出，但把 [行, 列] 这样的坐标压回一行，免得路径被拆成几十行。"""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return re.sub(r"\[\s+(-?\d+),\s+(-?\d+)\s+\]", r"[\1, \2]", text)


def _emit(text: str, output: str | None) -> None:
    """有 ``--output`` 就写文件，否则打到标准输出。"""
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
        print(f"已写入 {target}")
    else:
        print(text)


def cmd_generate(args: argparse.Namespace) -> int:
    maze = GENERATORS[args.algorithm].generate(args.rows, args.cols, random.Random(args.seed))
    if args.format == "json":
        # 额外字段只作记录，Maze.from_dict 会忽略不认识的键，因此生成的文件可以直接喂给 solve/validate
        payload = {"algorithm": args.algorithm, "seed": args.seed, **maze.to_dict()}
        _emit(_dump_json(payload), args.output)
    else:
        _emit(maze.to_ascii(), args.output)
    if not validate(maze).ok:
        print("警告：生成的迷宫未通过自检", file=sys.stderr)
        return 1
    return 0


def cmd_solve(args: argparse.Namespace) -> int:
    maze = _load(args.input)
    start = args.start or (0, 0)
    goal = args.goal or (maze.rows - 1, maze.cols - 1)
    if not maze.in_bounds(start) or not maze.in_bounds(goal):
        raise SystemExit(f"起点 {start} 或终点 {goal} 越界（迷宫 {maze.rows}×{maze.cols}）")

    path = SOLVERS[args.algorithm].solve(maze, start, goal)
    if path is None:
        print(f"无解：{start} 到 {goal} 不连通", file=sys.stderr)
        if args.format == "ascii":
            print(maze.to_ascii(marks={start: "S", goal: "G"}))
        return 2

    if args.format == "json":
        payload = {
            "algorithm": args.algorithm,
            "start": list(start),
            "goal": list(goal),
            "distance": len(path) - 1,
            "path": [list(p) for p in path],
        }
        _emit(_dump_json(payload), args.output)
    else:
        marks = {start: "S", goal: "G"} if start != goal else {start: "S"}
        _emit(maze.to_ascii(path=path, marks=marks), args.output)
        print(f"{args.algorithm}: 最短路径 {len(path) - 1} 步")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    maze = _load(args.input)
    report = validate(maze)
    print(f"迷宫 {maze.rows}×{maze.cols}，{maze.size} 格")
    print(report.render())
    return 0 if report.ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mazelab",
        description="MazeLab: 迷宫生成、求解与校验",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mazelab {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="生成迷宫")
    gen.add_argument("--rows", type=int, default=10, help="行数")
    gen.add_argument("--cols", type=int, default=10, help="列数")
    gen.add_argument("--algorithm", choices=list(GENERATOR_NAMES), default="dfs", help="生成算法")
    gen.add_argument("--seed", type=int, default=None, help="随机种子（相同种子结果相同）")
    gen.add_argument("--format", choices=("ascii", "json"), default="ascii", help="输出格式")
    gen.add_argument("--output", default=None, help="写入文件（默认打印到终端）")
    gen.set_defaults(func=cmd_generate)

    solve = sub.add_parser("solve", help="求解迷宫")
    solve.add_argument("--input", required=True, help="迷宫 JSON 文件")
    solve.add_argument("--start", type=_point, default=None, help="起点 行,列（默认左上角）")
    solve.add_argument("--goal", type=_point, default=None, help="终点 行,列（默认右下角）")
    solve.add_argument("--algorithm", choices=list(SOLVER_NAMES), default="bfs", help="求解算法")
    solve.add_argument("--format", choices=("ascii", "json"), default="ascii", help="输出格式")
    solve.add_argument("--output", default=None, help="写入文件（默认打印到终端）")
    solve.set_defaults(func=cmd_solve)

    validate_cmd = sub.add_parser("validate", help="验证迷宫")
    validate_cmd.add_argument("--input", required=True, help="迷宫 JSON 文件")
    validate_cmd.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
