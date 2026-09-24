#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from apebind import __version__
from apebind.schema import SchemaCodec


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREPARE_APE_LIB = PROJECT_ROOT / 'scripts' / 'prepare_ape_lib.py'


def test_prepare_ape_lib_copies_portable_runtime_dependencies(tmp_path: Path):
    library_directory = tmp_path / 'Lib'
    entry_path = tmp_path / 'APEBind.py'

    subprocess.run(
        [
            sys.executable,
            PREPARE_APE_LIB,
            '--output',
            library_directory,
            '--entry',
            entry_path,
        ],
        check=True,
    )

    assert (library_directory / 'apebind' / 'cli.py').is_file()
    assert (library_directory / 'apebind' / 'templates' / 'python' / 'runtime.py.j2').is_file()
    assert (library_directory / 'click' / '__init__.py').is_file()
    assert (library_directory / 'typing_extensions.py').is_file()

    assert not list(library_directory.rglob('*.pyd'))
    assert not list(library_directory.rglob('*.so'))

    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(library_directory)
    result = subprocess.run(
        [sys.executable, entry_path, '--version'],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert __version__ in result.stdout


def test_apebind_ape_can_bind_itself_repeatedly(tmp_path: Path):
    configured_ape = os.environ.get('APEBIND_SELF_APPLICATION_APE')
    ape_path = Path(configured_ape) if configured_ape else PROJECT_ROOT / 'ape' / 'apebind.com'
    if not ape_path.is_file():
        pytest.skip('APEBind APE is missing; run bash scripts/build_ape.sh first')

    if os.name == 'nt' and shutil.which('wsl') is None:
        pytest.skip('WSL is required to run an APE self-application test on Windows')

    schema_path = tmp_path / 'apebind.apebind.yaml'
    first_generation = tmp_path / 'apebind-python-generation-one'
    second_generation = tmp_path / 'apebind-python-generation-two'

    _run_ape(ape_path, 'inspect', ape_path, '--output', schema_path)

    _run_ape(ape_path, 'validate', schema_path)

    spec = SchemaCodec().load(schema_path)
    commands = {command.path: command for command in spec.commands}

    assert [item.api_name for item in commands[('generate',)].positionals] == ['schema_path']
    assert [item.api_name for item in commands[('inspect',)].positionals] == ['ape_path']
    assert [item.api_name for item in commands[('validate',)].positionals] == ['schema_path']

    _run_ape(
        ape_path,
        'generate',
        schema_path,
        '--ape',
        ape_path,
        '--lang',
        'python',
        '--output',
        first_generation,
    )

    first_source = first_generation / 'src'
    assert (first_source / 'apebind' / 'bin' / 'apebind.com').is_file()

    generate_source = _generation_source(schema_path, ape_path, second_generation)

    _run_generated_python(first_source, tmp_path, generate_source)

    second_source = second_generation / 'src'
    assert (second_source / 'apebind' / 'bin' / 'apebind.com').is_file()

    result = _run_generated_python(second_source, tmp_path, _version_source())

    assert __version__ in result.stdout


def _generation_source(
    schema_path: Path,
    ape_path: Path,
    output_directory: Path,
) -> str:
    return f'''import apebind

result = apebind.generate(
    {str(schema_path)!r},
    ape={str(ape_path)!r},
    lang='python',
    output={str(output_directory)!r},
)

assert result.return_code == 0, result.stderr
'''


def _version_source() -> str:
    return '''import apebind

result = apebind.run(version=True)

assert result.return_code == 0, result.stderr
print(result.stdout, end='')
'''


def _run_generated_python(
    generated_source: Path,
    working_directory: Path,
    source: str,
) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(generated_source)

    return subprocess.run(
        [sys.executable, '-c', source],
        check=True,
        capture_output=True,
        text=True,
        cwd=working_directory,
        env=environment,
        timeout=60,
    )


def _run_ape(ape_path: Path, *arguments: str | Path) -> None:
    if os.name == 'nt':
        command = [_wsl_path(ape_path)]
        converted_arguments = (
            _wsl_path(argument) if isinstance(argument, Path) else argument
            for argument in arguments
        )
        command.extend(converted_arguments)

        command_text = ' '.join(shlex.quote(part) for part in command)
        wsl_command = [
            'wsl',
            '-e',
            'sh',
            '-lc',
            f'cd {shlex.quote(_wsl_path(PROJECT_ROOT))} && {command_text}',
        ]

        subprocess.run(wsl_command, check=True)
        return

    subprocess.run(
        [
            '/bin/sh',
            '-c',
            'exec "$0" "$@"',
            str(ape_path),
            *(str(argument) for argument in arguments),
        ],
        check=True,
    )


def _wsl_path(path: Path) -> str:
    resolved_path = path.resolve()
    drive = resolved_path.drive.rstrip(':').lower()
    if not drive:
        raise RuntimeError(f'Cannot convert path to a WSL path: {resolved_path}')

    return f'/mnt/{drive}{resolved_path.as_posix()[2:]}'
