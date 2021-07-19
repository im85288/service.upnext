# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""UpNext script and service tests"""

from __future__ import absolute_import, division, unicode_literals
import dummydata
import plugin
import script


SKIP_TEST = False


def test_popup():
    if SKIP_TEST:
        assert True
        return

    test_complete = script.run(['', 'test_window', 'upnext'])
    assert test_complete is True


def test_overall():
    if SKIP_TEST:
        assert True
        return

    test_run = script.run(['', 'test_upnext', 'upnext'])
    test_complete = test_run.waitForAbort()
    assert test_complete is True


def test_plugin():
    if SKIP_TEST:
        assert True
        return

    dbid = dummydata.LIBRARY['episodes'][0]['episodeid']
    test_complete = plugin.handler([
        'plugin://service.upnext/', '1', '?play={0}'.format(dbid)
    ])
    assert test_complete is True
