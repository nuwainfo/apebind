#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re

from copy import deepcopy
from pathlib import Path
from typing import Any

from ..errors import GenerationError
from ..generation_model import BindingModel, EventModel, OperationModel, ParameterModel
from ..models import APEBindSpec, ValueType
from ..naming import to_camel_case_identifier, to_pascal_case_identifier
from ..template_backend import TemplateLanguageBackend


_JS_RESERVED_WORDS = {
    'await',
    'break',
    'case',
    'catch',
    'class',
    'const',
    'continue',
    'debugger',
    'default',
    'delete',
    'do',
    'else',
    'enum',
    'export',
    'extends',
    'false',
    'finally',
    'for',
    'function',
    'if',
    'implements',
    'import',
    'in',
    'instanceof',
    'interface',
    'let',
    'new',
    'null',
    'package',
    'private',
    'protected',
    'public',
    'return',
    'static',
    'super',
    'switch',
    'this',
    'throw',
    'true',
    'try',
    'typeof',
    'var',
    'void',
    'while',
    'with',
    'yield',
}


class NodeGenerator(TemplateLanguageBackend):
    """Generate a dependency-free ESM Node.js package with TypeScript declarations."""

    def __init__(self):
        super().__init__('node')

    @property
    def name(self) -> str:
        return 'node'

    @property
    def aliases(self) -> tuple[str, ...]:
        return ('javascript', 'js', 'nodejs')

    @staticmethod
    def _normalize_package_name(value: str) -> str:
        normalized = re.sub(r'[^a-z0-9._~-]+', '-', value.lower()).strip('-')
        if not normalized:
            raise GenerationError('APE name cannot produce an empty npm package name')

        return normalized

    @staticmethod
    def _validate_js_identifier(value: str, label: str) -> None:
        if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*', value):
            raise GenerationError(f'Invalid JavaScript {label}: {value}')

        if value in _JS_RESERVED_WORDS:
            raise GenerationError(f'JavaScript {label} is reserved: {value}')

    @staticmethod
    def _typescript_base_type(value_type: ValueType) -> str:
        if value_type in (ValueType.INTEGER, ValueType.FLOAT):
            return 'number'

        if value_type == ValueType.BOOLEAN:
            return 'boolean'

        return 'string'

    @classmethod
    def _parameter_context(cls, parameter: ParameterModel) -> dict[str, Any]:
        name = to_camel_case_identifier(parameter.api_name)
        base_type = cls._typescript_base_type(parameter.value_type)
        if parameter.value_optional:
            type_name = f'boolean | {base_type}'
        elif parameter.multiple:
            type_name = f'{base_type} | readonly {base_type}[]'
        else:
            type_name = base_type

        return {
            'source_name': parameter.api_name,
            'name': name,
            'required': parameter.required,
            'type_name': type_name,
        }

    @classmethod
    def _event_context(
        cls,
        operation: OperationModel,
        events: EventModel | None,
    ) -> dict[str, Any] | None:
        if events is None:
            return None

        event_types = []

        for event_type in events.types:
            event_name = to_camel_case_identifier(event_type.name)
            cls._validate_js_identifier(event_name, 'event name')
            event_types.append(
                {
                    'source_name': event_type.name,
                    'name': event_name,
                    'source_value': event_type.source_value,
                    'type_name': (
                        f'{to_pascal_case_identifier(operation.name)}'
                        f'{to_pascal_case_identifier(event_type.name)}Event'
                    ),
                    'fields': [
                        {
                            'source_name': event_field.api_name,
                            'name': to_camel_case_identifier(event_field.api_name),
                            'type_name': cls._typescript_base_type(event_field.value_type),
                            'required': event_field.required,
                        }
                        for event_field in event_type.fields
                    ],
                }
            )

        return {
            'map_type_name': f'{to_pascal_case_identifier(operation.name)}EventMap',
            'types': event_types,
        }

    @classmethod
    def _metadata_context(
        cls,
        operation: OperationModel,
        parameter_names: dict[str, str],
        event_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        metadata = deepcopy(operation.metadata)

        for level in metadata['levels']:
            for positional in level['positionals']:
                positional['api_name'] = parameter_names[positional['api_name']]

            for option in level['options']:
                api_name = option['api_name']
                if option['runtime_owned']:
                    continue

                option['api_name'] = parameter_names[api_name]

        if event_context is None:
            return metadata

        event_names = {
            event_type['source_name']: event_type['name']
            for event_type in event_context['types']
        }
        event_fields = {
            event_type['source_name']: {
                event_field['source_name']: event_field['name']
                for event_field in event_type['fields']
            }
            for event_type in event_context['types']
        }

        for event_type in metadata['events']['types']:
            source_name = event_type['name']
            event_type['name'] = event_names[source_name]

            for event_field in event_type['fields']:
                event_field['api_name'] = event_fields[source_name][event_field['api_name']]

        return metadata

    @classmethod
    def _operation_context(cls, operation: OperationModel) -> dict[str, Any]:
        name = to_camel_case_identifier(operation.name)
        cls._validate_js_identifier(name, 'operation name')

        parameters = [
            cls._parameter_context(parameter)
            for parameter in operation.parameters
        ]
        parameter_names = {
            parameter['source_name']: parameter['name']
            for parameter in parameters
        }
        events = cls._event_context(operation, operation.events)
        metadata = cls._metadata_context(operation, parameter_names, events)
        result_format = metadata['result']['format']
        if metadata['execution'] == 'persistent':
            if events is None:
                result_type = 'ProcessSession'
            else:
                result_type = f"ProcessSession<{events['map_type_name']}>"
        elif result_format == 'command':
            result_type = 'APEProcessResult'
        elif result_format == 'text':
            result_type = 'string'
        else:
            result_type = 'unknown'

        return {
            'source_name': operation.name,
            'name': name,
            'type_name': f'{to_pascal_case_identifier(operation.name)}Parameters',
            'parameters': parameters,
            'has_required_parameters': any(item['required'] for item in parameters),
            'result_type': result_type,
            'events': events,
            'metadata': metadata,
        }

    @classmethod
    def _context(cls, model: BindingModel) -> dict[str, Any]:
        operations = [cls._operation_context(operation) for operation in model.operations]

        return {
            'package_name': cls._normalize_package_name(model.distribution_name),
            'distribution_name': model.distribution_name,
            'binary_name': model.binary_name,
            'operations': operations,
            'operations_json': json.dumps(
                {item['name']: item['metadata'] for item in operations},
                indent=2,
            ),
            'runtime_json': json.dumps(
                {
                    'env_unset': list(model.env_unset),
                },
                indent=2,
            ),
        }

    def generate(self, spec: APEBindSpec, ape_path: Path, output_directory: Path) -> None:
        model = self._prepare(spec, ape_path)
        context = self._context(model)
        source_directory = output_directory / 'src'

        self._render('package.json.j2', output_directory / 'package.json', context)
        self._render('generated_readme.md.j2', output_directory / 'README.md', context)
        self._render('index.js.j2', source_directory / 'index.js', context)
        self._render('index.d.ts.j2', source_directory / 'index.d.ts', context)
        self._render('client.js.j2', source_directory / 'client.js', context)
        self._render('client.d.ts.j2', source_directory / 'client.d.ts', context)

        self._render('runtime.js.j2', source_directory / '_runtime.js', context)
        self._render('runtime.d.ts.j2', source_directory / '_runtime.d.ts', context)

        self._copy_ape(ape_path, source_directory / 'bin' / model.binary_name)
