#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from pathlib import Path

from apebind.help_parser import HelpParser
from apebind.models import ValueType


def test_cobra_available_commands_are_discovered():
    help_text = '''Usage:
  tool [command]

Available Commands:
  share       Share files
  download    Download a file

Flags:
  -h, --help   help for tool
'''
    parsed = HelpParser().parse(help_text)
    assert parsed.subcommands == ('share', 'download')


def test_click_usage_infers_required_positional_without_arguments_section():
    help_text = """Usage: tool generate [OPTIONS] SCHEMA_PATH

  Generate a package.

Options:
  --help  Show this message and exit.
"""
    parsed = HelpParser().parse(help_text)

    assert parsed.usage_path == ('generate',)
    assert len(parsed.positionals) == 1

    positional = parsed.positionals[0]
    assert positional.name == 'SCHEMA_PATH'
    assert positional.api_name == 'schema_path'
    assert positional.value_type == ValueType.PATH
    assert positional.required
    assert not positional.multiple


def test_click_python_module_usage_ignores_launcher_and_infers_positional():
    help_text = """Usage: python -m APEBind inspect [OPTIONS] APE_PATH

  Inspect an APE.

Options:
  -o, --output PATH  [required]
  --help              Show this message and exit.
"""
    parsed = HelpParser().parse(help_text)

    assert parsed.usage_path == ('inspect',)
    assert [positional.api_name for positional in parsed.positionals] == ['ape_path']
    assert parsed.positionals[0].value_type == ValueType.PATH


def test_click_root_usage_placeholders_are_not_imported_as_positionals():
    help_text = """Usage: python -m APEBind [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  generate  Generate a package.
"""
    parsed = HelpParser().parse(help_text)

    assert parsed.usage_path == ()
    assert parsed.positionals == ()
    assert parsed.subcommands == ('generate',)


def test_bare_positional_choices_are_not_executed_as_subcommands():
    help_text = '''usage: tool [-h] {fast,slow}

positional arguments:
  {fast,slow}  Execution mode

options:
  -h, --help   show help
'''
    parsed = HelpParser().parse(help_text)
    assert parsed.subcommands == ()


def test_argparse_required_multiple_positional_is_required():
    help_text = '''usage: tool echo [-h] text [text ...]

positional arguments:
  text       Text values

options:
  -h, --help show help
'''
    parsed = HelpParser().parse(help_text)
    assert parsed.positionals[0].required
    assert parsed.positionals[0].multiple


def test_flag_names_are_converted_to_snake_case():
    help_text = '''usage: tool [-h] [--max-downloads COUNT]

options:
  -h, --help             show help
  --max-downloads COUNT  Maximum downloads
'''
    parsed = HelpParser().parse(help_text)
    assert parsed.options[0].api_name == 'max_downloads'


def test_ffl_named_share_section_is_parsed():
    help_text = (Path(__file__).parent / 'fixtures' / 'ffl_help.txt').read_text(encoding='utf-8')

    parsed = HelpParser().parse(help_text)

    assert parsed.usage_path == ('share',)
    assert len(parsed.command_sections) == 1

    share = parsed.command_sections[0]
    assert share.name == 'share'

    positionals = {item.api_name: item for item in share.positionals}

    file_or_folder = positionals['file_or_folder']
    assert file_or_folder.value_type == ValueType.PATH
    assert not file_or_folder.required
    assert file_or_folder.multiple

    options = {item.api_name: item for item in share.options}
    assert options['name'].flags == ('--name', '-n')
    assert options['json'].value_type == ValueType.PATH
    assert options['upload'].choices == ('unavailable',)
    assert options['auth_password'].help.startswith('Password for HTTP Basic Authentication')


def test_wrapped_usage_does_not_become_summary():
    help_text = '''usage: tool share [-h] [--name NAME]
                  [--json FILE]

options:
  -h, --help   show help

share:
  --name NAME  Name
'''
    parsed = HelpParser().parse(help_text)
    assert parsed.summary == ''


def test_optional_value_options_are_distinguished_from_booleans():
    help_text = '''usage: tool share [-h] [--qr [FILE]] [--receipt [EMAIL]] [--flag]

options:
  -h, --help          show help
  --qr [FILE]         Optional QR output path
  --receipt [EMAIL]   Optional receipt email
  --flag              Plain boolean flag
'''
    parsed = HelpParser().parse(help_text)
    options = {item.api_name: item for item in parsed.options}

    assert options['qr'].value_optional
    assert options['receipt'].value_optional
    assert not options['receipt'].multiple
    assert not options['flag'].value_optional
    assert options['flag'].value_type == ValueType.BOOLEAN
