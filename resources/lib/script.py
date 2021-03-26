# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext script"""

from __future__ import absolute_import, division, unicode_literals
import xbmcaddon
import constants
import playbackmanager
import player
import state


def test_popup(popup_type, simple_style=False):
    # Create dummy episode to simulate now playing info
    test_episode = {
        'episodeid': constants.UNKNOWN_DATA,
        'tvshowid': constants.UNKNOWN_DATA,
        'title': 'Garden of Bones',
        'art': {
            'thumb': 'https://artworks.thetvdb.com/banners/episodes/121361/4245773.jpg',
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
        'rating': 8.8,
        'firstaired': 2012,
        'runtime': 3000,
        'file': 'Game of Thrones - S02E04 - Garden of Bones.mkv'
    }
    # Create dummy episode to simulate next episode to show in popup
    test_next_episode = {
        'episodeid': constants.UNKNOWN_DATA,
        'tvshowid': constants.UNKNOWN_DATA,
        'title': 'The Ghost of Harrenhal',
        'art': {
            'thumb': 'https://artworks.thetvdb.com/banners/episodes/121361/4245774.jpg',
            'tvshow.fanart': 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-4fd5fa8ed5e1b.jpg',
            'tvshow.clearart': 'https://fanart.tv/fanart/tv/121361/clearart/game-of-thrones-4fa1349588447.png',
            'tvshow.clearlogo': 'https://fanart.tv/fanart/tv/121361/hdtvlogo/game-of-thrones-504c49ed16f70.png',
            'tvshow.landscape': 'https://fanart.tv/detailpreview/fanart/tv/121361/tvthumb/game-of-thrones-4f78ce73d617c.jpg',
            'tvshow.poster': 'https://fanart.tv/fanart/tv/121361/tvposter/game-of-thrones-521441fd9b45b.jpg',
        },
        'season': 2,
        'episode': 5,
        'showtitle': 'Game of Thrones',
        'plot': 'Tyrion investigates a secret weapon that King Joffrey plans to use against Stannis. '
                'Meanwhile, as a token for saving his life, Jaqen H\'ghar offers to kill three people '
                'that Arya chooses.',
        'playcount': 0,
        'rating': 8.8,
        'firstaired': 2012,
        'runtime': 3300,
        'file': 'Game of Thrones - S02E05 - The Ghost of Harrenhal.mkv'
    }

    # Create test state object
    test_state = state.UpNextState()
    # Simulate after file has started
    test_state.starting = 0
    # And while it is playing
    test_state.playing = 1
    # Use test episodes so simulate currently/next playing episodes
    test_state.item = {
        'item': test_episode,
        'source': 'library'
    }
    test_state.next_item = {
        'item': test_next_episode,
        'source': 'library'
    }

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
        # Simulate dummy file name
        'playing_file': {'value': test_episode['file'], 'force': True},
        'next_file': {'value': test_next_episode['file'], 'force': True},
        'speed': {'value': 1, 'force': True},
        # Simulate runtime of endtime minus 10s
        'time': {'value': test_episode['runtime'] - 10, 'force': True},
        # Simulate endtime based on dummy episode
        'total_time': {'value': test_episode['runtime'], 'force': True},
        # 'next_file': {'value': None, 'force': False},
        # Simulate episode media type is being played based on dummy episode
        'media_type': {'value': 'episode', 'force': True},
        # 'playnext': {'force': False},
        # Simulate stop to ensure actual playback doesnt stop when popup closes
        'stop': {'force': True}
    })
    # Simulate player state could also be done using the following
    test_player.state.set('playing', True, force=True)
    test_player.state.set('playing_file', test_episode['file'], force=True)
    test_player.state.set('next_file', test_next_episode['file'], force=True)
    test_player.state.set('speed', 1, force=True)
    test_player.state.set('time', (test_episode['runtime'] - 10), force=True)
    test_player.state.set('total_time', test_episode['runtime'], force=True)
    test_player.state.set('media_type', 'episode', force=True)
    test_player.state.set('stop', force=True)

    # Create a test playbackmanager and create an actual popup for testing
    playbackmanager.UpNextPlaybackManager(
        player=test_player, state=test_state
    ).start()


def open_settings():
    xbmcaddon.Addon().openSettings()


def run(argv):
    """Route to API method"""

    # RunScript(service.upnext,test_window,upnext)
    # RunScript(service.upnext,test_window,stillwatching)
    # RunScript(service.upnext,test_window,upnext,simple)
    # RunScript(service.upnext,test_window,stillwatching,simple)
    if len(argv) > 2 and argv[1] == 'test_window':
        # Fancy style popup
        if len(argv) == 3:
            test_popup(argv[2])
        # Simple style popup
        elif len(argv) == 4:
            test_popup(argv[2], argv[3])
    else:
        open_settings()
