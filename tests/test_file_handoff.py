# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Handing over from one episode to the next (issue #352)"""

import monitor
from test_playbackmanager import Stub

EPISODE_1, EPISODE_2 = 'episode1.mkv', 'episode2.mkv'
NEXT_DATA = {'current_episode': {'episodeid': 2}, 'next_episode': {'episodeid': 3}}


class FakeApi:
    """Like Api: addon_data_received() replaces data, launching a popup resets it"""

    def __init__(self, data=None):
        self.data = dict(data or {})
        self.encoding = 'base64'

    def notification_time(self, total_time=None):  # pylint: disable=unused-argument
        return 70

    def has_addon_data(self):
        return self.data

    def addon_data_received(self, data, encoding='base64'):
        self.data = data
        self.encoding = encoding


def run_ticks(monkeypatch, ticks, addon_data=None, library=False, events=None):
    """Run the service loop over (file, total time, play time) ticks.

    events maps a tick number to a function called with the monitor before that tick, e.g. to
    re-enable tracking or to deliver upnext_data. Returns the monitor; its popups attribute lists
    (file, play time) for every popup that was actually shown."""
    events = events or {}
    position = {'tick': -1}

    def current():
        return ticks[min(max(position['tick'], 0), len(ticks) - 1)]

    class Player:
        tracking = True
        last_file = None
        state = Stub(played_in_a_row=1, current_tv_show_id=None)

        def is_tracking(self):
            return self.tracking

        def disable_tracking(self):
            self.tracking = False

        def enable_tracking(self):
            self.tracking = True

        def isExternalPlayer(self):  # pylint: disable=invalid-name
            return False

        def get_last_file(self):
            return self.last_file

        def set_last_file(self, filename):
            self.last_file = filename

        def getPlayingFile(self):  # pylint: disable=invalid-name
            return current()[0]

        def getTotalTime(self):  # pylint: disable=invalid-name
            return current()[1]

        def getTime(self):  # pylint: disable=invalid-name
            return current()[2]

        def reset_queue(self):
            pass

    class Monitor(monitor.UpNextMonitor):
        def __init__(self):  # pylint: disable=super-init-not-called
            self.player = Player()
            self.api = FakeApi(addon_data)
            self.playback_manager = Stub(launch_up_next=self.launch_up_next, popup_shown=False,
                                         demo=Stub(hide=lambda: None), handle_demo=lambda: None)
            self.skipper = Stub(update=lambda *args: None, hide=lambda: None, reset=lambda: None)
            self._sleep_state = None
            self._wake_retries = 0
            self._playback_state = None
            self._waiting_for = None
            self.messages = []
            self.popups = []

        def launch_up_next(self):
            # Like PlaybackManager: a popup needs add-on data, or a library episode to look up
            shown = bool(self.api.data.get('next_episode')) or library
            self.playback_manager.popup_shown = shown
            if shown:
                self.popups.append((current()[0], current()[2]))
                self.api.data = {}
            return False

        def abortRequested(self):  # pylint: disable=invalid-name
            return False

        def waitForAbort(self, timeout):  # pylint: disable=invalid-name
            position['tick'] += 1
            if position['tick'] >= len(ticks):
                return True
            if position['tick'] in events:
                events[position['tick']](self)
            return False

        def log(self, msg, level=1):
            self.messages.append(msg)

    monkeypatch.setattr(monitor, 'get_property', lambda name: '')
    monkeypatch.setattr(monitor, 'get_setting_bool', lambda name: False)
    monkeypatch.setattr(monitor, 'decode_json', lambda raw: (dict(NEXT_DATA), 'base64'))
    instance = Monitor()
    instance.run()
    return instance


def track(instance):
    """Kodi re-enables tracking for the next episode (e.g. onAVStarted)"""
    instance.player.tracking = True


def send_addon_data(instance):
    """The add-on sends upnext_data for the playing file"""
    instance.onNotification('plugin.video.example.SIGNAL', 'Other.upnext_data', '')


def test_new_file_with_the_previous_files_timing_is_not_acted_on(monkeypatch):
    # Issue #352: episode 1's popup, then Kodi reports episode 2 with episode 1's timing for a few seconds
    instance = run_ticks(monkeypatch, [
        (EPISODE_1, 2679.0, 2600.0),
        (EPISODE_1, 2679.0, 2610.0),         # 69 s left: popup for episode 1
        (EPISODE_2, 2679.0, 2620.0),         # episode 2 reported, with episode 1's timing
        (EPISODE_2, 2679.0, 2621.0),
        (EPISODE_2, 1800.0, 2.0),            # episode 2's own timing, then its add-on data
        (EPISODE_2, 1800.0, 1000.0),
        (EPISODE_2, 1800.0, 1750.0),         # 50 s left: popup for episode 2
    ], addon_data=NEXT_DATA, events={2: track, 5: send_addon_data})
    assert instance.popups == [(EPISODE_1, 2610.0), (EPISODE_2, 1750.0)]
    assert any("own position and duration" in message for message in instance.messages)


def test_same_length_file_resumed_further_in_is_accepted_after_waiting(monkeypatch):
    ticks = [(EPISODE_1, 2679.0, 1000.0), (EPISODE_2, 2679.0, 1500.0)]
    ticks += [(EPISODE_2, 2679.0, 1500.0 + tick) for tick in range(1, monitor.STALE_TIMING_WAIT + 2)]
    ticks += [(EPISODE_2, 2679.0, 2650.0)]
    instance = run_ticks(monkeypatch, ticks, addon_data=NEXT_DATA)
    assert instance.popups == [(EPISODE_2, 2650.0)]


def test_a_new_file_from_the_start_is_not_delayed(monkeypatch):
    instance = run_ticks(monkeypatch, [
        (EPISODE_1, 2679.0, 1000.0),
        (EPISODE_2, 2679.0, 0.0),            # same length, but starting from the beginning
        (EPISODE_2, 2679.0, 2650.0),
    ], addon_data=NEXT_DATA)
    assert instance.popups == [(EPISODE_2, 2650.0)]


def test_addon_data_arriving_after_an_empty_attempt_gets_the_popup(monkeypatch):
    # Episode 2 is checked before its add-on data arrives: nothing to show yet
    instance = run_ticks(monkeypatch, [
        (EPISODE_2, 1800.0, 1750.0),         # no add-on data, not in the library: no popup
        (EPISODE_2, 1800.0, 1751.0),
        (EPISODE_2, 1800.0, 1752.0),         # the add-on's data arrives, the file is checked again: popup
        (EPISODE_2, 1800.0, 1753.0),
        (EPISODE_2, 1800.0, 1754.0),
    ], events={2: send_addon_data})
    assert instance.popups == [(EPISODE_2, 1752.0)]


def test_addon_data_resent_after_a_popup_does_not_reopen_it(monkeypatch):
    instance = run_ticks(monkeypatch, [
        (EPISODE_2, 1800.0, 1750.0),         # popup with add-on data, then dismissed
        (EPISODE_2, 1800.0, 1751.0),
        (EPISODE_2, 1800.0, 1752.0),         # the add-on sends its data again
        (EPISODE_2, 1800.0, 1753.0),
        (EPISODE_2, 1800.0, 1754.0),
    ], addon_data=NEXT_DATA, events={2: send_addon_data})
    assert instance.popups == [(EPISODE_2, 1750.0)]


def test_addon_data_after_a_library_popup_does_not_reopen_it(monkeypatch):
    # A library popup is shown without add-on data; add-on data arriving later must not repeat it
    instance = run_ticks(monkeypatch, [
        (EPISODE_2, 1800.0, 1750.0),
        (EPISODE_2, 1800.0, 1751.0),
        (EPISODE_2, 1800.0, 1752.0),
        (EPISODE_2, 1800.0, 1753.0),
        (EPISODE_2, 1800.0, 1754.0),
    ], library=True, events={2: send_addon_data})
    assert instance.popups == [(EPISODE_2, 1750.0)]


def test_addon_data_for_another_file_keeps_the_handled_mark(monkeypatch):
    instance = run_ticks(monkeypatch, [(EPISODE_1, 2679.0, 2620.0)] * 2)
    assert instance.popups == []
    instance.player.last_file = EPISODE_2  # a different file is now marked handled
    send_addon_data(instance)
    assert instance.player.get_last_file() == EPISODE_2
