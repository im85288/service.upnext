# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import constants
import demo
import player
import state
import statichelper
import tracker
import utils


PLAYER_MONITOR_EVENTS = {
    'Player.OnPause': True,
    'Player.OnResume': True,
    'Player.OnSpeedChanged': True,
    # Use OnAVChange if available. It is also fired when OnSeek fires, so only
    # handle one event, not both
    'Player.OnAVChange': True,
    'Player.OnSeek': not utils.supports_python_api(18),
    'stop': 'Player.OnStop',
    # Use OnAVStart if available as OnPlay can fire too early for UpNext
    'start': (
        'Player.OnAVStart' if utils.supports_python_api(18)
        else 'Player.OnPlay'
    )
}


class UpNextMonitor(xbmc.Monitor):
    """Monitor service for Kodi"""

    def __init__(self):
        self.player = player.UpNextPlayer()
        self.state = state.UpNextState()
        self.tracker = tracker.UpNextTracker(
            player=self.player,
            state=self.state
        )

        xbmc.Monitor.__init__(self)
        self.log('Init')

    @classmethod
    def log(cls, msg, level=utils.LOGINFO):
        utils.log(msg, name=cls.__name__, level=level)

    def check_video(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        self.log('Starting video check')
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
            self.log('Skip video check: nothing playing', utils.LOGWARNING)
            return
        self.log('Playing: {0} - {1}'.format(media_type, playing_file))

        # Exit if starting counter has been reset or new start detected or
        # starting state has been reset by playback error/end/stop
        if not self.state.starting or start_num != self.state.starting:
            self.log('Skip video check: playing item not fully loaded')
            return
        self.state.starting = 0
        self.state.playing = 1

        if utils.get_property('PseudoTVRunning') == 'True':
            self.log('Skip video check: PsuedoTV detected')
            return

        if self.player.isExternalPlayer():
            self.log('Skip video check: external player detected')
            return

        # Exit if UpNext playlist handling has not been enabled
        playlist_position = api.get_playlist_position()
        if playlist_position and not self.state.enable_playlist:
            self.log('Skip video check: playlist handling not enabled')
            return

        # Use new addon data if provided or erase old addon data.
        # Note this may cause played in a row count to reset incorrectly if
        # playlist of mixed non-addon and addon content is used
        self.state.set_addon_data(data, encoding)
        addon_type = self.state.get_addon_type()

        # Start tracking if UpNext can handle the currently playing video
        # Process now playing video to get episode details and save playcount
        now_playing_item = self.state.process_now_playing(
            playlist_position, addon_type, media_type
        )
        if now_playing_item:
            self.state.set_tracking(playing_file)
            self.state.reset_queue()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(total_time)
            self.state.set_detect_time()

            # Handle demo mode functionality and notification
            demo.handle_demo_mode(self.state, self.player, now_playing_item)
            # Start tracking playback in order to launch popup at required time
            self.tracker.start()
            return

        self.log('Skip video check: UpNext unable to handle playing item')
        if self.state.is_tracking():
            self.state.reset()

    def run(self):
        # Re-trigger player play/start event if addon started mid playback
        if self.state.start_trigger and self.player.isPlaying():
            self.onNotification('UpNext', PLAYER_MONITOR_EVENTS['start'])

        # Wait indefinitely until addon is terminated
        self.waitForAbort()

        # Cleanup when abort requested
        self.tracker.stop(terminate=True)
        del self.tracker
        self.tracker = None
        self.log('Cleanup tracker')
        del self.state
        self.state = None
        self.log('Cleanup state')
        del self.player
        self.player = None
        self.log('Cleanup player')

    def onNotification(self, sender, method, data=None):  # pylint: disable=invalid-name
        """Handler for Kodi events and data transfer from addons"""

        if self.state.is_disabled():
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data) if data else ''
        self.log(' - '.join([sender, method, data]), utils.LOGDEBUG)

        # Start/Play event
        if method == PLAYER_MONITOR_EVENTS['start']:
            # Update player state and remove remnants from previous operations
            self.player.state.set('time', force=False)
            self.tracker.stop()

            # Update playcount and reset resume point of previous file
            if self.state.playing_next and self.state.mark_watched:
                api.handle_just_watched(
                    episodeid=self.state.episodeid,
                    playcount=self.state.playcount,
                    reset_playcount=(
                        self.state.mark_watched == constants.SETTING_FORCED_OFF
                    ),
                    reset_resume=True
                )
            self.state.playing_next = False

            # Check whether UpNext can start tracking
            self.check_video()

        # Stop event
        elif method == PLAYER_MONITOR_EVENTS['stop']:
            # Remove remnants from previous operations
            self.tracker.stop()

            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            # Reset state if UpNext has not requested the next file to play
            if not self.state.playing_next:
                self.state.reset()

        # All other events to be processed
        elif PLAYER_MONITOR_EVENTS.get(method):
            # Restart tracking if previously tracking
            self.tracker.start()

        # Data transfer from addons
        elif method.endswith('upnext_data'):
            decoded_data, encoding = utils.decode_json(data)
            sender = sender.replace('.SIGNAL', '')
            if not decoded_data or not isinstance(decoded_data, dict):
                self.log('Error: {0} addon, sent {1} as {2}'.format(
                    sender, decoded_data, data
                ), utils.LOGWARNING)
                return
            decoded_data.update(id='{0}_play_action'.format(sender))

            # Initial processing of data to start tracking
            self.check_video(decoded_data, encoding)

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        # Restart tracking if previously tracking
        self.tracker.start()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', utils.LOGDEBUG)
        self.state.update_settings()

        # Shutdown tracking loop if disabled
        if self.state.is_disabled():
            self.log('UpNext disabled', utils.LOGWARNING)
            self.tracker.stop(terminate=True)
        else:
            self.log('UpNext enabled')
