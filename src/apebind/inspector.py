#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from pathlib import Path

from .ape import APEDetector
from .errors import InspectionError
from .help_parser import HelpParser, ParsedHelp
from .models import APEBindSpec, APESpec, CommandSpec, OperationSpec
from .naming import to_snake_case_identifier
from .process_runner import ExecutableRunner


class APEInspector:
    """Orchestrate safe recursive help discovery into an editable schema."""

    def __init__(
        self,
        executable_path: Path,
        require_ape: bool = True,
        help_parser: HelpParser | None = None,
        runner: ExecutableRunner | None = None,
    ):
        if require_ape:
            APEDetector.require_ape(executable_path)

        self._executable_path = executable_path
        self._help_parser = help_parser or HelpParser()
        self._runner = runner or ExecutableRunner(executable_path)

    @staticmethod
    def _operation_name(command_path: tuple[str, ...]) -> str:
        if not command_path:
            return 'run'
        return to_snake_case_identifier('_'.join(command_path), fallback='command')

    @staticmethod
    def _expand_seed_paths(
        command_seeds: Iterable[tuple[str, ...]],
    ) -> tuple[tuple[str, ...], ...]:
        expanded: list[tuple[str, ...]] = []

        for command_path in command_seeds:
            if not command_path:
                raise InspectionError('Command seed path must not be empty')
            for depth in range(1, len(command_path) + 1):
                expanded.append(command_path[:depth])

        return tuple(dict.fromkeys(expanded))

    @staticmethod
    def _help_matches_command_path(
        command_path: tuple[str, ...],
        parsed_help: ParsedHelp,
    ) -> bool:
        if not command_path or not parsed_help.usage_path:
            return True
        if parsed_help.usage_path == command_path:
            return True
        if len(parsed_help.usage_path) > len(command_path):
            return False
        return command_path[-len(parsed_help.usage_path):] == parsed_help.usage_path

    def _inspect_command(self, command_path: tuple[str, ...]) -> ParsedHelp:
        result = self._runner.run([*command_path, '--help'])
        help_text = result.stdout if result.stdout.strip() else result.stderr
        joined_path = ' '.join(command_path) or '<root>'

        if result.return_code != 0 and not help_text.strip():
            raise InspectionError(
                f'Help failed for {joined_path} with exit code {result.return_code}'
            )
        if not help_text.strip():
            raise InspectionError(f'No help text returned for {joined_path}')

        parsed_help = self._help_parser.parse(help_text)

        if not self._help_matches_command_path(command_path, parsed_help):
            actual_path = ' '.join(parsed_help.usage_path) or '<unknown>'
            raise InspectionError(
                f'Help for {joined_path} describes a different command: {actual_path}'
            )

        return parsed_help

    def inspect(
        self,
        command_seeds: Iterable[tuple[str, ...]] = (),
    ) -> APEBindSpec:
        seed_paths = self._expand_seed_paths(command_seeds)
        queue: deque[tuple[str, ...]] = deque([(), *seed_paths])
        visited: set[tuple[str, ...]] = set()
        commands_by_path: dict[tuple[str, ...], CommandSpec] = {}
        operations_by_command: dict[tuple[str, ...], OperationSpec] = {}

        while queue:
            command_path = queue.popleft()
            if command_path in visited:
                continue
            visited.add(command_path)

            parsed_help = self._inspect_command(command_path)

            primary_command = self._help_parser.to_primary_command_spec(
                parsed_help,
                command_path,
            )
            if primary_command is not None:
                commands_by_path.setdefault((), CommandSpec(path=()))
                commands_by_path[primary_command.path] = primary_command
                operations_by_command.setdefault(
                    primary_command.path,
                    OperationSpec(
                        name=self._operation_name(primary_command.path),
                        command=primary_command.path,
                    ),
                )
                for subcommand in parsed_help.subcommands:
                    if subcommand != primary_command.path[-1]:
                        queue.append((subcommand,))
                continue

            command = self._help_parser.to_command_spec(parsed_help, command_path)
            commands_by_path[command_path] = command
            operations_by_command.setdefault(
                command_path,
                OperationSpec(
                    name=self._operation_name(command_path),
                    command=command_path,
                ),
            )
            for subcommand in parsed_help.subcommands:
                queue.append((*command_path, subcommand))

        spec = APEBindSpec(
            schema_version=1,
            ape=APESpec(name=self._executable_path.stem, binary=self._executable_path.name),
            commands=tuple(commands_by_path.values()),
            operations=tuple(operations_by_command.values()),
        )
        spec.validate()

        return spec
