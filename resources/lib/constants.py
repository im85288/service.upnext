# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals


ADDON_ID = 'service.upnext'

UNDEFINED = -1

WINDOW_HOME = 10000

PLAY_CONTROL_ID = 3012
CLOSE_CONTROL_ID = 3013
PROGRESS_CONTROL_ID = 3014
SHUFFLE_CONTROL_ID = 3015

STOP_STRING_ID = 30033
CLOSE_STRING_ID = 30034
NEXT_STRING_ID = 30049

UNWATCHED_MOVIE_PLOT = 0
UNWATCHED_EPISODE_PLOT = 1
UNWATCHED_EPISODE_THUMB = 2
DEFAULT_SPOILERS = [
    UNWATCHED_MOVIE_PLOT,
    UNWATCHED_EPISODE_PLOT,
    UNWATCHED_EPISODE_THUMB
]
NO_SPOILER_IMAGE = 'OverlaySpoiler.png'
NO_SPOILER_ART = {
    'tvshow.fanart': NO_SPOILER_IMAGE,
    'tvshow.landscape': NO_SPOILER_IMAGE,
    'tvshow.clearart': NO_SPOILER_IMAGE,
    'tvshow.clearlogo': NO_SPOILER_IMAGE,
    'tvshow.poster': NO_SPOILER_IMAGE,
    'thumb': NO_SPOILER_IMAGE,
}

BOOL_STRING_VALUES = {
    'false': False,
    'true': True
}

LOG_ENABLE_DISABLED = 0
LOG_ENABLE_INFO = 1
LOG_ENABLE_DEBUG = 2

PLUGIN_TYPES = (
    'plugin_data_error',
    'plugin_playlist',
    'plugin_play_url',
    'plugin_play_url_playlist',
    'plugin_play_info',
    'plugin_play_info_playlist'
)
PLUGIN_DATA_ERROR = 0
PLUGIN_PLAYLIST = 1
PLUGIN_PLAY_URL = 2
PLUGIN_PLAY_INFO = 4

SETTING_DISABLED = 0
SETTING_ON = 1
SETTING_OFF = 2

POPUP_MIN_DURATION = 5

POPUP_POSITIONS = {
    0: 'bottom',
    1: 'centre',
    2: 'top'
}

POPUP_ACCENT_COLOURS = {
    0: 'FFFF4081',
    1: 'FFFF2A00',
    2: 'FF84DE02',
    3: 'FF3399FF'
}

DEMO_SEEK_15S = 1
DEMO_SEEK_POPUP_TIME = 2
DEMO_SEEK_DETECT_TIME = 3
