#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import pytest

from apebind.backends.java import JavaGenerator
from apebind.backends.node import NodeGenerator
from apebind.backends.python import PythonGenerator
from apebind.errors import GenerationError
from apebind.generation_model import BindingModelBuilder
from apebind.models import OperationSpec, ResultFormat, ResultSpec


def _spec_with_operation(inspected_spec, operation_name: str):
    operation = OperationSpec(
        operation_name,
        ('echo',),
        result=ResultSpec(ResultFormat.TEXT),
    )

    return inspected_spec.__class__(
        schema_version=inspected_spec.schema_version,
        ape=inspected_spec.ape.__class__('keyword_fixture', 'fixture.com'),
        commands=inspected_spec.commands,
        operations=(operation,),
    )


def test_binding_model_is_language_neutral(inspected_spec):
    model = BindingModelBuilder.build(inspected_spec)

    assert model.distribution_name == inspected_spec.ape.name
    assert model.binary_name == inspected_spec.ape.binary
    assert [operation.name for operation in model.operations] == [
        operation.name for operation in inspected_spec.operations
    ]

    echo = next(operation for operation in model.operations if operation.name == 'echo')

    assert [parameter.api_name for parameter in echo.parameters] == [
        'text',
        'verbose',
        'upper',
        'repeat',
    ]
    assert echo.metadata['command_path'] == ['echo']
    assert echo.metadata['levels'][1]['token'] == 'echo'


def test_reserved_words_are_backend_specific(
    tmp_path,
    fixture_ape_path,
    inspected_spec,
):
    spec = _spec_with_operation(inspected_spec, 'lambda')

    spec.validate()

    with pytest.raises(GenerationError, match='Invalid Python operation name'):
        PythonGenerator().generate(spec, fixture_ape_path, tmp_path / 'python')

    NodeGenerator().generate(spec, fixture_ape_path, tmp_path / 'node')

    client_source = (tmp_path / 'node' / 'src' / 'client.js').read_text(encoding='utf-8')

    assert 'export async function lambda' in client_source


def test_java_reserved_words_are_backend_specific(
    tmp_path,
    fixture_ape_path,
    inspected_spec,
):
    spec = _spec_with_operation(inspected_spec, 'synchronized')

    spec.validate()

    PythonGenerator().generate(spec, fixture_ape_path, tmp_path / 'python-java-keyword')
    NodeGenerator().generate(spec, fixture_ape_path, tmp_path / 'node-java-keyword')

    with pytest.raises(GenerationError, match='Java operation name is reserved'):
        JavaGenerator().generate(spec, fixture_ape_path, tmp_path / 'java')


def test_binding_model_carries_event_semantics(event_spec):
    model = BindingModelBuilder.build(event_spec)
    serve = next(operation for operation in model.operations if operation.name == 'serve')

    assert serve.events is not None
    assert serve.events.source_kind == 'jsonl_file'
    assert serve.events.option_flag == '--events'
    assert serve.events.discriminator == 'event'
    assert [event_type.name for event_type in serve.events.types] == [
        'progress',
        'completed',
    ]
    assert serve.metadata['events']['types'][0]['fields'][0] == {
        'name': 'payload.bytes',
        'api_name': 'bytes_sent',
        'value_type': 'integer',
        'required': True,
    }

    event_option = next(
        option
        for level in serve.metadata['levels']
        for option in level['options']
        if option['primary_flag'] == '--events'
    )

    assert event_option['runtime_owned'] is True
    assert event_option['runtime_role'] == 'events'
    assert all(parameter.api_name != 'events' for parameter in serve.parameters)
