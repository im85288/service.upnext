# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import player
import state
import statichelper
import tracker
import utils


PLAYER_MONITOR_EVENTS = {
    'Player.OnPause',
    'Player.OnResume',
    'Player.OnSpeedChanged',
    # 'Player.OnSeek',
    'Player.OnAVChange'
}


class UpNextMonitor(xbmc.Monitor):
    """Monitor service for Kodi"""

    # Set True to force a playback event on addon start. Used for testing.
    # Set False for normal addon start
    # Default False
    _trigger = False

    def __init__(self):
        self.player = player.UpNextPlayer()
        self.state = state.UpNextState()
        self.tracker = tracker.UpNextTracker(
            player=self.player,
            state=self.state
        )

        xbmc.Monitor.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def check_video(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        self.log('Starting video check', 2)
        # Increment starting counter
        self.state.starting += 1
        start_num = max(1, self.state.starting)

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        wait_count = 5 * start_num
        while not self.abortRequested() and wait_count:
            self.waitForAbort(1)
            wait_count -= 1

        # Get video details, exit if no video playing
        with self.player as check_fail:
            playing_file = self.player.getPlayingFile()
            total_time = self.player.getTotalTime()
            media_type = self.player.get_media_type()
            check_fail = False
        if check_fail:
            self.log('Skip video check: nothing playing', 2)
            return
        self.log('Playing: %s - %s' % (media_type, playing_file), 2)

        # Exit if starting counter has been reset or new start detected or
        # starting state has been reset by playback error/end/stop
        if not self.state.starting or start_num != self.state.starting:
            self.log('Skip video check: playing item not fully loaded', 2)
            return
        self.state.starting = 0
        self.state.playing = 1

        if utils.get_property('PseudoTVRunning') == 'True':
            self.log('Skip video check: PsuedoTV detected', 2)
            return

        if self.player.isExternalPlayer():
            self.log('Skip video check: external player detected', 2)
            return

        # Exit if UpNext playlist handling has not been enabled
        is_playlist = api.get_playlist_position()
        if is_playlist and not self.state.enable_playlist:
            self.log('Skip video check: playlist handling not enabled', 2)
            return

        # Use new addon data if provided or erase old addon data.
        # Note this may cause played in a row count to reset incorrectly if
        # playlist of mixed non-addon and addon content is used
        self.state.set_addon_data(data, encoding)
        has_addon_data = self.state.has_addon_data()

        # Start tracking if UpNext can handle the currently playing video
        # Process now playing video to get episode details and save playcount
        if self.state.process_now_playing(
                is_playlist, has_addon_data, media_type
        ):
            self.state.set_tracking(playing_file)
            self.state.reset_queue()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(total_time)
            self.state.set_detect_time()

            # Handle demo mode functionality and notification
            self.handle_demo_mode()
            # Start tracking playback in order to launch popup at required time
            self.tracker.start()
            return

        self.log('Skip video check: UpNext unable to handle playing item', 2)
        if self.state.is_tracking():
            self.state.reset()

    def handle_demo_mode(self):
        if self.state.demo_mode:
            utils.notification('UpNext demo mode', 'Active')

        seek_time = 0
        if not self.state.demo_seek:
            return
        # Seek to popup start time
        if self.state.demo_seek == 2:
            seek_time = self.state.get_popup_time()
        # Seek to detector start time
        elif self.state.demo_seek == 3:
            seek_time = self.state.get_detect_time()

        with self.player as check_fail:
            # Seek to 15s before end of video if no other seek point set
            if not seek_time:
                total_time = self.player.getTotalTime()
                seek_time = total_time - 15
            self.player.seekTime(seek_time)
            check_fail = False
        if check_fail:
            self.log('Error: unable to seek in demo mode, nothing playing', 1)

    def run(self):
        # Re-trigger player event if addon started mid playback
        if self._trigger and self.player.isPlaying():
            if utils.supports_python_api(18):
                method = 'Player.OnAVStart'
            else:
                method = 'Player.OnPlay'
            self.onNotification('UpNext', method)

        # Wait indefinitely until addon is terminated
        self.waitForAbort()

        # Cleanup when abort requested
        self.tracker.stop(terminate=True)
        del self.tracker
        self.tracker = None
        self.log('Cleanup tracker', 2)
        del self.state
        self.state = None
        self.log('Cleanup state', 2)
        del self.player
        self.player = None
        self.log('Cleanup player', 2)

    def onNotification(self, sender, method, data=None):  # pylint: disable=invalid-name
        """Handler for Kodi events and data transfer from addons"""

        if self.state.is_disabled():
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data) if data else ''
        self.log(' - '.join([sender, method, data]), 2)

        if (method == 'Player.OnAVStart' or not utils.supports_python_api(18)
                and method == 'Player.OnPlay'):
            # Update player state and remove remnants from previous operations
            self.player.state.set('time', force=False)
            self.tracker.stop()

            # Increase playcount and reset resume point of previous file
            if self.state.playing_next:
                self.state.playing_next = False
                # TODO: Add settings to control whether file is marked as
                # watched and resume point is reset when next file is played
                api.handle_just_watched(
                    episodeid=self.state.episodeid,
                    playcount=self.state.playcount,
                    reset_resume=True
                )

            # Check whether UpNext can start tracking
            self.check_video()

        elif method == 'Player.OnStop':
            # Remove remnants from previous operations
            self.tracker.stop()

            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            # Reset state if UpNext has not requested the next file to play
            if not self.state.playing_next:
                self.state.reset()

        elif method in PLAYER_MONITOR_EVENTS:
            # Restart tracking if previously tracking
            self.tracker.start()

        # Data transfer from addons
        elif method.endswith('upnext_data'):
            decoded_data, encoding = utils.decode_json(data)
            sender = sender.replace('.SIGNAL', '')
            if not isinstance(decoded_data, dict) or not decoded_data:
                msg = 'Error: {0} addon, sent {1} as {2}'
                self.log(msg.format(sender, decoded_data, data), 1)
                return
            decoded_data.update(id='%s_play_action' % sender)

            # Initial processing of data to start tracking
            self.check_video(decoded_data, encoding)

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        # Restart tracking if previously tracking
        self.tracker.start()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', 2)
        self.state.update_settings()

        # Shutdown tracking loop if disabled
        if self.state.is_disabled():
            self.log('UpNext disabled', 0)
            self.tracker.stop(terminate=True)
