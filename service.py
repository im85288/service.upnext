import xbmcaddon
import xbmc
import os

cwd = xbmcaddon.Addon(id='service.upnext').getAddonInfo('path')
BASE_RESOURCE_PATH = xbmc.translatePath(os.path.join(cwd, 'resources', 'lib'))
sys.path.append(BASE_RESOURCE_PATH)

import resources.lib.utils as utils
from resources.lib.player import Player

class Service():

    def __init__(self, *args):
        self.logMsg("Starting UpNext Service", 0)
        self.logMsg("========  START %s  ========" % utils.addon_name(), 0)
        self.logMsg("KODI Version: %s" % xbmc.getInfoLabel("System.BuildVersion"), 0)
        self.logMsg("%s Version: %s" % (utils.addon_name(), utils.addon_version()), 0)

    def logMsg(self, msg, lvl=1):
        class_name = self.__class__.__name__
        utils.logMsg("%s %s" % (utils.addon_name(), class_name), str(msg), int(lvl))

    def ServiceEntryPoint(self):
        player = Player()
        monitor = xbmc.Monitor()
        last_file = None
        while not monitor.abortRequested():
            # check every 1 sec
            if monitor.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break
            if xbmc.Player().isPlaying():
                try:
                    play_time = xbmc.Player().getTime()
                    total_time = xbmc.Player().getTotalTime()
                    current_file = xbmc.Player().getPlayingFile()
                    playlist_size = xbmc.PlayList(xbmc.PLAYLIST_VIDEO).size()
                    notification_time = utils.settings("autoPlaySeasonTime")
                    up_next_disabled = utils.settings("disableNextUp") == "true"
                    enable_playlist = utils.settings("enablePlaylist") == "true"
                    if self.shouldShowUpNext(enable_playlist, playlist_size, up_next_disabled):
                        if (total_time - play_time <= int(notification_time) and (
                                        last_file is None or last_file != current_file)) and total_time != 0:
                            last_file = current_file
                            self.logMsg("Calling autoplayback totaltime - playtime is %s" % (total_time - play_time), 2)
                            player.autoPlayPlayback()
                            self.logMsg("Netflix style autoplay succeeded.", 2)

                except Exception as e:
                    self.logMsg("Exception in Playback Monitor Service: %s" % e)

        self.logMsg("======== STOP %s ========" % utils.addon_name(), 0)

    def shouldShowUpNext(self, enable_playlist, playlist_size, up_next_disabled):
        return utils.window("PseudoTVRunning") != "True" and not up_next_disabled and (
                    enable_playlist == playlist_size == 0 or enable_playlist)


# start the service
Service().ServiceEntryPoint()
