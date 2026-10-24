# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

import pytest
import api
import playitem
import stillwatching
import upnext
from test_playbackmanager import Stub
from test_resume_tracking import run_monitor


def test_failed_popup_does_not_stop_the_service(monkeypatch):
    calls = []

    def launch():
        calls.append('popup')
        raise AttributeError("'NoneType' object has no attribute 'get'")

    # run_monitor() only returns if no exception escaped the service loop
    events, attempts = run_monitor(monkeypatch, launch=launch, max_ticks=5)
    assert calls == ['popup']
    assert events == ['clear service.upnext.dialog', 'disabled']
    assert any('Up Next failed' in message for message in attempts['messages'])


def quiet_api():
    instance = object.__new__(api.Api)
    instance.log = lambda *args, **kwargs: None
    return instance


def test_get_now_playing_gives_up_without_an_active_player(monkeypatch):
    sleeps = []
    monkeypatch.setattr(api, 'jsonrpc', lambda **kwargs: {'result': []})
    monkeypatch.setattr(api, 'sleep', sleeps.append)
    assert quiet_api().get_now_playing() is None
    assert len(sleeps) == 10


def test_get_now_playing_waits_for_the_player(monkeypatch):
    responses = iter([{'result': []}, {'result': [{'playerid': 1}]}, {'result': {'item': {'type': 'episode'}}}])
    monkeypatch.setattr(api, 'jsonrpc', lambda **kwargs: next(responses))
    monkeypatch.setattr(api, 'sleep', lambda milliseconds: None)
    assert quiet_api().get_now_playing() == {'result': {'item': {'type': 'episode'}}}


def make_play_item(api_stub):
    instance = object.__new__(playitem.PlayItem)
    instance.api = api_stub
    instance.player = Stub(get_last_file=lambda: 'current.mkv')
    instance.state = Stub(current_episode_id=None, current_tv_show_id='show', played_in_a_row=3, tv_show_id=None, include_watched=True)
    instance.log = lambda *args, **kwargs: None
    instance.get_playlist_position = lambda: False
    return instance


@pytest.mark.parametrize('data,expected', [
    ({'next_episode': {'episodeid': 2}, 'play_url': 'plugin://next'}, {'episodeid': 2}),
    ({'current_episode': {'episodeid': 1}, 'play_url': 'plugin://next'}, None),
])
def test_addon_data_with_missing_episodes_is_tolerated(data, expected):
    real_api = quiet_api()
    real_api.data = data
    assert make_play_item(real_api).get_next() == (expected, 'addon')


def test_library_lookup_stops_without_a_playing_episode():
    lookups = []
    api_stub = Stub(has_addon_data=lambda: {}, get_now_playing=lambda: None,
                    handle_kodi_lookup_of_episode=lambda *args: lookups.append(args))
    assert make_play_item(api_stub).get_next() == (None, 'library')
    assert lookups == []


@pytest.mark.parametrize('item,title_id,expected_show', [
    ({'type': 'episode', 'showtitle': 'Show', 'season': 1, 'episode': 2}, 7, 7),
    ({'type': 'episode', 'tvshowid': -1, 'showtitle': 'Unknown', 'season': 1, 'episode': 2}, '-1', None),
    ({'type': 'movie'}, 7, None),
    ({}, 7, None),
])
def test_now_playing_needs_a_known_library_show(item, title_id, expected_show):
    api_stub = Stub(showtitle_to_id=lambda title: title_id, get_episode_id=lambda **kwargs: 5)
    instance = make_play_item(api_stub)
    assert instance.handle_now_playing_result({'result': {'item': item}}) is (expected_show is not None)
    if expected_show is not None:
        assert instance.state.tv_show_id == expected_show
        assert instance.state.current_episode_id == 5


@pytest.mark.parametrize('popup_class', [upnext.UpNext, stillwatching.StillWatching])
@pytest.mark.parametrize('item', [None, {}, {'title': 'Pilot', 'season': 1}])
def test_popup_tolerates_partial_episode_metadata(popup_class, item):
    popup = object.__new__(popup_class)
    properties = {}
    popup.setProperty = properties.__setitem__
    popup.set_item(item)
    popup.set_info()
    if item is None:
        assert not properties
    else:
        assert properties['seasonepisode'] == '{}x.'.format(item.get('season', ''))
        assert properties['fanart'] == ''
