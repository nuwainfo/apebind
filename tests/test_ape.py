#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import os
from pathlib import Path

import pytest

from apebind.ape import APEDetector
from apebind.errors import APEFormatError
from apebind.inspector import APEInspector


def test_detector_recognizes_all_ape_magic_values(tmp_path: Path):
    for magic_value in (b"MZqFpD='", b"jartsr='", b"APEDBG='"):
        ape_path = tmp_path / f'{magic_value[:2].hex()}.com'
        ape_path.write_bytes(magic_value + b'rest')
        assert APEDetector.is_ape(ape_path)


def test_detector_rejects_normal_executable(tmp_path: Path):
    normal_executable = tmp_path / 'normal.exe'
    normal_executable.write_bytes(b'MZ-not-an-ape')

    assert not APEDetector.is_ape(normal_executable)

    with pytest.raises(APEFormatError):
        APEDetector.require_ape(normal_executable)


def test_real_ape_fixture(fixture_ape_path: Path):
    default_path = Path(__file__).parent / 'fixtures' / 'ape_fixture.com'
    ape_path = Path(os.environ.get('APEBIND_TEST_APE', fixture_ape_path or default_path))

    APEDetector.require_ape(ape_path)

    spec = APEInspector(ape_path).inspect()
    paths = {command.path for command in spec.commands}

    assert ('math', 'add') in paths
    assert ('serve',) in paths
