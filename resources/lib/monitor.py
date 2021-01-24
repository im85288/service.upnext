# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import threading
import xbmc
import api
import detector
import playbackmanager
import player
import state
import statichelper
import utils


PLAYER_MONITOR_EVENTS = {
    'Player.OnPause',
    'Player.OnResume',
    'Player.OnSpeedChanged',
    # 'Player.OnSeek',
    'Player.OnAVChange'
}


class UpNextMonitor(xbmc.Monitor):
    """Service and player monitor/tracker for Kodi"""
    # Set True to enable threading.Thread method for triggering a popup
    # Will continuously poll playtime in a threading.Thread to track popup time
    # Default True
    use_thread = True
    # Set True to enable threading.Timer method for triggering a popup
    # Will schedule a threading.Timer to start tracking when popup is required
    # Overrides use_thread if set True
    # Default False
    use_timer = False
    # Set True to force a playback event on addon start. Used for testing.
    # Set False for normal addon start
    # Default False
    test_trigger = False

    def __init__(self):
        self.state = state.UpNextState()
        self.player = player.UpNextPlayer()
        self.playbackmanager = None
        self.tracker = None
        self.detector = None
        self.running = False
        self.sigstop = False
        self.sigterm = False

        xbmc.Monitor.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

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
        if self.test_trigger and self.player.isPlaying():
            if utils.supports_python_api(18):
                method = 'Player.OnAVStart'
            else:
                method = 'Player.OnPlay'
            self.onNotification('UpNext', method)

        # Wait indefinitely until addon is terminated
        self.waitForAbort()

        # Cleanup when abort requested
        if self.playbackmanager:
            self.playbackmanager.remove_popup(terminate=True)
            self.log('Cleanup popup', 2)
        if self.detector:
            self.detector.stop(terminate=True)
            del self.detector
            self.detector = None
            self.log('Cleanup detector', 2)
        self.stop_tracking(terminate=True)
        del self.tracker
        self.tracker = None
        self.log('Cleanup tracker', 2)
        del self.state
        self.state = None
        self.log('Cleanup state', 2)
        del self.player
        self.player = None
        self.log('Cleanup player', 2)
        del self.playbackmanager
        self.playbackmanager = None
        self.log('Cleanup playbackmanager', 2)

    def start_tracking(self, called=[False]):  # pylint: disable=dangerous-default-value
        # Exit if tracking disabled or start tracking previously requested
        if not self.state.is_tracking() or called[0]:
            return
        # Stop any existing tracker loop/thread/timer
        self.stop_tracking()
        called[0] = True

        # threading.Timer method not used by default. More testing required
        if self.use_timer:
            # getTime() needs some time to update correctly after seek/skip
            # Wait 1s, but this may not be enough to properly update play_time
            self.waitForAbort(1)
            with self.player as check_fail:
                play_time = self.player.getTime()
                speed = self.player.get_speed()
                check_fail = False
            # Exit if not playing, paused, or rewinding
            if check_fail or speed < 1:
                called[0] = False
                return

            # Determine play time left until popup is required
            popup_time = self.state.get_popup_time()
            detect_time = self.state.get_detect_time()

            # Convert to delay and scale to real time minus a 10s offset
            delay = (detect_time if detect_time else popup_time) - play_time
            delay = max(0, delay // speed - 10)
            msg = 'Tracker: starting at {0}s in {1}s'
            self.log(msg.format(
                detect_time if detect_time else popup_time,
                delay
            ), 2)

            # Schedule tracker to start when required
            self.tracker = threading.Timer(delay, self.track_playback)
            self.tracker.start()

        # Use while not abortRequested() loop in a separate thread to allow for
        # continued monitoring in main service thread
        elif self.use_thread:
            self.tracker = threading.Thread(target=self.track_playback)
            # Daemon threads may not work in Kodi, but enable it anyway
            self.tracker.daemon = True
            self.tracker.start()

        # Use while not abortRequested() loop in main service thread
        else:
            if self.running:
                self.sigstop = False
            else:
                self.track_playback()

        called[0] = False

    def stop_tracking(self, terminate=False):
        # Set terminate or stop signals if tracker is running
        if terminate:
            self.sigterm = self.running
            if self.playbackmanager:
                self.playbackmanager.remove_popup(terminate=True)
        else:
            self.sigstop = self.running

        # Exit if tracker thread has not been created
        if not self.tracker:
            return

        # Wait for thread to complete
        if self.running:
            self.tracker.join()
        # Or if tracker has not yet started on timer then cancel old timer
        elif self.use_timer:
            self.tracker.cancel()

        # Free resources
        del self.tracker
        self.tracker = None

    def track_playback(self):
        # Only track playback if old tracker is not running
        if self.running:
            return
        self.log('Tracker: started', 2)
        self.running = True

        # If tracker was (re)started, ensure detector is also reset
        if self.detector:
            self.detector.stop()
            self.detector.run()

        # Loop unless abort requested
        while not self.abortRequested() and not self.sigterm:
            # Exit loop if stop requested or if tracking stopped
            if self.sigstop or not self.state.is_tracking():
                self.log('Tracker: stopping', 2)
                break

            # Get video details, exit if nothing playing
            tracked_file = self.state.get_tracked_file()
            with self.player as check_fail:
                current_file = self.player.getPlayingFile()
                total_time = self.player.getTotalTime()
                play_time = self.player.getTime()
                check_fail = False
            if check_fail:
                self.log('Tracker: no file is playing', 2)
                self.state.set_tracking(False)
                continue
            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Error: unknown file playing', 1)
                self.state.set_tracking(False)
                continue

            # Detector starts before normal popup request time
            detect_time = self.state.get_detect_time()
            # Start detector if not already started
            if not self.detector and 0 < detect_time <= play_time:
                self.detector = detector.Detector(
                    player=self.player,
                    state=self.state
                )
                self.detector.run()
            # Otherwise check whether credits have been detected
            elif 0 < detect_time <= play_time and self.detector.detected():
                self.detector.stop()
                self.log('Tracker: credits detected', 2)
                self.state.set_detected_popup_time(
                    self.detector.update_timestamp(play_time)
                )

            popup_time = self.state.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                self.waitForAbort(min(1, popup_time - play_time))
                continue

            # Stop second thread and popup from being created after next file
            # has been requested but not yet loaded
            self.state.set_tracking(False)
            self.sigstop = True

            # Start UpNext to handle playback of next file
            msg = 'Tracker: popup at {0}s - file ({1}s runtime) ends in {2}s'
            msg = msg.format(popup_time, total_time, total_time - play_time)
            self.log(msg, 2)
            self.playbackmanager = playbackmanager.PlaybackManager(
                player=self.player,
                state=self.state
            )
            can_play_next = self.playbackmanager.launch_upnext()

            # Free up resources
            del self.playbackmanager
            self.playbackmanager = None

            # Stop detector and store hashes and timestamp for current video
            if self.detector:
                self.detector.store_data()
                # If credits were (in)correctly detected and popup is cancelled
                # by the user, then restart tracking loop to allow detector to
                # restart, or to launch popup at default time
                if (self.detector.credits_detected
                        and can_play_next
                        and not self.state.playing_next):
                    self.state.set_tracking(tracked_file)
                    self.sigstop = False
                    self.detector.reset()
                    self.state.set_popup_time(total_time)
                    continue
                self.detector.stop(terminate=True)
                del self.detector
                self.detector = None

            # Exit tracking loop once all processing complete
            break
        else:
            self.log('Tracker: abort', 1)

        # Reset thread signals
        self.log('Tracker: stopped', 2)
        self.running = False
        self.sigstop = False
        self.sigterm = False

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

        if self.state.detect_always and not self.detector:
            self.detector = detector.Detector(
                player=self.player,
                state=self.state
            )
            self.detector.run()

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

            # Start tracking playback in order to launch popup at required time
            self.start_tracking()
            # Handle demo mode functionality and notification
            self.handle_demo_mode()
            return

        self.log('Skip video check: UpNext unable to handle playing item', 2)
        if self.state.is_tracking():
            self.state.reset()

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', 2)
        self.state.update_settings()

        # Shutdown tracking loop if disabled
        if self.state.is_disabled():
            self.log('UpNext disabled', 0)
            if self.playbackmanager:
                self.playbackmanager.remove_popup(terminate=True)
            self.stop_tracking(terminate=True)

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        # Restart tracking if previously tracking
        self.start_tracking()

    def onNotification(self, sender, method, data=None):  # pylint: disable=invalid-name
        """Handler for Kodi events and data transfer from addons"""
        if self.state.is_disabled():
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data) if data else ''

        if (method == 'Player.OnAVStart' or not utils.supports_python_api(18)
                and method == 'Player.OnPlay'):
            # Update player state and remove remnants from previous operations
            self.player.state.set('time', force=False)
            if self.playbackmanager:
                self.playbackmanager.remove_popup()
            if self.detector:
                self.detector.stop()

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
            if self.playbackmanager:
                self.playbackmanager.remove_popup()
            if self.detector:
                self.detector.stop()
            self.stop_tracking()
            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            # Reset state if UpNext has not requested the next file to play
            if not self.state.playing_next:
                self.state.reset()

        elif method in PLAYER_MONITOR_EVENTS:
            # Restart tracking if previously tracking
            self.start_tracking()

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
