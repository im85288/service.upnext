# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import threading
import xbmc
import api
import playbackmanager
import player
import state
import statichelper
import utils


class UpNextMonitor(xbmc.Monitor):
    """Service and player monitor for Kodi"""

    def __init__(self):
        self.state = state.UpNextState()
        self.player = player.UpNextPlayer()
        self.playbackmanager = playbackmanager.PlaybackManager(
            player=self.player,
            state=self.state
        )
        self.running = False
        self.sigstop = False
        self.sigterm = False
        xbmc.Monitor.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def track_playback(self):
        if self.running or self.state.is_disabled():
            return
        new_tracker = threading.Thread(target=self.tracker)
        new_tracker.start()

    def tracker(self):
        self.log('Tracker started', 2)
        self.running = True

        while not self.abortRequested():
            # Exit loop if abort requested
            if self.waitForAbort(1) or self.sigterm:
                self.log('Tracker shutting down', 1)
                break

            if self.sigstop or not self.state.is_tracking():
                self.log('Tracker exiting', 2)
                break

            if bool(utils.get_property('PseudoTVRunning') == 'True'):
                self.state.set_tracking(False)
                continue

            if self.player.isExternalPlayer():
                self.log('External player used', 2)
                self.state.set_tracking(False)
                continue

            if not self.player.isPlaying():
                self.log('No file is playing', 2)
                self.state.set_tracking(False)
                continue

            last_file = self.state.get_last_file()
            tracked_file = self.state.get_tracked_file()
            current_file = self.player.getPlayingFile()
            # Already processed this playback before
            if last_file and last_file == current_file:
                self.log('Previous video is still playing', 2)
                continue

            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Error - unknown file playing', 1)
                self.state.set_tracking(False)
                continue

            # Check that video stream has actually loaded and started playing
            # TODO: This check should no longer be required. Test and remove
            total_time = self.player.getTotalTime()
            # if total_time == 0:
            #     self.log('Error - zero length file', 1)
            #     self.state.set_tracking(False)
            #     continue

            play_time = self.player.getTime()
            popup_time = self.state.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                continue

            # Stop thread to ensure second popup can't trigger after next file
            # has been requested but has not yet loaded
            self.sigstop = True

            # Store current file as last file played
            self.state.set_last_file(current_file)

            # Start Up Next to handle playback of next file
            msg = 'Popup requested - episode ({0}s runtime) ends in {1}s'
            msg = msg.format(total_time, total_time - play_time)
            self.log(msg, 2)
            self.playbackmanager.launch_up_next()

        # Clean up popup and state if thread was terminated rather than stopped
        if not self.sigstop:
            self.playbackmanager.remove_popup()
            self.state.reset()

        # Reset running state and thread signals
        self.log('Tracker stopped', 2)
        self.running = False
        self.sigstop = False
        self.sigterm = False

    def check_video(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        # Increment starting counter
        self.state.starting += 1
        start_num = self.state.starting

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        wait_limit = 5 * start_num
        wait_count = 0
        while not self.abortRequested() and wait_count < wait_limit:
            # Exit if starting state has been reset by playback error/end/stop
            if not self.state.starting:
                self.log('Error - starting state reset', 1)
                return

            self.waitForAbort(1)
            wait_count += 1

        # Exit if no file playing
        total_time = self.player.isPlaying() and self.player.getTotalTime()
        if not total_time:
            return

        # Exit if starting counter has been reset or new start detected
        if start_num != self.state.starting:
            return
        self.state.starting = 0
        self.state.ended = 0

        # Check what type of video is being played
        is_playlist_item = api.get_playlist_position()
        has_addon_data = bool(data)
        is_episode = xbmc.getCondVisibility('videoplayer.content(episodes)')

        # Exit if Up Next playlist handling has not been enabled
        if is_playlist_item and not self.state.enable_playlist:
            self.log('Playlist handling not enabled', 2)
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

        # Start tracking if Up Next can handle the currently playing video
        if is_playlist_item or has_addon_data or is_episode:
            self.state.set_tracking(self.player.getPlayingFile())
            self.state.reset_queue()

            # Get details of currently playing video to save playcount
            if has_addon_data:
                self.state.handle_addon_now_playing()
            else:
                self.state.handle_library_now_playing()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(total_time)

            # Start tracking loop to begin tracking playback
            self.track_playback()

        # Reset state if required
        elif self.state.is_tracking():
            self.state.reset()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', 2)
        self.state.update_settings()

        # Shutdown tracking loop if disabled
        if self.state.is_disabled():
            self.log('Up Next disabled', 0)
            self.sigterm = self.running

    def onScreensaverActivated(self):  # pylint: disable=invalid-name
        # Stop tracking loop if tracking was enabled e.g. when video is paused
        self.sigstop = self.state.is_tracking()

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        if self.state.is_tracking():
            self.track_playback()

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """Handler for Kodi state change and data transfer from addons"""
        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data)

        if (utils.get_kodi_version() < 18 and method == 'Player.OnPlay'
                or method == 'Player.OnAVStart'):
            # Check whether Up Next can start tracking
            self.check_video()

            # Disable any forces and remove any existing popups
            self.player.state['time']['force'] = False
            self.playbackmanager.remove_popup()

        elif method == 'Player.OnPause':
            self.sigstop = self.state.is_tracking()

            # Update paused state if not forced
            if not self.player.state['paused']['force']:
                self.player.state['paused']['value'] = True

        elif method == 'Player.OnResume':
            if self.state.is_tracking():
                self.track_playback()

            # Update paused state if not forced
            if not self.player.state['paused']['force']:
                self.player.state['paused']['value'] = False

        elif method == 'Player.OnStop':
            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            if self.state.playing_next:
                self.state.playing_next = False
            # Reset state if Up Next has not requested the next file to play
            else:
                self.state.reset()

        # Data transfer from addons
        elif method.endswith('upnext_data'):
            decoded_data, encoding = utils.decode_json(data)
            sender = sender.replace('.SIGNAL', '')
            if not isinstance(decoded_data, dict) or not decoded_data:
                msg = 'Addon data error - {0} sent {1} as {2}'
                self.log(msg.format(sender, decoded_data, data), 1)
                return
            decoded_data.update(id='%s_play_action' % sender)

            # Initial processing of data to start tracking
            self.check_video(decoded_data, encoding)
