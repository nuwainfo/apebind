#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import hashlib
import io
import importlib
import os
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path

import pytest

from apebind.backends.python import PythonGenerator
from apebind.models import (
    ExecutionMode,
    OperationSpec,
    OptionSpec,
    ProcessSpec,
    ResultFormat,
    ResultSpec,
    RuntimeSpec,
    ValueType,
)


def make_fixture_ape(tmp_path: Path, fixture_ape_path: Path) -> Path:
    fixture_ape = tmp_path / 'fixture.com'
    shutil.copy2(fixture_ape_path, fixture_ape)
    fixture_ape.chmod(0o755)
    return fixture_ape


def import_generated(output_directory: Path, package_name: str):
    sys.path.insert(0, str(output_directory / 'src'))
    try:
        return importlib.import_module(package_name)
    finally:
        sys.path.pop(0)


def clear_generated(package_name: str) -> None:
    for module_name in list(sys.modules):
        if module_name == package_name or module_name.startswith(f'{package_name}.'):
            del sys.modules[module_name]


@pytest.fixture
def generated_fixture_runtime(tmp_path: Path, fixture_ape_path: Path, inspected_spec):
    output_directory = tmp_path / 'generated-runtime'
    PythonGenerator().generate(inspected_spec, fixture_ape_path, output_directory)

    runtime = import_generated(output_directory, 'ape_fixture._runtime')

    try:
        yield runtime
    finally:
        clear_generated('ape_fixture')


def test_generated_one_shot_operations(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operations = []

    for operation in inspected_spec.operations:
        if operation.command == ('echo',):
            operations.append(
                OperationSpec('echo', ('echo',), result=ResultSpec(ResultFormat.TEXT))
            )
        elif operation.command == ('math', 'add'):
            operations.append(
                OperationSpec(
                    'math_add',
                    ('math', 'add'),
                    result=ResultSpec(ResultFormat.TEXT),
                )
            )
        elif operation.command == ('json',):
            operations.append(
                OperationSpec(
                    'json_value',
                    ('json',),
                    result=ResultSpec(ResultFormat.JSON, field='payload.value'),
                )
            )

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('fixturebind', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=tuple(operations),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated_path = output_directory / 'src' / 'fixturebind' / '_generated.py'
    generated_source = generated_path.read_text(encoding='utf-8')

    assert max(len(line) for line in generated_source.splitlines()) <= 100
    assert '\n\n\n\n' not in generated_source

    generated = import_generated(output_directory, 'fixturebind')
    try:
        assert generated.echo(['hello', 'world'], upper=True, repeat=1) == 'HELLO WORLD'
        assert generated.echo('single', repeat=1) == 'single'
        assert generated.echo(['global'], verbose=True) == 'global'
        assert generated.math_add(2, 5) == '7'
        assert generated.json_value(value='hello') == 'hello'
        assert generated.raw(['echo', 'raw']).stdout.strip() == 'raw'
    finally:
        clear_generated('fixturebind')


def test_generated_persistent_json_file_session(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operation = OperationSpec(
        name='serve',
        command=('serve',),
        execution=ExecutionMode.PERSISTENT,
        result=ResultSpec(
            format=ResultFormat.JSON_FILE,
            option_flag='--json',
            field='link',
            ready_timeout_seconds=2,
        ),
    )

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('fixturebind2', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated = import_generated(output_directory, 'fixturebind2')
    try:
        source = io.BytesIO(b'generated stdin')

        with generated.serve(message='abc', stdin=source) as session:
            exited = threading.Event()
            session.on_exit(exited.set)
            assert session.result == 'https://example.test/abc'
            assert session.running
            session.stop()
            assert exited.wait(timeout=1)
            assert source.closed
    finally:
        clear_generated('fixturebind2')


def test_generated_session_closes_stream_source_after_early_child_exit(
    generated_fixture_runtime,
):
    runtime = generated_fixture_runtime

    class Source:
        closed = False

        def read(self, size: int) -> bytes:
            del size
            return b'x' * 65536

        def close(self) -> None:
            self.closed = True

    source = Source()

    process = subprocess.Popen(
        [sys.executable, '-c', 'import sys, time; sys.stdin.close(); time.sleep(0.01)'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    session = runtime.ProcessSession(process, ['input-child'])
    session.attach_stdin(source)

    assert session.wait() == 0
    assert source.closed


def test_generated_process_session_drains_large_output_without_deadlock(
    generated_fixture_runtime,
):
    runtime = generated_fixture_runtime

    process = subprocess.Popen(
        [
            sys.executable,
            '-c',
            "import sys; sys.stdout.buffer.write(b'x' * (2 * 1024 * 1024)); "
            "sys.stderr.buffer.write(b'y' * (2 * 1024 * 1024))",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    session = runtime.ProcessSession(process, ['large-output-child'])

    try:
        assert session.wait(timeout=3) == 0
        assert session.process_result.return_code == 0
        chunks = list(session.iter_stdout_bytes())
        assert sum(map(len, chunks)) == 2 * 1024 * 1024
    finally:
        session.close()


def test_generated_process_session_streams_fixed_size_binary_chunks(
    generated_fixture_runtime,
):
    runtime = generated_fixture_runtime

    process = subprocess.Popen(
        [sys.executable, '-c', "import sys; sys.stdout.buffer.write(b'x' * (2 * 1024 * 1024))"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    session = runtime.ProcessSession(
        process,
        ['binary-stream-child'],
        capture_stdout=False,
    )

    try:
        chunks = list(session.iter_stdout_bytes())
        assert sum(map(len, chunks)) == 2 * 1024 * 1024
        assert max(map(len, chunks)) <= 65536
        assert session.wait(timeout=3) == 0
    finally:
        session.close()


def test_generated_process_error_is_not_hidden(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operation = OperationSpec('fail', ('fail',))

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('fixturebind3', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated = import_generated(output_directory, 'fixturebind3')
    try:
        with pytest.raises(generated.APEProcessError) as error_info:
            generated.fail(code=9)
        assert error_info.value.result.return_code == 9
        assert 'requested failure' in error_info.value.result.stderr
    finally:
        clear_generated('fixturebind3')


def test_generated_wheel_installs_and_runs(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operation = OperationSpec('echo', ('echo',), result=ResultSpec(ResultFormat.TEXT))

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('wheel_fixturebind', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    wheel_directory = tmp_path / 'wheel'
    wheel_directory.mkdir()
    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'wheel',
            '.',
            '--no-deps',
            '--no-build-isolation',
            '-w',
            str(wheel_directory),
        ],
        cwd=output_directory,
        check=True,
        capture_output=True,
        text=True,
    )

    install_directory = tmp_path / 'installed'
    wheel_path = next(wheel_directory.glob('*.whl'))

    with zipfile.ZipFile(wheel_path) as archive:
        assert 'wheel_fixturebind/py.typed' in archive.namelist()
        if os.name != 'nt':
            mode = archive.getinfo('wheel_fixturebind/bin/fixture.com').external_attr >> 16
            assert mode & 0o111

    subprocess.run(
        [
            sys.executable,
            '-m',
            'pip',
            'install',
            '--no-deps',
            '--target',
            str(install_directory),
            str(wheel_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(install_directory)
    completed = subprocess.run(
        [
            sys.executable,
            '-c',
            "import wheel_fixturebind; print(wheel_fixturebind.echo(['installed']))",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.stdout.strip() == 'installed'


def test_generated_runtime_supports_optional_value_flags(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    optional_option = OptionSpec(
        flags=('--label',),
        api_name='label',
        value_type=ValueType.STRING,
        value_optional=True,
    )
    commands = tuple(
        command.__class__(
            path=command.path,
            summary=command.summary,
            positionals=command.positionals,
            options=(*command.options, optional_option),
        )
        if command.path == ('echo',)
        else command
        for command in inspected_spec.commands
    )

    operation = OperationSpec('echo', ('echo',), result=ResultSpec(ResultFormat.TEXT))
    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('optional_fixturebind', 'fixture.com'),
        commands=commands,
        operations=(operation,),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated_client = import_generated(output_directory, 'optional_fixturebind._generated')
    try:
        operation_metadata = generated_client._OPERATIONS['echo']
        option_metadata = next(
            option
            for level in operation_metadata['levels']
            for option in level['options']
            if option['api_name'] == 'label'
        )

        runtime_client = generated_client._CLIENT
        assert runtime_client._build_argv(
            operation_metadata,
            {'text': 'x', 'label': True},
            None,
        )[-2:] == ['--label', 'x']
        assert runtime_client._build_argv(
            operation_metadata,
            {'text': 'x', 'label': 'value'},
            None,
        )[-3:] == ['--label', 'value', 'x']
        assert '--label' not in runtime_client._build_argv(
            operation_metadata,
            {'text': 'x', 'label': None},
            None,
        )
    finally:
        clear_generated('optional_fixturebind')


def test_generated_runtime_unsets_configured_environment(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
    monkeypatch,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operation = OperationSpec('echo', ('echo',), result=ResultSpec(ResultFormat.TEXT))

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('env_fixturebind', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
        runtime=RuntimeSpec(env_unset=('APEBIND_TEST_SECRET',)),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated_client = import_generated(output_directory, 'env_fixturebind._generated')
    try:
        monkeypatch.setenv('APEBIND_TEST_SECRET', 'hidden')
        environment = generated_client._CLIENT._environment()
        assert 'APEBIND_TEST_SECRET' not in environment
    finally:
        clear_generated('env_fixturebind')


def test_generated_oneshot_process_timeout_is_applied(
    tmp_path: Path,
    fixture_ape_path: Path,
    inspected_spec,
):
    fake_ape = make_fixture_ape(tmp_path, fixture_ape_path)
    operation = OperationSpec(
        'serve_timeout',
        ('serve',),
        process=ProcessSpec(timeout_seconds=0.05),
    )

    spec = inspected_spec.__class__(
        schema_version=1,
        ape=inspected_spec.ape.__class__('timeout_fixturebind', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
    )

    output_directory = tmp_path / 'generated'
    PythonGenerator().generate(spec, fake_ape, output_directory)

    generated = import_generated(output_directory, 'timeout_fixturebind')
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            generated.serve_timeout(json=str(tmp_path / 'result.json'))
    finally:
        clear_generated('timeout_fixturebind')


def test_generated_runtime_requires_streamed_stdout_consumption_before_waiting(
    generated_fixture_runtime,
):
    runtime = generated_fixture_runtime

    process = subprocess.Popen(
        [
            sys.executable,
            '-c',
            "import sys; sys.stdout.buffer.write(b'x' * (2 * 1024 * 1024))",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    session = runtime.ProcessSession(process, ['stream-child'], capture_stdout=False)

    try:
        with pytest.raises(
            RuntimeError,
            match='streamed stdout must be consumed before waiting',
        ):
            session.wait(timeout=1)
    finally:
        session.stop()


def test_generated_runtime_does_not_chmod_installed_ape(
    tmp_path: Path,
    monkeypatch,
    generated_fixture_runtime,
):
    runtime = generated_fixture_runtime

    binary_path = tmp_path / 'ffl.com'
    client = runtime.APEClient(binary_path, {})
    executable = str(binary_path.resolve())

    def fail_chmod(*_args, **_kwargs):
        raise AssertionError('launch must not chmod an installed APE')

    monkeypatch.setattr(runtime.os, 'name', 'posix')
    monkeypatch.setattr(runtime.Path, 'chmod', fail_chmod)

    assert client._launch_command(['version']) == [
        '/bin/sh',
        '-c',
        'exec "$0" "$@"',
        executable,
        'version',
    ]


def test_python_runtime_streams_jsonl_events(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-events'

    PythonGenerator().generate(event_spec, fixture_ape_path, output_directory)

    runtime = import_generated(output_directory, 'ape_fixture._runtime')
    operation = event_operation_factory(str(event_writer_path))

    client = runtime.APEClient(
        Path(sys.executable),
        {'transfer': operation},
    )
    received = []

    try:
        session = client.invoke('transfer', {})
        session.on('progress', received.append)
        events = list(session.events())
        return_code = session.wait()

        assert session.result == 'https://example.test/events'
        assert return_code == 0

        assert received == [
            {'bytes_sent': 10, 'speed': 1.5},
            {'bytes_sent': 20},
        ]

        assert [(event.name, event.known) for event in events] == [
            ('progress', True),
            ('progress', True),
            ('future_event', False),
        ]
        assert events[-1].data['value'] == 42

        session.close()
    finally:
        clear_generated('ape_fixture')


def test_python_runtime_rejects_invalid_event_field_types(
    tmp_path: Path,
    fixture_ape_path: Path,
    event_spec,
    invalid_event_writer_path: Path,
    event_operation_factory,
):
    output_directory = tmp_path / 'generated-invalid-events'

    PythonGenerator().generate(event_spec, fixture_ape_path, output_directory)

    runtime = import_generated(output_directory, 'ape_fixture._runtime')
    operation = event_operation_factory(str(invalid_event_writer_path))

    client = runtime.APEClient(
        Path(sys.executable),
        {'transfer': operation},
    )

    try:
        session = client.invoke('transfer', {})

        with pytest.raises(runtime.APEEventError, match='must be integer'):
            list(session.events())

        with pytest.raises(runtime.APEEventError, match='must be integer'):
            session.close()
    finally:
        clear_generated('ape_fixture')
