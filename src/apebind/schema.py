#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from enum import IntEnum
from pathlib import Path
from typing import Any, TypeVar

import yaml
from cattrs import Converter, transform_error
from cattrs.errors import BaseValidationError

from .errors import SchemaError
from .models import APEBindSpec, EventSourceKind, ExecutionMode, ResultFormat, ValueType


enum_type_t = TypeVar('enum_type_t', bound=IntEnum)


class SchemaCodec:
    """Strict YAML/JSON serialization boundary for :class:`APEBindSpec`."""

    def __init__(self):
        self._converter = Converter(forbid_extra_keys=True)

        self._register_scalar_hooks()

        self._register_enum_hooks(ValueType)
        self._register_enum_hooks(ExecutionMode)
        self._register_enum_hooks(ResultFormat)
        self._register_enum_hooks(EventSourceKind)

    @staticmethod
    def _strict_string(value: Any, _type: Any) -> str:
        if not isinstance(value, str):
            raise TypeError('expected a string')

        return value

    @staticmethod
    def _strict_boolean(value: Any, _type: Any) -> bool:
        if not isinstance(value, bool):
            raise TypeError('expected a boolean')

        return value

    @staticmethod
    def _strict_integer(value: Any, _type: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError('expected an integer')

        return value

    @staticmethod
    def _strict_float(value: Any, _type: Any) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError('expected a number')

        return float(value)

    @classmethod
    def _structure_enum(cls, enum_type: type[enum_type_t], value: Any) -> enum_type_t:
        if not isinstance(value, str):
            raise TypeError(f'expected {enum_type.__name__} to be a string enum name')

        member_name = value.upper()
        if member_name not in enum_type.__members__:
            choices = ', '.join(name.lower() for name in enum_type.__members__)
            raise ValueError(f'invalid {enum_type.__name__}: {value}; expected one of: {choices}')

        return enum_type[member_name]

    def _register_scalar_hooks(self) -> None:
        self._converter.register_structure_hook(str, self._strict_string)
        self._converter.register_structure_hook(bool, self._strict_boolean)
        self._converter.register_structure_hook(int, self._strict_integer)
        self._converter.register_structure_hook(float, self._strict_float)

    def _register_enum_hooks(self, enum_type: type[enum_type_t]) -> None:
        self._converter.register_structure_hook(
            enum_type,
            lambda value, _type: self._structure_enum(enum_type, value),
        )
        self._converter.register_unstructure_hook(enum_type, lambda value: value.name.lower())

    @staticmethod
    def _read_data(path: Path) -> Any:
        with path.open('r', encoding='utf-8') as input_file:
            if path.suffix.lower() == '.json':
                return json.load(input_file)

            return yaml.safe_load(input_file)

    @staticmethod
    def _write_data(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('w', encoding='utf-8') as output_file:
            if path.suffix.lower() == '.json':
                json.dump(data, output_file, indent=2, ensure_ascii=False)
                output_file.write('\n')
                return

            yaml.safe_dump(data, output_file, sort_keys=False, allow_unicode=True)

    def from_dict(self, data: dict[str, Any]) -> APEBindSpec:
        try:
            spec = self._converter.structure(data, APEBindSpec)
        except BaseValidationError as error:
            details = '; '.join(transform_error(error))
            raise SchemaError(f'Invalid APEBind schema: {details}') from error
        except (TypeError, ValueError) as error:
            raise SchemaError(f'Invalid APEBind schema: {error}') from error

        spec.validate()

        return spec

    def to_dict(self, spec: APEBindSpec) -> dict[str, Any]:
        spec.validate()

        data = self._converter.unstructure(spec)

        if not isinstance(data, dict):
            raise SchemaError('APEBind schema did not serialize to a mapping')

        return data

    def load(self, path: Path) -> APEBindSpec:
        data = self._read_data(path)

        if not isinstance(data, dict):
            raise SchemaError('Schema root must be a mapping')

        return self.from_dict(data)

    def dump(self, spec: APEBindSpec, path: Path) -> None:
        self._write_data(path, self.to_dict(spec))
