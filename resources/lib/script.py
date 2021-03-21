# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext script"""

from __future__ import absolute_import, division, unicode_literals
import xbmcaddon
import playbackmanager
import player
import state


def test_popup(popup_type, simple_style=False):
    # Create dummy episode to show in popup
    test_episode = {
        'episodeid': -1,
        'tvshowid': -1,
        'title': 'Garden of Bones',
        'art': {
            'thumb': 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-556979e5eda6b.jpg',
            'tvshow.fanart': 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-4fd5fa8ed5e1b.jpg',
            'tvshow.clearart': 'https://fanart.tv/fanart/tv/121361/clearart/game-of-thrones-4fa1349588447.png',
            'tvshow.clearlogo': 'https://fanart.tv/fanart/tv/121361/hdtvlogo/game-of-thrones-504c49ed16f70.png',
            'tvshow.landscape': 'https://fanart.tv/detailpreview/fanart/tv/121361/tvthumb/game-of-thrones-4f78ce73d617c.jpg',
            'tvshow.poster': 'https://fanart.tv/fanart/tv/121361/tvposter/game-of-thrones-521441fd9b45b.jpg',
        },
        'season': 2,
        'episode': 4,
        'showtitle': 'Game of Thrones',
        'plot': 'Lord Baelish arrives at Renly\'s camp just before he faces off against Stannis. '
                'Daenerys and her company are welcomed into the city of Qarth. Arya, Gendry, and '
                'Hot Pie find themselves imprisoned at Harrenhal.',
        'playcount': 1,
        'rating': 8.9,
        'firstaired': 2012,
        'runtime': 3000,
    }
    # Create test state object
    test_state = state.UpNextState()
    # Simulate after file has started
    test_state.starting = 0
    # And while it is playing
    test_state.playing = 1

    # Choose popup style
    test_state.simple_mode = bool(simple_style)
    # Choose popup type
    if popup_type == 'stillwatching':
        test_state.played_in_a_row = test_state.played_limit

    # Create test player object
    test_player = player.UpNextPlayer()
    # Simulate player state
    test_player.state.update({
        # 'external_player': {'value': False, 'force': False},
        # Simulate file is playing
        'playing': {'value': True, 'force': True},
        # 'paused': {'value': False, 'force': False},
        # 'playing_file': {'value': None, 'force': False},
        'speed': {'value': 1, 'force': True},
        # Simulate runtime of endtime minus 10s
        'time': {'value': test_episode['runtime'] - 10, 'force': True},
        # Simulate endtime based on dummy episode
        'total_time': {'value': test_episode['runtime'], 'force': True},
        # 'next_file': {'value': None, 'force': False},
        # 'media_type': {'value': None, 'force': False}
        # 'playnext': {'force': False},
        # Simulate stop to ensure actual playback doesnt stop when popup closes
        'stop': {'force': True}
    })
    # Simulate player state could also be done using the following
    test_player.state.set('playing', True, force=True)
    test_player.state.set('speed', 1, force=True)
    test_player.state.set('time', (test_episode['runtime'] - 10), force=True)
    test_player.state.set('total_time', test_episode['runtime'], force=True)
    test_player.state.set('stop', force=True)

    # Create a test playbackmanager and create an actual popup for testing
    playbackmanager.UpNextPlaybackManager(
        player=test_player,
        state=test_state
    ).launch_popup(
        episode=test_episode,
        source='library'
    )


def open_settings():
    xbmcaddon.Addon().openSettings()


def run(argv):
    """Route to API method"""

    if len(argv) > 2 and argv[1] == 'test_window':
        # Fancy style popup
        if len(argv) == 3:
            test_popup(argv[2])
        # Simple style popup
        elif len(argv) == 4:
            test_popup(argv[2], argv[3])
    else:
        open_settings()
