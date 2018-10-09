import xbmc
import resources.lib.utils as utils
import AddonSignals
from resources.lib.upnext import UpNext
from resources.lib.stillwatching import StillWatching
import sys

if sys.version_info < (2, 7):
    import simplejson as json
else:
    import json

# service class for playback monitoring
class Player(xbmc.Player):
    # Borg - multiple instances, shared state
    _shared_state = {}

    xbmcplayer = xbmc.Player()
    logLevel = 0
    currenttvshowid = None
    currentepisodeid = None
    playedinarow = 1

    def __init__(self, *args):
        self.__dict__ = self._shared_state
        self.logMsg("Starting playback monitor service", 1)
        self.emby_data = None
        self.emby_mode = False
        AddonSignals.registerSlot('embycon', 'embycon_next_episode', self.emby_data_received)

    def logMsg(self, msg, lvl=1):
        self.className = self.__class__.__name__
        utils.logMsg("%s %s" % (utils.addon_name(), self.className), msg, int(lvl))

    def getNowPlaying(self):
        # Get the active player
        result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Player.GetActivePlayers"}')
        result = unicode(result, 'utf-8', errors='ignore')
        self.logMsg("Got active player " + result, 2)
        result = json.loads(result)

        # Seems to work too fast loop whilst waiting for it to become active
        while not result["result"]:
            result = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "id": 1, "method": "Player.GetActivePlayers"}')
            result = unicode(result, 'utf-8', errors='ignore')
            self.logMsg("Got active player " + result, 2)
            result = json.loads(result)

        if 'result' in result and result["result"][0] is not None:
            playerid = result["result"][0]["playerid"]

            # Get details of the playing media
            self.logMsg("Getting details of now  playing media", 1)
            result = xbmc.executeJSONRPC(
                '{"jsonrpc": "2.0", "id": 1, "method": "Player.GetItem", "params": {"playerid": ' + str(
                    playerid) + ', "properties": ["showtitle", "tvshowid", "episode", "season", "playcount","genre","plotoutline"] } }')
            result = unicode(result, 'utf-8', errors='ignore')
            self.logMsg("Got details of now playing media" + result, 2)

            result = json.loads(result)
            return result


    def showtitle_to_id(self, title):
        query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetTVShows",
                "params": {
                    "properties": ["title"]
                },
                "id": "libTvShows"
                }
        try:
            json_result = json.loads(xbmc.executeJSONRPC(json.dumps(query, encoding='utf-8')))
            if 'result' in json_result and 'tvshows' in json_result['result']:
                json_result = json_result['result']['tvshows']
                for tvshow in json_result:
                    if tvshow['label'] == title:
                        return tvshow['tvshowid']
            return '-1'
        except Exception:
            return '-1'

    def get_episode_id(self, showid, showseason, showepisode):
        showseason = int(showseason)
        showepisode = int(showepisode)
        episodeid = 0
        query = {
                "jsonrpc": "2.0",
                "method": "VideoLibrary.GetEpisodes",
                "params": {
                    "properties": ["season", "episode"],
                    "tvshowid": int(showid)
                },
                "id": "1"
                }
        try:
            json_result = json.loads(xbmc.executeJSONRPC(json.dumps(query, encoding='utf-8')))
            if 'result' in json_result and 'episodes' in json_result['result']:
                json_result = json_result['result']['episodes']
                for episode in json_result:
                    if episode['season'] == showseason and episode['episode'] == showepisode:
                        if 'episodeid' in episode:
                            episodeid = episode['episodeid']
            return episodeid
        except Exception:
            return episodeid

    def findNextEpisode(self, result, currentFile, includeWatched):
        self.logMsg("Find next episode called", 1)
        position = 0
        for episode in result["result"]["episodes"]:
            # find position of current episode
            if self.currentepisodeid == episode["episodeid"]:
                # found a match so add 1 for the next and get out of here
                position += 1
                break
            position += 1
        # check if it may be a multi-part episode
        while result["result"]["episodes"][position]["file"] == currentFile:
            position += 1
        # skip already watched episodes?
        while not includeWatched and result["result"]["episodes"][position]["playcount"] > 1:
            position += 1

        # now return the episode
        self.logMsg("Find next episode found next episode in position: " + str(position), 1)
        try:
            episode = result["result"]["episodes"][position]
        except:
            # no next episode found
            episode = None

        return episode

    def handle_kodi_lookup_of_episode(self, tvshowid, currentFile, includeWatched):
        result = xbmc.executeJSONRPC(
            '{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, '
            '"properties": [ "title", "playcount", "season", "episode", "showtitle", "plot", '
            '"file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer", '
            '"dateadded", "lastplayed" , "streamdetails"], "sort": {"method": "episode"}}, "id": 1}'
            % tvshowid)

        if result:
            result = unicode(result, 'utf-8', errors='ignore')
            result = json.loads(result)
            self.logMsg("Got details of next up episode %s" % str(result), 2)
            xbmc.sleep(100)

            # Find the next unwatched and the newest added episodes
            if "result" in result and "episodes" in result["result"]:
                episode = self.findNextEpisode(result, currentFile, includeWatched)
                return episode

    def handle_kodi_lookup_of_current_episode(self, tvshowid):
        result = xbmc.executeJSONRPC(
            '{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, '
            '"properties": [ "title", "playcount", "season", "episode", "showtitle", "plot", '
            '"file", "rating", "resume", "tvshowid", "art", "firstaired", "runtime", "writer", '
            '"dateadded", "lastplayed" , "streamdetails"], "sort": {"method": "episode"}}, "id": 1}'
            % tvshowid)
        self.logMsg("Find current episode called", 1)
        position = 0
        for episode in result["result"]["episodes"]:
            # find position of current episode
            if self.currentepisodeid == episode["episodeid"]:
                # found a match so get out of here
                break
            position += 1

        # now return the episode
        self.logMsg("Find current episode found episode in position: " + str(position), 1)
        try:
            episode = result["result"]["episodes"][position]
        except:
            # no next episode found
            episode = None

        return episode

    def handle_emby_lookup_of_episode(self, embyid):
        self.logMsg("handle_emby_lookup_of_episode called with embyid %s " % str(embyid), 2)
        if self.emby_data:
            previousembyid = self.emby_data["current_item"]["id"]
            if str(previousembyid) == str(embyid):
                self.logMsg("handle_emby_lookup_of_episode returning data %s " % str(self.emby_data["next_item"]), 2)
                return self.emby_data["next_item"]

    def handle_emby_lookup_of_current_episode(self, embyid):
        self.logMsg("handle_emby_lookup_of_current_episode called with embyid %s " % str(embyid), 2)
        if self.emby_data:
            previousembyid = self.emby_data["current_item"]["id"]
            if str(previousembyid) == embyid:
                return self.emby_data["current_item"]

    def emby_data_received(self, data):
        self.logMsg("emby_data_received called with data %s " % str(data), 2)
        self.emby_data = data

    def transform_emby_data_to_kodi_format(self, episode):
        self.logMsg("transform_emby_data_to_kodi_format called with data %s " % str(episode), 2)
        data = {}
        data["episodeid"] = episode["id"]
        data["art"] = {}
        data["art"]["tvshow.poster"] = episode["image"]
        data["art"]["thumb"] = episode["thumb"]
        data["art"]["tvshow.fanart"] = episode["fanartimage"]
        data["plot"] = episode["overview"]
        data["showtitle"] = episode["tvshowtitle"]
        data["title"] = episode["title"]
        data["playcount"] = episode["playcount"]
        data["season"] = episode["season"]
        data["episode"] = episode["episode"]
        data["rating"] = episode["rating"]
        data["firstaired"] = episode["year"]
        self.logMsg("transform_emby_data_to_kodi_format completed with data %s " % str(data), 2)
        return data

    def handle_now_playing_result(self, result):
        if 'result' in result:
            itemtype = result["result"]["item"]["type"]
            self.playMode = utils.settings("autoPlayMode")
            self.currentepisodenumber = result["result"]["item"]["episode"]
            self.currentseasonid = result["result"]["item"]["season"]
            self.currentshowtitle = result["result"]["item"]["showtitle"].encode('utf-8')
            self.currentshowtitle = utils.unicodetoascii( self.currentshowtitle)
            self.tvshowid = result["result"]["item"]["tvshowid"]
            self.embyid = result["result"]["item"]["plotoutline"]
            self.shortplayMode = utils.settings("shortPlayMode")
            self.shortplayNotification = utils.settings("shortPlayNotification")
            self.shortplayLength = int(utils.settings("shortPlayLength")) * 60
            self.includeWatched = utils.settings("includeWatched") == "true"
            if itemtype == "episode":
                if self.embyid:
                    embyid = str(self.embyid)
                    if embyid.startswith("emby_id:"):
                        self.embyid = embyid[8:]
                        self.logMsg("EmbyID retrieved %s " % str(embyid), 2)
                        self.emby_mode = True
                        currentepisodeid = embyid
                else:
                    embyid = ""

                if not embyid:
                    # Try to get tvshowid by showtitle from kodidb if tvshowid is -1 like in strm streams which are added to kodi db
                    if int(self.tvshowid) == -1:
                        self.tvshowid = self.showtitle_to_id(title=self.currentshowtitle)
                        self.logMsg("Fetched missing tvshowid " + str( self.tvshowid), 2)

                    # Get current episodeid
                    currentepisodeid = self.get_episode_id(showid=str(self.tvshowid), showseason=self.currentseasonid, showepisode=self.currentepisodenumber)
            else:
                # wtf am i doing here error.. ####
                self.logMsg("Error: cannot determine if episode", 1)
                return False
        else:
            # wtf am i doing here error.. ####
            self.logMsg("Error: no result returned from check on now playing...exiting", 1)
            return False

        self.currentepisodeid = currentepisodeid
        if self.currenttvshowid != self.tvshowid:
            self.currenttvshowid = self.tvshowid
            self.playedinarow = 1

        return True

    def autoPlayPlayback(self):
        self.emby_mode = False
        currentFile = xbmc.Player().getPlayingFile()
        # Get the active player
        result = self.getNowPlaying()
        if not self.handle_now_playing_result(result):
            self.logMsg("Error: no result returned from check on now playing...exiting", 1)
            return

        if not self.emby_mode:
            # get the next episode from kodi
            episode = self.handle_kodi_lookup_of_episode(self.tvshowid, currentFile, self.includeWatched)
        else:
            episode = self.transform_emby_data_to_kodi_format(self.handle_emby_lookup_of_episode(self.embyid))

        if episode is None:
            # no episode get out of here
            self.logMsg("Error: no episode could be found to play next...exiting", 1)
            return
        self.logMsg("episode details %s" % str(episode), 2)
        episodeid = episode["episodeid"]
        includePlaycount = True if self.includeWatched else episode["playcount"] == 0
        if includePlaycount and self.currentepisodeid != episodeid:
            # we have a next up episode
            nextUpPage = UpNext("script-upnext-upnext.xml",
                                    self.addon_settings.getAddonInfo('path'), "default", "1080i")
            nextUpPage.setItem(episode)
            stillWatchingPage = StillWatching(
                "script-upnext-stillwatching.xml",
                self.addon_settings.getAddonInfo('path'), "default", "1080i")
            stillWatchingPage.setItem(episode)
            playedinarownumber = self.addon_settings.getSetting("playedInARow")
            playTime = xbmc.Player().getTime()
            totalTime =  xbmc.Player().getTotalTime()
            self.logMsg("played in a row settings %s" % str(playedinarownumber), 2)
            self.logMsg("played in a row %s" % str(self.playedinarow), 2)

            if int(self.playedinarow) <= int(playedinarownumber):
                self.logMsg(
                    "showing next up page as played in a row is %s" % str(self.playedinarow), 2)
                if (self.shortplayNotification == "false") and (self.shortplayLength >= totalTime) and (self.shortplayMode == "true"):
                    self.logMsg("hiding notification for short videos")
                else:
                    nextUpPage.show()
            else:
                self.logMsg(
                    "showing still watching page as played in a row %s" % str(self.playedinarow), 2)
                if (self.shortplayNotification == "false") and (self.shortplayLength >= totalTime) and (self.shortplayMode == "true"):
                    self.logMsg("hiding notification for short videos")
                else:
                    stillWatchingPage.show()

            while xbmc.Player().isPlaying() and (
                    totalTime - playTime > 1) and not nextUpPage.isCancel() and not nextUpPage.isWatchNow() and not stillWatchingPage.isStillWatching() and not stillWatchingPage.isCancel():
                xbmc.sleep(100)
                try:
                    playTime = xbmc.Player().getTime()
                    totalTime = xbmc.Player().getTotalTime()
                except:
                    pass
            if self.shortplayLength >= totalTime and self.shortplayMode == "true":
                #play short video and don't add to playcount
                self.playedinarow += 0
                self.logMsg("Continuing short video autoplay - %s")
                if nextUpPage.isWatchNow() or stillWatchingPage.isStillWatching():
                    self.playedinarow = 1
                shouldPlayDefault = not nextUpPage.isCancel()
            else:
                if int(self.playedinarow) <= int(playedinarownumber):
                    nextUpPage.close()
                    shouldPlayDefault = not nextUpPage.isCancel()
                    shouldPlayNonDefault = nextUpPage.isWatchNow()
                else:
                    stillWatchingPage.close()
                    shouldPlayDefault = stillWatchingPage.isStillWatching()
                    shouldPlayNonDefault = stillWatchingPage.isStillWatching()

                if nextUpPage.isWatchNow() or stillWatchingPage.isStillWatching():
                    self.playedinarow = 1
                else:
                    self.playedinarow += 1

            if (shouldPlayDefault and self.playMode == "0") or (shouldPlayNonDefault and self.playMode == "1"):
                self.logMsg("playing media episode id %s" % str(episodeid), 2)
                # Signal to trakt previous episode watched
                AddonSignals.sendSignal("NEXTUPWATCHEDSIGNAL", {'episodeid': self.currentepisodeid})

                # Play media
                if not self.emby_mode:
                    xbmc.executeJSONRPC(
                        '{ "jsonrpc": "2.0", "id": 0, "method": "Player.Open", '
                        '"params": { "item": {"episodeid": ' + str(episode["episodeid"]) + '} } }')
                else:
                    self.logMsg("sending id %s to embyCon to play" % str(episodeid))
                    play_info = {'item_id': str(episodeid), 'auto_resume': False, 'force_transcode': False, 'media_source_id': '', 'use_default': True}
                    AddonSignals.sendSignal("embycon_play_action", play_info, source_id="embycon")

