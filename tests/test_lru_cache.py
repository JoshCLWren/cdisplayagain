"""Test LRU cache eviction behavior."""

import pytest

from cdisplayagain import LRUCache


def test_lru_cache_evicts_oldest_when_full():
    """Verify that LRU cache evicts oldest item when at capacity."""
    cache = LRUCache(maxsize=3)

    cache["key1"] = "value1"
    cache["key2"] = "value2"
    cache["key3"] = "value3"

    assert len(cache) == 3

    cache["key4"] = "value4"

    assert len(cache) == 3
    assert "key1" not in cache, "Oldest key should be evicted"
    assert "key2" in cache
    assert "key3" in cache
    assert "key4" in cache


def test_lru_cache_updates_access_order():
    """Verify that accessing items updates their position."""
    cache = LRUCache(maxsize=3)

    cache["key1"] = "value1"
    cache["key2"] = "value2"
    cache["key3"] = "value3"

    _ = cache["key2"]

    cache["key4"] = "value4"

    assert len(cache) == 3
    assert "key1" not in cache, "Oldest (key1) should be evicted"
    assert "key2" in cache, "Recently accessed (key2) should remain"
    assert "key3" in cache
    assert "key4" in cache


def test_lru_cache_get_method():
    """Verify that get method returns None for missing keys."""
    cache = LRUCache(maxsize=3)

    cache["key1"] = "value1"

    assert cache.get("key1") == "value1"
    assert cache.get("missing") is None


def test_lru_cache_rejects_invalid_maxsize():
    """Verify that LRU cache raises ValueError for invalid maxsize."""
    with pytest.raises(ValueError, match="maxsize must be positive"):
        LRUCache(maxsize=0)

    with pytest.raises(ValueError, match="maxsize must be positive"):
        LRUCache(maxsize=-1)


def test_lru_cache_clear():
    """Verify that clear removes all items."""
    cache = LRUCache(maxsize=3)

    cache["key1"] = "value1"
    cache["key2"] = "value2"

    assert len(cache) == 2

    cache.clear()

    assert len(cache) == 0
    assert "key1" not in cache
    assert "key2" not in cache
