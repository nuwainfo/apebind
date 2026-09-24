#!/usr/bin/env python
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MIT

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OWNED_PYTHON_DIRECTORIES = (
    PROJECT_ROOT / 'src' / 'apebind',
    PROJECT_ROOT / 'scripts',
    PROJECT_ROOT / 'tests',
)
PYTHON_HEADER = (
    '#!/usr/bin/env python',
    '# -*- coding: utf-8 -*-',
    '# SPDX-License-Identifier: MIT',
)


def test_apebind_owned_python_files_have_mit_headers():
    for directory in OWNED_PYTHON_DIRECTORIES:
        for path in directory.rglob('*.py'):
            lines = path.read_text(encoding='utf-8').splitlines()
            assert tuple(lines[:3]) == PYTHON_HEADER, path.relative_to(PROJECT_ROOT)


def test_shell_scripts_have_mit_spdx_headers():
    for path in (PROJECT_ROOT / 'scripts').glob('*.sh'):
        lines = path.read_text(encoding='utf-8').splitlines()
        assert lines[:2] == ['#!/usr/bin/env bash', '# SPDX-License-Identifier: MIT']


def test_generated_binding_templates_do_not_assign_a_license():
    for path in (PROJECT_ROOT / 'src' / 'apebind' / 'templates').rglob('*.j2'):
        content = path.read_text(encoding='utf-8')
        assert 'SPDX-License-Identifier:' not in content, path.relative_to(PROJECT_ROOT)

    package_template = PROJECT_ROOT / 'src' / 'apebind' / 'templates' / 'node' / 'package.json.j2'
    assert '"license"' not in package_template.read_text(encoding='utf-8')
