#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from pathlib import Path

import pytest

from apebind.discovery import CommandSeedLoader
from apebind.errors import InspectionError
from apebind.help_parser import HelpParser
from apebind.inspector import APEInspector
from apebind.process_runner import ProcessResult


class MappingHelpRunner:
    def __init__(self, help_by_arguments: dict[tuple[str, ...], str]):
        self._help_by_arguments = help_by_arguments
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments, timeout_seconds=10.0):
        del timeout_seconds
        argument_tuple = tuple(arguments)
        self.calls.append(argument_tuple)

        help_text = self._help_by_arguments[argument_tuple]
        return ProcessResult(argument_tuple, 0, help_text, '')


def _fixture_text(name: str) -> str:
    return (Path(__file__).parent / 'fixtures' / name).read_text(encoding='utf-8')


def test_command_seed_loader_combines_cli_and_yaml(tmp_path: Path):
    command_file = tmp_path / 'commands.yaml'
    command_file.write_text(
        'commands:\n'
        '  - download\n'
        '  - [admin, users]\n'
        '  - "keygen"\n',
        encoding='utf-8',
    )

    command_paths = CommandSeedLoader.combine(('download', 'admin groups'), command_file)

    assert command_paths == (
        ('download',),
        ('admin', 'groups'),
        ('admin', 'users'),
        ('keygen',),
    )


def test_command_seed_loader_rejects_unknown_file_fields(tmp_path: Path):
    command_file = tmp_path / 'commands.yaml'
    command_file.write_text('commands: []\nunknown: true\n', encoding='utf-8')

    with pytest.raises(InspectionError, match='Unknown command seed file field'):
        CommandSeedLoader.load(command_file)


def test_hidden_command_seeds_are_inspected_and_generated_as_operations():
    root_help = _fixture_text('ffl_help.txt')
    download_help = _fixture_text('ffl_download_help.txt')
    keygen_help = _fixture_text('ffl_keygen_help.txt')
    runner = MappingHelpRunner(
        {
            ('--help',): root_help,
            ('download', '--help'): download_help,
            ('keygen', '--help'): keygen_help,
        }
    )

    spec = APEInspector(
        Path('ffl.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    ).inspect((('download',), ('keygen',)))

    commands = {command.path: command for command in spec.commands}

    assert set(commands) == {(), ('share',), ('download',), ('keygen',)}
    assert commands[('download',)].positionals[0].api_name == 'url'
    assert any(option.api_name == 'output' for option in commands[('download',)].options)
    assert any(option.api_name == 'name' for option in commands[('keygen',)].options)

    operations = {operation.command: operation.name for operation in spec.operations}
    assert operations == {
        ('share',): 'share',
        ('download',): 'download',
        ('keygen',): 'keygen',
    }
    assert runner.calls == [
        ('--help',),
        ('download', '--help'),
        ('keygen', '--help'),
    ]


def test_seeding_primary_command_directly_does_not_duplicate_it():
    share_help = _fixture_text('ffl_help.txt')
    runner = MappingHelpRunner(
        {
            ('--help',): share_help,
            ('share', '--help'): share_help,
        }
    )

    spec = APEInspector(
        Path('ffl.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    ).inspect((('share',),))

    assert [command.path for command in spec.commands] == [(), ('share',)]

    share = next(command for command in spec.commands if command.path == ('share',))
    assert share.positionals[0].api_name == 'file_or_folder'
    assert any(option.api_name == 'json' for option in share.options)
    assert [operation.name for operation in spec.operations] == ['share']


def test_seeded_parent_recursively_discovers_children():
    root_help = 'usage: tool [-h]\n\noptions:\n  -h, --help  show help\n'
    admin_help = (
        'usage: tool admin [-h] {user,group} ...\n\n'
        'positional arguments:\n'
        '  {user,group}\n'
        '    user        Manage users.\n'
        '    group       Manage groups.\n\n'
        'options:\n'
        '  -h, --help   show help\n'
    )
    user_help = 'usage: tool admin user [-h]\n\noptions:\n  -h, --help  show help\n'
    group_help = 'usage: tool admin group [-h]\n\noptions:\n  -h, --help  show help\n'
    runner = MappingHelpRunner(
        {
            ('--help',): root_help,
            ('admin', '--help'): admin_help,
            ('admin', 'user', '--help'): user_help,
            ('admin', 'group', '--help'): group_help,
        }
    )

    spec = APEInspector(
        Path('tool.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    ).inspect((('admin',),))

    paths = {command.path for command in spec.commands}

    assert paths == {(), ('admin',), ('admin', 'user'), ('admin', 'group')}

    operations = {operation.name for operation in spec.operations}
    assert operations == {'run', 'admin', 'admin_user', 'admin_group'}


def test_nested_seed_inspects_missing_parent_prefixes():
    root_help = 'usage: tool [-h]\n\noptions:\n  -h, --help  show help\n'
    admin_help = 'usage: tool admin [-h]\n\noptions:\n  -h, --help  show help\n'
    secret_help = 'usage: tool admin secret [-h]\n\noptions:\n  -h, --help  show help\n'
    reset_help = 'usage: tool admin secret reset [-h]\n\noptions:\n  -h, --help  show help\n'
    runner = MappingHelpRunner(
        {
            ('--help',): root_help,
            ('admin', '--help'): admin_help,
            ('admin', 'secret', '--help'): secret_help,
            ('admin', 'secret', 'reset', '--help'): reset_help,
        }
    )

    spec = APEInspector(
        Path('tool.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    ).inspect((('admin', 'secret', 'reset'),))

    paths = [command.path for command in spec.commands]

    assert paths == [(), ('admin',), ('admin', 'secret'), ('admin', 'secret', 'reset')]


def test_seed_rejects_help_for_a_different_command():
    share_help = _fixture_text('ffl_help.txt')
    runner = MappingHelpRunner(
        {
            ('--help',): share_help,
            ('missing', '--help'): share_help,
        }
    )

    inspector = APEInspector(
        Path('ffl.com'),
        require_ape=False,
        help_parser=HelpParser(),
        runner=runner,
    )

    with pytest.raises(InspectionError, match='describes a different command: share'):
        inspector.inspect((('missing',),))
