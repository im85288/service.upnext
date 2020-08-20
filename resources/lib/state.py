# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from utils import get_setting_bool, get_setting_int


# keeps track of the state parameters
class State:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        # Settings state variables
        self.disabled = get_setting_bool('disableNextUp')
        self.auto_play = get_setting_int('autoPlayMode') == 0
        self.unwatched_only = not get_setting_bool('includeWatched')
        self.enable_playlist = get_setting_bool('enablePlaylist')
        self.played_limit = get_setting_int('playedInARow')
        self.simple_mode = get_setting_int('simpleMode') == 0
        # Current file details
        self.tvshowid = None
        self.episodeid = None
        self.playcount = 0
        # Previous file details
        self.last_file = None
        # Internal state variables
        self.track = False
        self.pause = False
        self.queued = False
        self.playing_next = False
        self.starting = False
        self.played_in_a_row = 1
