# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Tracking videos that aren't library episodes when they play from a playlist (issue #278)"""

import pytest
import player
from test_playbackmanager import Stub


def make_player(monkeypatch, episode_content=False, playlist_setting=True, position=0, size=3, addon_data=False, video=True):
    playlists = []

    class Playlist:
        def __init__(self, playlistid):
            playlists.append(playlistid)

        @staticmethod
        def getposition():
            return position

        @staticmethod
        def size():
            return size

    class Player(player.UpNextPlayer):
        def __init__(self):  # pylint: disable=super-init-not-called
            self.state = Stub(pause=True, track=False)
            self.api = Stub(has_addon_data=lambda: addon_data, get_playlistid=lambda playlistid_cache: 1)
            self.monitor = Stub(waitForAbort=lambda seconds: False)

        def isPlayingVideo(self):  # pylint: disable=invalid-name
            return video

    monkeypatch.setattr(player, 'getCondVisibility', lambda condition: episode_content)
    monkeypatch.setattr(player, 'get_setting_bool', lambda key: playlist_setting if key == 'enablePlaylist' else False)
    monkeypatch.setattr(player, 'PlayList', Playlist)
    instance = Player()
    instance.playlists = playlists
    return instance


@pytest.mark.parametrize('episode_content,playlist_setting,position,size,expected', [
    (True, False, -1, 0, True),     # library episodes are always tracked
    (False, True, 0, 3, True),      # a file with a next item in the playlist
    (False, True, 1, 3, True),
    (False, True, 2, 3, False),     # the last item has nothing to play next
    (False, True, 0, 1, False),     # a single file
    (False, True, -1, 0, False),    # no playlist at all, e.g. a movie played on its own
    (False, False, 0, 3, False),    # playlist integration off: unchanged behaviour
])
def test_is_trackable(monkeypatch, episode_content, playlist_setting, position, size, expected):
    instance = make_player(monkeypatch, episode_content, playlist_setting, position, size)
    assert instance.is_trackable() is expected


def test_music_playlist_is_not_tracked(monkeypatch):
    # A song with another track queued must not get the video popup
    instance = make_player(monkeypatch, video=False)
    assert not instance.is_trackable()
    instance._check_video()  # pylint: disable=protected-access
    instance.onPlayBackResumed()
    assert instance.state.track is False
    assert instance.playlists == []


def test_playlist_is_only_read_when_needed(monkeypatch):
    instance = make_player(monkeypatch, episode_content=True)
    assert instance.is_trackable()
    assert instance.playlists == []
    instance = make_player(monkeypatch, playlist_setting=False)
    assert not instance.is_trackable()
    assert instance.playlists == []


@pytest.mark.parametrize('size,expected', [(3, True), (1, False)])
def test_non_library_playlist_item_starts_tracking(monkeypatch, size, expected):
    instance = make_player(monkeypatch, size=size)
    instance._check_video()  # pylint: disable=protected-access
    assert instance.state.track is expected
    assert instance.playlists == [1]


@pytest.mark.parametrize('size,expected', [(3, True), (1, False)])
def test_resume_rearms_a_non_library_playlist_item(monkeypatch, size, expected):
    instance = make_player(monkeypatch, size=size)
    instance.onPlayBackResumed()
    assert instance.state.pause is False
    assert instance.is_tracking() is expected
