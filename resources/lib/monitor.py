# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import constants
import demo
import detector
import player
import popuphandler
import state
import statichelper
import utils


class UpNextMonitor(xbmc.Monitor):
    """Monitor service for Kodi"""

    def __init__(self, restart=False, **kwargs):
        self.log('Restart' if restart else 'Init')

        if not restart:
            self.running = False
            xbmc.Monitor.__init__(self)

        self.state = kwargs.get('state') or state.UpNextState()
        if self.state.is_disabled():
            return

        self.player = kwargs.get('player') or player.UpNextPlayer()
        self.detector = None
        self.popuphandler = None

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def _check_video(self, data=None, encoding=None):
        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        # Increment starting counter
        self.state.starting += 1
        start_num = max(1, self.state.starting)
        self.log('Starting video check attempt #{0}'.format(start_num))

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        wait_count = 5 * start_num
        while not self.abortRequested() and wait_count > 0:
            self.waitForAbort(1)
            wait_count -= 1

        # Get video details, exit if no video playing
        playback = self._get_playback_details(use_infolabel=True)
        if not playback:
            self.log('Skip video check: nothing playing', utils.LOGWARNING)
            return
        self.log('Playing: {media_type} - {file}'.format(**playback))

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
            playlist_position, addon_type, playback['media_type']
        )
        if now_playing_item:
            self.state.set_tracking(playback['file'])
            self.state.reset_queue()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(playback['duration'])

            # Handle demo mode functionality and notification
            demo.handle_demo_mode(
                monitor=self,
                player=self.player,
                state=self.state,
                now_playing_item=now_playing_item
            )

            self._start_tracking()
            return

        self.log('Skip video check: UpNext unable to handle playing item')
        if self.state.is_tracking():
            self.state.reset()

    def _event_handler_player_general(self, **_kwargs):
        # Player events can fire in quick succession, ensure only one is
        # handled at a time
        if self.state.event_queued:
            return

        # Flag that event handler has started
        self.state.event_queued = True
        self._start_tracking()

        # Reset event handler queued status
        self.state.event_queued = False

    def _event_handler_player_start(self, **_kwargs):
        # Remove remnants from previous operations
        self._stop_detector()
        self._stop_popuphandler()

        # Playback can start without triggering a stop callback on previous
        # video. Reset state if playback was not requested by UpNext
        if not self.state.playing_next and not self.state.starting:
            self.state.reset()
        # Otherwise just ensure details of current/next item to play are reset
        else:
            self.state.reset_item()
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
        self._stop_detector()
        self._stop_popuphandler()

        self.state.reset_queue()
        # OnStop can occur before/after the next video has started playing
        # Full reset of state if UpNext has not requested the next file to play
        if not self.state.playing_next:
            self.state.reset()
        # Otherwise just ensure details of current/next item to play are reset
        else:
            self.state.reset_item()

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

    def _get_playback_details(self, use_infolabel=False):
        with self.player as check_fail:
            playback = {
                'file': self.player.getPlayingFile(),
                'media_type': self.player.get_media_type(),
                'time': self.player.getTime(use_infolabel),
                'speed': self.player.get_speed(),
                'duration': self.player.getTotalTime(use_infolabel)
            }
            check_fail = False
        if check_fail:
            return None

        return playback

    def _launch_detector(self):
        playback = self._get_playback_details()
        if not playback:
            return

        # Start detector to detect end credits and trigger popup
        self.log('Detector started at {time}s of {duration}s'.format(
            **playback), utils.LOGINFO)
        if not isinstance(self.detector, detector.UpNextDetector):
            self.detector = detector.UpNextDetector(
                monitor=self,
                player=self.player,
                state=self.state
            )
        self.detector.start()

    def _launch_popup(self):
        playback = self._get_playback_details()
        if not playback:
            return

        # Stop second thread and popup from being created after next video
        # has been requested but not yet loaded
        self.state.set_tracking(False)

        # Stop detector once popup is shown
        if self.detector:
            self.detector.cancel()

        # Start popuphandler to show popup and handle playback of next video
        self.log('Popuphandler started at {time}s of {duration}s'.format(
            **playback), utils.LOGINFO)
        if not isinstance(self.popuphandler, popuphandler.UpNextPopupHandler):
            self.popuphandler = popuphandler.UpNextPopupHandler(
                monitor=self,
                player=self.player,
                state=self.state
            )
        # Check if popuphandler found a video to play next
        has_next_item = self.popuphandler.start()
        # And whether playback was cancelled by the user
        playback_cancelled = has_next_item and not self.state.playing_next

        if not self.detector:
            return

        # If credits were (in)correctly detected and popup is cancelled
        # by the user, then restart tracking loop to allow detector to
        # restart, or to launch popup at default time
        if self.detector.credits_detected() and playback_cancelled:
            # Re-start detector and reset match counts
            self.detector.reset()
            self.detector.start()
            popup_restart = True
        else:
            # Store hashes and timestamp for current video
            self.detector.store_data()
            # Stop detector and release resources
            self.detector.stop(terminate=True)
            popup_restart = False

        if popup_restart:
            self.state.set_popup_time(playback['duration'])
            self.state.set_tracking(playback['file'])
            utils.event('upnext_trigger')

    def _start_tracking(self):
        # Exit if tracking disabled
        if not self.state.is_tracking():
            return

        # Remove remnants from previous operations
        self._stop_detector()
        self._stop_popuphandler()

        # Playtime needs some time to update correctly after seek/skip
        # Try waiting 1s for update, longer delay may be required
        self.waitForAbort(1)

        # Get playback details and use VideoPlayer.Time infolabel over
        # xbmc.Player.getTime() as the infolabel appears to update quicker
        playback = self._get_playback_details(use_infolabel=True)

        # Exit if not playing, paused, or rewinding
        if not playback or playback['speed'] < 1:
            self.log('Skip tracking: nothing playing', utils.LOGINFO)
            return

        # Stop tracking if new stream started
        if self.state.get_tracked_file() != playback['file']:
            self.log('Error: unknown file playing', utils.LOGWARNING)
            self.state.set_tracking(False)
            return

        # Determine time until popup is required, scaled to real time
        popup_delay = utils.wait_time(
            end_time=self.state.get_popup_time(),
            start_time=playback['time'],
            rate=playback['speed']
        )

        # Determine time until detector is required, scaled to real time
        detector_delay = utils.wait_time(
            end_time=self.state.get_detect_time(),
            start_time=playback['time'],
            rate=playback['speed']
        )

        # Schedule detector to start when required
        if detector_delay is not None:
            self.log('Detector starting in {0}s'.format(detector_delay))
            self.detector = utils.run_threaded(
                self._launch_detector,
                delay=detector_delay
            )

        # Schedule popuphandler to start when required
        if popup_delay is not None:
            self.log('Popuphandler starting in {0}s'.format(popup_delay))
            self.popuphandler = utils.run_threaded(
                self._launch_popup,
                delay=popup_delay
            )

    def _stop_detector(self, terminate=False):
        if not self.detector:
            return
        if isinstance(self.detector, detector.UpNextDetector):
            self.detector.stop(terminate=terminate)
        else:
            self.detector.cancel()

    def _stop_popuphandler(self, terminate=False):
        if not self.popuphandler:
            return
        if isinstance(self.popuphandler, popuphandler.UpNextPopupHandler):
            self.popuphandler.stop(terminate=terminate)
        else:
            self.popuphandler.cancel()

    def start(self):
        if self.state and not self.state.is_disabled():
            self.log('UpNext starting', utils.LOGINFO)

            # Re-trigger player play/start event if addon started mid playback
            if self.state.start_trigger and self.player.isPlaying():
                # This is a fake event, use Other.OnAVStart
                utils.event('OnAVStart')

        if not self.running:
            self.running = True

            # Wait indefinitely until addon is terminated
            self.waitForAbort()
            # Cleanup when abort requested
            self.stop()

    def stop(self):
        self.log('UpNext exiting', utils.LOGINFO)

        # Free references/resources
        self._stop_detector()
        self._stop_popuphandler()
        del self.state
        self.state = None
        self.log('Cleanup state')
        del self.player
        self.player = None
        self.log('Cleanup player')

    EVENTS_MAP = {
        'Other.upnext_credits_detected': _event_handler_player_general,
        'Other.upnext_data': _event_handler_upnext_signal,
        'Other.upnext_trigger': _event_handler_player_general,
        'Other.OnAVStart': _event_handler_player_start,
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

        self._start_tracking()

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
