#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import sys

from pathlib import Path

from _project import ProjectTasks, ScriptBoundary


class TestCommand:
    def __init__(self):
        self._tasks = ProjectTasks()

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description='Run the APEBind test suite.')
        parser.add_argument(
            '--build-ape-fixture',
            action='store_true',
            help='Build the real APE fixture before running tests.',
        )
        parser.add_argument(
            '--group',
            choices=('common', 'python', 'node', 'java', 'ffl', 'all'),
            default='all',
            help='Run one isolated test group or all groups.',
        )
        parser.add_argument(
            '--python',
            type=Path,
            default=Path(sys.executable),
            help='Python interpreter used to run pytest.',
        )
        return parser

    def run(self, argv: list[str] | None = None) -> int:
        args = self._build_parser().parse_args(argv)
        if args.build_ape_fixture:
            self._tasks.build_ape_fixture()
        self._tasks.run_tests(args.python.resolve(), args.group)
        return 0


def main() -> int:
    return TestCommand().run()


if __name__ == '__main__':
    raise SystemExit(ScriptBoundary.invoke(main))
