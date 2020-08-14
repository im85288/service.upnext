# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import PlayList, PLAYLIST_VIDEO
from api import Api
from player import Player
from state import State
from utils import log as ulog


class PlayItem:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.player = Player()
        self.state = State()

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    @staticmethod
    def playlist_position():
        playlist = PlayList(PLAYLIST_VIDEO)
        position = playlist.getposition()
        # A playlist with only one element has no next item and PlayList().getposition() starts counting from zero
        if playlist.size() > 1 and position < (playlist.size() - 1):
            # Return 1 based index value
            return position + 1
        return None

    def get_next(self):
        position = self.playlist_position()
        if position:
            episode = self.api.get_next_in_playlist(position)

        elif self.api.has_addon_data():
            episode = self.api.handle_addon_lookup_of_next_episode()
            current_episode = self.api.handle_addon_lookup_of_current_episode()
            self.state.current_episode_id = current_episode.get('episodeid')
            if self.state.current_tv_show_id != current_episode.get('tvshowid'):
                self.state.current_tv_show_id = current_episode.get('tvshowid')
                self.state.played_in_a_row = 1

        else:
            current_file = self.player.getPlayingFile()
            # Get the active player
            result = self.api.get_now_playing()
            self.handle_now_playing_result(result)
            # Get the next episode from Kodi
            episode = self.api.get_next_episode_from_library(self.state.tv_show_id,
                                                             current_file,
                                                             self.state.include_watched,
                                                             self.state.current_episode_id)
        return episode, position

    def handle_now_playing_result(self, result):
        if not result.get('result'):
            return

        item = result.get('result').get('item')
        self.state.tv_show_id = item.get('tvshowid')
        if item.get('type') != 'episode':
            return

        if int(self.state.tv_show_id) == -1:
            current_show_title = item.get('showtitle').encode('utf-8')
            self.state.tv_show_id = self.api.showtitle_to_id(title=current_show_title)
            self.log('Fetched missing tvshowid %s' % self.state.tv_show_id, 2)

        current_episode_number = item.get('episode')
        current_season_id = item.get('season')
        # Get current episodeid
        current_episode_id = self.api.get_episode_id(
            tvshowid=str(self.state.tv_show_id),
            episode=current_episode_number,
            season=current_season_id,
        )
        self.state.current_episode_id = current_episode_id
        if self.state.current_tv_show_id != self.state.tv_show_id:
            self.state.current_tv_show_id = self.state.tv_show_id
            self.state.played_in_a_row = 1
