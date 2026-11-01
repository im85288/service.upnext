# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Settings are read through one Addon until Kodi reports that they changed"""

import pytest
import monitor
import utils

SAVED = {'disableNextUp': 'false', 'playedInARow': '3'}


class SnapshotAddon:
    """Like Kodi's Addon: each instance loads the saved settings once, when it is created"""
    created = 0

    def __init__(self):
        SnapshotAddon.created += 1
        self.values = dict(SAVED)

    def getSetting(self, key):  # pylint: disable=invalid-name
        return self.values.get(key, '')


@pytest.fixture
def addon(monkeypatch):
    SnapshotAddon.created = 0
    monkeypatch.setattr(utils, 'Addon', SnapshotAddon)
    monkeypatch.setitem(SAVED, 'disableNextUp', 'false')
    utils.reload_settings()
    yield SnapshotAddon
    utils.reload_settings()


def test_settings_reuse_one_addon(addon):
    for _ in range(5):
        assert utils.get_setting_bool('disableNextUp') is False
        assert utils.get_setting_int('playedInARow') == 3
    assert addon.created == 1


def test_changed_settings_are_read_after_on_settings_changed(addon):
    assert utils.get_setting_bool('disableNextUp') is False
    SAVED['disableNextUp'] = 'true'
    assert utils.get_setting_bool('disableNextUp') is False  # still the loaded copy
    monitor.UpNextMonitor.onSettingsChanged(object.__new__(monitor.UpNextMonitor))
    assert utils.get_setting_bool('disableNextUp') is True
    assert addon.created == 2
