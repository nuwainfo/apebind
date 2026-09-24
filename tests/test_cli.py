#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from click.testing import CliRunner

from apebind.cli import main
from apebind.schema import SchemaCodec


def test_version_command():
    result = CliRunner().invoke(main, ['--version'])

    assert result.exit_code == 0
    assert '0.4.1' in result.output


def test_validate_command_uses_click_boundary(tmp_path, inspected_spec):
    schema_path = tmp_path / 'fixture.yaml'
    SchemaCodec().dump(inspected_spec, schema_path)

    result = CliRunner().invoke(main, ['validate', str(schema_path)])

    assert result.exit_code == 0
    assert result.output.strip() == 'valid'


def test_inspect_help_documents_hidden_command_seeds():
    result = CliRunner().invoke(main, ['inspect', '--help'])

    assert result.exit_code == 0
    assert '--command PATH' in result.output
    assert '--command-file FILE' in result.output


def test_inspect_command_accepts_explicit_command_sources(tmp_path, fixture_ape_path):
    command_file = tmp_path / 'commands.yaml'
    command_file.write_text('commands:\n  - "math add"\n', encoding='utf-8')
    output_path = tmp_path / 'fixture.yaml'

    result = CliRunner().invoke(
        main,
        [
            'inspect',
            str(fixture_ape_path),
            '-o',
            str(output_path),
            '--command',
            'echo',
            '--command-file',
            str(command_file),
        ],
    )

    assert result.exit_code == 0, result.output

    spec = SchemaCodec().load(output_path)
    paths = [command.path for command in spec.commands]

    assert paths.count(('echo',)) == 1
    assert paths.count(('math', 'add')) == 1


def test_generate_help_lists_language_backends():
    result = CliRunner().invoke(main, ['generate', '--help'])

    assert result.exit_code == 0
    assert 'java' in result.output
    assert 'node' in result.output
    assert 'python' in result.output
