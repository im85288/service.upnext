# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

import pytest
import api
import playbackmanager
import upnext
from test_playbackmanager import Stub


@pytest.mark.parametrize('offset,delay,play_time,total_time,expected', [
    (120, 6, 120, 200, 126),
    ('120', 6, 130, 200, 136),
    (150, 6, 120, 200, 156),
    (195, 6, 198, 200, 200),
    (120, 0, 120, 200, None),
    (None, 6, 120, 200, None),
    ('invalid', 6, 120, 200, None),
    (-1, 6, 120, 200, None),
    (0, 6, 120, 200, None),
    (200, 6, 120, 200, None),
    (float('nan'), 6, 120, 200, None),
    (float('inf'), 6, 120, 200, None),
])
def test_credits_deadline_requires_valid_metadata(monkeypatch, offset, delay, play_time, total_time, expected):
    instance = object.__new__(api.Api)
    instance.data = {'notification_offset': offset}
    monkeypatch.setattr(api, 'get_setting_int', lambda key: delay)
    assert api.credits_autoplay_deadline(instance.data, play_time, total_time) == expected


def test_notification_time_keeps_priority_without_changing_credits_start(monkeypatch):
    instance = object.__new__(api.Api)
    instance.data = {'notification_time': 80, 'notification_offset': 150}
    monkeypatch.setattr(api, 'get_setting_int', lambda key: 6)
    assert instance.notification_time(total_time=200) == 80
    assert api.credits_autoplay_deadline(instance.data, 120, 200) == 156


@pytest.fixture
def run_credits(monkeypatch):
    def run(action=None, offset=120, delay=6, mode=0, source='addon', queued=False, still=False, pause=False, replace=False):
        events, popups = [], []
        clock = Stub(time=120.0, ticks=0, active=True, file='current.mkv', replaced=None)
        state = Stub(playing_next=False, queued=False, track=True, include_watched=True,
                     current_episode_id='current', play_mode=mode, played_in_a_row=1, pause=False)

        class Popup(upnext.UpNext):
            def __init__(self, *args):
                self.cancel = self.dismissed = self.watchnow = self.auto_advance = False
                self.current_progress_percent = 100
                self.progress_step_size = 0
                self.values = []
                self.properties = {}
                self.shown_properties = {}
                popups.append(self)

            def show(self):
                self.shown_properties = self.properties.copy()

            def close(self):
                events.append('close')

            def getControl(self, control):  # pylint: disable=invalid-name
                return Stub(setPercent=lambda percent: None)

            def setProperty(self, key, value):  # pylint: disable=invalid-name
                self.properties[key] = value
                if key == 'remaining':
                    self.values.append(int(value))

        class StillPopup(Popup):
            stillwatching = False

            def is_still_watching(self):
                return self.stillwatching

            def update_progress_control(self, **kwargs):
                pass

        def sleep(milliseconds):
            clock.ticks += 1
            assert clock.ticks < 1000, 'Popup did not finish'
            state.pause = pause and 2 <= clock.ticks <= 5
            if not state.pause:
                clock.time += .5
            if clock.ticks == 2 and action in ('back', 'stop', 'watch'):
                if action == 'back':
                    popups[0].onAction(92)
                else:
                    popups[0].onClick(3013 if action == 'stop' else 3012)
            if replace and clock.ticks == 2:
                # Another episode starts and keeps playing past the original credits deadline
                clock.file = 'replacement.mkv'
            if action == 'back-at-expiry' and clock.time >= 126:
                popups[0].onAction(92)

        player = Stub(getTime=lambda: clock.time, getTotalTime=lambda: 200,
                      getPlayingFile=lambda: clock.file, isPlaying=lambda: clock.active and clock.time < 200,
                      stop=lambda: events.append('stop'), playnext=lambda: events.append('playlist-next'))

        class Api(api.Api):
            def __init__(self):
                self.data = {'notification_offset': offset}

            def queue_next_item(self, episode):
                return queued

            def dequeue_next_item(self):
                events.append('dequeue')
                return False

            def reset_addon_data(self):
                events.append('reset')

            def play_addon_item(self):
                events.append('addon-next')

        class Manager(playbackmanager.PlaybackManager):
            def __init__(self):
                self.api, self.player, self.state = Api(), player, state
                self.play_item = Stub(get_next=lambda: ({'episodeid': 'next', 'playcount': 0}, source))

            def log(self, *args):
                pass

        def setting(key):
            return {'simpleMode': 0, 'playedInARow': 1 if still else 15, 'autoPlayCreditsTime': delay}[key]

        monkeypatch.setattr(api, 'get_setting_int', setting)
        monkeypatch.setattr(playbackmanager, 'get_setting_int', setting)
        monkeypatch.setattr(playbackmanager, 'get_setting_bool', lambda key: True)
        monkeypatch.setattr(playbackmanager, 'addon_path', lambda: '')
        monkeypatch.setattr(playbackmanager, 'set_property', lambda *args: None)
        monkeypatch.setattr(playbackmanager, 'clear_property', lambda *args: None)
        monkeypatch.setattr(playbackmanager, 'event', lambda **kwargs: events.append('watched'))
        monkeypatch.setattr(playbackmanager, 'sleep', sleep)
        monkeypatch.setattr(playbackmanager, 'UpNext', Popup)
        monkeypatch.setattr(playbackmanager, 'StillWatching', StillPopup)
        manager = Manager()
        clock.replaced = manager.launch_up_next()
        return events, state, clock, popups[0]

    return run


@pytest.mark.parametrize('source,queued,expected', [
    ('addon', False, 'addon-next'),
    ('addon', True, 'playlist-next'),
    ('playlist', False, 'playlist-next'),
])
def test_credits_expiry_advances_once_and_keeps_still_watching_count(run_credits, source, queued, expected):
    events, state, clock, popup = run_credits(source=source, queued=queued)
    assert events.count(expected) == 1
    assert 'stop' not in events
    assert 126 <= clock.time <= 126.5
    assert popup.values[0] == 6 and popup.values[-1] == 0
    assert popup.shown_properties == {'credits_countdown': 'true', 'credits_remaining': '6', 'remaining': '06'}
    assert popup.properties['credits_remaining'] == '0'
    assert popup.is_auto_advance() and not popup.is_watch_now()
    assert state.played_in_a_row == 2


@pytest.mark.parametrize('action', ['back', 'back-at-expiry'])
def test_back_during_credits_keeps_video_and_does_not_advance(run_credits, action):
    events, _, _, _ = run_credits(action=action, queued=True)
    assert not any(event in events for event in ('stop', 'addon-next', 'playlist-next'))
    assert events.count('dequeue') == 1


@pytest.mark.parametrize('delay', [6, 0])
@pytest.mark.parametrize('queued', [False, True])
def test_replacement_playback_closes_popup_without_advancing(run_credits, delay, queued):
    events, _, clock, popup = run_credits(delay=delay, queued=queued, replace=True)
    assert events == ['close']
    assert not popup.is_auto_advance()
    assert clock.time < 126
    assert clock.replaced is True


def test_stop_during_credits_is_called_once_after_close(run_credits):
    events, _, _, _ = run_credits(action='stop', queued=True)
    assert events.count('stop') == 1
    assert events.index('close') < events.index('stop')
    assert not any(event in events for event in ('addon-next', 'playlist-next'))


def test_manual_watch_now_is_still_immediate(run_credits):
    events, state, clock, _ = run_credits(action='watch')
    assert events.count('addon-next') == 1
    assert clock.time < 126
    assert state.played_in_a_row == 1


@pytest.mark.parametrize('options', [{'offset': None}, {'delay': 0}, {'mode': 1}, {'still': True}])
def test_credits_timer_preserves_legacy_modes_and_missing_metadata(run_credits, options):
    _, _, clock, popup = run_credits(**options)
    assert clock.time >= 199
    assert not popup.is_auto_advance()
    assert popup.properties.get('credits_countdown', '') == ''


def test_pause_does_not_use_up_credits_countdown(run_credits):
    events, _, clock, popup = run_credits(pause=True)
    assert events.count('addon-next') == 1
    assert 126 <= clock.time <= 126.5 and clock.ticks == 17
    assert popup.values[-1] == 0


def test_disabling_credits_countdown_clears_previous_skin_properties():
    popup = object.__new__(upnext.UpNext)
    properties = {}
    popup.setProperty = properties.__setitem__
    popup.set_credits_countdown(6)
    popup.set_credits_countdown()
    assert properties['credits_countdown'] == properties['credits_remaining'] == ''
