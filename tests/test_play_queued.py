# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Playing the queued next episode when the current video didn't come from the playlist (#388)"""

import pytest
import api
import playbackmanager
from test_playbackmanager import Stub


def manager(monkeypatch, position, pause_until_next=False, queued_items=True):
    events = []
    monkeypatch.setattr(playbackmanager, 'playlist_position', lambda: position)
    monkeypatch.setattr(playbackmanager, 'play_queued_item', lambda: events.append('open-queued') or queued_items)
    instance = object.__new__(playbackmanager.PlaybackManager)
    instance.state = Stub(queued=True)
    instance.player = Stub(playnext=lambda: events.append('playnext'), pause=lambda: events.append('pause'))
    instance.api = Stub(has_addon_data=lambda: True, play_addon_item=lambda: events.append('open-addon-url'))
    instance.log = lambda *args: None
    instance.pause_until_next = lambda: pause_until_next
    return instance, events


@pytest.mark.parametrize('advance', [True, False])
def test_video_outside_the_playlist_opens_the_queued_item(monkeypatch, advance):
    # Watch now (advance) or the popup running out at the end of the file (no advance): either way Kodi
    # won't move into the playlist from a video it didn't start from there
    instance, events = manager(monkeypatch, position=-1)
    instance._play_next({}, 'addon', queued=True, advance_queued=advance)  # pylint: disable=protected-access
    assert events == ['open-queued']
    # The item playing next must not be removed as a leftover when it starts
    assert instance.state.queued is False


@pytest.mark.parametrize('advance,expected', [(True, ['playnext']), (False, [])])
@pytest.mark.parametrize('position', [0, None])
def test_video_from_the_playlist_keeps_the_playlist_advance(monkeypatch, position, advance, expected):
    # From the playlist, or when Kodi gives no position, nothing changes: playnext() or Kodi's own advance
    instance, events = manager(monkeypatch, position=position)
    instance._play_next({}, 'addon', queued=True, advance_queued=advance)  # pylint: disable=protected-access
    assert events == expected
    assert instance.state.queued is True


def test_pause_until_next_still_opens_the_add_on_url(monkeypatch):
    instance, events = manager(monkeypatch, position=-1, pause_until_next=True)
    instance._play_next({}, 'addon', queued=True, advance_queued=True)  # pylint: disable=protected-access
    assert events == ['open-addon-url']


def test_pause_until_next_at_the_end_of_the_file_opens_the_queued_item(monkeypatch):
    instance, events = manager(monkeypatch, position=-1, pause_until_next=True)
    instance._play_next({}, 'addon', queued=True, advance_queued=False)  # pylint: disable=protected-access
    assert events == ['open-queued']


def test_existing_playlist_is_left_to_kodi(monkeypatch):
    # Up Next didn't queue anything: the video is part of the viewer's own playlist
    instance, events = manager(monkeypatch, position=-1)
    instance._play_next({}, 'playlist', queued=False, advance_queued=True)  # pylint: disable=protected-access
    assert events == ['playnext']


@pytest.fixture(name='rpc')
def fixture_rpc(monkeypatch):
    calls = []
    answers = {}

    def jsonrpc(**kwargs):
        calls.append((kwargs['method'], kwargs.get('params')))
        return answers.get(kwargs['method'], {})

    monkeypatch.setattr(api, 'jsonrpc', jsonrpc)
    monkeypatch.setattr(api.Api, '_get_playerid', staticmethod(lambda playerid_cache=None: 1))
    monkeypatch.setattr(api.Api, 'get_playlistid', staticmethod(lambda playlistid_cache=None: 1))
    return calls, answers


@pytest.mark.parametrize('answer,expected', [({'result': {'position': -1}}, -1), ({'result': {'position': 2}}, 2),
                                             ({'error': {'code': -32100}}, None)])
def test_playlist_position(rpc, answer, expected):
    rpc[1]['Player.GetProperties'] = answer
    assert api.playlist_position() == expected


def test_playlist_position_without_a_player(monkeypatch, rpc):
    monkeypatch.setattr(api.Api, '_get_playerid', staticmethod(lambda playerid_cache=None: None))
    assert api.playlist_position() is None
    assert rpc[0] == []


def test_play_queued_item_opens_the_last_playlist_item(rpc):
    calls, answers = rpc
    answers['Playlist.GetItems'] = {'result': {'items': [{'label': 'old'}, {'label': 'next'}]}}
    assert api.play_queued_item() is True
    assert calls[-1] == ('Player.Open', {'item': {'playlistid': 1, 'position': 1}})


def test_play_queued_item_with_an_empty_playlist(rpc):
    calls, answers = rpc
    answers['Playlist.GetItems'] = {'result': {'limits': {'total': 0}}}
    assert api.play_queued_item() is False
    assert [method for method, _ in calls] == ['Playlist.GetItems']
