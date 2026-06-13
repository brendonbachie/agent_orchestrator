from unittest.mock import patch

import pytest

from utils.analysis_cache import cache_get, cache_key, cache_set


@pytest.fixture
def tmp_cache(tmp_path):
    with patch("utils.analysis_cache._CACHE_DIR", tmp_path / "ac"):
        yield


def test_cache_key_is_deterministic():
    assert cache_key("desc", ["a", "b"]) == cache_key("desc", ["a", "b"])


def test_cache_key_varies_with_descricao():
    assert cache_key("desc A", ["a"]) != cache_key("desc B", ["a"])


def test_cache_key_varies_with_templates():
    assert cache_key("desc", ["a"]) != cache_key("desc", ["a", "b"])


def test_cache_get_miss_returns_none(tmp_cache):
    assert cache_get("inexistente") is None


def test_cache_roundtrip(tmp_cache):
    valor = {"claude_md": "# x", "agentes": [], "hooks": [], "primeiro_prompt": "go"}
    cache_set("k1", valor)
    assert cache_get("k1") == valor


def test_cache_get_ignores_non_dict(tmp_cache):
    cache_set("k2", {"ok": True})
    # corrompe o arquivo com um valor que não é objeto
    from utils import analysis_cache

    (analysis_cache._CACHE_DIR / "k2.json").write_text("[1, 2, 3]", encoding="utf-8")
    assert cache_get("k2") is None
