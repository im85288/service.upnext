# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)


import pytest
import monitor
import player
import playitem
from skip import Skipper


class Stub:
    def __init__(self, **values):
        self.__dict__.update(values)


def run_monitor(monkeypatch, unavailable=None, processed=False, always_unavailable=False, max_ticks=3, replaced=False, launch=None):
    events = []
    attempts = {}

    def value(name, ready):
        attempts[name] = attempts.get(name, 0) + 1
        if unavailable == name and (always_unavailable or attempts[name] == 1):
            if name == 'zero_duration':
                return 0
            raise RuntimeError('Player is not ready')
        return ready

    class Player:
        tracking = True
        last_file = 'episode.mkv' if processed else None
        state = Stub(played_in_a_row=1, current_tv_show_id=None)

        def is_tracking(self):
            return self.tracking

        def disable_tracking(self):
            self.tracking = False
            events.append('disabled')

        def isExternalPlayer(self):
            return False

        def get_last_file(self):
            return self.last_file

        def set_last_file(self, filename):
            self.last_file = filename

        def getPlayingFile(self):
            return value('filename', 'episode.mkv')

        def getTotalTime(self):
            return value('zero_duration' if unavailable == 'zero_duration' else 'duration', 1200)

        def getTime(self):
            return value('time', 1190)

    def hide_demo():
        attempts['hidden'] = attempts.get('hidden', 0) + 1

    class Monitor(monitor.UpNextMonitor):
        def __init__(self):
            self.player = Player()
            self.api = Stub(notification_time=lambda **kwargs: 30, data={}, encoding='base64')
            self.playback_manager = Stub(launch_up_next=launch or (lambda: events.append('popup') or replaced), demo=Stub(hide=hide_demo))
            self.skipper = Skipper(self.player)
            self.ticks = 0
            self._sleep_state = None
            self._wake_retries = 0
            self._playback_state = None
            self._waiting_for = None

        def abortRequested(self):
            return False

        def waitForAbort(self, timeout):
            self.ticks += 1
            return self.ticks > max_ticks

        def log(self, *args):
            attempts.setdefault('messages', []).append(args[0])

    monkeypatch.setattr(monitor, 'get_property', lambda name: '')
    monkeypatch.setattr(monitor, 'clear_property', lambda name: events.append('clear %s' % name))
    monkeypatch.setattr(monitor, 'get_setting_bool', lambda name: False)
    instance = Monitor()
    instance.run()
    return events, attempts


@pytest.mark.parametrize('unavailable', ['filename', 'duration', 'zero_duration', 'time'])
def test_temporary_player_unavailability_does_not_lose_popup(monkeypatch, unavailable):
    events, attempts = run_monitor(monkeypatch, unavailable=unavailable)
    assert events == ['popup', 'disabled']
    assert attempts[unavailable] >= 2


def test_replaced_playback_keeps_tracking(monkeypatch):
    events, _ = run_monitor(monkeypatch, replaced=True)
    assert events == ['popup']


def test_unready_player_does_not_show_popup(monkeypatch):
    events, _ = run_monitor(monkeypatch, unavailable='duration', always_unavailable=True)
    assert 'popup' not in events


@pytest.mark.parametrize('unavailable', ['filename', 'duration', 'zero_duration', 'time'])
def test_persistent_player_unavailability_does_not_repeat_waiting_side_effects(monkeypatch, unavailable):
    events, attempts = run_monitor(monkeypatch, unavailable=unavailable, always_unavailable=True, max_ticks=35)
    assert events == []
    assert attempts[unavailable] == 35
    assert attempts['hidden'] == 1
    assert len([message for message in attempts['messages'] if 'waiting for' in message]) == 1


def test_processed_file_does_not_show_another_popup_after_rearming(monkeypatch):
    events, _ = run_monitor(monkeypatch, processed=True)
    assert 'popup' not in events


@pytest.mark.parametrize('addon_data,episode_content,expected_tracking', [
    (True, False, True),
    (False, True, True),
    (False, False, False),
])
def test_resume_rearms_episode_tracking(monkeypatch, addon_data, episode_content, expected_tracking):
    class Player(player.UpNextPlayer):
        def __init__(self):
            self.state = Stub(pause=True, track=False)
            self.api = Stub(has_addon_data=lambda: addon_data)

    monkeypatch.setattr(player, 'getCondVisibility', lambda condition: episode_content)
    instance = Player()
    instance.onPlayBackResumed()
    assert instance.state.pause is False
    assert instance.is_tracking() is expected_tracking


@pytest.fixture
def sleeping_monitor():
    class Api:
        def __init__(self):
            self.data = {'next_episode': {'episodeid': 'next'}}
            self.encoding = 'base64'

        def has_addon_data(self):
            return self.data

        def addon_data_received(self, data, encoding):
            self.data = data
            self.encoding = encoding

    class Player:
        filename = 'episode.mkv'
        duration = 1200
        last_file = None
        tracking = True

        def __init__(self):
            self.state = Stub(played_in_a_row=1, current_tv_show_id=None)

        def getPlayingFile(self):
            if self.filename is None:
                raise RuntimeError('Player is not ready')
            return self.filename

        def getTotalTime(self):
            return self.duration

        def get_last_file(self):
            return self.last_file

        def set_last_file(self, filename):
            self.last_file = filename

        def is_tracking(self):
            return self.tracking

        def enable_tracking(self):
            self.tracking = True

    class Monitor(monitor.UpNextMonitor):
        def __init__(self):
            self.player = Player()
            self.api = Api()
            self.skipper = Skipper(self.player)
            self._sleep_state = None
            self._wake_retries = 0
            self._playback_state = None
            self._waiting_for = None

        def log(self, *args):
            pass

    return Monitor()


def sleep_and_stop(instance):
    instance.remember_playback()
    instance.onNotification('xbmc', 'System.OnSleep', '{}')
    instance.api.data = {}
    instance.player.tracking = False
    instance.player.last_file = None
    instance.player.state.played_in_a_row = 1
    instance.onNotification('xbmc', 'System.OnWake', '{}')


def test_wake_restores_metadata_after_native_stop(sleeping_monitor):
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data == {'next_episode': {'episodeid': 'next'}}
    assert sleeping_monitor.player.tracking is True
    assert sleeping_monitor._sleep_state is None


def test_wake_waits_for_player_readiness(sleeping_monitor):
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.player.filename = None
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data == {}
    sleeping_monitor.player.filename = 'episode.mkv'
    sleeping_monitor.player.duration = 0
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data == {}
    sleeping_monitor.player.duration = 1200
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.player.tracking is True
    assert sleeping_monitor.api.data


def test_wake_does_not_restore_metadata_to_another_file(sleeping_monitor):
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.player.filename = 'replacement.mkv'
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data == {}
    assert sleeping_monitor.player.tracking is False
    assert sleeping_monitor._sleep_state is None


def test_wake_preserves_prior_popup_dismissal(sleeping_monitor):
    sleeping_monitor.player.last_file = 'episode.mkv'
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.player.last_file == 'episode.mkv'


@pytest.mark.parametrize('current_show_id,expected_count', [('show', 3), ('other', 1)])
def test_wake_restores_still_watching_count_after_real_state_reset(sleeping_monitor, monkeypatch, current_show_id, expected_count):
    monkeypatch.setattr(player.State, '_shared_state', {})
    sleeping_monitor.player.state = player.State()
    manager_state = player.State()
    sleeping_monitor.player.state.played_in_a_row = 3
    sleeping_monitor.player.state.current_tv_show_id = 'show'
    sleeping_monitor.remember_playback()
    sleeping_monitor.onNotification('xbmc', 'System.OnSleep', '{}')

    sleeping_monitor.player.api = sleeping_monitor.api
    sleeping_monitor.player.reset_queue = lambda: None
    sleeping_monitor.api.reset_addon_data = lambda: setattr(sleeping_monitor.api, 'data', {})
    player.UpNextPlayer.onPlayBackStopped(sleeping_monitor.player)
    sleeping_monitor.onNotification('xbmc', 'Player.OnStop', '{}')
    assert manager_state.played_in_a_row == 1

    sleeping_monitor.onNotification('xbmc', 'System.OnWake', '{}')
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.player.state.played_in_a_row == 3
    assert manager_state.played_in_a_row == 3
    lookup = Stub(state=manager_state, get_playlist_position=lambda: False, log=lambda *args: None,
                  api=Stub(has_addon_data=lambda: True,
                           handle_addon_lookup_of_next_episode=lambda: {'episodeid': 'next'},
                           handle_addon_lookup_of_current_episode=lambda: {'episodeid': 'current', 'tvshowid': current_show_id}))
    episode, source = playitem.PlayItem.get_next(lookup)
    assert episode['episodeid'] == 'next'
    assert source == 'addon'
    assert manager_state.played_in_a_row == expected_count


def test_wake_preserves_fresh_metadata(sleeping_monitor):
    sleep_and_stop(sleeping_monitor)
    fresh = {'next_episode': {'episodeid': 'fresh'}}
    sleeping_monitor.api.data = fresh
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data is fresh


def test_sleep_metadata_is_copied(sleeping_monitor):
    sleeping_monitor.remember_playback()
    sleeping_monitor.onNotification('xbmc', 'System.OnSleep', '{}')
    sleeping_monitor.api.data['next_episode']['episodeid'] = 'changed'
    sleeping_monitor.api.data = {}
    sleeping_monitor.onNotification('xbmc', 'System.OnWake', '{}')
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data['next_episode']['episodeid'] == 'next'


def test_unchanged_playback_updates_state_without_copying_metadata(sleeping_monitor, monkeypatch):
    copies = []
    original_copy = monitor.deepcopy

    def copy_metadata(data):
        copies.append(data)
        return original_copy(data)

    monkeypatch.setattr(monitor, 'deepcopy', copy_metadata)
    sleeping_monitor.remember_playback()
    sleeping_monitor.player.last_file = 'episode.mkv'
    sleeping_monitor.player.tracking = False
    sleeping_monitor.player.state.played_in_a_row = 3
    sleeping_monitor.player.state.current_tv_show_id = 'show'
    sleeping_monitor.remember_playback()
    assert len(copies) == 1
    assert sleeping_monitor._playback_state['last_file'] == 'episode.mkv'
    assert sleeping_monitor._playback_state['tracking'] is False
    assert sleeping_monitor._playback_state['played_in_a_row'] == 3
    assert sleeping_monitor._playback_state['current_tv_show_id'] == 'show'


@pytest.mark.parametrize('changed', ['filename', 'metadata', 'encoding'])
def test_changed_playback_refreshes_metadata_snapshot(sleeping_monitor, changed):
    sleeping_monitor.remember_playback()
    previous = sleeping_monitor._playback_state
    if changed == 'filename':
        sleeping_monitor.player.filename = 'replacement.mkv'
    elif changed == 'metadata':
        sleeping_monitor.api.data['next_episode']['episodeid'] = 'changed'
    else:
        sleeping_monitor.api.encoding = 'hex'
    sleeping_monitor.remember_playback()
    snapshot = sleeping_monitor._playback_state
    assert snapshot is not previous
    assert snapshot['filename'] == sleeping_monitor.player.filename
    assert snapshot['encoding'] == sleeping_monitor.api.encoding
    assert snapshot['data'] == sleeping_monitor.api.data
    assert snapshot['data'] is not sleeping_monitor.api.data


def test_wake_expires_when_player_does_not_return(sleeping_monitor):
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.player.filename = None
    for _ in range(30):
        sleeping_monitor.restore_after_wake()
    assert sleeping_monitor._sleep_state is None
    assert sleeping_monitor.api.data == {}


def test_sleep_without_playback_does_not_restore(sleeping_monitor):
    sleeping_monitor.player.filename = None
    sleeping_monitor.onNotification('xbmc', 'System.OnSleep', '{}')
    sleeping_monitor.onNotification('xbmc', 'System.OnWake', '{}')
    assert sleeping_monitor._sleep_state is None
    assert sleeping_monitor._wake_retries == 0


def test_new_addon_notification_cancels_cached_sleep_state(sleeping_monitor, monkeypatch):
    sleeping_monitor.player.state.played_in_a_row = 3
    sleep_and_stop(sleeping_monitor)
    sleeping_monitor.player.state.played_in_a_row = 4
    fresh = {'next_episode': {'episodeid': 'fresh'}}
    monkeypatch.setattr(monitor, 'decode_json', lambda data: (fresh, 'base64'))
    sleeping_monitor.playback_manager = Stub(handle_demo=lambda: None)
    sleeping_monitor.player.reset_queue = lambda: None
    sleeping_monitor.onNotification('plugin.example.SIGNAL', 'Other.upnext_data', 'data')
    assert sleeping_monitor.api.data is fresh
    assert sleeping_monitor._sleep_state is None
    assert sleeping_monitor._wake_retries == 0
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.player.state.played_in_a_row == 4


def test_delayed_sleep_callback_uses_previously_captured_metadata(sleeping_monitor):
    sleeping_monitor.remember_playback()
    sleeping_monitor.player.filename = None
    sleeping_monitor.api.data = {}
    sleeping_monitor.onNotification('xbmc', 'System.OnSleep', '{}')
    sleeping_monitor.onNotification('xbmc', 'Player.OnStop', '{}')
    sleeping_monitor.onNotification('xbmc', 'System.OnWake', '{}')
    sleeping_monitor.player.filename = 'episode.mkv'
    sleeping_monitor.player.tracking = False
    sleeping_monitor.restore_after_wake()
    assert sleeping_monitor.api.data == {'next_episode': {'episodeid': 'next'}}
    assert sleeping_monitor.player.tracking is True


def test_normal_stop_discards_cached_metadata(sleeping_monitor):
    sleeping_monitor.remember_playback()
    sleeping_monitor.onNotification('xbmc', 'Player.OnStop', '{}')
    sleeping_monitor.player.filename = None
    sleeping_monitor.api.data = {}
    sleeping_monitor.onNotification('xbmc', 'System.OnSleep', '{}')
    assert sleeping_monitor._sleep_state is None
