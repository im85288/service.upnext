# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals


ADDON_ID = 'service.upnext'

UNKNOWN_DATA = -1

WINDOW_HOME = 10000

PLAY_CONTROL_ID = 3012
CLOSE_CONTROL_ID = 3013
PROGRESS_CONTROL_ID = 3014
SHUFFLE_CONTROL_ID = 3015

STOP_STRING_ID = 30033
CLOSE_STRING_ID = 30034
NEXT_STRING_ID = 30049

BOOL_STRING_VALUES = {
    'false': False,
    'true': True
}

LOG_ENABLE_DISABLED = 0
LOG_ENABLE_INFO = 1
LOG_ENABLE_DEBUG = 2

ADDON_TYPES = (
    'addon_data_error',
    'addon_playlist',
    'addon_play_url',
    'addon_play_url_playlist',
    'addon_play_info',
    'addon_play_info_playlist'
)
ADDON_DATA_ERROR = 0
ADDON_PLAYLIST = 1
ADDON_PLAY_URL = 2
ADDON_PLAY_INFO = 4

SETTING_DISABLED = 0
SETTING_FORCED_ON = 1
SETTING_FORCED_OFF = 2

POPUP_MIN_DURATION = 5

TRACKER_MODE_LOOP = 0
TRACKER_MODE_THREAD = 1
TRACKER_MODE_TIMER = 2

DEMO_SEEK_15S = 1
DEMO_SEEK_POPUP_TIME = 2
DEMO_SEEK_DETECT_TIME = 3
