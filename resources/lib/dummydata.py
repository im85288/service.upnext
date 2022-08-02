# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import random
import constants

LIBRARY = {
    'tvshows': {
        'Game of Thrones': {
            'tvshowid': constants.UNDEFINED,
        },
        'Breaking Bad': {
            'tvshowid': constants.UNDEFINED,
        },
        'The Mandalorian': {
            'tvshowid': constants.UNDEFINED,
        },
        'The Handmaid\'s Tale': {
            'tvshowid': constants.UNDEFINED,
        },
        'Mad Men': {
            'tvshowid': constants.UNDEFINED,
        }
    },
    'episodes': [
        {
            'episodeid': constants.UNDEFINED,
            'tvshowid': constants.UNDEFINED,
            'title': 'Garden of Bones',
            'art': {
                'thumb': 'https://artworks.thetvdb.com/banners/episodes/121361/4245773.jpg',
                'tvshow.fanart': 'https://artworks.thetvdb.com/banners/fanart/original/121361-5.jpg',
                'tvshow.landscape': 'https://artworks.thetvdb.com/banners/fanart/original/121361-4.jpg',
                'tvshow.poster': 'https://artworks.thetvdb.com/banners/posters/121361-4.jpg',
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
            'episodeid': constants.UNDEFINED,
            'tvshowid': constants.UNDEFINED,
            'title': 'The Ghost of Harrenhal',
            'art': {
                'thumb': 'https://artworks.thetvdb.com/banners/episodes/121361/4245774.jpg',
                'tvshow.fanart': 'https://artworks.thetvdb.com/banners/fanart/original/121361-5.jpg',
                'tvshow.landscape': 'https://artworks.thetvdb.com/banners/fanart/original/121361-4.jpg',
                'tvshow.poster': 'https://artworks.thetvdb.com/banners/posters/121361-4.jpg',
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


def update_library_ids():
    for idx, tvshow in enumerate(LIBRARY['tvshows']):
        min_id = idx * 10
        max_id = min_id + 9
        LIBRARY['tvshows'][tvshow]['tvshowid'] = random.randint(min_id, max_id)

    for idx, episode in enumerate(LIBRARY['episodes']):
        min_id = idx * 10
        max_id = min_id + 9
        episode['episodeid'] = random.randint(min_id, max_id)

        tvshow = LIBRARY['tvshows'].get(episode['showtitle'], {})
        episode['tvshowid'] = tvshow.get('tvshowid', constants.UNDEFINED)


update_library_ids()
