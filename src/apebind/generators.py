#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from .errors import GenerationError
from .models import APEBindSpec


class LanguageBackend(ABC):
    """Generate one host-language project from a language-neutral APEBind spec."""

    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @property
    def aliases(self) -> tuple[str, ...]:
        return ()

    @property
    def language_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    @abstractmethod
    def generate(self, spec: APEBindSpec, ape_path: Path, output_directory: Path) -> None:
        raise NotImplementedError


LanguageGenerator = LanguageBackend


class GeneratorRegistry:
    def __init__(self, backends: Iterable[LanguageBackend]):
        self._backends: dict[str, LanguageBackend] = {}

        for backend in backends:
            for language_name in backend.language_names:
                if language_name in self._backends:
                    raise GenerationError(
                        f'Duplicate language backend registration: {language_name}'
                    )
                self._backends[language_name] = backend

    @property
    def language_names(self) -> tuple[str, ...]:
        return tuple(sorted(self._backends))

    @property
    def canonical_names(self) -> tuple[str, ...]:
        return tuple(sorted({backend.name for backend in self._backends.values()}))

    def get(self, language: str) -> LanguageBackend:
        backend = self._backends.get(language)

        if backend is None:
            supported = ', '.join(self.canonical_names)
            raise GenerationError(f'Unsupported language: {language}; supported: {supported}')

        return backend
