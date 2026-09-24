#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import copy
from pathlib import Path

from attrs import evolve
import pytest
import yaml

from apebind.errors import SchemaError
from apebind.models import ExecutionMode
from apebind.schema import SchemaCodec


@pytest.mark.parametrize('suffix', ('.yaml', '.json'))
def test_schema_round_trip(tmp_path: Path, inspected_spec, suffix: str):
    codec = SchemaCodec()
    schema_path = tmp_path / f'fixture.apebind{suffix}'

    codec.dump(inspected_spec, schema_path)
    loaded = codec.load(schema_path)

    assert loaded == inspected_spec


def _replace_serve_operation(event_spec, **changes):
    return evolve(
        event_spec,
        operations=tuple(
            evolve(operation, **changes) if operation.name == 'serve' else operation
            for operation in event_spec.operations
        ),
    )


def test_unknown_fields_fail_fast(tmp_path: Path, inspected_spec):
    codec = SchemaCodec()
    data = codec.to_dict(inspected_spec)
    data['operatoins'] = []
    schema_path = tmp_path / 'bad.yaml'

    schema_path.write_text(yaml.safe_dump(data), encoding='utf-8')

    with pytest.raises(SchemaError, match='operatoins'):
        codec.load(schema_path)


def test_broken_operation_fails_validation(tmp_path: Path, inspected_spec):
    codec = SchemaCodec()
    data = copy.deepcopy(codec.to_dict(inspected_spec))
    data['operations'][0]['command'] = ['missing']
    schema_path = tmp_path / 'bad.yaml'

    schema_path.write_text(yaml.safe_dump(data), encoding='utf-8')

    with pytest.raises(SchemaError, match='unknown command'):
        codec.load(schema_path)


def test_string_boolean_is_rejected(tmp_path: Path, inspected_spec):
    codec = SchemaCodec()
    data = codec.to_dict(inspected_spec)
    data['commands'][0]['options'][0]['required'] = 'false'
    schema_path = tmp_path / 'bad-bool.yaml'

    schema_path.write_text(yaml.safe_dump(data), encoding='utf-8')

    with pytest.raises(SchemaError, match='bool'):
        codec.load(schema_path)


def test_camel_case_api_name_is_rejected(tmp_path: Path, inspected_spec):
    codec = SchemaCodec()
    data = codec.to_dict(inspected_spec)
    data['operations'][0]['name'] = 'rootCommand'
    schema_path = tmp_path / 'camel-case.yaml'

    schema_path.write_text(yaml.safe_dump(data), encoding='utf-8')

    with pytest.raises(SchemaError, match='snake_case'):
        codec.load(schema_path)


def test_event_schema_round_trip(event_spec, tmp_path: Path):
    codec = SchemaCodec()
    schema_path = tmp_path / 'events.apebind.yaml'

    codec.dump(event_spec, schema_path)
    loaded = codec.load(schema_path)

    assert loaded == event_spec


def test_events_require_persistent_execution(event_spec):
    spec = _replace_serve_operation(event_spec, execution=ExecutionMode.ONESHOT)

    with pytest.raises(SchemaError, match='events require persistent execution'):
        spec.validate()


def test_event_source_option_must_exist(event_spec):
    operation = next(operation for operation in event_spec.operations if operation.name == 'serve')

    events = evolve(
        operation.events,
        source=evolve(operation.events.source, option_flag='--missing-events'),
    )
    spec = _replace_serve_operation(event_spec, events=events)

    with pytest.raises(SchemaError, match='event option_flag must match exactly one option'):
        spec.validate()


def test_result_and_events_cannot_own_same_option(event_spec):
    operation = next(operation for operation in event_spec.operations if operation.name == 'serve')

    events = evolve(
        operation.events,
        source=evolve(operation.events.source, option_flag='--json'),
    )
    spec = _replace_serve_operation(event_spec, events=events)

    with pytest.raises(SchemaError, match='cannot own the same option flag'):
        spec.validate()
