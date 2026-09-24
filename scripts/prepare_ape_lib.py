#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import importlib.machinery
import importlib.metadata
import importlib.util
import shutil

from pathlib import Path


RUNTIME_DISTRIBUTIONS = {
    'attrs': ('attr', 'attrs'),
    'cattrs': ('cattrs',),
    'click': ('click',),
    'Jinja2': ('jinja2',),
    'MarkupSafe': ('markupsafe',),
    'PyYAML': ('yaml',),
    'typing_extensions': ('typing_extensions',),
}

IGNORED_NAMES = shutil.ignore_patterns(
    '__pycache__',
    '*.pyc',
    '*.pyo',
    '*.pyd',
    '*.so',
    '*.dylib',
    '*.dll',
)

ENTRY_POINT_SOURCE = """from apebind.cli import main


if __name__ == '__main__':
    main()
"""


class APELibraryBuilder:
    """Copy APEBind and its portable runtime dependencies into an APE Lib tree."""

    def __init__(self, project_root: Path, output_directory: Path):
        self._project_root = project_root
        self._output_directory = output_directory

    def build(self) -> None:
        if self._output_directory.exists():
            shutil.rmtree(self._output_directory)

        self._output_directory.mkdir(parents=True)
        self._copy_directory(self._project_root / 'src' / 'apebind', 'apebind')

        for distribution_name, module_names in RUNTIME_DISTRIBUTIONS.items():
            self._copy_distribution(distribution_name, module_names)

    def _copy_distribution(self, distribution_name: str, module_names: tuple[str, ...]) -> None:
        distribution = importlib.metadata.distribution(distribution_name)

        for module_name in module_names:
            self._copy_imported_package(module_name)

        metadata_directory = self._distribution_metadata_directory(distribution)
        if metadata_directory is not None:
            self._copy_directory(metadata_directory, metadata_directory.name)

    @staticmethod
    def _distribution_metadata_directory(
        distribution: importlib.metadata.Distribution,
    ) -> Path | None:
        for file_path in distribution.files or ():
            if file_path.parts and file_path.parts[0].endswith(('.dist-info', '.egg-info')):
                return Path(distribution.locate_file(file_path.parts[0]))

        return None

    def _copy_imported_package(self, module_name: str) -> None:
        specification = importlib.util.find_spec(module_name)
        if specification is None:
            raise RuntimeError(f'Cannot locate installed package: {module_name}')

        if specification.submodule_search_locations is None:
            self._copy_module_file(module_name, specification)
            return

        source_directory = Path(next(iter(specification.submodule_search_locations)))
        self._copy_directory(source_directory, module_name)

    def _copy_module_file(self, module_name: str, specification: importlib.machinery.ModuleSpec) -> None:
        if specification.origin is None:
            raise RuntimeError(f'Installed module has no source file: {module_name}')

        source_path = Path(specification.origin)
        if source_path.suffix != '.py':
            raise RuntimeError(f'Installed module is not portable Python source: {source_path}')

        shutil.copy2(source_path, self._output_directory / f'{module_name}.py')

    def _copy_directory(self, source_directory: Path, destination_name: str) -> None:
        if not source_directory.is_dir():
            raise RuntimeError(f'Package directory is missing: {source_directory}')

        shutil.copytree(
            source_directory,
            self._output_directory / destination_name,
            ignore=IGNORED_NAMES,
            dirs_exist_ok=True,
        )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Prepare the portable Python library tree for the APEBind APE.'
    )
    parser.add_argument('--output', type=Path, required=True, help='Destination Lib directory.')
    parser.add_argument('--entry', type=Path, required=True, help='Generated APE entry-point path.')
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output_directory = args.output.resolve()
    entry_path = args.entry.resolve()

    APELibraryBuilder(project_root, output_directory).build()

    entry_path.parent.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(ENTRY_POINT_SOURCE, encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
