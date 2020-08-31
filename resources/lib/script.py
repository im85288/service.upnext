# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual Up Next script"""

from __future__ import absolute_import, division, unicode_literals
import xbmcaddon
import playbackmanager
import player
import state
import utils


def test_popup(popup_type, simple_style=False):
    episode = dict(
        episodeid=-1,
        tvshowid=-1,
        title='Garden of Bones',
        art={
            'thumb': 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-556979e5eda6b.jpg',
            'tvshow.fanart': 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-4fd5fa8ed5e1b.jpg',
            'tvshow.clearart': 'https://fanart.tv/fanart/tv/121361/clearart/game-of-thrones-4fa1349588447.png',
            'tvshow.clearlogo': 'https://fanart.tv/fanart/tv/121361/hdtvlogo/game-of-thrones-504c49ed16f70.png',
            'tvshow.landscape': 'https://fanart.tv/detailpreview/fanart/tv/121361/tvthumb/game-of-thrones-4f78ce73d617c.jpg',
            'tvshow.poster': 'https://fanart.tv/fanart/tv/121361/tvposter/game-of-thrones-521441fd9b45b.jpg',
        },
        season=2,
        episode=4,
        showtitle='Game of Thrones',
        plot='Lord Baelish arrives at Renly\'s camp just before he faces off against Stannis. '
             'Daenerys and her company are welcomed into the city of Qarth. Arya, Gendry, and '
             'Hot Pie find themselves imprisoned at Harrenhal.',
        playcount=1,
        rating=8.9,
        firstaired=2012,
        runtime=3000,
    )

    test_state = state.UpNextState()
    test_state.starting = 0
    test_state.ended = 0
    test_state.simple_mode = bool(simple_style)
    if popup_type == 'stillwatching':
        test_state.played_in_a_row = test_state.played_limit

    test_player = player.UpNextPlayer()
    player_state = dict(
        # external_player={'value': False, 'force': False},
        playing={'value': True, 'force': True},
        # paused={'value': False, 'force': False},
        # playing_file={'value': '', 'force': False},
        time={'value': episode['runtime'] - 60, 'force': True},
        total_time={'value': episode['runtime'], 'force': True},
        # next_file={'value': '', 'force': False},
        # playnext={'force': False},
        stop={'force': True}
    )
    test_player.state.update(player_state)
    playbackmanager.PlaybackManager(
        player=test_player,
        state=test_state
    ).launch_popup(
        episode=episode,
        playlist_item=False
    )


def open_settings():
    xbmcaddon.Addon().openSettings()


def run(argv):
    """Route to API method"""
    if len(argv) > 2 and argv[1] == 'test_window':
        if len(argv) == 3:
            test_popup(argv[2])
        elif len(argv) == 4:
            test_popup(argv[2], argv[3])
    else:
        open_settings()
