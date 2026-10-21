# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from importlib import import_module


def test_script():
    import_module('script_entry')


def test_service():
    import_module('service_entry')
