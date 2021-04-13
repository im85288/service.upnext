# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import random

LIBRARY = {
    'tvshows': {
        'Game of Thrones': {
            'tvshowid': random.randint(0, 9)
        },
        'Breaking Bad': {
            'tvshowid': random.randint(10, 19)
        },
        'The Mandalorian': {
            'tvshowid': random.randint(20, 29)
        },
        'The Handmaid\'s Tale': {
            'tvshowid': random.randint(30, 39)
        },
        'Mad Men': {
            'tvshowid': random.randint(40, 49)
        }
    },
    'episodes': [
        {
            'episodeid': random.randint(0, 9),
            'tvshowid': -1,
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
            'firstaired': 'April 22, 2012',
            'runtime': 3000,
            'file': 'file://media/tvshows/Game of Thrones/Season 02/Game of Thrones - S02E04 - Garden of Bones.mkv'
        },
        {
            'episodeid': random.randint(10, 19),
            'tvshowid': -1,
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
            'firstaired': 'April 29, 2012',
            'runtime': 3300,
            'file': 'file://media/tvshows/Game of Thrones/Season 02/Game of Thrones - S02E05 - The Ghost of Harrenhal.mkv'
        }
    ]
}

for episode in LIBRARY['episodes']:
    episode['tvshowid'] = (
        LIBRARY['tvshows'].get(episode['showtitle'], {}).get('tvshowid', -1)
    )
del episode  # pylint: disable=undefined-loop-variable
