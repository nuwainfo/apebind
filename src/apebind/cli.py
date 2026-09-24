#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import click

from . import __version__

from .backends import create_generator_registry
from .discovery import CommandSeedLoader
from .errors import APEBindError
from .inspector import APEInspector
from .schema import SchemaCodec


class APEBindCLI:
    """Own the Click service boundary and application composition."""

    def __init__(self):
        self._schema_codec = SchemaCodec()
        self._generator_registry = create_generator_registry()

    @property
    def language_names(self) -> tuple[str, ...]:
        return self._generator_registry.language_names

    def inspect(
        self,
        ape_path: Path,
        output_path: Path,
        command_seeds: tuple[str, ...] = (),
        command_file: Path | None = None,
    ) -> None:
        seed_paths = CommandSeedLoader.combine(command_seeds, command_file)
        spec = APEInspector(ape_path).inspect(seed_paths)

        self._schema_codec.dump(spec, output_path)

    def validate(self, schema_path: Path) -> None:
        self._schema_codec.load(schema_path)

    def generate(
        self,
        schema_path: Path,
        ape_path: Path,
        language: str,
        output_directory: Path,
    ) -> None:
        spec = self._schema_codec.load(schema_path)
        self._generator_registry.get(language).generate(spec, ape_path, output_directory)

    def invoke(self, action: Callable[[], None]) -> None:
        try:
            action()
        except APEBindError as error:
            raise click.ClickException(str(error)) from error


_APPLICATION = APEBindCLI()


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Turn Actually Portable Executable CLIs into generated libraries."""


@main.command('inspect')
@click.argument('ape_path', type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option('-o', '--output', 'output_path', type=click.Path(path_type=Path), required=True)
@click.option(
    '--command',
    'command_seeds',
    multiple=True,
    metavar='PATH',
    help='Explicit command path to inspect; repeat for hidden commands.',
)
@click.option(
    '--command-file',
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    help='YAML file containing additional command paths to inspect.',
)
def inspect_command(
    ape_path: Path,
    output_path: Path,
    command_seeds: tuple[str, ...],
    command_file: Path | None,
) -> None:
    """Recursively inspect APE help into an editable YAML/JSON schema."""
    _APPLICATION.invoke(
        lambda: _APPLICATION.inspect(
            ape_path,
            output_path,
            command_seeds,
            command_file,
        )
    )

    click.echo(output_path)


@main.command('validate')
@click.argument('schema_path', type=click.Path(path_type=Path, exists=True, dir_okay=False))
def validate_command(schema_path: Path) -> None:
    """Validate an APEBind schema."""
    _APPLICATION.invoke(lambda: _APPLICATION.validate(schema_path))

    click.echo('valid')


@main.command('generate')
@click.argument('schema_path', type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option(
    '--ape',
    'ape_path',
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    required=True,
)
@click.option(
    '--lang',
    'language',
    type=click.Choice(_APPLICATION.language_names),
    default='python',
    show_default=True,
)
@click.option('-o', '--output', 'output_directory', type=click.Path(path_type=Path), required=True)
def generate_command(
    schema_path: Path,
    ape_path: Path,
    language: str,
    output_directory: Path,
) -> None:
    """Generate a language package that bundles the APE."""
    _APPLICATION.invoke(
        lambda: _APPLICATION.generate(schema_path, ape_path, language, output_directory)
    )

    click.echo(output_directory)
