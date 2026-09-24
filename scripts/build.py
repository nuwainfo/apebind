#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import sys

from pathlib import Path

from _project import ProjectTasks, ScriptBoundary


class BuildCommand:
    def __init__(self):
        self._tasks = ProjectTasks()

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description='Test and build APEBind distributions.')
        parser.add_argument(
            '--skip-tests',
            action='store_true',
            help='Build without running pytest first.',
        )
        parser.add_argument(
            '--no-clean',
            action='store_true',
            help='Keep existing build/dist artifacts.',
        )
        parser.add_argument(
            '--python',
            type=Path,
            default=Path(sys.executable),
            help='Python interpreter used for tests and builds.',
        )
        return parser

    def run(self, argv: list[str] | None = None) -> int:
        args = self._build_parser().parse_args(argv)
        python_executable = args.python.resolve()
        if not args.skip_tests:
            self._tasks.run_tests(python_executable)
            
        self._tasks.build_distribution(python_executable, clean=not args.no_clean)
        return 0


def main() -> int:
    return BuildCommand().run()


if __name__ == '__main__':
    raise SystemExit(ScriptBoundary.invoke(main))
