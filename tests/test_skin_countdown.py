# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""The default skin's countdown follows the add-on's time left, in minutes when the popup opens early"""

import os
import re
import xml.etree.ElementTree as ET
import pytest

SKIN = os.path.join('resources', 'skins', 'default', '1080i')
POPUPS = ['script-upnext-upnext.xml', 'script-upnext-upnext-simple.xml',
          'script-upnext-stillwatching.xml', 'script-upnext-stillwatching-simple.xml']
LONG = {'30054', '30055', '30056'}  # m:ss labels
SECONDS = {'30036', '30037', '30035', '30050'}  # labels counting seconds, including the credits countdown
OVER_A_MINUTE = 'Integer.IsGreater(Window.Property(remaining),59)'


def controls(name):
    return ET.parse(os.path.join(SKIN, name)).getroot().iter('control')


def label_ids(control):
    return set(re.findall(r'\$ADDON\[service\.upnext (\d+)\]', control.findtext('label') or ''))


@pytest.mark.parametrize('name', POPUPS)
def test_countdown_uses_the_add_ons_time_left(name):
    with open(os.path.join(SKIN, name)) as handle:
        text = handle.read()
    assert 'Player.TimeRemaining' not in text


@pytest.mark.parametrize('name', POPUPS)
def test_each_label_shows_on_its_own_side_of_a_minute(name):
    found = set()
    for control in controls(name):
        ids = label_ids(control)
        visible = control.findtext('visible') or ''
        if ids & LONG:
            assert '!' + OVER_A_MINUTE not in visible and OVER_A_MINUTE in visible
            found |= ids & LONG
        elif ids & SECONDS:
            assert '!' + OVER_A_MINUTE in visible
    assert found


@pytest.mark.parametrize('name', ['script-upnext-upnext.xml', 'script-upnext-upnext-simple.xml'])
def test_credits_countdown_over_a_minute_uses_minutes(name):
    # A minute-and-seconds label must be able to show while the credits countdown runs
    visibles = [control.findtext('visible') or '' for control in controls(name) if '30055' in label_ids(control)]
    assert any('!String.IsEqual(Window.Property(credits_countdown),true)' not in visible for visible in visibles)


@pytest.mark.parametrize('name', ['script-upnext-upnext-simple.xml', 'script-upnext-stillwatching-simple.xml'])
def test_simple_popups_have_one_ring_driven_by_the_add_on(name):
    rings = [control for control in controls(name) if 'nextupicons/' in (control.findtext('texture') or '')]
    assert [ring.findtext('texture') for ring in rings] == ['$INFO[Window.Property(remaining_icon),nextupicons/,.png]']
    assert rings[0].find('visible') is None


def test_new_labels_are_translatable():
    with open(os.path.join('resources', 'language', 'resource.language.en_gb', 'strings.po')) as handle:
        strings = handle.read()
    for string_id in LONG:
        assert 'msgctxt "#%s"\nmsgid "' % string_id in strings
        assert 'Window.Property(remaining_time)' in strings.split('msgctxt "#%s"' % string_id)[1].split('msgctxt')[0]
