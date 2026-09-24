#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import os
import sys
from pathlib import Path

from scripts._project import ProjectPaths, ProjectTasks


def test_project_paths_find_sibling_cosmocc(tmp_path: Path, monkeypatch):
    compiler = tmp_path / 'cosmocc' / 'bin' / 'cosmocc'
    compiler.parent.mkdir(parents=True)
    compiler.write_text('fixture', encoding='utf-8')
    monkeypatch.delenv('COSMOCC', raising=False)

    paths = ProjectPaths(tmp_path)

    assert paths.find_cosmocc() == compiler.resolve()


def test_project_paths_honor_cosmocc_binary_environment(tmp_path: Path, monkeypatch):
    compiler = tmp_path / 'custom-cosmocc'
    compiler.write_text('fixture', encoding='utf-8')
    monkeypatch.setenv('COSMOCC', str(compiler))

    paths = ProjectPaths(tmp_path / 'project')

    assert paths.find_cosmocc() == compiler.resolve()


def test_project_paths_honor_cosmocc_directory_environment(tmp_path: Path, monkeypatch):
    compiler = tmp_path / 'toolchain' / 'bin' / 'cosmocc'
    compiler.parent.mkdir(parents=True)
    compiler.write_text('fixture', encoding='utf-8')
    monkeypatch.setenv('COSMOCC', str(tmp_path / 'toolchain'))

    paths = ProjectPaths(tmp_path / 'project')

    assert paths.find_cosmocc() == compiler.resolve()


class FixtureBuildRunner:
    def __init__(self):
        self.command = None
        self.cwd = None

    def run(self, command, *, cwd=None, environment=None):
        del environment
        self.command = [str(part) for part in command]
        self.cwd = cwd
        output_index = self.command.index('-o') + 1
        output_path = Path(self.command[output_index])
        if not output_path.is_absolute() and cwd is not None:
            output_path = cwd / output_path

        output_path.write_bytes(b"MZqFpD='fixture")


def test_build_ape_fixture_uses_project_paths(tmp_path: Path):
    fixture_source = tmp_path / 'tests' / 'fixtures' / 'ape_fixture.c'
    fixture_source.parent.mkdir(parents=True)
    fixture_source.write_text('int main(void) { return 0; }', encoding='utf-8')
    compiler = tmp_path / 'cosmocc' / 'bin' / 'cosmocc'
    compiler.parent.mkdir(parents=True)
    compiler.write_text('fixture', encoding='utf-8')
    runner = FixtureBuildRunner()

    result = ProjectTasks(ProjectPaths(tmp_path), runner).build_ape_fixture()

    assert result == tmp_path / 'tests' / 'fixtures' / 'ape_fixture.com'
    assert result.read_bytes().startswith(b"MZqFpD='")

    if os.name == 'nt':
        assert runner.command[0].lower().endswith('bash.exe')
        assert runner.command[1] == 'cosmocc/bin/cosmocc'
    else:
        assert runner.command[0] == str(compiler.resolve())

    assert '-Wall' in runner.command
    assert '-Werror' in runner.command
    assert runner.cwd == tmp_path


class RecordingRunner:
    def __init__(self):
        self.calls = []

    def run(self, command, *, cwd=None, environment=None):
        self.calls.append(
            {
                'command': [str(part) for part in command],
                'cwd': cwd,
                'environment': dict(environment or {}),
            }
        )


def test_run_tests_isolates_external_ffl_integration(tmp_path: Path, monkeypatch):
    runner = RecordingRunner()
    python_executable = Path(sys.executable)
    monkeypatch.setenv('APEBIND_FFL_APE', '/tmp/ffl.com')
    monkeypatch.setenv('APEBIND_RUN_FFL_INTEGRATION', 'stale')

    ProjectTasks(ProjectPaths(tmp_path), runner).run_tests(python_executable)

    assert len(runner.calls) == 5
    common_call, python_call, node_call, java_call, integration_call = runner.calls

    assert common_call['command'] == [
        str(python_executable),
        '-m',
        'pytest',
        'tests',
        '--ignore=tests/generation/backends',
        '--ignore=tests/test_ffl_integration.py',
    ]
    assert python_call['command'][-1] == 'tests/generation/backends/test_python_backend.py'
    assert node_call['command'][-1] == 'tests/generation/backends/test_node_backend.py'
    assert java_call['command'][-1] == 'tests/generation/backends/test_java_backend.py'
    assert 'APEBIND_RUN_FFL_INTEGRATION' not in common_call['environment']

    assert integration_call['command'] == [
        str(python_executable),
        '-m',
        'pytest',
        'tests/test_ffl_integration.py',
    ]
    assert integration_call['environment']['APEBIND_RUN_FFL_INTEGRATION'] == '1'


def test_shell_scripts_use_lf_line_endings():
    project_root = Path(__file__).resolve().parents[1]
    attributes = (project_root / '.gitattributes').read_text(encoding='utf-8')

    assert '*.sh text eol=lf' in attributes.splitlines()

    shell_scripts = sorted(project_root.rglob('*.sh'))
    assert shell_scripts

    for shell_script in shell_scripts:
        assert b'\r\n' not in shell_script.read_bytes(), shell_script
