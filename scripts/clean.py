#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import annotations

from _project import ProjectTasks, ScriptBoundary


def main() -> int:
    ProjectTasks().clean_build_artifacts()
    return 0


if __name__ == '__main__':
    raise SystemExit(ScriptBoundary.invoke(main))
