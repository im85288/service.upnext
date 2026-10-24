# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Tests for picking the next episode from the Kodi library and from playlists"""

import pytest
import api
import playitem
from test_playbackmanager import Stub


def episode(episodeid, season, number, playcount=0, filename=None, tvshowid=10):
    return {
        'episodeid': episodeid, 'season': season, 'episode': number, 'playcount': playcount,
        'file': filename or 'S%02dE%02d.mkv' % (season, number), 'tvshowid': tvshowid,
    }


class FakeKodi:
    """Answers the JSON-RPC calls Up Next makes, and records them"""

    def __init__(self, episodes=(), tvshows=(), playing=None, playlist_items=()):
        self.episodes = list(episodes)
        self.tvshows = list(tvshows)
        self.playing = playing
        self.playlist_items = list(playlist_items)
        self.calls = []

    def __call__(self, method, params=None, **kwargs):
        self.calls.append((method, params))
        if method == 'Player.GetActivePlayers':
            return {'result': [{'playerid': 1, 'type': 'video'}]}
        if method == 'Player.GetItem':
            return {'result': {'item': self.playing}}
        if method == 'Player.GetProperties':
            return {'result': {'playlistid': 1}}
        if method == 'VideoLibrary.GetEpisodes':
            return {'result': {'episodes': [item for item in self.episodes if item['tvshowid'] == params['tvshowid']]}}
        if method == 'VideoLibrary.GetTVShows':
            return {'result': {'tvshows': self.tvshows}}
        if method == 'Playlist.GetItems':
            start = params['limits']['start']
            return {'result': {'items': self.playlist_items[start:start + 1]}}
        raise AssertionError('Unexpected JSON-RPC call %s' % method)


@pytest.fixture
def kodi(monkeypatch):
    fake = FakeKodi()
    monkeypatch.setattr(api, 'jsonrpc', fake)
    monkeypatch.setattr(api, 'sleep', lambda milliseconds: None)
    return fake


def library_api(data=None):
    instance = object.__new__(api.Api)
    instance.data = data or {}
    instance.encoding = 'base64'
    instance.log = lambda *args, **kwargs: None
    return instance


SEASON = [
    episode(1, 1, 1, playcount=1),
    episode(2, 1, 2, playcount=1),
    episode(3, 1, 3, playcount=1),
    episode(4, 1, 4),
    episode(5, 2, 1),
]


@pytest.mark.parametrize('current_id,include_watched,expected_id', [
    (1, True, 2),       # the episode straight after the current one
    (1, False, 4),      # skips watched episodes when they are excluded
    (3, False, 4),
    (4, True, 5),       # carries on into the next season
    (5, True, None),    # nothing after the last episode
    (99, True, None),   # current episode not in the show
])
def test_find_next_episode(current_id, include_watched, expected_id):
    result = {'result': {'episodes': SEASON}}
    found = library_api().find_next_episode(result, 'playing.mkv', include_watched, current_id)
    assert (found or {}).get('episodeid') == expected_id


def test_find_next_episode_skips_other_parts_of_a_multi_part_episode():
    episodes = [
        episode(1, 1, 1, filename='S01E01-E02.mkv'),
        episode(2, 1, 2, filename='S01E01-E02.mkv'),
        episode(3, 1, 3),
    ]
    found = library_api().find_next_episode({'result': {'episodes': episodes}}, 'S01E01-E02.mkv', True, 1)
    assert found['episodeid'] == 3


def test_find_next_episode_skips_the_playing_file_before_matching_the_id():
    # The playing file can differ from the library path (e.g. a stack:// URL)
    episodes = [episode(1, 1, 1, filename='lib/S01E01.mkv'), episode(2, 1, 2, filename='lib/S01E01.mkv'), episode(3, 1, 3)]
    found = library_api().find_next_episode({'result': {'episodes': episodes}}, 'stack://S01E01.mkv', True, 1)
    assert found['episodeid'] == 3


def test_kodi_lookup_requests_the_show_sorted_by_episode(kodi):
    kodi.episodes = SEASON + [episode(50, 1, 1, tvshowid=20)]
    found = library_api().handle_kodi_lookup_of_episode(10, 'S01E01.mkv', True, 1)
    assert found['episodeid'] == 2
    method, params = kodi.calls[-1]
    assert method == 'VideoLibrary.GetEpisodes'
    assert params['tvshowid'] == 10 and params['sort'] == {'method': 'episode'}
    assert {'file', 'playcount', 'season', 'episode', 'art'} <= set(params['properties'])


def test_kodi_lookup_without_library_result_returns_nothing(monkeypatch):
    monkeypatch.setattr(api, 'jsonrpc', lambda **kwargs: {'error': {'code': -32602}})
    monkeypatch.setattr(api, 'sleep', lambda milliseconds: None)
    assert library_api().handle_kodi_lookup_of_episode(10, 'S01E01.mkv', True, 1) is None
    assert library_api().handle_kodi_lookup_of_current_episode(10, 1) is None


def test_kodi_lookup_of_current_episode(kodi):
    kodi.episodes = SEASON
    assert library_api().handle_kodi_lookup_of_current_episode(10, 3)['episode'] == 3
    assert library_api().handle_kodi_lookup_of_current_episode(10, 99) is None


@pytest.mark.parametrize('season,number,expected', [
    (1, 3, 3),
    ('2', '1', 5),   # season and episode may arrive as strings
    (3, 1, 0),       # not in the library
])
def test_get_episode_id(kodi, season, number, expected):
    kodi.episodes = SEASON
    assert api.Api.get_episode_id(showid='10', show_season=season, show_episode=number) == expected


def test_showtitle_to_id(kodi):
    kodi.tvshows = [{'label': 'Other', 'tvshowid': 20}, {'label': 'Show', 'tvshowid': 10}]
    assert api.Api.showtitle_to_id('Show') == 10
    assert api.Api.showtitle_to_id('Missing') == '-1'


def test_next_playlist_item_fills_in_missing_details(kodi):
    kodi.playlist_items = [
        {'label': 'Current', 'id': 7},
        {'label': 'Home video', 'id': 8, 'season': -1, 'episode': -1},
    ]
    item = library_api().get_next_in_playlist(1)
    assert item['title'] == 'Home video'
    assert item['episodeid'] == 8
    assert item['tvshowid'] == -1
    assert item['season'] == '' and item['episode'] == ''
    assert kodi.calls[-1][1]['limits'] == {'start': 1, 'end': 2}


def test_next_playlist_item_keeps_library_details(kodi):
    kodi.playlist_items = [{}, {'label': 'x', 'title': 'Pilot', 'id': 8, 'tvshowid': 10, 'season': 1, 'episode': 2}]
    item = library_api().get_next_in_playlist(1)
    assert (item['title'], item['tvshowid'], item['season'], item['episode']) == ('Pilot', 10, 1, 2)


def test_end_of_playlist_has_no_next_item(kodi):
    kodi.playlist_items = [{'label': 'Only', 'id': 7}]
    assert library_api().get_next_in_playlist(1) is None


def make_play_item(monkeypatch, api_instance, playlist_size=0, playlist_position=0, last_file='S01E01.mkv'):
    playlist = Stub(size=lambda: playlist_size, getposition=lambda: playlist_position)
    monkeypatch.setattr(playitem, 'PlayList', lambda playlistid: playlist)
    instance = object.__new__(playitem.PlayItem)
    instance.api = api_instance
    instance.player = Stub(get_last_file=lambda: last_file)
    instance.state = Stub(current_episode_id=None, current_tv_show_id=None, tv_show_id=None,
                          include_watched=True, played_in_a_row=3)
    instance.log = lambda *args, **kwargs: None
    return instance


@pytest.mark.parametrize('size,position,expected', [
    (0, -1, False),   # no playlist
    (1, 0, False),    # a single item has no next item
    (3, 0, 1),        # one-based position of the next item
    (3, 1, 2),
    (3, 2, False),    # last item
])
def test_playlist_position(monkeypatch, kodi, size, position, expected):
    instance = make_play_item(monkeypatch, library_api(), playlist_size=size, playlist_position=position)
    assert instance.get_playlist_position() == expected


def test_library_episode_end_to_end(monkeypatch, kodi):
    kodi.episodes = SEASON
    kodi.playing = {'type': 'episode', 'tvshowid': 10, 'season': 1, 'episode': 1, 'showtitle': 'Show'}
    instance = make_play_item(monkeypatch, library_api())
    instance.state.include_watched = False
    found, source = instance.get_next()
    assert (found['episodeid'], source) == (4, 'library')
    assert (instance.state.tv_show_id, instance.state.current_episode_id) == (10, 1)
    assert instance.state.current_tv_show_id == 10 and instance.state.played_in_a_row == 1


def test_library_episode_found_by_show_title(monkeypatch, kodi):
    kodi.episodes = SEASON
    kodi.tvshows = [{'label': 'Show', 'tvshowid': 10}]
    kodi.playing = {'type': 'episode', 'tvshowid': -1, 'season': 1, 'episode': 3, 'showtitle': 'Show'}
    found, source = make_play_item(monkeypatch, library_api()).get_next()
    assert (found['episodeid'], source) == (4, 'library')


def test_same_show_keeps_the_still_watching_count(monkeypatch, kodi):
    kodi.episodes = SEASON
    kodi.playing = {'type': 'episode', 'tvshowid': 10, 'season': 1, 'episode': 2}
    instance = make_play_item(monkeypatch, library_api())
    instance.state.current_tv_show_id = 10
    instance.get_next()
    assert instance.state.played_in_a_row == 3


def test_playlist_takes_priority_over_the_library(monkeypatch, kodi):
    kodi.playlist_items = [{'label': 'Current', 'id': 1}, {'label': 'Queued', 'id': 2}]
    found, source = make_play_item(monkeypatch, library_api(), playlist_size=2, playlist_position=0).get_next()
    assert (found['title'], source) == ('Queued', 'playlist')
    assert not any(method == 'VideoLibrary.GetEpisodes' for method, _ in kodi.calls)


@pytest.mark.parametrize('size,expected_source', [(0, 'addon'), (2, 'playlist')])
def test_addon_data_takes_priority(monkeypatch, kodi, size, expected_source):
    data = {'current_episode': {'episodeid': 1, 'tvshowid': 10}, 'next_episode': {'episodeid': 2, 'title': 'Next'}}
    found, source = make_play_item(monkeypatch, library_api(data), playlist_size=size).get_next()
    assert (found['title'], source) == ('Next', expected_source)
    assert not any(method.startswith('VideoLibrary') for method, _ in kodi.calls)
