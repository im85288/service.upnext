# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Binge mode overrides the auto-play, auto-skip and credits settings without changing them"""

import pytest
import api
import skip
import state
import utils
from test_skip import DATA, Button, Player


@pytest.fixture(name='settings')
def fixture_settings(monkeypatch):
    values = {'bingeMode': False, 'enableSkipSegments': False, 'autoSkipIntro': False, 'autoSkipRecap': False,
              'autoPlayMode': 1, 'autoPlayCreditsTime': 0}
    monkeypatch.setattr(utils, 'get_setting_bool', lambda key, default=None: values.get(key, default))
    monkeypatch.setattr(utils, 'get_setting_int', lambda key, default=None: values.get(key, default))
    for module in (skip, state):
        monkeypatch.setattr(module, 'get_setting_bool', utils.get_setting_bool)
    for module in (api, state):
        monkeypatch.setattr(module, 'get_setting_int', utils.get_setting_int)
    monkeypatch.setattr(skip, 'localize', lambda string_id: 'Skip')
    state.State._shared_state.clear()  # pylint: disable=protected-access
    yield values
    state.State._shared_state.clear()  # pylint: disable=protected-access


def skipper():
    buttons = []
    result = skip.Skipper(Player(), button_factory=lambda label, on_skip: buttons.append(Button(label, on_skip)) or buttons[-1])
    result.buttons = buttons
    return result


@pytest.mark.parametrize('binge, expected', [(False, []), (True, [45.0, 120.0])])
def test_binge_mode_skips_intros_and_recaps_even_when_skipping_is_off(settings, binge, expected):
    settings['bingeMode'] = binge
    result = skipper()
    result.update(DATA, 10)
    result.player.time = 61
    result.update(DATA, 61)
    assert result.player.seeks == expected
    assert not result.buttons


@pytest.mark.parametrize('binge, expected', [(False, 1), (True, 0)])
def test_binge_mode_plays_next_by_default(settings, binge, expected):
    settings['bingeMode'] = binge
    assert state.State().play_mode == expected


@pytest.mark.parametrize('binge, delay, expected', [
    (False, 0, None),
    (True, 0, 150 + api.BINGE_CREDITS_DELAY),
    (True, 30, 180),  # the viewer's own credits delay wins
])
def test_binge_mode_moves_on_during_the_credits(settings, binge, delay, expected):
    settings['bingeMode'], settings['autoPlayCreditsTime'] = binge, delay
    assert api.credits_autoplay_deadline({'notification_offset': 150}, 120, 200) == expected


def test_binge_mode_needs_a_credits_offset(settings):
    settings['bingeMode'] = True
    assert api.credits_autoplay_deadline({}, 120, 200) is None


def test_binge_mode_is_off_by_default():
    with open('resources/settings.xml', encoding='utf-8') as handle:
        assert 'id="bingeMode" default="false"' in handle.read()


@pytest.mark.parametrize('key', ['autoPlayMode', 'enableSkipSegments', 'autoSkipIntro', 'autoSkipRecap'])
def test_overridden_settings_are_greyed_out_by_binge_mode(key):
    """Kodi's enable="eq(-N,false)" counts back N settings: it must land on bingeMode"""
    from xml.etree import ElementTree  # pylint: disable=import-outside-toplevel
    category = ElementTree.parse('resources/settings.xml').find("category[@label='30600']")
    entries = list(category.iter('setting'))
    index = [entry.get('id') for entry in entries].index(key)
    offset = int(entries[index].get('enable').split('(')[1].split(',')[0])
    assert entries[index + offset].get('id') == 'bingeMode'
