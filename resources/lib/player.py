# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import getCondVisibility, Monitor, Player
from api import get_playlist_position, get_popup_time
from state import State
from utils import log as ulog


class PlayerMonitor(Player):
    """Service class for playback monitoring"""

    def __init__(self, state):
        self.state = state
        Player.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def isPlaying(self, *args, **kwargs):  # pylint: disable=invalid-name
        return getattr(Player, 'isPlaying')(self, *args, **kwargs)

    def getTotalTime(self, *args, **kwargs):  # pylint: disable=invalid-name
        return getattr(Player, 'getTotalTime')(self, *args, **kwargs)

    def getPlayingFile(self, *args, **kwargs):  # pylint: disable=invalid-name
        return getattr(Player, 'getPlayingFile')(self, *args, **kwargs)

    def stop(self, *args, **kwargs):
        return getattr(Player, 'stop')(self, *args, **kwargs)

    def isExternalPlayer(self, *args, **kwargs):  # pylint: disable=invalid-name
        return getattr(Player, 'isExternalPlayer')(self, *args, **kwargs)

    def getTime(self, *args, **kwargs):  # pylint: disable=invalid-name
        return getattr(Player, 'getTime')(self, *args, **kwargs)

    def playnext(self, *args, **kwargs):
        return getattr(Player, 'playnext')(self, *args, **kwargs)

    def track_playback(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        # Increment starting counter
        self.state.starting += 1
        start_num = self.state.starting

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        monitor = Monitor()
        wait_limit = 5 * start_num
        wait_count = 0
        while not monitor.abortRequested() and wait_count < wait_limit:
            # Exit if starting state has been reset by playback error/end/stop
            if not self.state.starting:
                self.log('Tracking: failed - starting state reset', 1)
                return

            monitor.waitForAbort(1)
            wait_count += 1

        # Exit if no file playing
        total_time = self.isPlaying() and self.getTotalTime()
        if not total_time:
            return

        # Exit if starting counter has been reset or new start detected
        if start_num != self.state.starting:
            return
        self.state.starting = 0

        is_playlist_item = get_playlist_position()
        has_addon_data = bool(data)
        is_episode = getCondVisibility('videoplayer.content(episodes)')

        # Exit if Up Next playlist handling has not been enabled
        if is_playlist_item and not self.state.enable_playlist:
            self.log('Tracking: disabled - playlist handling not enabled', 2)
            return

        # Use new addon data if provided
        if data:
            self.state.set_addon_data(data, encoding)
        # Ensure that old addon data is not used. Note this may cause played in
        # a row count to reset incorrectly if playlist of mixed non-addon and
        # addon content is used
        else:
            self.state.reset_addon_data()
            has_addon_data = False

        # Start tracking if Up Next can handle the currently playing file
        if is_playlist_item or has_addon_data or is_episode:
            self.state.set_tracking(self.getPlayingFile())
            self.state.reset_queue()

            # Get details of currently playing file to save playcount
            if has_addon_data:
                self.state.handle_addon_now_playing()
            else:
                self.state.handle_library_now_playing()

            # Store popup time and check if cue point was provided
            popup_time, cue = get_popup_time(self.state.data, total_time)
            self.state.popup_time = popup_time
            self.state.popup_cue = cue

    if callable(getattr(Player, 'onAVStarted', None)):
        def onAVStarted(self):  # pylint: disable=invalid-name
            """Will be called when Kodi has a video or audiostream"""
            self.track_playback()
    else:
        def onPlayBackStarted(self):  # pylint: disable=invalid-name
            """Will be called when kodi starts playing a file"""
            self.track_playback()

    def onPlayBackPaused(self):  # pylint: disable=invalid-name
        self.state.pause = True

    def onPlayBackResumed(self):  # pylint: disable=invalid-name
        self.state.pause = False

    def onPlayBackStopped(self):  # pylint: disable=invalid-name
        """Will be called when user stops playing a file"""
        self.state.reset_queue()
        self.state.reset_addon_data()
        self.state = State(reset=True)  # Reset state

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """Will be called when Kodi has ended playing a file"""
        self.state.reset_queue()
        self.state.set_tracking(False)
        # Event can occur before or after the next file has started playing
        # Only reset state if Up Next has not requested the next file to play
        if not self.state.playing_next:
            self.state.reset_addon_data()
            self.state = State(reset=True)  # Reset state

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """Will be called when when playback stops due to an error"""
        self.state.reset_queue()
        self.state.reset_addon_data()
        self.state = State(reset=True)  # Reset state
