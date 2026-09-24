#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import shlex

from collections.abc import Iterable
from pathlib import Path

import yaml

from .errors import InspectionError


class CommandSeedLoader:
    """Parse explicit command paths that bootstrap hidden-command discovery."""

    @staticmethod
    def _validate_path(command_path: tuple[str, ...]) -> tuple[str, ...]:
        if not command_path:
            raise InspectionError('Command seed must contain at least one command token')

        for token in command_path:
            if not token:
                raise InspectionError('Command seed tokens must not be empty')
            if token.startswith('-'):
                raise InspectionError(
                    f'Command seed tokens must be commands, not options: {token}'
                )

        return command_path

    @classmethod
    def parse(cls, value: str) -> tuple[str, ...]:
        if not isinstance(value, str):
            raise InspectionError('Command seed must be a string')

        try:
            tokens = tuple(shlex.split(value))
        except ValueError as error:
            raise InspectionError(f'Invalid command seed {value!r}: {error}') from error

        return cls._validate_path(tokens)

    @classmethod
    def _structure_file_item(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, str):
            return cls.parse(value)

        if isinstance(value, list):
            if not all(isinstance(token, str) for token in value):
                raise InspectionError('Command seed token lists must contain only strings')
            return cls._validate_path(tuple(value))

        raise InspectionError('Each commands entry must be a string or a list of strings')

    @staticmethod
    def _deduplicate(
        command_paths: Iterable[tuple[str, ...]],
    ) -> tuple[tuple[str, ...], ...]:
        return tuple(dict.fromkeys(command_paths))

    @classmethod
    def load(cls, path: Path) -> tuple[tuple[str, ...], ...]:
        try:
            data = yaml.safe_load(path.read_text(encoding='utf-8'))
        except yaml.YAMLError as error:
            raise InspectionError(f'Invalid command seed YAML in {path}: {error}') from error

        if data is None:
            return ()

        if not isinstance(data, dict):
            raise InspectionError('Command seed file root must be a mapping')

        unknown_fields = set(data) - {'commands'}

        if unknown_fields:
            names = ', '.join(sorted(str(field) for field in unknown_fields))
            raise InspectionError(f'Unknown command seed file field(s): {names}')

        commands = data.get('commands', [])

        if not isinstance(commands, list):
            raise InspectionError('Command seed file commands must be a list')

        return cls._deduplicate(cls._structure_file_item(value) for value in commands)

    @classmethod
    def combine(
        cls,
        values: Iterable[str],
        command_file: Path | None = None,
    ) -> tuple[tuple[str, ...], ...]:
        command_paths = [cls.parse(value) for value in values]

        if command_file is not None:
            command_paths.extend(cls.load(command_file))

        return cls._deduplicate(command_paths)
