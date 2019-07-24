import xbmc
import json
import resources.lib.utils as utils


class Api:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.data = {}

    def log(self, msg, lvl=2):
        class_name = self.__class__.__name__
        utils.log("%s %s" % (utils.addon_name(), class_name), msg, int(lvl))

    def has_addon_data(self):
       return self.data

    def reset_addon_data(self):
        self.data = {}

    def addon_data_received(self, data):
        self.log("addon_data_received called with data %s " % json.dumps(data), 2)
        self.data = data

    @staticmethod
    def play_kodi_item(episode):
        utils.JSONRPC("Player.Open", id=0).execute({"item": {"episodeid": episode["episodeid"]}})

    def get_next_in_playlist(self, position):
        result = utils.JSONRPC("Playlist.GetItems").execute({
            "playlistid": 1,
            "limits": {"start": position+1, "end": position+2},
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed" , "streamdetails"]})
        if result:
            self.log("Got details of next playlist item %s" % json.dumps(result), 2)
            if "result" in result and result["result"].get("items"):
                item = result["result"]["items"][0]
                if item["type"] == "episode":
                    item["episodeid"] = item["id"]
                    item["tvshowid"] = item.get("tvshowid", item["id"])
                    return item

    def play_addon_item(self):
        self.log("sending data to addon to play:  %s " % json.dumps(self.data['play_info']), 2)
        utils.event(self.data['id'], self.data['play_info'], "upnextprovider")

    def handle_addon_lookup_of_next_episode(self):
        if self.data:
            text = ("handle_addon_lookup_of_next_episode episode returning data %s "
                    % json.dumps(self.data["next_episode"]))
            self.log(text, 2)
            return self.data["next_episode"]

    def handle_addon_lookup_of_current_episode(self):
        if self.data:
            text = ("handle_addon_lookup_of_current episode returning data %s "
                    % json.dumps(self.data["current_episode"]))
            self.log(text, 2)
            return self.data["current_episode"]

    def notification_time(self):
        return self.data.get('notification_time') or utils.settings('autoPlaySeasonTime')

    def get_now_playing(self):
        # Get the active player
        result = utils.JSONRPC("Player.GetActivePlayers").execute()
        self.log("Got active player %s" % json.dumps(result), 2)

        # Seems to work too fast loop whilst waiting for it to become active
        while not result["result"]:
            result = utils.JSONRPC("Player.GetActivePlayers").execute()
            self.log("Got active player %s" % json.dumps(result), 2)

        if 'result' in result and result["result"][0] is not None:
            playerid = result["result"][0]["playerid"]

            # Get details of the playing media
            self.log("Getting details of now playing media", 2)
            result = utils.JSONRPC("Player.GetItem").execute({
                "playerid": playerid, 
                "properties": ["showtitle","tvshowid","episode","season","playcount","genre","plotoutline"]})
            self.log("Got details of now playing media %s" % json.dumps(result), 2)
            return result

    def handle_kodi_lookup_of_episode(self, tvshowid, current_file, include_watched, current_episode_id):
        result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute({
            "tvshowid": tvshowid, 
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed" , "streamdetails"],
            "sort": {"method": "episode"}})

        if result:
            self.log("Got details of next up episode %s" % json.dumps(result), 2)
            xbmc.sleep(100)

            # Find the next unwatched and the newest added episodes
            if "result" in result and "episodes" in result["result"]:
                episode = self.find_next_episode(result, current_file, include_watched, current_episode_id)
                return episode

    def handle_kodi_lookup_of_current_episode(self, tvshowid, current_episode_id):
        result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute({
            "tvshowid": tvshowid,
            "properties": ["title", "playcount", "season", "episode", "showtitle", "plot",
                           "file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer",
                           "dateadded", "lastplayed" , "streamdetails"],
            "sort": {"method": "episode"}})
        self.log("Find current episode called", 2)
        position = 0
        if result:
            xbmc.sleep(100)

            # Find the next unwatched and the newest added episodes
            if "result" in result and "episodes" in result["result"]:
                for episode in result["result"]["episodes"]:
                    # find position of current episode
                    if current_episode_id == episode["episodeid"]:
                        # found a match so get out of here
                        break
                    position += 1

                # now return the episode
                self.log("Find current episode found episode in position: %s" % str(position), 2)
                try:
                    episode = result["result"]["episodes"][position]
                except Exception as e:
                    # no next episode found
                    episode = None
                    self.log("error handle_kodi_lookup_of_current_episode  %s" % repr(e), 1)

                return episode

    def showtitle_to_id(self, title):
        try:
            json_result = utils.JSONRPC("VideoLibrary.GetTVShows", id="libTvShows").execute({"properties": ["title"]})
            if 'result' in json_result and 'tvshows' in json_result['result']:
                json_result = json_result['result']['tvshows']
                for tvshow in json_result:
                    if tvshow['label'] == title:
                        return tvshow['tvshowid']
            return '-1'
        except Exception as e:
            self.log("error showtitle_to_id  %s" % repr(e), 1)
            return '-1'

    def get_episode_id(self, showid, show_season, show_episode):
        show_season = int(show_season)
        show_episode = int(show_episode)
        episodeid = 0
        query = {
            "properties": ["season", "episode"],
            "tvshowid": int(showid)
        }
        try:
            json_result = utils.JSONRPC("VideoLibrary.GetEpisodes").execute(query)
            if 'result' in json_result and 'episodes' in json_result['result']:
                json_result = json_result['result']['episodes']
                for episode in json_result:
                    if episode['season'] == show_season and episode['episode'] == show_episode:
                        if 'episodeid' in episode:
                            episodeid = episode['episodeid']
            return episodeid
        except Exception as e:
            self.log("error get_episode_id  %s" % repr(e), 1)
            return episodeid

    def find_next_episode(self, result, current_file, include_watched, current_episode_id):
        position = 0
        for episode in result["result"]["episodes"]:
            # find position of current episode
            if current_episode_id == episode["episodeid"]:
                # found a match so add 1 for the next and get out of here
                position += 1
                break
            position += 1
        # check if it may be a multi-part episode
        while result["result"]["episodes"][position]["file"] == current_file:
            position += 1
        # skip already watched episodes?
        while not include_watched and result["result"]["episodes"][position]["playcount"] > 1:
            position += 1

        try:
            episode = result["result"]["episodes"][position]
        except Exception as e:
            self.log("error get_episode_id  %s" % repr(e), 1)
            # no next episode found
            episode = None

        return episode
