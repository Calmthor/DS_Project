"""命令行入口。"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="mazelab",
        description="Maze generation and solving toolkit",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate", help="生成迷宫")
    sub.add_parser("solve", help="求解迷宫")
    sub.add_parser("validate", help="验证迷宫")
    args = parser.parse_args()
    raise SystemExit(f"命令 {args.command} 尚未实现")


if __name__ == "__main__":
    main()