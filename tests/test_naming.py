#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from apebind.naming import to_snake_case_identifier


def test_to_snake_case_identifier_normalizes_cli_names():
    assert to_snake_case_identifier('max-downloads') == 'max_downloads'
    assert to_snake_case_identifier('HTTPServer') == 'http_server'
    assert to_snake_case_identifier('123-mode') == 'value_123_mode'


def test_to_snake_case_identifier_escapes_python_keywords():
    assert to_snake_case_identifier('class') == 'class_'
