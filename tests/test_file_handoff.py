# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Handing over from one episode to the next (issue #352)"""

import monitor
from test_playbackmanager import Stub

EPISODE_1, EPISODE_2 = 'episode1.mkv', 'episode2.mkv'


def run_ticks(monkeypatch, ticks, addon_data=None):
    """Run the service loop over (file, total time, play time, tracking) ticks; return the popups as (file, play time)"""
    popups = []
    data = {'value': dict(addon_data or {})}
    position = {'tick': -1}

    def current():
        return ticks[min(position['tick'], len(ticks) - 1)]

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

    def launch_up_next():
        popups.append((current()[0], current()[2]))
        return False

    class Monitor(monitor.UpNextMonitor):
        def __init__(self):  # pylint: disable=super-init-not-called
            self.player = Player()
            self.api = Stub(notification_time=lambda **kwargs: 70, has_addon_data=lambda: data['value'],
                            addon_data_received=lambda received, encoding: data.update(value=received))
            self.api.data = data['value']
            self.api.encoding = 'base64'
            self.playback_manager = Stub(launch_up_next=launch_up_next, demo=Stub(hide=lambda: None), handle_demo=lambda: None)
            self.skipper = Stub(update=lambda *args: None, hide=lambda: None, reset=lambda: None)
            self._sleep_state = None
            self._wake_retries = 0
            self._playback_state = None
            self._waiting_for = None
            self.messages = []

        def abortRequested(self):  # pylint: disable=invalid-name
            return False

        def waitForAbort(self, timeout):  # pylint: disable=invalid-name
            position['tick'] += 1
            if position['tick'] >= len(ticks):
                return True
            # Kodi re-enables tracking for the next episode (e.g. onAVStarted) when the tick says so
            if len(ticks[position['tick']]) > 3 and ticks[position['tick']][3]:
                self.player.tracking = True
            return False

        def log(self, msg, level=1):
            self.messages.append(msg)

    monkeypatch.setattr(monitor, 'get_property', lambda name: '')
    monkeypatch.setattr(monitor, 'get_setting_bool', lambda name: False)
    instance = Monitor()
    instance.run()
    return popups, instance


def handoff(next_ticks):
    """Episode 1 reaches its popup, then Kodi starts episode 2 and briefly reports episode 1's timing"""
    return [
        (EPISODE_1, 2679.0, 2600.0),
        (EPISODE_1, 2679.0, 2610.0),         # 69 s left: popup for episode 1, tracking stops
        (EPISODE_2, 2679.0, 2620.0, True),   # episode 2 is reported, with episode 1's timing
        (EPISODE_2, 2679.0, 2621.0),
    ] + next_ticks


def test_new_file_with_the_previous_files_timing_is_not_acted_on(monkeypatch):
    popups, instance = run_ticks(monkeypatch, handoff([
        (EPISODE_2, 1800.0, 2.0),            # episode 2's own timing
        (EPISODE_2, 1800.0, 1000.0),
        (EPISODE_2, 1800.0, 1750.0),         # 50 s left: popup for episode 2
    ]))
    assert popups == [(EPISODE_1, 2610.0), (EPISODE_2, 1750.0)]
    assert any("own position and duration" in message for message in instance.messages)


def test_same_length_file_resumed_further_in_is_accepted_after_waiting(monkeypatch):
    # A genuinely new file of exactly the same length, resumed past the previous position
    ticks = [(EPISODE_1, 2679.0, 1000.0), (EPISODE_2, 2679.0, 1500.0)]
    ticks += [(EPISODE_2, 2679.0, 1500.0 + tick) for tick in range(1, monitor.STALE_TIMING_WAIT + 2)]
    ticks += [(EPISODE_2, 2679.0, 2650.0)]
    popups, _ = run_ticks(monkeypatch, ticks)
    assert popups == [(EPISODE_2, 2650.0)]


def test_a_new_file_from_the_start_is_not_delayed(monkeypatch):
    popups, _ = run_ticks(monkeypatch, [
        (EPISODE_1, 2679.0, 1000.0),
        (EPISODE_2, 2679.0, 0.0),            # same length, but starting from the beginning
        (EPISODE_2, 2679.0, 2650.0),
    ])
    assert popups == [(EPISODE_2, 2650.0)]


def notify(instance, monkeypatch, data):
    monkeypatch.setattr(monitor, 'decode_json', lambda raw: (data, 'base64'))
    instance.onNotification('plugin.video.example.SIGNAL', 'Other.upnext_data', '')


def test_addon_data_retries_a_file_handled_before_it_arrived(monkeypatch):
    # Without the timing guard (e.g. a longer stale period), episode 2 gets handled without add-on data...
    ticks = [(EPISODE_2, 2679.0, 2620.0)] * 3
    popups, instance = run_ticks(monkeypatch, ticks)
    assert popups == [(EPISODE_2, 2620.0)]
    assert instance.player.get_last_file() == EPISODE_2
    # ...then the add-on's data for episode 2 arrives and Up Next looks at it again
    notify(instance, monkeypatch, {'current_episode': {'episodeid': 2}, 'next_episode': {'episodeid': 3}})
    assert instance.player.get_last_file() is None
    assert instance.player.is_tracking()


def test_addon_data_resent_after_a_popup_does_not_repeat_it(monkeypatch):
    data = {'current_episode': {'episodeid': 2}, 'next_episode': {'episodeid': 3}}
    popups, instance = run_ticks(monkeypatch, [(EPISODE_2, 1800.0, 1750.0)] * 3, addon_data=data)
    assert popups == [(EPISODE_2, 1750.0)]
    notify(instance, monkeypatch, data)
    assert instance.player.get_last_file() == EPISODE_2


def test_addon_data_for_another_file_keeps_the_handled_mark(monkeypatch):
    popups, instance = run_ticks(monkeypatch, [(EPISODE_1, 2679.0, 2620.0)] * 3)
    assert popups == [(EPISODE_1, 2620.0)]
    instance.player.last_file = EPISODE_2  # a different file is now marked handled
    notify(instance, monkeypatch, {'current_episode': {'episodeid': 2}})
    assert instance.player.get_last_file() == EPISODE_2
