# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import getCondVisibility, Player, Monitor
from api import Api
from playitem import PlayItem
from state import State
from utils import log as ulog


class UpNextPlayer(Player):
    """Service class for playback monitoring"""

    def __init__(self):
        self.api = Api()
        self.state = State()
        self.play_item = PlayItem()
        Player.__init__(self)

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def set_last_file(self, filename):
        self.state.last_file = filename
        self.state.playing_next = False

    def get_last_file(self):
        return self.state.last_file

    def is_disabled(self):
        return self.state.disabled

    def is_tracking(self):
        return self.state.track

    def set_tracking(self, track=True):
        msg = 'Up Next tracking: {0}'
        msg = msg.format('Enabled' if track else 'Disabled')
        self.log(msg, 2)
        self.state.track = track

    def reset_queue(self):
        if self.state.queued:
            self.state.queued = self.api.reset_queue()

    def get_popup_time(self):
        return self.state.popup_time

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
                self.log('Up Next tracking failed: starting state reset', 2)
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

        is_playlist_item = self.api.get_playlist_position()
        has_addon_data = bool(data)
        is_episode = getCondVisibility('videoplayer.content(episodes)')

        # Exit if Up Next playlist handling has not been enabled
        if is_playlist_item and not self.state.enable_playlist:
            self.log('Up Next tracking failed: playlist handling disabled', 2)
            return

        # Use new addon data if provided
        if data:
            self.api.addon_data_received(data, encoding)
        # Ensure that old addon data is not used. Note this may cause played in
        # a row count to reset incorrectly if playlist of mixed non-addon and
        # addon content is used
        else:
            self.api.reset_addon_data()
            has_addon_data = False

        # Start tracking if Up Next can handle the currently playing file
        if is_playlist_item or has_addon_data or is_episode:
            self.set_tracking()
            self.reset_queue()

            # Get details of currently playing file to save playcount
            if has_addon_data:
                self.play_item.handle_addon_now_playing()
            else:
                self.play_item.handle_library_now_playing()

            # Store popup time and check if cue point was provided
            popup_time, cue = self.api.calc_popup_time(total_time)
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
        self.reset_queue()
        self.api.reset_addon_data()
        self.state = State()  # Reset state

    def onPlayBackEnded(self):  # pylint: disable=invalid-name
        """Will be called when Kodi has ended playing a file"""
        self.reset_queue()
        self.set_tracking(False)
        # Event can occur before or after the next file has started playing
        # Only reset state if Up Next has not requested the next file to play
        if not self.state.playing_next:
            self.api.reset_addon_data()
            self.state = State()  # Reset state

    def onPlayBackError(self):  # pylint: disable=invalid-name
        """Will be called when when playback stops due to an error"""
        self.reset_queue()
        self.api.reset_addon_data()
        self.state = State()  # Reset state
