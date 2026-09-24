#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import os
from pathlib import Path

import pytest

from apebind.inspector import APEInspector
from apebind.models import (
    EventFieldSpec,
    EventSourceKind,
    EventSourceSpec,
    EventSpec,
    EventTypeSpec,
    ExecutionMode,
    OptionSpec,
    ResultFormat,
    ResultSpec,
    ValueType,
)


@pytest.fixture(scope='session')
def fixture_ape_path() -> Path:
    path = Path(__file__).parent / 'fixtures' / 'ape_fixture.com'
    if not path.is_file():
        pytest.fail(
            'APE fixture is missing. Run python scripts/build_ape_fixture.py '
            'or python scripts/bootstrap.py before running tests.'
        )

    if os.name != 'nt':
        path.chmod(0o755)

    return path


@pytest.fixture(scope='session')
def inspected_spec(fixture_ape_path: Path):
    return APEInspector(fixture_ape_path).inspect()


@pytest.fixture
def event_spec(inspected_spec):
    event_option = OptionSpec(
        flags=('--events',),
        api_name='events',
        value_type=ValueType.PATH,
        required=True,
        help='Write events as JSONL.',
    )

    commands = tuple(
        command.__class__(
            path=command.path,
            summary=command.summary,
            positionals=command.positionals,
            options=(*command.options, event_option),
        )
        if command.path == ('serve',)
        else command
        for command in inspected_spec.commands
    )

    events = EventSpec(
        source=EventSourceSpec(EventSourceKind.JSONL_FILE, '--events'),
        discriminator='event',
        types=(
            EventTypeSpec(
                name='progress',
                source_value='upload_progress',
                fields=(
                    EventFieldSpec(
                        name='payload.bytes',
                        api_name='bytes_sent',
                        value_type=ValueType.INTEGER,
                    ),
                    EventFieldSpec(
                        name='payload.speed',
                        api_name='speed',
                        value_type=ValueType.FLOAT,
                        required=False,
                    ),
                ),
            ),
            EventTypeSpec(name='completed'),
        ),
    )

    operations = tuple(
        operation.__class__(
            name=operation.name,
            command=operation.command,
            execution=ExecutionMode.PERSISTENT,
            result=ResultSpec(
                format=ResultFormat.JSON_FILE,
                option_flag='--json',
                field='link',
                ready_timeout_seconds=2,
            ),
            process=operation.process,
            events=events,
        )
        if operation.name == 'serve'
        else operation
        for operation in inspected_spec.operations
    )

    return inspected_spec.__class__(
        schema_version=inspected_spec.schema_version,
        ape=inspected_spec.ape,
        commands=commands,
        operations=operations,
        runtime=inspected_spec.runtime,
    )


@pytest.fixture
def event_writer_path(tmp_path: Path) -> Path:
    helper_path = tmp_path / 'event_writer.py'
    helper_path.write_text(
        '''
import argparse
import json
import time
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--json', required=True)
parser.add_argument('--events', required=True)
arguments = parser.parse_args()

Path(arguments.json).write_text(
    json.dumps({'link': 'https://example.test/events'}),
    encoding='utf-8',
)

time.sleep(0.05)

with Path(arguments.events).open('a', encoding='utf-8') as output_file:
    output_file.write(json.dumps({
        'event': 'upload_progress',
        'payload': {'bytes': 10, 'speed': 1.5},
    }) + '\\n')
    output_file.flush()

    time.sleep(0.05)

    output_file.write(json.dumps({
        'event': 'upload_progress',
        'payload': {'bytes': 20},
    }) + '\\n')
    output_file.write(json.dumps({
        'event': 'future_event',
        'value': 42,
    }) + '\\n')
    output_file.flush()

time.sleep(0.05)
'''.lstrip(),
        encoding='utf-8',
    )

    return helper_path


@pytest.fixture
def invalid_event_writer_path(tmp_path: Path) -> Path:
    helper_path = tmp_path / 'invalid_event_writer.py'
    helper_path.write_text(
        """
import argparse
import json
import time
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--json', required=True)
parser.add_argument('--events', required=True)
arguments = parser.parse_args()

Path(arguments.json).write_text(
    json.dumps({'link': 'https://example.test/events'}),
    encoding='utf-8',
)

time.sleep(0.05)

with Path(arguments.events).open('a', encoding='utf-8') as output_file:
    output_file.write(json.dumps({
        'event': 'upload_progress',
        'payload': {'bytes': 'not-an-integer'},
    }) + '\\n')
    output_file.flush()

time.sleep(0.05)
""".lstrip(),
        encoding='utf-8',
    )

    return helper_path


@pytest.fixture
def event_operation_factory():
    def create(command_token: str, *, bytes_api_name: str = 'bytes_sent'):
        return {
            'command_path': [command_token],
            'execution': 'persistent',
            'process': {'timeout_seconds': None},
            'result': {
                'format': 'json_file',
                'field': 'link',
                'option_flag': '--json',
                'ready_timeout_seconds': 2,
                'strip': True,
            },
            'events': {
                'source': {
                    'kind': 'jsonl_file',
                    'option_flag': '--events',
                },
                'discriminator': 'event',
                'types': [
                    {
                        'name': 'progress',
                        'source_value': 'upload_progress',
                        'fields': [
                            {
                                'name': 'payload.bytes',
                                'api_name': bytes_api_name,
                                'value_type': 'integer',
                                'required': True,
                            },
                            {
                                'name': 'payload.speed',
                                'api_name': 'speed',
                                'value_type': 'float',
                                'required': False,
                            },
                        ],
                    },
                ],
            },
            'levels': [
                {
                    'path': [],
                    'token': None,
                    'positionals': [],
                    'options': [],
                },
                {
                    'path': [command_token],
                    'token': command_token,
                    'positionals': [],
                    'options': [
                        {
                            'flags': ['--json'],
                            'primary_flag': '--json',
                            'api_name': 'json',
                            'boolean': False,
                            'required': True,
                            'multiple': False,
                            'value_optional': False,
                            'runtime_owned': True,
                        },
                        {
                            'flags': ['--events'],
                            'primary_flag': '--events',
                            'api_name': 'events',
                            'boolean': False,
                            'required': True,
                            'multiple': False,
                            'value_optional': False,
                            'runtime_owned': True,
                            'runtime_role': 'events',
                        },
                    ],
                },
            ],
        }

    return create
