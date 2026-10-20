# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)


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
