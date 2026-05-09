"""Atomic CSV writes and optional cross-process file locking (fcntl on Linux)."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pandas as pd

try:
    import fcntl as _fcntl

    _HAS_FCNTL = True
except ImportError:
    _fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False


def _lock_path(path: Path) -> Path:
    return path.with_name(path.name + ".lock")


@contextmanager
def _file_lock(lock_file: Path, exclusive: bool = True) -> Iterator[None]:
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    mode = "a+"
    with open(lock_file, mode, encoding="utf-8") as lf:
        if _HAS_FCNTL and _fcntl is not None:
            flag = _fcntl.LOCK_EX if exclusive else _fcntl.LOCK_SH
            _fcntl.flock(lf.fileno(), flag)
        try:
            yield
        finally:
            if _HAS_FCNTL and _fcntl is not None:
                _fcntl.flock(lf.fileno(), _fcntl.LOCK_UN)


def write_dataframe_csv_atomic(df: pd.DataFrame, path: Path, encoding: str = "utf-8") -> None:
    """Write CSV via temp file in the same directory + os.replace (crash-safe)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp_", suffix=".csv", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp)
    try:
        df.to_csv(tmp_path, index=False, encoding=encoding)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def write_dataframe_csv_atomic_guarded(df: pd.DataFrame, path: Path, encoding: str = "utf-8") -> None:
    """Atomic CSV write serialized with a companion `.lock` file (best-effort on non-Linux)."""
    path = Path(path)
    with _file_lock(_lock_path(path), exclusive=True):
        write_dataframe_csv_atomic(df, path, encoding=encoding)


def read_csv_optional_locked(path: Path, encoding: str = "utf-8") -> pd.DataFrame:
    """Read CSV with shared lock when the target file exists."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame()
    with _file_lock(_lock_path(path), exclusive=False):
        return pd.read_csv(path, encoding=encoding)
