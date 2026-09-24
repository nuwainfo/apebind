#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from pathlib import Path

from apebind.help_parser import HelpParser
from apebind.inspector import APEInspector
from apebind.process_runner import ProcessResult


class StaticHelpRunner:
    def __init__(self, help_text: str):
        self._help_text = help_text
        self.calls = []

    def run(self, arguments, timeout_seconds=10.0):
        del timeout_seconds
        self.calls.append(tuple(arguments))
        return ProcessResult(tuple(arguments), 0, self._help_text, '')


def test_recursive_inspection_finds_nested_commands(inspected_spec):
    paths = {command.path for command in inspected_spec.commands}

    assert () in paths
    assert ('echo',) in paths
    assert ('math',) in paths
    assert ('math', 'add') in paths
    assert ('math', 'multiply') in paths
    assert ('json',) in paths
    assert ('serve',) in paths


def test_inspection_infers_basic_argument_shapes(inspected_spec):
    commands = {command.path: command for command in inspected_spec.commands}

    echo = commands[('echo',)]
    assert echo.positionals[0].api_name == 'text'
    assert echo.positionals[0].multiple

    options = {option.api_name: option for option in echo.options}
    assert options['upper'].value_type.name == 'BOOLEAN'
    assert options['repeat'].value_type.name == 'INTEGER'


def test_inspection_generates_snake_case_operation_names(inspected_spec):
    operations = {operation.command: operation.name for operation in inspected_spec.operations}

    assert operations[('math', 'add')] == 'math_add'
    assert operations[('math', 'multiply')] == 'math_multiply'


def test_named_primary_command_section_becomes_operation():
    help_text = (Path(__file__).parent / 'fixtures' / 'ffl_help.txt').read_text(encoding='utf-8')
    runner = StaticHelpRunner(help_text)

    spec = APEInspector(
        Path('ffl.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    ).inspect()

    commands = {command.path: command for command in spec.commands}

    assert set(commands) == {(), ('share',)}
    assert commands[()].options == ()

    share = commands[('share',)]

    assert share.positionals[0].api_name == 'file_or_folder'

    options = {option.api_name: option for option in share.options}
    assert {'version', 'cli', 'name', 'json', 'upload'} <= set(options)
    assert options['name'].flags == ('--name', '-n')

    assert [(operation.name, operation.command) for operation in spec.operations] == [
        ('share', ('share',))
    ]
    assert runner.calls == [('--help',)]
