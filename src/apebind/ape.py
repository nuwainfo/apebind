#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from pathlib import Path

from .errors import APEFormatError


class APEDetector:
    """Recognize APE v0.1 file headers without interpreting the executable."""

    _MAGIC_VALUES = (b"MZqFpD='", b"jartsr='", b"APEDBG='")

    @classmethod
    def is_ape(cls, path: Path) -> bool:
        with path.open('rb') as input_file:
            magic = input_file.read(8)
        return magic in cls._MAGIC_VALUES

    @classmethod
    def require_ape(cls, path: Path) -> None:
        if not path.is_file():
            raise APEFormatError(f'APE does not exist: {path}')

        if not cls.is_ape(path):
            raise APEFormatError(f'Not a supported APE v0.1 executable: {path}')
