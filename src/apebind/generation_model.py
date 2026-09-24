#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from attrs import define

from .errors import GenerationError
from .models import (
    APEBindSpec,
    CommandSpec,
    EventSpec,
    OperationSpec,
    ResultFormat,
    ValueType,
)


@define(frozen=True)
class ParameterModel:
    api_name: str
    value_type: ValueType
    required: bool
    multiple: bool
    value_optional: bool = False
    option: bool = False


@define(frozen=True)
class EventFieldModel:
    name: str
    api_name: str
    value_type: ValueType
    required: bool


@define(frozen=True)
class EventTypeModel:
    name: str
    source_value: str
    fields: tuple[EventFieldModel, ...]


@define(frozen=True)
class EventModel:
    source_kind: str
    option_flag: str
    discriminator: str
    types: tuple[EventTypeModel, ...]


@define(frozen=True)
class OperationModel:
    name: str
    parameters: tuple[ParameterModel, ...]
    events: EventModel | None
    persistent: bool
    metadata: dict[str, Any]


@define(frozen=True)
class BindingModel:
    distribution_name: str
    binary_name: str
    env_unset: tuple[str, ...]
    operations: tuple[OperationModel, ...]


class BindingModelBuilder:
    """Build language-neutral code generation data from a validated schema."""

    @staticmethod
    def _runtime_option_role(
        operation: OperationSpec,
        option_flags: tuple[str, ...],
    ) -> str | None:
        if (
            operation.result.format == ResultFormat.JSON_FILE
            and operation.result.option_flag in option_flags
        ):
            return 'result'

        if operation.events is not None and operation.events.source.option_flag in option_flags:
            return 'events'

        return None

    @classmethod
    def _level_metadata(
        cls,
        command: CommandSpec,
        operation: OperationSpec,
    ) -> dict[str, Any]:
        options = []

        for item in command.options:
            runtime_role = cls._runtime_option_role(operation, item.flags)
            metadata = {
                'flags': list(item.flags),
                'primary_flag': item.primary_flag,
                'api_name': item.api_name,
                'boolean': item.value_type == ValueType.BOOLEAN,
                'required': item.required,
                'multiple': item.multiple,
                'value_optional': item.value_optional,
                'runtime_owned': runtime_role is not None,
            }
            if runtime_role == 'events':
                metadata['runtime_role'] = runtime_role

            options.append(metadata)

        return {
            'path': list(command.path),
            'token': command.path[-1] if command.path else None,
            'positionals': [
                {
                    'api_name': item.api_name,
                    'required': item.required,
                    'multiple': item.multiple,
                }
                for item in command.positionals
            ],
            'options': options,
        }

    @classmethod
    def _collect_parameters(
        cls,
        levels: list[CommandSpec],
        operation: OperationSpec,
    ) -> tuple[ParameterModel, ...]:
        parameters: list[ParameterModel] = []
        seen_names: set[str] = set()

        for command in levels:
            for positional in command.positionals:
                if positional.api_name in seen_names:
                    raise GenerationError(
                        'Duplicate API parameter across command chain: '
                        f'{positional.api_name}'
                    )

                seen_names.add(positional.api_name)
                parameters.append(
                    ParameterModel(
                        api_name=positional.api_name,
                        value_type=positional.value_type,
                        required=positional.required,
                        multiple=positional.multiple,
                        option=False,
                    )
                )

            for option in command.options:
                if cls._runtime_option_role(operation, option.flags) is not None:
                    continue

                if option.api_name in seen_names:
                    raise GenerationError(
                        f'Duplicate API parameter across command chain: {option.api_name}'
                    )

                seen_names.add(option.api_name)
                parameters.append(
                    ParameterModel(
                        api_name=option.api_name,
                        value_type=option.value_type,
                        required=option.required,
                        multiple=option.multiple,
                        value_optional=option.value_optional,
                        option=True,
                    )
                )

        required = [item for item in parameters if item.required]
        optional = [item for item in parameters if not item.required]

        return tuple((*required, *optional))

    @staticmethod
    def _event_model(events: EventSpec | None) -> EventModel | None:
        if events is None:
            return None

        return EventModel(
            source_kind=events.source.kind.name.lower(),
            option_flag=events.source.option_flag,
            discriminator=events.discriminator,
            types=tuple(
                EventTypeModel(
                    name=event_type.name,
                    source_value=event_type.match_value,
                    fields=tuple(
                        EventFieldModel(
                            name=event_field.name,
                            api_name=event_field.api_name,
                            value_type=event_field.value_type,
                            required=event_field.required,
                        )
                        for event_field in event_type.fields
                    ),
                )
                for event_type in events.types
            ),
        )

    @staticmethod
    def _event_metadata(events: EventModel | None) -> dict[str, Any] | None:
        if events is None:
            return None

        return {
            'source': {
                'kind': events.source_kind,
                'option_flag': events.option_flag,
            },
            'discriminator': events.discriminator,
            'types': [
                {
                    'name': event_type.name,
                    'source_value': event_type.source_value,
                    'fields': [
                        {
                            'name': event_field.name,
                            'api_name': event_field.api_name,
                            'value_type': event_field.value_type.name.lower(),
                            'required': event_field.required,
                        }
                        for event_field in event_type.fields
                    ],
                }
                for event_type in events.types
            ],
        }

    @classmethod
    def _operation_model(
        cls,
        spec: APEBindSpec,
        operation: OperationSpec,
    ) -> OperationModel:
        commands_by_path = {command.path: command for command in spec.commands}
        levels = [
            commands_by_path[operation.command[:depth]]
            for depth in range(len(operation.command) + 1)
        ]
        events = cls._event_model(operation.events)

        metadata = {
            'command_path': list(operation.command),
            'execution': operation.execution.name.lower(),
            'process': {
                'timeout_seconds': operation.process.timeout_seconds,
            },
            'result': {
                'format': operation.result.format.name.lower(),
                'field': operation.result.field,
                'option_flag': operation.result.option_flag,
                'ready_timeout_seconds': operation.result.ready_timeout_seconds,
                'strip': operation.result.strip,
            },
            'levels': [cls._level_metadata(command, operation) for command in levels],
        }
        event_metadata = cls._event_metadata(events)

        if event_metadata is not None:
            metadata['events'] = event_metadata

        return OperationModel(
            name=operation.name,
            parameters=cls._collect_parameters(levels, operation),
            events=events,
            persistent=operation.execution.name.lower() == 'persistent',
            metadata=metadata,
        )

    @classmethod
    def build(cls, spec: APEBindSpec) -> BindingModel:
        spec.validate()

        return BindingModel(
            distribution_name=spec.ape.name,
            binary_name=spec.ape.binary,
            env_unset=spec.runtime.env_unset,
            operations=tuple(
                cls._operation_model(spec, operation)
                for operation in spec.operations
            ),
        )
