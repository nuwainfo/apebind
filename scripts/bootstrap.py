#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse

from pathlib import Path

from _project import ProjectPaths, ProjectTasks, ScriptBoundary


class BootstrapCommand:
    def __init__(self):
        self._paths = ProjectPaths.discover()
        self._tasks = ProjectTasks(self._paths)

    def _build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            description='Set up APEBind, build the APE fixture, run tests, and build distributions.'
        )
        parser.add_argument(
            '--venv',
            type=Path,
            default=self._paths.default_venv,
            help='Virtual environment directory (default: .venv).',
        )
        parser.add_argument(
            '--skip-ape-fixture',
            action='store_true',
            help='Do not compile tests/fixtures/ape_fixture.com with cosmocc.',
        )
        parser.add_argument('--skip-tests', action='store_true', help='Do not run pytest.')
        parser.add_argument('--skip-build', action='store_true', help='Do not build sdist/wheel.')
        return parser

    def run(self, argv: list[str] | None = None) -> int:
        args = self._build_parser().parse_args(argv)
        self._tasks.require_python_version()
        
        python_executable = self._tasks.create_venv(args.venv.resolve())
        self._tasks.install_development(python_executable)
        
        if not args.skip_ape_fixture:
            fixture_path = self._tasks.build_ape_fixture()
            print(f'Built APE fixture: {fixture_path}')
            
        if not args.skip_tests:
            self._tasks.run_tests(python_executable)
            
        if not args.skip_build:
            self._tasks.build_distribution(python_executable)
            
        print('Bootstrap complete.')
        return 0


def main() -> int:
    return BootstrapCommand().run()


if __name__ == '__main__':
    raise SystemExit(ScriptBoundary.invoke(main))
