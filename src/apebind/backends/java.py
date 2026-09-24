#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re

from pathlib import Path
from typing import Any

from ..errors import GenerationError
from ..generation_model import BindingModel, EventModel, OperationModel, ParameterModel
from ..models import APEBindSpec, ValueType
from ..naming import to_camel_case_identifier, to_pascal_case_identifier, to_snake_case_identifier
from ..template_backend import TemplateLanguageBackend


_JAVA_RESERVED_WORDS = {
    '_',
    'abstract',
    'assert',
    'boolean',
    'break',
    'byte',
    'case',
    'catch',
    'char',
    'class',
    'const',
    'continue',
    'default',
    'do',
    'double',
    'else',
    'enum',
    'exports',
    'extends',
    'false',
    'final',
    'finally',
    'float',
    'for',
    'goto',
    'if',
    'implements',
    'import',
    'instanceof',
    'int',
    'interface',
    'long',
    'module',
    'native',
    'new',
    'non-sealed',
    'null',
    'open',
    'opens',
    'package',
    'permits',
    'private',
    'protected',
    'provides',
    'public',
    'record',
    'requires',
    'return',
    'sealed',
    'short',
    'static',
    'strictfp',
    'super',
    'switch',
    'synchronized',
    'this',
    'throw',
    'throws',
    'to',
    'transient',
    'transitive',
    'true',
    'try',
    'uses',
    'var',
    'void',
    'volatile',
    'while',
    'with',
    'yield',
}


class JavaGenerator(TemplateLanguageBackend):
    """Generate a dependency-free Java 17 Maven project with a bundled APE."""

    def __init__(self):
        super().__init__('java')

    @property
    def name(self) -> str:
        return 'java'

    @property
    def aliases(self) -> tuple[str, ...]:
        return ('jvm',)

    @staticmethod
    def _normalize_artifact_name(value: str) -> str:
        normalized = re.sub(r'[^a-z0-9._-]+', '-', value.lower()).strip('-')

        if not normalized:
            raise GenerationError('APE name cannot produce an empty Maven artifact name')

        return normalized

    @staticmethod
    def _package_segment(value: str) -> str:
        segment = to_snake_case_identifier(value, fallback='ape').lower()

        if segment in _JAVA_RESERVED_WORDS:
            segment = f'{segment}_binding'

        if not re.fullmatch(r'[a-z_][a-z0-9_]*', segment):
            raise GenerationError(f'Invalid Java package segment: {segment}')

        return segment

    @staticmethod
    def _validate_java_identifier(value: str, label: str) -> None:
        if not re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$]*', value):
            raise GenerationError(f'Invalid Java {label}: {value}')

        if value in _JAVA_RESERVED_WORDS:
            raise GenerationError(f'Java {label} is reserved: {value}')

    @staticmethod
    def _java_base_type(value_type: ValueType) -> str:
        if value_type == ValueType.INTEGER:
            return 'Long'
        if value_type == ValueType.FLOAT:
            return 'Double'
        if value_type == ValueType.PATH:
            return 'Path'
        if value_type == ValueType.BOOLEAN:
            return 'Boolean'

        return 'String'

    @classmethod
    def _parameter_context(cls, parameter: ParameterModel) -> dict[str, Any]:
        name = to_camel_case_identifier(parameter.api_name)
        cls._validate_java_identifier(name, 'parameter name')
        base_type = cls._java_base_type(parameter.value_type)

        if parameter.value_optional:
            field_type = f'OptionalValue<{base_type}>'
        elif parameter.multiple:
            field_type = f'List<{base_type}>'
        else:
            field_type = base_type

        return {
            'source_name': parameter.api_name,
            'name': name,
            'base_type': base_type,
            'field_type': field_type,
            'required': parameter.required,
            'multiple': parameter.multiple,
            'value_optional': parameter.value_optional,
        }

    @classmethod
    def _event_context(cls, events: EventModel | None) -> dict[str, Any] | None:
        if events is None:
            return None

        return {
            'types': [
                {
                    'source_name': event_type.name,
                    'name': to_camel_case_identifier(event_type.name),
                    'fields': [
                        {
                            'source_name': event_field.api_name,
                            'name': to_camel_case_identifier(event_field.api_name),
                        }
                        for event_field in event_type.fields
                    ],
                }
                for event_type in events.types
            ],
        }

    @classmethod
    def _event_metadata(
        cls,
        metadata: dict[str, Any],
        event_context: dict[str, Any] | None,
    ) -> dict[str, Any]:
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

        metadata = json.loads(json.dumps(metadata))

        for event_type in metadata['events']['types']:
            source_name = event_type['name']
            event_type['name'] = event_names[source_name]

            for event_field in event_type['fields']:
                event_field['api_name'] = event_fields[source_name][event_field['api_name']]

        return metadata

    @classmethod
    def _operation_context(cls, operation: OperationModel) -> dict[str, Any]:
        name = to_camel_case_identifier(operation.name)
        cls._validate_java_identifier(name, 'operation name')
        type_name = f'{to_pascal_case_identifier(operation.name)}Parameters'
        cls._validate_java_identifier(type_name, 'parameter type')
        events = cls._event_context(operation.events)
        metadata = cls._event_metadata(operation.metadata, events)
        result_format = metadata['result']['format']

        if metadata['execution'] == 'persistent':
            result_type = 'ProcessSession'
        elif result_format == 'command':
            result_type = 'APEProcessResult'
        elif result_format == 'text':
            result_type = 'String'
        else:
            result_type = 'Object'

        return {
            'source_name': operation.name,
            'name': name,
            'type_name': type_name,
            'execution': metadata['execution'],
            'parameters': [
                cls._parameter_context(parameter)
                for parameter in operation.parameters
            ],
            'result_type': result_type,
            'events': events,
            'metadata': metadata,
        }

    @classmethod
    def _context(cls, model: BindingModel) -> dict[str, Any]:
        package_segment = cls._package_segment(model.distribution_name)
        package_name = f'apebind.generated.{package_segment}'
        binding_class = f'{to_pascal_case_identifier(model.distribution_name)}Binding'
        cls._validate_java_identifier(binding_class, 'binding class')
        operations = [cls._operation_context(operation) for operation in model.operations]

        return {
            'artifact_name': cls._normalize_artifact_name(model.distribution_name),
            'distribution_name': model.distribution_name,
            'binary_name': model.binary_name,
            'package_name': package_name,
            'package_path': package_name.replace('.', '/'),
            'binding_class': binding_class,
            'operations': operations,
            'operations_json': json.dumps(
                {item['source_name']: item['metadata'] for item in operations},
                indent=2,
            ),
            'runtime_json': json.dumps(
                {'env_unset': list(model.env_unset)},
                indent=2,
            ),
        }

    def generate(self, spec: APEBindSpec, ape_path: Path, output_directory: Path) -> None:
        model = self._prepare(spec, ape_path)
        context = self._context(model)
        source_directory = (
            output_directory
            / 'src'
            / 'main'
            / 'java'
            / context['package_path']
        )
        resource_directory = output_directory / 'src' / 'main' / 'resources' / 'apebind'

        self._render('pom.xml.j2', output_directory / 'pom.xml', context)
        self._render('generated_readme.md.j2', output_directory / 'README.md', context)

        templates = [
            ('binding.java.j2', f"{context['binding_class']}.java"),
            ('ape_process_result.java.j2', 'APEProcessResult.java'),
            ('ape_process_exception.java.j2', 'APEProcessException.java'),
            ('ape_timeout_exception.java.j2', 'APETimeoutException.java'),
            ('ape_event.java.j2', 'APEEvent.java'),
            ('ape_event_exception.java.j2', 'APEEventException.java'),
            ('jsonl_file_event_channel.java.j2', 'JSONLFileEventChannel.java'),
            ('optional_value.java.j2', 'OptionalValue.java'),
            ('process_session.java.j2', 'ProcessSession.java'),
            ('ape_client.java.j2', 'APEClient.java'),
            ('binary_resource.java.j2', 'BinaryResource.java'),
            ('json.java.j2', 'Json.java'),
        ]

        for template_name, file_name in templates:
            self._render(template_name, source_directory / file_name, context)

        self._copy_ape(ape_path, resource_directory / model.binary_name)
