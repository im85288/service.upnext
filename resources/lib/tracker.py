# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import constants
import detector
import playbackmanager
import utils


class UpNextTracker(object):  # pylint: disable=useless-object-inheritance
    """UpNext playback tracker class"""

    __slots__ = (
        'monitor',
        'player',
        'state',
        'thread',
        'detector',
        'playbackmanager',
        'running',
        'sigstop',
        'sigterm'
    )

    def __init__(self, monitor, player, state):
        self.log('Init')

        self.monitor = monitor
        self.player = player
        self.state = state

        self.thread = None
        self.detector = None
        self.playbackmanager = None

        self.running = False
        self.sigstop = False
        self.sigterm = False

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def _detector_post_run(self, playback_cancelled):
        if not self.detector:
            tracker_restart = False
            return tracker_restart

        # If credits were (in)correctly detected and popup is cancelled
        # by the user, then restart tracking loop to allow detector to
        # restart, or to launch popup at default time
        if self.detector.credits_detected() and playback_cancelled:
            # Re-start detector and reset match counts
            self.detector.start(reset=True)
            tracker_restart = True
        else:
            # Store hashes and timestamp for current video
            self.detector.store_data()
            # Stop detector and release resources
            self.detector.stop(terminate=True)
            tracker_restart = False

        return tracker_restart

    def _get_playback_details(self, use_infolabel=False):
        with self.player as check_fail:
            playback = {
                'current_file': self.player.getPlayingFile(),
                'play_time': self.player.getTime(use_infolabel=use_infolabel),
                'speed': self.player.get_speed(),
                'total_time': self.player.getTotalTime()
            }
            check_fail = False
        if check_fail:
            return None

        if playback['speed'] < 1:
            return playback

        # Determine time until popup is required, scaled to real time
        popup_time = self.state.get_popup_time()
        playback['popup_wait_time'] = (
            (popup_time - playback['play_time']) // playback['speed']
        )

        # Determine time until detector is required, scaled to real time
        detect_time = self.state.get_detect_time()
        if detect_time and not (self.detector and self.detector.is_alive()):
            playback['detector_wait_time'] = (
                (detect_time - playback['play_time']) // playback['speed']
            )

        return playback

    def _launch_detector(self):
        if not isinstance(self.detector, detector.UpNextDetector):
            self.detector = detector.UpNextDetector(
                monitor=self.monitor,
                player=self.player,
                state=self.state
            )
        self.detector.start()

    def _launch_popup(self, playback):
        # Stop second thread and popup from being created after next video
        # has been requested but not yet loaded
        self.state.set_tracking(False)
        self.sigstop = True

        # Stop detector once popup is shown
        if self.detector:
            self.detector.stop()

        # Start playbackmanager to show popup and handle playback of next video
        self.log('Popup at {0}s of {1}s'.format(
            playback['play_time'], playback['total_time']
        ), utils.LOGINFO)
        self.playbackmanager = playbackmanager.UpNextPlaybackManager(
            monitor=self.monitor,
            player=self.player,
            state=self.state
        )
        # Check if playbackmanager found a video to play next
        has_next_item = self.playbackmanager.start()
        # And whether playback was cancelled by the user
        playback_cancelled = has_next_item and not self.state.playing_next

        # Cleanup detector data and check if tracker needs to be reset if
        # credits were incorrectly detected
        tracker_restart = self._detector_post_run(playback_cancelled)
        return tracker_restart

    def _run(self):
        # Only track playback if old tracker is not running
        if self.running:
            return
        self.log('Started')
        self.running = True

        # Get playback details
        playback = self._get_playback_details()
        # Loop until popup is due, unless abort requested
        while not (self.monitor.abortRequested() or self.sigterm):

            # Stop tracking if nothing playing
            if not playback:
                self.log('No file is playing', utils.LOGINFO)
                self.state.set_tracking(False)

            # Stop tracking if new stream started
            elif self.state.get_tracked_file() != playback['current_file']:
                self.log('Error: unknown file playing', utils.LOGWARNING)
                self.state.set_tracking(False)

            # Exit tracker if stop requested or if tracking stopped
            if self.sigstop or not self.state.is_tracking():
                self.log('Stopped')
                self.running = False
                self.sigstop = False
                self.sigterm = False
                return

            # Exit loop if popup is due
            if playback['popup_wait_time'] <= 0.1:
                break
            # Or start detector if start time is due
            if playback.get('detector_wait_time', 1) <= 0.1:
                self._launch_detector()

            # Media hasn't reach popup time yet, waiting a bit longer
            self.monitor.waitForAbort(
                max(0.1, min(1, playback['popup_wait_time']))
            )
            playback = self._get_playback_details()
        else:
            self.log('Abort', utils.LOGWARNING)
            self.running = False
            self.sigstop = False
            self.sigterm = False
            return

        # Create UpNext popup to handle display and playback of next video
        tracker_restart = self._launch_popup(playback)

        # Reset thread signals
        self.log('Stopped')
        self.running = False
        self.sigstop = False
        self.sigterm = False

        if tracker_restart:
            self.state.set_popup_time(playback['total_time'])
            self.state.set_tracking(playback['current_file'])
            self._run()

    def start(self, called=[False]):  # pylint: disable=dangerous-default-value
        # Exit if tracking disabled or start tracking previously requested
        if not self.state.is_tracking() or called[0]:
            return
        # Stop any existing tracker loop/thread/timer
        self.stop()
        called[0] = True

        # Schedule a threading.Timer to check playback details only when popup
        # is expected to be shown. Experimental mode, more testing required.
        if self.state.tracker_mode == constants.TRACKER_MODE_TIMER:
            # Playtime needs some time to update correctly after seek/skip
            # Try waiting 1s for update, longer delay may be required
            self.monitor.waitForAbort(1)

            # Get playback details and use VideoPlayer.Time infolabel over
            # xbmc.Player.getTime() as the infolabel appears to update quicker
            playback = self._get_playback_details(use_infolabel=True)

            # Exit if not playing, paused, or rewinding
            if not playback or playback['speed'] < 1:
                self.log('Skip tracker start: nothing playing', utils.LOGINFO)
                called[0] = False
                return

            # Schedule detector to start when required
            detector_delay = playback.get('detector_wait_time')
            if detector_delay is not None:
                detector_delay = max(0, detector_delay)
                self.log('Detector starting in {0}s'.format(detector_delay))
                self.detector = utils.run_after(
                    detector_delay, self._launch_detector
                )

            # Schedule tracker to start when required
            # Tracker starting delay is actual delay minus a 10s offset
            tracker_delay = max(0, playback['popup_wait_time'] - 10)
            self.log('Tracker starting in {0}s'.format(tracker_delay))
            self.thread = utils.run_after(tracker_delay, self._run)

        # Use while not abortRequested() loop in a separate threading.Thread to
        # continuously poll playback details while callbacks continue to be
        # processed in main service thread. Default mode.
        elif self.state.tracker_mode == constants.TRACKER_MODE_THREAD:
            self.thread = utils.run_threaded(self._run)

        # Use while not abortRequested() loop in main service thread. Old mode.
        else:
            if self.running:
                self.sigstop = False
            else:
                self._run()

        called[0] = False

    def stop(self, terminate=False):
        # Set terminate or stop signals if tracker is running
        if terminate:
            self.sigterm = self.running
        else:
            self.sigstop = self.running

        # If detector has been started
        if isinstance(self.detector, detector.UpNextDetector):
            # Stop detector and release resources if terminating tracker
            self.detector.stop(terminate=terminate)

        # Stop playbackmanager, force close popup and release resources if
        # terminating tracker
        if self.playbackmanager:
            self.playbackmanager.stop(terminate=terminate)

        # Exit if tracker thread has not been created
        if not self.thread:
            return

        # Wait for thread to complete
        if self.running:
            self.thread.join()
        # Or if tracker has not yet started on timer then cancel old timer
        elif self.state.tracker_mode == constants.TRACKER_MODE_TIMER:
            self.thread.cancel()
            if self.detector:
                self.detector.cancel()

        # Free references/resources
        del self.thread
        self.thread = None
        del self.playbackmanager
        self.playbackmanager = None
        if terminate:
            del self.detector
            self.detector = None
            del self.monitor
            self.monitor = None
            del self.player
            self.player = None
            del self.state
            self.state = None
