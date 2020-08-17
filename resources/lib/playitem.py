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
        position = self.api.playlist_position()
        has_addon_data = self.api.has_addon_data()

        if position and not has_addon_data:
            episode = self.api.get_next_in_playlist(position)

        elif has_addon_data:
            current_episode = self.api.handle_addon_lookup_of_current_episode()
            episode = self.api.handle_addon_lookup_of_next_episode()
            self.state.current_episode_id = get_int(current_episode, 'episodeid')
            tvshowid = get_int(current_episode, 'tvshowid')
            if self.state.current_tv_show_id != tvshowid:
                self.state.current_tv_show_id = tvshowid
                self.state.played_in_a_row = 1

        else:
            # Get the next episode from Kodi
            episode = self.api.get_next_episode_from_library(self.state.tv_show_id,
                                                             self.state.current_episode_id,
                                                             self.state.include_watched)
        return episode, position

    def handle_now_playing_result(self):
        item = self.api.get_now_playing()
        if not item or item.get('type') != 'episode':
            return None

        self.state.tv_show_id = get_int(item, 'tvshowid')
        if self.state.tv_show_id == -1:
            current_show_title = item.get('showtitle').encode('utf-8')
            self.state.tv_show_id = self.api.showtitle_to_id(title=current_show_title)
            self.log('Fetched missing tvshowid %s' % self.state.tv_show_id, 2)

        # Get current episodeid
        self.state.current_episode_id = get_int(item, 'id')
        if self.state.current_episode_id == -1:
            self.state.current_episode_id = self.api.get_episode_id(
                tvshowid=str(self.state.tv_show_id),
                episode=item.get('episode'),
                season=item.get('season'),
            )
            self.log('Fetched missing episodeid %s' % self.state.current_episode_id, 2)

        if self.state.current_tv_show_id != self.state.tv_show_id:
            self.state.current_tv_show_id = self.state.tv_show_id
            self.state.played_in_a_row = 1

        self.state.current_playcount = item.get('playcount', 0)

        return item
