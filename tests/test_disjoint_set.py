"""并查集测试：合并、查找、路径压缩与分量计数。"""

from __future__ import annotations

import pytest

from mazelab.core.disjoint_set import DisjointSet


def test_initial_state_has_n_components() -> None:
    dsu = DisjointSet(4)
    assert dsu.components == 4
    assert len(dsu) == 4
    assert not dsu.connected(0, 1)


def test_union_merges_and_counts_components() -> None:
    dsu = DisjointSet(4)
    assert dsu.union(0, 1) is True
    assert dsu.components == 3
    assert dsu.connected(0, 1)
    # 重复合并不应改变分量数
    assert dsu.union(1, 0) is False
    assert dsu.components == 3


def test_transitive_connectivity() -> None:
    dsu = DisjointSet(5)
    dsu.union(0, 1)
    dsu.union(1, 2)
    assert dsu.connected(0, 2)
    assert not dsu.connected(0, 3)


def test_chain_union_reduces_to_one_component() -> None:
    dsu = DisjointSet(10)
    for i in range(9):
        dsu.union(i, i + 1)
    assert dsu.components == 1
    assert dsu.find(0) == dsu.find(9)


def test_path_compression_keeps_find_correct() -> None:
    dsu = DisjointSet(6)
    for i in range(1, 6):
        dsu.union(0, i)
    for i in range(6):
        assert dsu.find(i) == dsu.find(0)


@pytest.mark.parametrize("bad", [-1, 100])
def test_find_rejects_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="越界"):
        DisjointSet(3).find(bad)


def test_negative_size_rejected() -> None:
    with pytest.raises(ValueError):
        DisjointSet(-1)
