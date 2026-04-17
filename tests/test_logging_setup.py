from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

from core import logging_setup


@pytest.fixture(autouse=True)
def _reset_imagerect_logging() -> None:
    _remove_imagerect_handlers()
    yield
    logging.shutdown()
    _remove_imagerect_handlers()


def test_configure_logging_creates_file(tmp_path: Path) -> None:
    log_file = logging_setup.configure_logging(log_dir=tmp_path)

    assert log_file == tmp_path / "imagerect.log"
    assert log_file.exists()


def test_configure_logging_idempotent(tmp_path: Path) -> None:
    logging_setup.configure_logging(log_dir=tmp_path)
    logging_setup.configure_logging(log_dir=tmp_path)

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, "_imagerect_handler", False)
    ]

    assert len(handlers) == 2
    assert sum(isinstance(handler, RotatingFileHandler) for handler in handlers) == 1
    assert sum(isinstance(handler, logging.StreamHandler) for handler in handlers) == 2


@pytest.mark.parametrize(
    ("platform_name", "env_name", "env_value", "expected_path"),
    [
        ("linux", "HOME", "linux-home", Path("linux-home/.imagerect/logs")),
        ("darwin", "HOME", "darwin-home", Path("darwin-home/Library/Logs/ImageRect")),
        (
            "win32",
            "LOCALAPPDATA",
            "windows-localappdata",
            Path("windows-localappdata/ImageRect/logs"),
        ),
    ],
)
def test_log_directory_platform_specific(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    platform_name: str,
    env_name: str,
    env_value: str,
    expected_path: Path,
) -> None:
    monkeypatch.setattr(logging_setup.sys, "platform", platform_name)
    monkeypatch.setenv(env_name, str(tmp_path / env_value))
    # Path.home() reads USERPROFILE on Windows and HOME on Unix. Patch it
    # directly so the test is host-platform independent.
    fake_home = tmp_path / env_value
    monkeypatch.setattr(logging_setup.Path, "home", classmethod(lambda _cls: fake_home))

    log_dir = logging_setup.log_directory()

    assert log_dir == tmp_path / expected_path
    assert log_dir.exists()


def _remove_imagerect_handlers() -> None:
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, "_imagerect_handler", False):
            root.removeHandler(handler)
            handler.close()
