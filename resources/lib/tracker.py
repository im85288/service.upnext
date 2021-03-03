# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import threading
import xbmc
import detector
import playbackmanager
import utils


class UpNextTracker(object):  # pylint: disable=useless-object-inheritance
    """UpNext playback tracker class"""

    # Set True to enable threading.Thread method for triggering a popup
    # Will continuously poll playtime in a threading.Thread to track popup time
    # Default True
    _use_thread = True
    # Set True to enable threading.Timer method for triggering a popup
    # Will schedule a threading.Timer to start tracking when popup is required
    # Overrides _use_thread if set True
    # Default False
    _use_timer = False

    def __init__(self, player, state):
        self.player = player
        self.state = state

        self.tracker = None
        self.detector = None
        self.playbackmanager = None

        self.running = False
        self.sigstop = False
        self.sigterm = False

        self.log('Init')

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def run(self):
        # Only track playback if old tracker is not running
        if self.running:
            return
        self.log('Tracker: started')
        self.running = True

        # If tracker was (re)started, ensure detector is also restarted
        if self.detector and not self.detector.detected():
            self.detector.start(restart=True)

        # Loop unless abort requested
        monitor = xbmc.Monitor()
        while not monitor.abortRequested() and not self.sigterm:
            # Exit loop if stop requested or if tracking stopped
            if self.sigstop or not self.state.is_tracking():
                self.log('Tracker: stopping')
                break

            # Get video details, exit if nothing playing
            tracked_file = self.state.get_tracked_file()
            with self.player as check_fail:
                current_file = self.player.getPlayingFile()
                total_time = self.player.getTotalTime()
                play_time = self.player.getTime()
                check_fail = False
            if check_fail:
                self.log('Tracker: no file is playing')
                self.state.set_tracking(False)
                continue
            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Error: unknown file playing', 4)
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
                self.detector.start()
            # Otherwise check whether credits have been detected
            elif 0 < detect_time <= play_time and self.detector.detected():
                self.detector.stop()
                self.log('Tracker: credits detected')
                self.state.set_detected_popup_time(
                    self.detector.update_timestamp(play_time)
                )

            popup_time = self.state.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                monitor.waitForAbort(min(1, popup_time - play_time))
                continue

            # Stop second thread and popup from being created after next file
            # has been requested but not yet loaded
            self.state.set_tracking(False)
            self.sigstop = True

            # Start UpNext to handle playback of next file
            self.log('Tracker: popup at {0}s of {1}s'.format(
                popup_time, total_time
            ))
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
                # If credits were (in)correctly detected and popup is cancelled
                # by the user, then restart tracking loop to allow detector to
                # restart, or to launch popup at default time
                if (self.detector.credits_detected
                        and can_play_next
                        and not self.state.playing_next):
                    self.state.set_tracking(tracked_file)
                    self.sigstop = False
                    self.detector.start(resume=True)
                    self.state.set_popup_time(total_time)
                    continue
                self.detector.store_data()
                self.detector.stop(terminate=True)
                del self.detector
                self.detector = None

            # Exit tracking loop once all processing is complete
            break
        else:
            self.log('Tracker: abort', 4)

        # Free resources
        del monitor

        # Reset thread signals
        self.log('Tracker: stopped')
        self.running = False
        self.sigstop = False
        self.sigterm = False

    def start(self, called=[False]):  # pylint: disable=dangerous-default-value
        # Exit if tracking disabled or start tracking previously requested
        if not self.state.is_tracking() or called[0]:
            return
        # Stop any existing tracker loop/thread/timer
        self.stop()
        called[0] = True

        # threading.Timer method not used by default. More testing required
        if self._use_timer:
            # Playtime needs some time to update correctly after seek/skip
            # Try waiting 1s for update, longer delay may be required
            xbmc.Monitor().waitForAbort(1)
            with self.player as check_fail:
                # Use VideoPlayer.Time infolabel over xbmc.Player.getTime(), as
                # the infolabel appears to update quicker
                play_time = self.player.getTime(use_infolabel=True)
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
            self.log('Tracker: starting at {0}s in {1}s'.format(
                detect_time if detect_time else popup_time, delay
            ))

            # Schedule tracker to start when required
            self.tracker = threading.Timer(delay, self.run)
            self.tracker.start()

        # Use while not abortRequested() loop in a separate thread to allow for
        # continued monitoring in main service thread
        elif self._use_thread:
            self.tracker = threading.Thread(target=self.run)
            # Daemon threads may not work in Kodi, but enable it anyway
            self.tracker.daemon = True
            self.tracker.start()

        # Use while not abortRequested() loop in main service thread
        else:
            if self.running:
                self.sigstop = False
            else:
                self.run()

        called[0] = False

    def stop(self, terminate=False):
        # Set terminate or stop signals if tracker is running
        if terminate:
            self.sigterm = self.running
            if self.detector:
                self.detector.stop(terminate=True)
            if self.playbackmanager:
                self.playbackmanager.remove_popup(terminate=True)
        else:
            self.sigstop = self.running
            if self.detector:
                self.detector.stop(reset=True)
            if self.playbackmanager:
                self.playbackmanager.remove_popup()

        # Exit if tracker thread has not been created
        if not self.tracker:
            return

        # Wait for thread to complete
        if self.running:
            self.tracker.join()
        # Or if tracker has not yet started on timer then cancel old timer
        elif self._use_timer:
            self.tracker.cancel()

        # Free resources
        del self.tracker
        self.tracker = None
        del self.detector
        self.detector = None
        del self.playbackmanager
        self.playbackmanager = None
