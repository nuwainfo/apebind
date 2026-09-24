#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

class APEBindError(Exception):
    """Base exception for APEBind failures."""


class APEFormatError(APEBindError):
    """Raised when an input is not a supported APE."""


class InspectionError(APEBindError):
    """Raised when CLI inspection cannot continue safely."""


class SchemaError(APEBindError):
    """Raised when an APEBind schema is invalid."""


class GenerationError(APEBindError):
    """Raised when source generation cannot complete."""
