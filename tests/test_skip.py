# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Skip intro and recap from skip_segments in upnext_data"""

import pytest
import skip

DATA = {'skip_segments': [
    {'kind': 'recap', 'start': 0, 'end': 45},
    {'kind': 'intro', 'start': 60, 'end': 120},
    {'kind': 'credits', 'start': 2500, 'end': 2600},
    {'kind': 'intro', 'start': 900, 'end': 930},
]}


class Button:
    def __init__(self, label, on_skip):
        self.label = label
        self.on_skip = on_skip
        self.shown = self.closed = 0
        self.dismissed = False

    def show(self):
        self.shown += 1

    def close(self):
        self.closed += 1

    def press(self):
        self.on_skip()
        self.close()


class Player:
    def __init__(self):
        self.seeks = []
        self.time = 0

    def seekTime(self, seconds):  # pylint: disable=invalid-name
        self.seeks.append(seconds)

    def getTime(self):  # pylint: disable=invalid-name
        return self.time


@pytest.fixture
def skipper(monkeypatch):
    settings = {'enableSkipSegments': True, 'autoSkipIntro': False, 'autoSkipRecap': False}
    monkeypatch.setattr(skip, 'get_setting_bool', lambda key, default=None: settings.get(key, default))
    monkeypatch.setattr(skip, 'localize', lambda string_id: {30052: 'Skip intro', 30053: 'Skip recap'}[string_id])
    buttons = []

    def factory(label, on_skip):
        buttons.append(Button(label, on_skip))
        return buttons[-1]

    result = skip.Skipper(Player(), button_factory=factory)
    result.settings, result.buttons = settings, buttons
    return result


def test_segments_are_parsed_sorted_and_only_intro_and_recap():
    assert skip.parse_segments(DATA) == [('recap', 0.0, 45.0), ('intro', 60.0, 120.0), ('intro', 900.0, 930.0)]


def test_bad_payloads_are_ignored():
    assert not skip.parse_segments(None)
    assert not skip.parse_segments({'skip_segments': [{'kind': 'intro'}, {'kind': 'intro', 'start': 50, 'end': 10},
                                                      {'kind': 'intro', 'start': 'soon', 'end': 'later'}, 'junk']})


def test_a_range_needs_an_explicit_start():
    # A missing or empty start must not become zero and skip the opening.
    assert not skip.parse_segments({'skip_segments': [{'kind': 'intro', 'end': 120},
                                                      {'kind': 'intro', 'start': None, 'end': 120},
                                                      {'kind': 'intro', 'start': '', 'end': 120}]})
    assert skip.parse_segments({'skip_segments': [{'kind': 'intro', 'start': 0, 'end': 120}]}) == [('intro', 0.0, 120.0)]


def test_a_button_pressed_after_its_range_never_seeks_backwards(skipper):
    skipper.update(DATA, 61)
    skipper.player.time = 200  # the Up Next popup held the loop while playback moved on
    skipper.buttons[0].press()
    assert not skipper.player.seeks


def test_button_shows_inside_a_range_and_skips_to_its_end(skipper):
    skipper.update(DATA, 50)
    assert not skipper.buttons  # between the recap and the intro
    skipper.update(DATA, 61)
    skipper.update(DATA, 62)
    assert [(b.label, b.shown) for b in skipper.buttons] == [('Skip intro', 1)]
    skipper.player.time = 62
    skipper.buttons[0].press()
    assert skipper.player.seeks == [120.0]
    skipper.update(DATA, 120)
    assert len(skipper.buttons) == 1


def test_button_goes_when_the_range_ends(skipper):
    skipper.update(DATA, 10)
    assert skipper.buttons[0].label == 'Skip recap'
    skipper.update(DATA, 50)
    assert skipper.buttons[0].closed == 1
    assert not skipper.player.seeks


def test_no_button_in_the_last_second(skipper):
    skipper.update(DATA, 119.5)
    assert not skipper.buttons


def test_back_dismisses_only_that_range(skipper):
    skipper.update(DATA, 61)
    skipper.buttons[0].dismissed = True
    skipper.update(DATA, 62)
    skipper.update(DATA, 63)
    assert len(skipper.buttons) == 1 and not skipper.player.seeks
    # The second intro of the episode is a range of its own.
    skipper.update(DATA, 905)
    assert len(skipper.buttons) == 2


def test_auto_skip_follows_the_settings(skipper):
    skipper.settings['autoSkipIntro'] = True
    skipper.update(DATA, 10)  # recaps still ask
    skipper.player.time = 61
    skipper.update(DATA, 61)
    assert skipper.player.seeks == [120.0]
    skipper.update(DATA, 62)  # the seek hasn't landed yet: no second skip
    assert skipper.player.seeks == [120.0]
    assert [b.label for b in skipper.buttons] == ['Skip recap']


def test_setting_off_hides_everything(skipper):
    skipper.update(DATA, 61)
    skipper.settings['enableSkipSegments'] = False
    skipper.update(DATA, 62)
    assert skipper.buttons[0].closed == 1
    skipper.update(DATA, 63)
    assert len(skipper.buttons) == 1


def test_reset_forgets_handled_ranges(skipper):
    skipper.update(DATA, 61)
    skipper.buttons[0].press()
    skipper.reset()
    skipper.update(DATA, 61)
    assert len(skipper.buttons) == 2
