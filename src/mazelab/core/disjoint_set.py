"""并查集（Disjoint Set Union）：Kruskal 生成迷宫的核心结构。

实现要点：
- ``find`` 带路径压缩（路过的节点直接挂到根上），均摊接近 O(1)；
- ``union`` 按集合大小合并（小树挂大树），把树高压在 O(log n) 以内；
- ``components`` 维护连通分量数，Kruskal 用"分量数是否为 1"判断生成结束。
"""

from __future__ import annotations


class DisjointSet:
    """下标 0..n-1 上的并查集。"""

    def __init__(self, n: int) -> None:
        if n < 0:
            raise ValueError(f"元素个数不能为负：{n}")
        self._parent = list(range(n))
        self._size = [1] * n
        self._components = n

    @property
    def components(self) -> int:
        """当前连通分量个数。"""
        return self._components

    def __len__(self) -> int:
        return len(self._parent)

    def find(self, x: int) -> int:
        """返回 x 所在集合的代表元，顺带压缩路径。"""
        if not 0 <= x < len(self._parent):
            raise ValueError(f"下标 {x} 越界（共 {len(self._parent)} 个元素）")
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:  # 路径压缩：把沿途节点直接挂到根上
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: int, b: int) -> bool:
        """合并两个集合；本来就在同一集合时返回 ``False``。"""
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        if self._size[ra] < self._size[rb]:
            ra, rb = rb, ra
        self._parent[rb] = ra
        self._size[ra] += self._size[rb]
        self._components -= 1
        return True

    def connected(self, a: int, b: int) -> bool:
        return self.find(a) == self.find(b)
