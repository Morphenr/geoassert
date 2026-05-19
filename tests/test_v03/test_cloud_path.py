"""Tests for cloud path support in pyarrow engine."""

from __future__ import annotations

from geoassert.engines.pyarrow import _resolve_filesystem


def test_local_path_no_filesystem(tmp_path):
    path_str, fs = _resolve_filesystem(tmp_path / "data.parquet")
    assert fs is None
    assert "://" not in str(path_str)


def test_local_string_no_filesystem():
    path_str, fs = _resolve_filesystem("/some/local/path.parquet")
    assert fs is None


def test_s3_uri_returns_filesystem():
    """_resolve_filesystem should return a pyarrow S3FileSystem for s3:// URIs."""
    try:
        import pyarrow.fs  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("pyarrow.fs not available")

    path_on_fs, fs = _resolve_filesystem("s3://my-bucket/path/data.parquet")
    assert fs is not None
    assert "s3" in type(fs).__name__.lower()
    assert path_on_fs == "my-bucket/path/data.parquet"


def test_gcs_uri_returns_filesystem():
    try:
        import pyarrow.fs  # noqa: F401
    except ImportError:
        import pytest
        pytest.skip("pyarrow.fs not available")

    path_on_fs, fs = _resolve_filesystem("gs://my-bucket/path/data.parquet")
    assert fs is not None
