#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess

from pathlib import Path

from attrs import define


@define(frozen=True)
class ProcessResult:
    argv: tuple[str, ...]
    return_code: int
    stdout: str
    stderr: str


def _normalize_ape_return_code(return_code: int) -> int:
    if os.name == 'nt' and return_code > 0 and return_code % 256 == 0:
        return return_code // 256
    return return_code


class ExecutableRunner:
    """Own subprocess invocation used during inspection."""

    def __init__(self, executable_path: Path):
        self._executable_path = executable_path.resolve()

    @property
    def executable_path(self) -> Path:
        return self._executable_path

    def run(self, arguments: list[str], timeout_seconds: float = 30.0) -> ProcessResult:
        completed = subprocess.run(
            self._build_command(arguments),
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout_seconds,
            check=False,
        )

        return ProcessResult(
            argv=tuple(arguments),
            return_code=_normalize_ape_return_code(completed.returncode),
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def _build_command(self, arguments: list[str]) -> list[str]:
        executable = str(self._executable_path)

        if os.name == 'nt':
            return [executable, *arguments]

        return ['/bin/sh', '-c', 'exec "$0" "$@"', executable, *arguments]
