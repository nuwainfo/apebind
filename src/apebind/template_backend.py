#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, StrictUndefined

from .ape import APEDetector
from .generation_model import BindingModel, BindingModelBuilder
from .generators import LanguageBackend
from .models import APEBindSpec


class TemplateLanguageBackend(LanguageBackend):
    """Shared validation, template rendering, and APE copying for template backends."""

    def __init__(self, template_directory: str):
        self._template_directory = template_directory.rstrip('/')
        self._templates = Environment(
            loader=PackageLoader('apebind', 'templates'),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )

    def _prepare(self, spec: APEBindSpec, ape_path: Path) -> BindingModel:
        model = BindingModelBuilder.build(spec)
        APEDetector.require_ape(ape_path)

        return model

    def _render(
        self,
        template_name: str,
        output_path: Path,
        context: dict[str, Any],
    ) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        template_path = f'{self._template_directory}/{template_name}'
        rendered = self._templates.get_template(template_path).render(**context)

        output_path.write_text(rendered, encoding='utf-8')

    @staticmethod
    def _copy_ape(ape_path: Path, binary_path: Path) -> None:
        binary_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ape_path, binary_path)

        binary_path.chmod(0o755)
