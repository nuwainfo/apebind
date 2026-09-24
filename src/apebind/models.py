#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re

from enum import IntEnum
from pathlib import PurePath

from attrs import define, field

from .errors import SchemaError


class ValueType(IntEnum):
    STRING = 1
    INTEGER = 2
    FLOAT = 3
    PATH = 4
    BOOLEAN = 5


class ExecutionMode(IntEnum):
    ONESHOT = 1
    PERSISTENT = 2


class ResultFormat(IntEnum):
    COMMAND = 1
    TEXT = 2
    JSON = 3
    JSON_FILE = 4


class EventSourceKind(IntEnum):
    JSONL_FILE = 1


@define(frozen=True)
class PositionalSpec:
    name: str
    api_name: str
    value_type: ValueType = ValueType.STRING
    required: bool = True
    multiple: bool = False
    help: str = ''


@define(frozen=True)
class OptionSpec:
    flags: tuple[str, ...]
    api_name: str
    value_type: ValueType = ValueType.STRING
    required: bool = False
    multiple: bool = False
    value_optional: bool = False
    choices: tuple[str, ...] = ()
    help: str = ''

    @property
    def primary_flag(self) -> str:
        for flag_value in self.flags:
            if flag_value.startswith('--'):
                return flag_value

        return self.flags[0]


@define(frozen=True)
class CommandSpec:
    path: tuple[str, ...]
    summary: str = ''
    positionals: tuple[PositionalSpec, ...] = ()
    options: tuple[OptionSpec, ...] = ()


@define(frozen=True)
class ResultSpec:
    format: ResultFormat = ResultFormat.COMMAND
    field: str | None = None
    option_flag: str | None = None
    ready_timeout_seconds: float | None = None
    strip: bool = True


@define(frozen=True)
class ProcessSpec:
    timeout_seconds: float | None = None


@define(frozen=True)
class EventFieldSpec:
    name: str
    api_name: str
    value_type: ValueType = ValueType.STRING
    required: bool = True


@define(frozen=True)
class EventTypeSpec:
    name: str
    source_value: str | None = None
    fields: tuple[EventFieldSpec, ...] = ()

    @property
    def match_value(self) -> str:
        return self.name if self.source_value is None else self.source_value


@define(frozen=True)
class EventSourceSpec:
    kind: EventSourceKind
    option_flag: str


@define(frozen=True)
class EventSpec:
    source: EventSourceSpec
    discriminator: str = 'type'
    types: tuple[EventTypeSpec, ...] = ()


@define(frozen=True)
class OperationSpec:
    name: str
    command: tuple[str, ...]
    execution: ExecutionMode = ExecutionMode.ONESHOT
    result: ResultSpec = field(factory=ResultSpec)
    process: ProcessSpec = field(factory=ProcessSpec)
    events: EventSpec | None = None


@define(frozen=True)
class APESpec:
    name: str
    binary: str


@define(frozen=True)
class RuntimeSpec:
    env_unset: tuple[str, ...] = ()


@define(frozen=True)
class APEBindSpec:
    schema_version: int
    ape: APESpec
    commands: tuple[CommandSpec, ...]
    operations: tuple[OperationSpec, ...]
    runtime: RuntimeSpec = field(factory=RuntimeSpec)

    @classmethod
    def _validate_identifier(cls, value: str, label: str) -> None:
        if not re.fullmatch(r'[a-z_][a-z0-9_]*', value):
            raise SchemaError(f'{label} must be a snake_case identifier: {value}')

    @staticmethod
    def _validate_field_path(value: str, label: str) -> None:
        if not value or any(not part for part in value.split('.')):
            raise SchemaError(f'{label} must be a non-empty dotted path: {value!r}')

    @classmethod
    def _validate_command(
        cls,
        command: CommandSpec,
        commands_by_path: dict[tuple[str, ...], CommandSpec],
    ) -> None:
        if command.path and command.path[:-1] not in commands_by_path:
            raise SchemaError(f'Missing parent command for: {" ".join(command.path)}')

        api_names: set[str] = set()
        flags: set[str] = set()

        for positional in command.positionals:
            cls._validate_identifier(positional.api_name, 'positional api_name')

            if positional.api_name in api_names:
                raise SchemaError(
                    f'Duplicate api_name in command {command.path}: {positional.api_name}'
                )

            api_names.add(positional.api_name)

        for option in command.options:
            cls._validate_identifier(option.api_name, 'option api_name')

            if option.api_name in api_names:
                raise SchemaError(
                    f'Duplicate api_name in command {command.path}: {option.api_name}'
                )

            api_names.add(option.api_name)

            if not option.flags:
                raise SchemaError(f'Option {option.api_name} must define at least one flag')

            if option.value_type == ValueType.BOOLEAN and option.value_optional:
                raise SchemaError(
                    f'Boolean option cannot also have an optional value: {option.api_name}'
                )

            for flag_value in option.flags:
                if flag_value in flags:
                    raise SchemaError(
                        f'Duplicate option flag in command {command.path}: {flag_value}'
                    )

                flags.add(flag_value)

    @classmethod
    def _validate_result(
        cls,
        operation: OperationSpec,
        commands_by_path: dict[tuple[str, ...], CommandSpec],
    ) -> None:
        if operation.execution == ExecutionMode.PERSISTENT and operation.result.format not in (
            ResultFormat.COMMAND,
            ResultFormat.JSON_FILE,
        ):
            raise SchemaError('Persistent operations support only command or json_file results')

        if operation.result.format != ResultFormat.JSON_FILE:
            return

        if not operation.result.option_flag:
            raise SchemaError(f'Operation {operation.name} json_file result requires option_flag')

        matches = cls._find_option_matches(
            operation.command,
            operation.result.option_flag,
            commands_by_path,
        )
        if len(matches) != 1:
            raise SchemaError(
                f'Operation {operation.name} option_flag must match exactly one option: '
                f'{operation.result.option_flag}'
            )

    @classmethod
    def _validate_events(
        cls,
        operation: OperationSpec,
        commands_by_path: dict[tuple[str, ...], CommandSpec],
    ) -> None:
        events = operation.events
        if events is None:
            return

        if operation.execution != ExecutionMode.PERSISTENT:
            raise SchemaError(f'Operation {operation.name} events require persistent execution')

        cls._validate_field_path(
            events.discriminator,
            f'Operation {operation.name} events.discriminator',
        )

        if events.source.kind != EventSourceKind.JSONL_FILE:
            raise SchemaError(
                f'Operation {operation.name} has unsupported event source: '
                f'{events.source.kind.name.lower()}'
            )

        matches = cls._find_option_matches(
            operation.command,
            events.source.option_flag,
            commands_by_path,
        )
        if len(matches) != 1:
            raise SchemaError(
                f'Operation {operation.name} event option_flag must match exactly one option: '
                f'{events.source.option_flag}'
            )

        if (
            operation.result.format == ResultFormat.JSON_FILE
            and operation.result.option_flag == events.source.option_flag
        ):
            raise SchemaError(
                f'Operation {operation.name} result and events cannot own the same option flag'
            )

        event_names: set[str] = set()
        source_values: set[str] = set()

        for event_type in events.types:
            cls._validate_identifier(event_type.name, 'event type name')
            if event_type.name in event_names:
                raise SchemaError(
                    f'Operation {operation.name} has duplicate event type: {event_type.name}'
                )

            event_names.add(event_type.name)
            if not event_type.match_value:
                raise SchemaError(
                    f'Operation {operation.name} event source_value must not be empty'
                )

            if event_type.match_value in source_values:
                raise SchemaError(
                    f'Operation {operation.name} has duplicate event source_value: '
                    f'{event_type.match_value}'
                )

            source_values.add(event_type.match_value)
            field_names: set[str] = set()

            for event_field in event_type.fields:
                cls._validate_field_path(
                    event_field.name,
                    f'Operation {operation.name} event field name',
                )
                cls._validate_identifier(event_field.api_name, 'event field api_name')
                if event_field.api_name in field_names:
                    raise SchemaError(
                        f'Operation {operation.name} event {event_type.name} has duplicate '
                        f'field api_name: {event_field.api_name}'
                    )

                field_names.add(event_field.api_name)

    @classmethod
    def _validate_operation(
        cls,
        operation: OperationSpec,
        commands_by_path: dict[tuple[str, ...], CommandSpec],
    ) -> None:
        cls._validate_identifier(operation.name, 'operation name')

        if operation.command not in commands_by_path:
            raise SchemaError(f'Operation references unknown command: {operation.command}')

        if operation.process.timeout_seconds is not None:
            if operation.process.timeout_seconds <= 0:
                raise SchemaError(
                    f'Operation {operation.name} process.timeout_seconds must be positive'
                )

            if operation.execution != ExecutionMode.ONESHOT:
                raise SchemaError(
                    f'Operation {operation.name} process.timeout_seconds is only valid for oneshot'
                )

        cls._validate_result(operation, commands_by_path)
        cls._validate_events(operation, commands_by_path)

    @staticmethod
    def _find_option_matches(
        command_path: tuple[str, ...],
        option_flag: str,
        commands_by_path: dict[tuple[str, ...], CommandSpec],
    ) -> list[OptionSpec]:
        matches: list[OptionSpec] = []

        for depth in range(len(command_path) + 1):
            command = commands_by_path[command_path[:depth]]

            for option in command.options:
                if option_flag in option.flags:
                    matches.append(option)

        return matches

    def validate(self) -> None:
        if self.schema_version != 1:
            raise SchemaError(f'Unsupported schema_version: {self.schema_version}')

        if not self.ape.name:
            raise SchemaError('ape.name must not be empty')

        if PurePath(self.ape.binary).name != self.ape.binary:
            raise SchemaError('ape.binary must be a file name, not a path')

        for env_name in self.runtime.env_unset:
            if not env_name or '=' in env_name or '\x00' in env_name:
                raise SchemaError(f'Invalid runtime env_unset entry: {env_name!r}')

        commands_by_path = {command.path: command for command in self.commands}

        if len(commands_by_path) != len(self.commands):
            raise SchemaError('Duplicate command path')

        if () not in commands_by_path:
            raise SchemaError('Root command path [] is required')

        for command in self.commands:
            self._validate_command(command, commands_by_path)

        operation_names: set[str] = set()

        for operation in self.operations:
            if operation.name in operation_names:
                raise SchemaError(f'Duplicate operation name: {operation.name}')

            operation_names.add(operation.name)
            self._validate_operation(operation, commands_by_path)
