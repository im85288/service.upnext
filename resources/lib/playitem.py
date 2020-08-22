# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from api import Api
from state import State
from utils import get_int, log as ulog


class PlayItem:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.state = State()

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def get_next(self):
        episode = None
        position = self.api.get_playlist_position()
        has_addon_data = self.api.has_addon_data()

        # File from non addon playlist
        if position and not has_addon_data:
            episode = self.api.get_next_in_playlist(position)

        # File from addon
        elif has_addon_data:
            episode = self.api.handle_addon_lookup_of_next_episode()

        # File from Kodi library
        else:
            episode, new_season = self.api.get_next_episode_from_library(
                self.state.tvshowid,
                self.state.episodeid,
                self.state.unwatched_only
            )
            # Show Still Watching? popup if next episode is from next season
            if new_season:
                self.state.played_in_a_row = self.state.played_limit

        return episode, position

    def handle_addon_now_playing(self):
        item = self.api.handle_addon_lookup_of_current_episode()
        if not item:
            return None

        tvshowid = get_int(item, 'tvshowid')

        # Reset play count if new show playing
        if self.state.tvshowid != tvshowid:
            msg = 'Reset played count: tvshowid change from {0} to {1}'
            msg = msg.format(
                self.state.tvshowid,
                tvshowid
            )
            self.log(msg, 2)
            self.state.tvshowid = tvshowid
            self.state.played_in_a_row = 1

        self.state.episodeid = get_int(item, 'episodeid')

        self.state.playcount = get_int(item, 'playcount', 0)

        return item

    def handle_library_now_playing(self):
        item = self.api.get_now_playing()
        if not item or item.get('type') != 'episode':
            return None

        # Get current tvshowid or search in library if detail missing
        tvshowid = get_int(item, 'tvshowid')
        if tvshowid == -1:
            title = item.get('showtitle').encode('utf-8')
            self.state.tvshowid = self.api.get_tvshowid(title)
            self.log('Fetched tvshowid: %s' % self.state.tvshowid, 2)

        # Reset play count if new show playing
        if self.state.tvshowid != tvshowid:
            msg = 'Reset played count: tvshowid change from {0} to {1}'
            msg = msg.format(
                self.state.tvshowid,
                tvshowid
            )
            self.log(msg, 2)
            self.state.tvshowid = tvshowid
            self.state.played_in_a_row = 1

        # Get current episodeid or search in library if detail missing
        self.state.episodeid = get_int(item, 'id')
        if self.state.episodeid == -1:
            self.state.episodeid = self.api.get_episodeid(
                tvshowid,
                item.get('season'),
                item.get('episode')
            )
            self.log('Fetched episodeid: %s' % self.state.episodeid, 2)

        self.state.playcount = get_int(item, 'playcount', 0)

        return item
