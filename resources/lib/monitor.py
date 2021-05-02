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


class UpNextMonitor(xbmc.Monitor):
    """Monitor service for Kodi"""

    def __init__(self, restart=False, **kwargs):
        self.log('Restart' if restart else 'Init')

        if not restart:
            self.running = False
            xbmc.Monitor.__init__(self)

        self.state = kwargs.get('state', state.UpNextState())
        if self.state.is_disabled():
            return

        self.player = kwargs.get('player', player.UpNextPlayer())
        self.tracker = tracker.UpNextTracker(
            monitor=self,
            player=self.player,
            state=self.state
        )

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def _check_video(self, data=None, encoding=None):
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
        addon_type = self.state.get_addon_type(playlist_position)

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

            # Handle demo mode functionality and notification
            demo.handle_demo_mode(
                monitor=self,
                player=self.player,
                state=self.state,
                now_playing_item=now_playing_item
            )
            # Start tracking playback in order to launch popup at required time
            self.tracker.start()
            return

        self.log('Skip video check: UpNext unable to handle playing item')
        if self.state.is_tracking():
            self.state.reset()

    def _event_handler_player_general(self, **_kwargs):
        # Restart tracking if previously tracking
        self.tracker.start()

    def _event_handler_player_start(self, **_kwargs):
        # Remove remnants from previous operations
        self.tracker.stop()

        # Playback can start without triggering a stop callback on previous
        # video. Reset state if playback was not requested by UpNext
        if not self.state.playing_next and not self.state.starting:
            self.state.reset()
        # Update playcount and reset resume point of previous file
        if self.state.playing_next and self.state.mark_watched:
            api.handle_just_watched(
                episodeid=self.state.get_episodeid(),
                playcount=self.state.get_playcount(),
                reset_playcount=(
                    self.state.mark_watched == constants.SETTING_FORCED_OFF
                ),
                reset_resume=True
            )
        self.state.playing_next = False

        # Check whether UpNext can start tracking
        self._check_video()

    def _event_handler_player_stop(self, **_kwargs):
        # Remove remnants from previous operations
        self.tracker.stop()

        self.state.reset_queue()
        # OnStop can occur before/after the next video has started playing
        # Reset state if UpNext has not requested the next file to play
        if not self.state.playing_next:
            self.state.reset()

    def _event_handler_upnext_signal(self, **kwargs):
        sender = kwargs.get('sender').replace('.SIGNAL', '')
        data = kwargs.get('data')

        decoded_data, encoding = utils.decode_data(data)
        if not decoded_data or not isinstance(decoded_data, dict):
            self.log('Error: {0} addon, sent {1} as {2}'.format(
                sender, decoded_data, data
            ), utils.LOGWARNING)
            return
        self.log('Data received from {0}'.format(sender), utils.LOGINFO)
        decoded_data.update(id='{0}_play_action'.format(sender))

        # Initial processing of data to start tracking
        self._check_video(decoded_data, encoding)

    def start(self):
        if self.state and not self.state.is_disabled():
            self.log('UpNext starting', utils.LOGINFO)

            # Re-trigger player play/start event if addon started mid playback
            if self.state.start_trigger and self.player.isPlaying():
                # This is a fake event, use Player.OnAVStart
                self.onNotification('UpNext', 'Player.OnAVStart')

        if not self.running:
            self.running = True

            # Wait indefinitely until addon is terminated
            self.waitForAbort()
            # Cleanup when abort requested
            self.stop()

    def stop(self):
        self.log('UpNext exiting', utils.LOGINFO)

        # Free references/resources
        if self.tracker:
            self.tracker.stop(terminate=True)
        del self.state
        self.state = None
        self.log('Cleanup state')
        del self.player
        self.player = None
        self.log('Cleanup player')
        del self.tracker
        self.tracker = None
        self.log('Cleanup tracker')

    EVENTS_MAP = {
        'Other.upnext_data': _event_handler_upnext_signal,
        'Other.upnext_trigger': _event_handler_player_general,
        'Player.OnPause': _event_handler_player_general,
        'Player.OnResume': _event_handler_player_general,
        'Player.OnSpeedChanged': _event_handler_player_general,
        # Use OnAVChange if available. It is also fired when OnSeek fires, so
        # only handle one event, not both
        'Player.OnAVChange': _event_handler_player_general,
        'Player.OnSeek': (
            _event_handler_player_general
            if not utils.supports_python_api(18)
            else None
        ),
        # Use OnAVStart if available as OnPlay can fire too early for UpNext
        'Player.OnAVStart': _event_handler_player_start,
        'Player.OnPlay': (
            _event_handler_player_start
            if not utils.supports_python_api(18)
            else None
        ),
        'Player.OnStop': _event_handler_player_stop
    }

    def onNotification(self, sender, method, data=None):  # pylint: disable=invalid-name
        """Handler for Kodi events and data transfer from addons"""

        if not self.state or self.state.is_disabled():
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data) if data else ''
        self.log(' - '.join([sender, method, data]))

        handler = UpNextMonitor.EVENTS_MAP.get(method)
        if handler:
            handler(self, sender=sender, data=data)

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        if not self.state or self.state.is_disabled():
            return

        # Restart tracking if previously tracking
        self.tracker.start()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        if self.state:
            self.state.update_settings()
            if self.state.is_disabled():
                self.log('UpNext disabled', utils.LOGINFO)
                self.stop()
        else:
            new_state = state.UpNextState()
            if not new_state.is_disabled():
                self.log('UpNext enabled', utils.LOGINFO)
                self.__init__(restart=True, state=new_state)
                self.start()
