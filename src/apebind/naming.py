#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

import keyword
import re


_PASCAL_CASE_ACRONYMS = frozenset({'ape', 'ffl'})


def to_snake_case_identifier(value: str, *, fallback: str = 'value') -> str:
    """Normalize arbitrary CLI text into a valid snake_case Python identifier."""
    normalized = re.sub(r'[^A-Za-z0-9]+', '_', value).strip('_')
    normalized = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', normalized)
    normalized = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', normalized).lower()

    if not normalized:
        normalized = fallback

    if normalized[0].isdigit():
        normalized = f'{fallback}_{normalized}'

    if keyword.iskeyword(normalized):
        normalized = f'{normalized}_'

    return normalized


def to_camel_case_identifier(value: str, *, fallback: str = 'value') -> str:
    """Convert a snake_case identifier into lower camelCase."""
    snake_name = to_snake_case_identifier(value, fallback=fallback)
    parts = snake_name.rstrip('_').split('_')

    if not parts:
        return fallback

    return parts[0] + ''.join(part[:1].upper() + part[1:] for part in parts[1:])


def to_pascal_case_identifier(value: str, *, fallback: str = 'Value') -> str:
    """Convert a snake_case identifier into PascalCase."""
    snake_name = to_snake_case_identifier(value, fallback=fallback.lower())

    return ''.join(
        part.upper() if part in _PASCAL_CASE_ACRONYMS else part[:1].upper() + part[1:]
        for part in snake_name.rstrip('_').split('_')
    )
