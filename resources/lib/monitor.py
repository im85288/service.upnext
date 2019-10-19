# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
from . import utils
from .api import Api
from .playbackmanager import PlaybackManager
from .player import Player


class Monitor(xbmc.Monitor):

    def __init__(self):
        self.player = Player()
        self.api = Api()
        self.playback_manager = PlaybackManager()
        xbmc.Monitor.__init__(self)

    def log(self, msg, lvl=1):
        class_name = self.__class__.__name__
        utils.log('[%s] %s' % (utils.ADDON_ID, class_name), msg, int(lvl))

    def run(self):

        while not self.abortRequested():
            # check every 1 sec
            if self.waitForAbort(1):
                # Abort was requested while waiting. We should exit
                break
            if self.player.is_tracking():
                try:
                    play_time = self.player.getTime()
                    total_time = self.player.getTotalTime()
                    last_file = self.player.get_last_file()
                    current_file = self.player.getPlayingFile()
                    notification_time = self.api.notification_time()
                    up_next_disabled = utils.settings("disableNextUp") == "true"
                    if utils.window("PseudoTVRunning") != "True" and not up_next_disabled:
                        if (total_time - play_time <= int(notification_time) and (
                                last_file is None or last_file != current_file)) and total_time != 0:
                            self.player.set_last_file(current_file)
                            self.log("Calling autoplayback totaltime - playtime is %s" % (total_time - play_time), 2)
                            self.playback_manager.launch_up_next()
                            self.log("Up Next style autoplay succeeded.", 2)
                            self.player.disable_tracking()

                except Exception as exc:  # pylint: disable=broad-except
                    self.log("Exception in Playback Monitor Service: %s" % repr(exc))

                    if 'not playing any media file' in str(exc):
                        self.log("No file is playing - stop up next tracking.", 2)
                        self.player.disable_tracking()

        self.log('Service stopped.', 0)

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name

        if method.split('.')[1].lower() != 'upnext_data':  # method looks like Other.upnext_data
            return

        data = utils.decode_data(data)
        data['id'] = "%s_play_action" % str(sender.replace(".SIGNAL", ""))

        self.api.addon_data_received(data)
