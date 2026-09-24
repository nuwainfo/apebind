#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from ..generators import GeneratorRegistry
from .java import JavaGenerator
from .node import NodeGenerator
from .python import PythonGenerator


def create_generator_registry() -> GeneratorRegistry:
    """Compose all built-in language backends in one application boundary."""
    return GeneratorRegistry((PythonGenerator(), NodeGenerator(), JavaGenerator()))
