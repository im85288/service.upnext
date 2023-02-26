# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals


def test_script():
    try:
        import script_entry
        test_complete = True
    except ImportError:
        test_complete = False
    
    assert test_complete is True


def test_service():
    try:
        import service_entry
        test_complete = True
    except ImportError:
        test_complete = False
    
    assert test_complete is True
