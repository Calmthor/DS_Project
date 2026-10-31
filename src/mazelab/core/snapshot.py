"""单步快照：统一生成器与求解器的逐步输出格式。

生成器与求解器都实现为 Python 生成器，每 yield 一个 :class:`StepSnapshot`
就是可视化里的一帧。``structure`` 存放当前算法正在操作的数据结构
（栈 / 队列 / 堆），``extra`` 放算法特有的补充信息（如刚刚打通的边）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Point = tuple[int, int]


@dataclass
class StepSnapshot:
    """一帧状态：动作描述 + 当前格 + 活动数据结构 + 已访问/候选集合。"""

    action: str
    current: Point | None = None
    structure: list[Any] = field(default_factory=list)
    visited: set[Point] = field(default_factory=set)
    frontier: set[Point] = field(default_factory=set)
    path: list[Point] = field(default_factory=list)
    done: bool = False
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典（集合转列表，坐标保持二元组）。"""
        return {
            "action": self.action,
            "current": self.current,
            "structure": list(self.structure),
            "visited": sorted(self.visited),
            "frontier": sorted(self.frontier),
            "path": list(self.path),
            "done": self.done,
            "extra": self.extra,
        }
