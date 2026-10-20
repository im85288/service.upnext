# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals

import pytest
import xbmc
import playbackmanager
import stillwatching
import upnext


class Stub(object):
    def __init__(self, **values):
        self.__dict__.update(values)


@pytest.fixture
def run_popup(monkeypatch):
    def run(action='stop', stop_after_close=True, play_mode=0, source='addon', playback_change=None, active=True, queued=False, popup_kind='next'):
        events = []
        playing_file = ['current.mkv' if active else None]
        popups = []
        state = Stub(playing_next=False, queued=queued, track=True, include_watched=True,
                     current_episode_id='current', play_mode=play_mode, played_in_a_row=1)

        def record(name):
            events.append((name, playing_file[0]))

        def get_playing_file():
            if playing_file[0] is None:
                raise RuntimeError('No active playback')
            return playing_file[0]

        def setting(name):
            return {'enablePlaylist': True, 'stopAfterClose': stop_after_close}[name]

        # Capture Stop from either the dialog's xbmc.Player or the manager's player.
        monkeypatch.setattr(xbmc.Player, 'stop', lambda self: record('stop'))
        player = Stub(getPlayingFile=get_playing_file, stop=lambda: record('stop'), playnext=lambda: record('next-playlist'))
        api = Stub(queue_next_item=lambda episode: queued,
                   dequeue_next_item=lambda: record('dequeue'), reset_addon_data=lambda: record('reset'),
                   has_addon_data=lambda: True, play_addon_item=lambda: record('next-addon'),
                   play_kodi_item=lambda episode: record('next-library'))

        class Popup(upnext.UpNext):
            def __init__(self, *args):
                self.cancel = False
                self.watchnow = False
                self.closed = False
                popups.append(self)

            def close(self):
                if not self.closed:
                    record('close')
                    self.closed = True
                    if playback_change == 'replacement':
                        playing_file[0] = 'replacement.mkv'

        class StillPopup(stillwatching.StillWatching):
            def __init__(self, *args):
                self.cancel = False
                self.stillwatching = False
                self.closed = False

            def close(self):
                if not self.closed:
                    record('close')
                    self.closed = True

        class Manager(playbackmanager.PlaybackManager):
            def __init__(self):
                self.state = state
                self.player = player
                self.api = api
                self.play_item = Stub(get_next=lambda: ({'episodeid': 'next', 'playcount': 0}, source))

            def log(self, *args):
                pass

            def show_popup_and_wait(self, episode, popup, still_watching):
                target = popup if popup_kind == 'next' else still_watching
                if playback_change == 'ended':
                    playing_file[0] = None
                    state.track = False
                elif action == 'stop':
                    target.onClick(3013)
                elif action == 'watch':
                    target.onClick(3012)
                elif action == 'back':
                    target.onAction(92)
                else:
                    assert action == 'timeout'
                return popup_kind == 'next', popup_kind == 'still'

        monkeypatch.setattr(playbackmanager, 'get_setting_bool', setting)
        monkeypatch.setattr(upnext, 'get_setting_bool', setting)
        monkeypatch.setattr(playbackmanager, 'get_setting_int', lambda name: 1)
        monkeypatch.setattr(playbackmanager, 'addon_path', lambda: '')
        monkeypatch.setattr(playbackmanager, 'UpNext', Popup)
        monkeypatch.setattr(playbackmanager, 'StillWatching', StillPopup)
        monkeypatch.setattr(playbackmanager, 'event', lambda **kwargs: record('watched'))
        monkeypatch.setattr(playbackmanager, 'clear_property', lambda name: None)
        manager = Manager()
        manager.launch_up_next()
        return events, manager, popups

    return run


def test_stop_once_after_popup_closes(run_popup):
    events, _, _ = run_popup()
    assert [event for event in events if event[0] == 'stop'] == [('stop', 'current.mkv')]
    assert events.index(('close', 'current.mkv')) < events.index(('stop', 'current.mkv'))


def test_close_keeps_playback_when_stop_is_disabled(run_popup):
    events, _, _ = run_popup(stop_after_close=False)
    assert not any(event[0] == 'stop' for event in events)


@pytest.mark.parametrize('action,play_mode,source,expected', [
    ('watch', 0, 'addon', 'next-addon'),
    ('watch', 1, 'addon', 'next-addon'),
    ('timeout', 0, 'addon', 'next-addon'),
    ('watch', 0, 'playlist', 'next-playlist'),
])
def test_next_episode_behavior_is_preserved(run_popup, action, play_mode, source, expected):
    events, _, _ = run_popup(action=action, play_mode=play_mode, source=source)
    assert sum(event[0] == expected for event in events) == 1
    assert not any(event[0] == 'stop' for event in events)


def test_replacement_playback_and_queue_are_preserved(run_popup):
    events, manager, _ = run_popup(playback_change='replacement', queued=True)
    assert not any(event[0] in ('stop', 'dequeue', 'reset') for event in events)
    assert manager.state.queued is True


def test_ended_playback_is_not_stopped_again(run_popup):
    events, _, _ = run_popup(playback_change='ended')
    assert not any(event[0] in ('stop', 'dequeue', 'reset') for event in events)


def test_inactive_playback_does_not_open_popup(run_popup):
    events, _, popups = run_popup(active=False)
    assert events == []
    assert popups == []


@pytest.mark.parametrize('popup_kind', ['next', 'still'])
@pytest.mark.parametrize('stop_after_close', [True, False])
def test_back_dismisses_popup_without_stopping_video(run_popup, popup_kind, stop_after_close):
    events, _, _ = run_popup(action='back', popup_kind=popup_kind, stop_after_close=stop_after_close)
    assert any(event[0] == 'close' for event in events)
    assert not any(event[0] == 'stop' for event in events)


def test_still_watching_stop_button_still_stops(run_popup):
    events, _, _ = run_popup(popup_kind='still')
    assert [event for event in events if event[0] == 'stop'] == [('stop', 'current.mkv')]
