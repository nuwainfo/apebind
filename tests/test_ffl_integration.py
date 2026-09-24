#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import os
import subprocess
import sys
from pathlib import Path

import pytest

from apebind.schema import SchemaCodec


def _run_generated_operation(
    generated_environment: dict[str, str],
    source: str,
) -> None:
    completed = subprocess.run(
        [sys.executable, '-c', source],
        check=True,
        capture_output=True,
        text=True,
        env=generated_environment,
        timeout=120,
    )

    assert completed.stdout.splitlines()[-2:] == ['0', 'True']


@pytest.mark.ffl_integration
def test_real_ffl_end_to_end(tmp_path: Path):
    if os.environ.get('APEBIND_RUN_FFL_INTEGRATION') != '1':
        pytest.skip('Real FFL integration is run in an isolated pytest process')

    configured_path = os.environ.get('APEBIND_FFL_APE')
    if not configured_path:
        pytest.fail('APEBIND_FFL_APE is required for the real FFL integration test')

    ffl_path = Path(configured_path).resolve()

    if not ffl_path.is_file():
        pytest.fail(f'APEBIND_FFL_APE does not exist: {ffl_path}')

    if os.name != 'nt':
        ffl_path.chmod(0o755)

    project_root = Path(__file__).parents[1]
    schema_path = tmp_path / 'ffl.apebind.yaml'
    generated_path = tmp_path / 'generated'
    environment = dict(os.environ)
    source_path = str(project_root / 'src')
    environment['PYTHONPATH'] = source_path

    subprocess.run(
        [
            sys.executable,
            '-m',
            'apebind',
            'inspect',
            str(ffl_path),
            '-o',
            str(schema_path),
            '--command-file',
            str(project_root / 'examples' / 'ffl.commands.yaml'),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=120,
    )

    subprocess.run(
        [sys.executable, '-m', 'apebind', 'validate', str(schema_path)],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )

    spec = SchemaCodec().load(schema_path)
    commands = {command.path: command for command in spec.commands}

    assert {('share',), ('download',), ('keygen',)} <= set(commands)

    operations = {operation.command: operation.name for operation in spec.operations}
    assert operations[('share',)] == 'share'
    assert operations[('download',)] == 'download'
    assert operations[('keygen',)] == 'keygen'

    assert commands[('share',)].positionals[0].api_name == 'file_or_folder'
    assert any(option.api_name == 'name' for option in commands[('share',)].options)
    assert any(option.api_name == 'json' for option in commands[('share',)].options)

    subprocess.run(
        [
            sys.executable,
            '-m',
            'apebind',
            'generate',
            str(schema_path),
            '--ape',
            str(ffl_path),
            '--lang',
            'python',
            '-o',
            str(generated_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )

    generated_environment = dict(environment)
    generated_environment['PYTHONPATH'] = os.pathsep.join(
        [str(generated_path / 'src'), source_path]
    )

    operation_sources = (
        (
            'import ffl; '
            'result = ffl.share(version=True); '
            'print(result.return_code); '
            "print('FastFileLink' in result.stdout)"
        ),
        (
            'import ffl; '
            "result = ffl.download('https://example.invalid', version=True); "
            'print(result.return_code); '
            "print('FastFileLink' in result.stdout)"
        ),
        (
            'import ffl; '
            'result = ffl.keygen(version=True); '
            'print(result.return_code); '
            "print('FastFileLink' in result.stdout)"
        ),
    )

    for source in operation_sources:
        _run_generated_operation(generated_environment, source)
