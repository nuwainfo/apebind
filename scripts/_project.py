#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ProjectPaths:
    root: Path

    @classmethod
    def discover(cls) -> 'ProjectPaths':
        return cls(Path(__file__).resolve().parents[1])

    @property
    def cosmocc_directory(self) -> Path:
        return self.root / 'cosmocc'

    @property
    def fixture_source(self) -> Path:
        return self.root / 'tests' / 'fixtures' / 'ape_fixture.c'

    @property
    def fixture_ape(self) -> Path:
        return self.root / 'tests' / 'fixtures' / 'ape_fixture.com'

    @property
    def default_venv(self) -> Path:
        return self.root / '.venv'

    def venv_python(self, venv_directory: Path) -> Path:
        if os.name == 'nt':
            return venv_directory / 'Scripts' / 'python.exe'
        return venv_directory / 'bin' / 'python'

    def find_cosmocc(self) -> Path | None:
        configured = os.environ.get('COSMOCC')
        candidates: list[Path] = []
        if configured:
            configured_path = Path(configured)
            if configured_path.is_dir():
                candidates.extend(
                    [
                        configured_path / 'bin' / 'cosmocc',
                        configured_path / 'bin' / 'cosmocc.exe',
                    ]
                )
            else:
                candidates.append(configured_path)
                
        candidates.extend(
            [
                self.cosmocc_directory / 'bin' / 'cosmocc',
                self.cosmocc_directory / 'bin' / 'cosmocc.exe',
            ]
        )
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        discovered = shutil.which('cosmocc')
        if discovered:
            return Path(discovered).resolve()
        return None


class CommandRunner:
    def run(
        self,
        command: Sequence[str | os.PathLike[str]],
        *,
        cwd: Path | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        rendered = [str(part) for part in command]
        print('+', subprocess.list2cmdline(rendered), flush=True)
        subprocess.run(
            rendered,
            cwd=cwd,
            env=None if environment is None else dict(environment),
            check=True,
        )


class ScriptBoundary:
    @staticmethod
    def invoke(action: Callable[[], int]) -> int:
        try:
            return action()
        except (RuntimeError, subprocess.CalledProcessError) as error:
            print(f'error: {error}', file=sys.stderr)
            return 1


class ProjectTasks:
    def __init__(
        self,
        paths: ProjectPaths | None = None,
        runner: CommandRunner | None = None,
    ):
        self.paths = paths or ProjectPaths.discover()
        self.runner = runner or CommandRunner()

    @staticmethod
    def require_python_version() -> None:
        if sys.version_info < (3, 11):
            raise RuntimeError('APEBind development requires Python 3.11 or newer')

    def create_venv(self, venv_directory: Path) -> Path:
        if not venv_directory.exists():
            print(f'Creating virtual environment: {venv_directory}')
            venv.EnvBuilder(with_pip=True).create(venv_directory)
            
        python_executable = self.paths.venv_python(venv_directory)
        if not python_executable.is_file():
            raise RuntimeError(f'Virtual environment Python was not created: {python_executable}')
            
        return python_executable

    def install_development(self, python_executable: Path) -> None:
        self.runner.run(
            [python_executable, '-m', 'pip', 'install', '-e', '.[dev]'],
            cwd=self.paths.root,
        )

    def build_ape_fixture(self, cosmocc: Path | None = None) -> Path:
        compiler = cosmocc or self.paths.find_cosmocc()
        if compiler is None:
            expected = self.paths.cosmocc_directory / 'bin' / 'cosmocc'
            raise RuntimeError(
                'cosmocc was not found. Put the Cosmopolitan toolchain in '
                f'{self.paths.cosmocc_directory} (expected {expected}) or set COSMOCC.'
            )
            
        compiler_command: list[str | Path] = [compiler]
        fixture_ape: str | Path = self.paths.fixture_ape
        fixture_source: str | Path = self.paths.fixture_source
        if os.name == 'nt' and compiler.suffix.lower() != '.exe':
            shell = shutil.which('bash')
            if shell is None:
                raise RuntimeError(
                    'A POSIX shell is required to run the Unix cosmocc wrapper on Windows. '
                    'Install WSL or provide cosmocc.exe via COSMOCC.'
                )
                
            def shell_path(path: Path) -> str:
                try:
                    return path.relative_to(self.paths.root).as_posix()
                except ValueError:
                    drive = path.drive.rstrip(':').lower()
                    if drive:
                        return f'/mnt/{drive}{path.as_posix()[2:]}'
                    return path.as_posix()

            compiler_argument = shell_path(compiler)
            compiler_command = [shell, compiler_argument]
            fixture_ape = shell_path(self.paths.fixture_ape)
            fixture_source = shell_path(self.paths.fixture_source)
            
        self.runner.run(
            [
                *compiler_command,
                '-O2',
                '-std=c11',
                '-Wall',
                '-Wextra',
                '-Werror',
                '-o',
                fixture_ape,
                fixture_source,
            ],
            cwd=self.paths.root,
        )
        
        if not self.paths.fixture_ape.is_file():
            raise RuntimeError(f'cosmocc did not create {self.paths.fixture_ape}')
            
        if os.name != 'nt':
            self.paths.fixture_ape.chmod(0o755)
            
        return self.paths.fixture_ape

    def run_tests(self, python_executable: Path, group: str = 'all') -> None:
        environment = dict(os.environ)
        source_path = str(self.paths.root / 'src')
        existing_python_path = environment.get('PYTHONPATH')
        environment['PYTHONPATH'] = (
            source_path
            if not existing_python_path
            else source_path + os.pathsep + existing_python_path
        )
        environment.pop('APEBIND_RUN_FFL_INTEGRATION', None)

        test_groups = {
            'common': [
                'tests',
                '--ignore=tests/generation/backends',
                '--ignore=tests/test_ffl_integration.py',
            ],
            'python': ['tests/generation/backends/test_python_backend.py'],
            'node': ['tests/generation/backends/test_node_backend.py'],
            'java': ['tests/generation/backends/test_java_backend.py'],
        }
        
        if group == 'ffl':
            self._run_ffl_integration(python_executable, environment, required=True)
            return
            
        group_names = tuple(test_groups) if group == 'all' else (group,)
        for group_name in group_names:
            self.runner.run(
                [python_executable, '-m', 'pytest', *test_groups[group_name]],
                cwd=self.paths.root,
                environment=environment,
            )
            
        if group == 'all':
            self._run_ffl_integration(python_executable, environment, required=False)

    def _run_ffl_integration(
        self,
        python_executable: Path,
        environment: Mapping[str, str],
        *,
        required: bool,
    ) -> None:
        if not environment.get('APEBIND_FFL_APE'):
            if required:
                raise RuntimeError('APEBIND_FFL_APE is required for the ffl test group')
            return
            
        integration_environment = dict(environment)
        integration_environment['APEBIND_RUN_FFL_INTEGRATION'] = '1'
        self.runner.run(
            [python_executable, '-m', 'pytest', 'tests/test_ffl_integration.py'],
            cwd=self.paths.root,
            environment=integration_environment,
        )

    def clean_build_artifacts(self) -> None:
        targets = [
            self.paths.root / 'build',
            self.paths.root / 'dist',
            self.paths.root / '.pytest_cache',
        ]
        targets.extend((self.paths.root / 'src').glob('*.egg-info'))
        
        for target in targets:
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()

    def build_distribution(self, python_executable: Path, *, clean: bool = True) -> None:
        if clean:
            self.clean_build_artifacts()
            
        self.runner.run(
            [python_executable, '-m', 'build', '--no-isolation'],
            cwd=self.paths.root,
        )
