# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import json
import xbmc
from . import utils


class Api:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.data = {}

    def log(self, msg, lvl=2):
        class_name = self.__class__.__name__
        utils.log('[%s] %s' % (utils.ADDON_ID, class_name), msg, int(lvl))

    def has_addon_data(self):
        return self.data

    def reset_addon_data(self):
        self.data = {}

    def addon_data_received(self, data):
        self.log("addon_data_received called with data %s " % json.dumps(data), 2)
        self.data = data

    @staticmethod
    def play_kodi_item(episode):
        utils.JSONRPC("Player.Open", id=0).execute({"item": {"episodeid": episode.get('episodeid')}})

    def get_next_in_playlist(self, position):
        result = utils.JSONRPC("Playlist.GetItems").execute({
            "playlistid": 1,
            "limits": {"start": position + 1, "end": position + 2},
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed", "streamdetails"]})
        if result:
            self.log("Got details of next playlist item %s" % json.dumps(result), 2)
            if result.get('result') and result.get('result', {}).get('items'):
                item = result.get('result', {}).get('items', [])[0]
                if item.get('type') == 'episode':
                    item['episodeid'] = item.get('id')
                    item['tvshowid'] = item.get('tvshowid', item.get('id'))
                    return item
        return None

    def play_addon_item(self):
        self.log("sending data to addon to play:  %s " % json.dumps(self.data.get('play_info')), 2)
        utils.event(self.data.get('id'), self.data.get('play_info'), 'upnextprovider')

    def handle_addon_lookup_of_next_episode(self):
        if not self.data:
            return None
        text = ("handle_addon_lookup_of_next_episode episode returning data %s "
                % json.dumps(self.data.get('next_episode')))
        self.log(text, 2)
        return self.data.get('next_episode')

    def handle_addon_lookup_of_current_episode(self):
        if not self.data:
            return None
        text = ("handle_addon_lookup_of_current episode returning data %s "
                % json.dumps(self.data.get('current_episode')))
        self.log(text, 2)
        return self.data.get('current_episode')

    def notification_time(self):
        return self.data.get('notification_time') or utils.settings('autoPlaySeasonTime')

    def get_now_playing(self):
        # Get the active player
        result = utils.JSONRPC("Player.GetActivePlayers").execute()
        self.log("Got active player %s" % json.dumps(result), 2)

        # Seems to work too fast loop whilst waiting for it to become active
        while not result.get('result'):
            result = utils.JSONRPC("Player.GetActivePlayers").execute()
            self.log("Got active player %s" % json.dumps(result), 2)

        if result.get('result') and result.get('result', [])[0] is not None:
            playerid = result.get('result')[0].get('playerid')

            # Get details of the playing media
            self.log("Getting details of now playing media", 2)
            result = utils.JSONRPC("Player.GetItem").execute({
                "playerid": playerid,
                "properties": ["showtitle", "tvshowid", "episode", "season", "playcount", "genre", "plotoutline"]})
            self.log("Got details of now playing media %s" % json.dumps(result), 2)
            return result

    def handle_kodi_lookup_of_episode(self, tvshowid, current_file, include_watched, current_episode_id):
        result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute({
            "tvshowid": tvshowid,
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed", "streamdetails"],
            "sort": {"method": "episode"}})

        if result:
            self.log("Got details of next up episode %s" % json.dumps(result), 2)
            xbmc.sleep(100)

            # Find the next unwatched and the newest added episodes
            if result.get('result') and result.get('result', {}).get('episodes'):
                episode = self.find_next_episode(result, current_file, include_watched, current_episode_id)
                return episode
        return None

    def handle_kodi_lookup_of_current_episode(self, tvshowid, current_episode_id):
        result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute({
            "tvshowid": tvshowid,
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed", "streamdetails"],
            "sort": {"method": "episode"}})
        self.log("Find current episode called", 2)
        position = 0
        if result:
            xbmc.sleep(100)

            # Find the next unwatched and the newest added episodes
            if result.get('result') and result.get('result', {}).get('episodes'):
                for episode in result.get('result').get('episodes'):
                    # find position of current episode
                    if current_episode_id == episode.get('episodeid'):
                        # found a match so get out of here
                        break
                    position += 1

                # now return the episode
                self.log("Find current episode found episode in position: %d" % position, 2)
                try:
                    episode = result.get('result').get('episodes')[position]
                except Exception as exc:  # pylint: disable=broad-except
                    # no next episode found
                    episode = None
                    self.log("error handle_kodi_lookup_of_current_episode  %s" % repr(exc), 1)

                return episode
        return None

    @staticmethod
    def showtitle_to_id(title):
        json_result = utils.JSONRPC("VideoLibrary.GetTVShows", id="libTvShows").execute({"properties": ["title"]})
        if json_result.get('result') and json_result.get('result', {}).get('tvshows'):
            json_result = json_result.get('result').get('tvshows')
            for tvshow in json_result:
                if tvshow.get('label') == title:
                    return tvshow.get('tvshowid')
        return '-1'

    @staticmethod
    def get_episode_id(showid, show_season, show_episode):
        show_season = int(show_season)
        show_episode = int(show_episode)
        episodeid = 0
        query = {
            "properties": ["season", "episode"],
            "tvshowid": int(showid)
        }
        json_result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute(query)
        if json_result.get('result') and json_result.get('result', {}).get('episodes'):
            json_result = json_result.get('result').get('episodes')
            for episode in json_result:
                if episode.get('season') == show_season and episode.get('episode') == show_episode:
                    if episode.get('episodeid'):
                        episodeid = episode.get('episodeid')
        return episodeid

    def find_next_episode(self, result, current_file, include_watched, current_episode_id):
        position = 0
        for episode in result.get('result').get('episodes'):
            # find position of current episode
            if current_episode_id == episode.get('episodeid'):
                # found a match so add 1 for the next and get out of here
                position += 1
                break
            position += 1
        # check if it may be a multi-part episode
        while result.get('result').get('episodes')[position].get('file') == current_file:
            position += 1
        # skip already watched episodes?
        while not include_watched and result.get('result').get('episodes')[position].get('playcount') > 1:
            position += 1

        try:
            episode = result.get('result').get('episodes')[position]
        except Exception as exc:  # pylint: disable=broad-except
            self.log("error get_episode_id  %s" % repr(exc), 1)
            # no next episode found
            episode = None

        return episode
