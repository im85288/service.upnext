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
from settings import SETTINGS
import state
import statichelper
import utils


class UpNextMonitor(xbmc.Monitor, object):  # pylint: disable=useless-object-inheritance
    """Monitor service for Kodi"""

    __slots__ = (
        '_monitoring',
        '_queue_length',
        '_started',
        'detector',
        'player',
        'popuphandler',
        'state',
    )

    def __init__(self):
        if SETTINGS.disabled:
            return

        self.log('Init')

        self._monitoring = False
        self._queue_length = 0
        self._started = False

        self.detector = None
        self.player = None
        self.popuphandler = None
        self.state = None

        xbmc.Monitor.__init__(self)

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

        if utils.get_property('PseudoTVRunning') == 'True':
            self.log('Skip video check: PsuedoTV detected')
            return

        if self.player.isExternalPlayer():
            self.log('Skip video check: external player detected')
            return

        # Exit if UpNext playlist handling has not been enabled
        playlist_position = api.get_playlist_position()
        if playlist_position and not SETTINGS.enable_playlist:
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
        # Only process this event if it is the last in the queue
        if self._queue_length != 1:
            return

        # Restart tracking if previously enabled
        self._start_tracking()

    def _event_handler_player_start(self, **_kwargs):
        # Clear queue to stop processing additional queued events
        self._queue_length = 0

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
        if self.state.playing_next and SETTINGS.mark_watched:
            api.handle_just_watched(
                episodeid=self.state.get_episodeid(),
                playcount=self.state.get_playcount(),
                reset_playcount=(
                    SETTINGS.mark_watched == constants.SETTING_OFF
                ),
                reset_resume=True
            )
        self.state.playing_next = False

        # Check whether UpNext can start tracking
        self._check_video()

    def _event_handler_player_stop(self, **_kwargs):
        # Only process this event if it is the last in the queue
        if self._queue_length != 1:
            return

        # Remove remnants from previous operations
        self._stop_detector()
        self._stop_popuphandler()

        self.state.reset_queue()
        # OnStop can occur before/after the next video has started playing
        # Full reset of state if UpNext has not requested the next file to play
        if not self.state.playing_next and not self.state.starting:
            self.state.reset()
        # Otherwise just ensure details of current/next item to play are reset
        else:
            self.state.reset_item()

    def _event_handler_upnext_signal(self, **kwargs):
        # Clear queue to stop processing additional queued events
        self._queue_length = 0

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
        # And check whether popup/playback was cancelled/stopped by the user
        playback_cancelled = (
            has_next_item
            and self.state.keep_playing
            and not self.state.playing_next
        )

        if not isinstance(self.detector, detector.UpNextDetector):
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

    def _start_tracking(self, called=[False]):  # pylint: disable=dangerous-default-value
        # Exit if tracking disabled
        if not self.state.is_tracking() or called[0]:
            return
        called[0] = True

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
            called[0] = False
            return

        # Stop tracking if new stream started
        if self.state.get_tracked_file() != playback['file']:
            self.log('Error: unknown file playing', utils.LOGWARNING)
            self.state.set_tracking(False)
            called[0] = False
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

        called[0] = False

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

    def start(self, **kwargs):
        if SETTINGS.disabled:
            return

        self.log('UpNext starting', utils.LOGINFO)

        self.state = kwargs.get('state') or state.UpNextState()
        self.player = kwargs.get('player') or player.UpNextPlayer()

        self._started = True

        # Re-trigger player play/start event if addon started mid playback
        if SETTINGS.start_trigger and self.player.isPlaying():
            # This is a fake event, use Other.OnAVStart
            utils.event('OnAVStart')

        if not self._monitoring:
            self._monitoring = True

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

        self._started = False

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

        if SETTINGS.disabled:
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data) if data else ''
        self.log(' - '.join([sender, method, data]))

        handler = UpNextMonitor.EVENTS_MAP.get(method)
        if not handler:
            return

        # Player events can fire in quick succession, queue them up rather than
        # trying to handle all of them
        self._queue_length += 1
        self.waitForAbort(1)

        # Call event handler and reduce queue length
        handler(self, sender=sender, data=data)
        if self._queue_length:
            self._queue_length -= 1

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        if SETTINGS.disabled:
            return

        self._start_tracking()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        SETTINGS.update()
        if SETTINGS.disabled and self._started:
            self.log('UpNext disabled', utils.LOGINFO)
            self.stop()
        elif not SETTINGS.disabled and not self._started:
            self.log('UpNext enabled', utils.LOGINFO)
            self.start()
