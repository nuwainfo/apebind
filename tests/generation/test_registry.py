#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import pytest

from apebind.backends import create_generator_registry
from apebind.errors import GenerationError
from apebind.backends.java import JavaGenerator
from apebind.backends.node import NodeGenerator
from apebind.backends.python import PythonGenerator


def test_default_registry_exposes_canonical_backends_and_aliases():
    registry = create_generator_registry()

    assert registry.canonical_names == ('java', 'node', 'python')
    assert registry.get('python').name == 'python'
    assert registry.get('py').name == 'python'
    assert registry.get('node').name == 'node'
    assert registry.get('java').name == 'java'
    assert registry.get('jvm').name == 'java'
    assert registry.get('js').name == 'node'
    assert registry.get('javascript').name == 'node'
    assert registry.get('nodejs').name == 'node'


def test_registry_fails_for_unknown_language():
    registry = create_generator_registry()

    with pytest.raises(GenerationError, match='supported: java, node, python'):
        registry.get('ruby')


def test_backend_types_are_separate():
    registry = create_generator_registry()

    assert isinstance(registry.get('python'), PythonGenerator)
    assert isinstance(registry.get('node'), NodeGenerator)
    assert isinstance(registry.get('java'), JavaGenerator)
