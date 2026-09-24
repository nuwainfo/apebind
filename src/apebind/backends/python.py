#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import keyword

from pathlib import Path
from typing import Any

from ..errors import GenerationError
from ..generation_model import BindingModel, OperationModel, ParameterModel
from ..models import APEBindSpec, ValueType
from ..naming import to_snake_case_identifier
from ..template_backend import TemplateLanguageBackend


class PythonGenerator(TemplateLanguageBackend):
    """Generate a standalone Python package with a bundled APE runtime."""

    def __init__(self):
        super().__init__('python')

    @property
    def name(self) -> str:
        return 'python'

    @property
    def aliases(self) -> tuple[str, ...]:
        return ('py',)

    @staticmethod
    def _parameter_declaration(parameter: dict[str, Any]) -> str:
        name = parameter['name']
        if not name.isidentifier() or keyword.iskeyword(name):
            raise GenerationError(f'Invalid Python parameter name: {name}')

        if parameter['required']:
            return name

        return f"{name}={parameter.get('default', 'None')}"

    @staticmethod
    def _normalize_package_name(value: str) -> str:
        normalized = to_snake_case_identifier(value, fallback='ape')
        if not normalized:
            raise GenerationError('APE name cannot produce an empty Python package name')

        return normalized

    @classmethod
    def _parameter_context(cls, parameter: ParameterModel) -> dict[str, Any]:
        default_value = 'None'
        if parameter.option and parameter.value_type == ValueType.BOOLEAN:
            default_value = 'False'

        context = {
            'name': parameter.api_name,
            'required': parameter.required,
            'multiple': parameter.multiple,
        }
        if parameter.option:
            context['default'] = default_value

        context['declaration'] = cls._parameter_declaration(context)

        return context

    @classmethod
    def _operation_context(cls, operation: OperationModel) -> dict[str, Any]:
        if not operation.name.isidentifier() or keyword.iskeyword(operation.name):
            raise GenerationError(f'Invalid Python operation name: {operation.name}')

        return {
            'name': operation.name,
            'parameters': [
                cls._parameter_context(parameter)
                for parameter in operation.parameters
            ],
            'persistent': operation.persistent,
            'metadata': operation.metadata,
        }

    @classmethod
    def _context(cls, model: BindingModel) -> dict[str, Any]:
        package_name = cls._normalize_package_name(model.distribution_name)
        operations = [cls._operation_context(operation) for operation in model.operations]

        return {
            'package_name': package_name,
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
        package_directory = output_directory / 'src' / context['package_name']

        self._render('pyproject.toml.j2', output_directory / 'pyproject.toml', context)
        self._render('generated_readme.md.j2', output_directory / 'README.md', context)
        self._render('__init__.py.j2', package_directory / '__init__.py', context)
        self._render('client.py.j2', package_directory / '_generated.py', context)

        self._render('runtime.py.j2', package_directory / '_runtime.py', context)
        self._render('py.typed.j2', package_directory / 'py.typed', context)

        self._copy_ape(
            ape_path,
            package_directory / 'bin' / model.binary_name,
        )
