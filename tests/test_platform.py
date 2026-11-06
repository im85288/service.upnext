# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Platform detection has to work where Python cannot start a process, like Kodi on Xbox"""

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import utils

LIB = Path(__file__).resolve().parent.parent / 'resources' / 'lib'


def test_no_os_uname_means_not_armv7(monkeypatch):
    """Windows and Xbox have no os.uname"""
    monkeypatch.delattr(os, 'uname', raising=False)
    assert utils.is_armv7() is False


@pytest.mark.parametrize('machine, expected', [
    ('armv7l', True),
    ('armv7a', True),
    ('aarch64', False),
    ('x86_64', False),
])
def test_is_armv7_follows_the_machine(monkeypatch, machine, expected):
    monkeypatch.setattr(os, 'uname', lambda: SimpleNamespace(machine=machine), raising=False)
    assert utils.is_armv7() is expected


@pytest.mark.parametrize('path', sorted(LIB.glob('*.py')), ids=lambda path: path.name)
def test_add_on_does_not_use_modules_that_start_processes(path):
    """platform.machine() crashes the service on Xbox: _winapi has no CreateProcess there"""
    imported = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module)
    assert not imported & {'platform', 'subprocess'}
