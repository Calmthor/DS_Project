"""支持 ``python -m mazelab`` 直接调用命令行。"""

from __future__ import annotations

from mazelab.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
