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
    """Service and player monitor/tracker for Kodi"""
    # Disable threading.Timer method by default
    use_timer = False

    def __init__(self):
        self.state = state.UpNextState()
        self.player = player.UpNextPlayer()
        self.playbackmanager = None
        self.tracker = None
        self.running = False
        self.sigstop = False
        self.sigterm = False

        xbmc.Monitor.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def start_tracking(self):
        if not self.state.is_tracking():
            return
        self.stop_tracking()

        # threading.Timer method not used by default. More testing required
        if UpNextMonitor.use_timer:
            if not self.player.isPlaying() or self.player.get_speed() < 1:
                return

            # Determine play time left until popup is required
            delay = self.state.get_popup_time() - self.player.getTime()
            # Scale play time to real time minus a 1s offset
            delay = max(0, int(delay / self.player.get_speed()) - 1)
            self.log('Tracker - starting in {0}s'.format(delay), 2)

            # Schedule tracker to start when required
            self.tracker = threading.Timer(delay, self.track_playback)
            self.tracker.start()

        # Use while not abortRequested() loop in a separate thread to allow for
        # continued monitoring in main thread
        else:
            # Only spawn a new tracker if old tracker is not running
            if self.running:
                return
            self.tracker = threading.Thread(target=self.track_playback)
            # Daemon threads may not work in Kodi, but enable it anyway
            self.tracker.daemon = True
            self.tracker.start()

    def stop_tracking(self, terminate=False):
        # Clean up any old popups
        if self.playbackmanager:
            self.playbackmanager.remove_popup(abort=True)

        # Set terminate or stop signals if tracker is running
        if terminate:
            self.sigterm = self.running
        else:
            self.sigstop = self.running

        # If tracker has not yet started on timer then cancel old timer
        if UpNextMonitor.use_timer and self.tracker and not self.running:
            self.tracker.cancel()
        # Wait for thread to complete
        if self.tracker and self.running:
            self.tracker.join()

        # Free resources
        del self.tracker
        self.tracker = None

    def track_playback(self):
        self.log('Tracker started', 2)
        self.running = True

        # Loop unless abort requested
        while not self.abortRequested() and not self.sigterm:
            # Exit loop if stop requested or if tracking stopped
            if self.sigstop or not self.state.is_tracking():
                self.log('Tracker exit', 2)
                break

            if not self.player.isPlaying():
                self.log('No file is playing', 2)
                self.state.set_tracking(False)
                continue

            tracked_file = self.state.get_tracked_file()
            current_file = self.player.getPlayingFile()
            # New stream started without tracking being updated
            if tracked_file and tracked_file != current_file:
                self.log('Error - unknown file playing', 1)
                self.state.set_tracking(False)
                continue

            total_time = self.player.getTotalTime()
            play_time = self.player.getTime()
            popup_time = self.state.get_popup_time()
            # Media hasn't reach popup time yet, waiting a bit longer
            if play_time < popup_time:
                self.waitForAbort(min(1, popup_time - play_time))
                continue

            # Stop second thread and popup from being created after next file
            # has been requested but not yet loaded
            self.state.set_tracking(False)
            self.sigstop = True

            # Start Up Next to handle playback of next file
            msg = 'Popup requested - episode ({0}s runtime) ends in {1}s'
            msg = msg.format(total_time, total_time - play_time)
            self.log(msg, 2)
            self.playbackmanager = playbackmanager.PlaybackManager(
                player=self.player,
                state=self.state
            )
            self.playbackmanager.launch_up_next()
            break
        else:
            self.log('Tracker abort', 1)

        # Reset thread signals
        self.log('Tracker stopped', 2)
        self.running = False
        self.sigstop = False
        self.sigterm = False

    def check_video(self, data=None, encoding=None):
        if self.state.playing_next:
            self.state.playing_next = False
            # Increase playcount and reset resume point of previous file
            # TODO: Add settings to control whether file is marked as watched
            #       and resume point is reset when next file is played
            api.handle_just_watched(
                episodeid=self.state.episodeid,
                playcount=self.state.playcount,
                reset_resume=True
            )

        # Only process one start at a time unless addon data has been received
        if self.state.starting and not data:
            return
        self.log('Starting video check', 2)
        # Increment starting counter
        self.state.starting += 1
        start_num = max(1, self.state.starting)

        # onPlayBackEnded for current file can trigger after next file starts
        # Wait additional 5s after onPlayBackEnded or last start
        wait_limit = 5 * start_num
        wait_count = 0
        while not self.abortRequested() and wait_count < wait_limit:
            # Exit if starting state has been reset by playback error/end/stop
            if not self.state.starting:
                self.log('Video check error - starting state reset', 1)
                return

            self.waitForAbort(1)
            wait_count += 1

        # Exit if no file playing
        playing_file = self.player.isPlaying() and self.player.getPlayingFile()
        total_time = self.player.getTotalTime() if playing_file else 0
        if not playing_file or not total_time:
            self.log('Video check error - nothing playing', 1)
            return
        self.log('Playing - %s' % playing_file, 2)

        # Exit if starting counter has been reset or new start detected
        if start_num != self.state.starting:
            self.log('Skip video check - stream not fully loaded', 2)
            return
        self.state.starting = 0
        self.state.playing = 1

        if utils.get_property('PseudoTVRunning') == 'True':
            self.log('Skip video check - PsuedoTV detected', 2)
            return

        if self.player.isExternalPlayer():
            self.log('Skip video check - external player detected', 2)
            return

        # Check what type of video is being played
        is_playlist_item = api.get_playlist_position()
        # Use new addon data if provided or erase old addon data.
        # Note this may cause played in a row count to reset incorrectly if
        # playlist of mixed non-addon and addon content is used
        has_addon_data = self.state.set_addon_data(data, encoding)
        is_episode = xbmc.getCondVisibility('videoplayer.content(episodes)')

        # Exit if Up Next playlist handling has not been enabled
        if is_playlist_item and not self.state.enable_playlist:
            self.log('Skip video check - playlist handling not enabled', 2)
            return

        # Start tracking if Up Next can handle the currently playing video
        if is_playlist_item or has_addon_data or is_episode:
            self.state.set_tracking(playing_file)
            self.state.reset_queue()

            # Get details of currently playing video to save playcount
            if has_addon_data:
                self.state.handle_addon_now_playing()
            else:
                self.state.handle_library_now_playing()

            # Store popup time and check if cue point was provided
            self.state.set_popup_time(total_time)

            # Start tracking playback in order to launch popup at required time
            self.start_tracking()

        # Reset state if required
        elif self.state.is_tracking():
            self.state.reset()

    # Override waitForAbort to ensure thread and popup cleanup is always done
    def waitForAbort(self, *args, **kwargs):  # pylint: disable=invalid-name
        if xbmc.Monitor.waitForAbort(self, *args, **kwargs):
            # Cleanup if abort requested
            self.stop_tracking(terminate=True)
            return True
        return False

    def onSettingsChanged(self):  # pylint: disable=invalid-name
        self.log('Settings changed', 2)
        self.state.update_settings()

        # Shutdown tracking loop if disabled
        if self.state.is_disabled():
            self.log('Up Next disabled', 0)
            self.stop_tracking(terminate=True)

    def onScreensaverActivated(self):  # pylint: disable=invalid-name
        # Stop tracking loop if tracking was enabled e.g. when video is paused
        self.stop_tracking()

    def onScreensaverDeactivated(self):  # pylint: disable=invalid-name
        # Restart tracking if previously tracking
        self.start_tracking()

    def onNotification(self, sender, method, data):  # pylint: disable=invalid-name
        """Handler for Kodi events and data transfer from addons"""

        if self.state.is_disabled():
            return

        sender = statichelper.to_unicode(sender)
        method = statichelper.to_unicode(method)
        data = statichelper.to_unicode(data)

        if (utils.get_kodi_version() < 18 and method == 'Player.OnPlay'
                or method == 'Player.OnAVStart'):
            # Update player state and remove any existing popups
            self.player.state.set('time', force=False)
            self.player.get_speed(data)
            if self.playbackmanager:
                self.playbackmanager.remove_popup()

            # Check whether Up Next can start tracking
            self.check_video()

        elif method == 'Player.OnPause':
            self.stop_tracking()
            # Update player state
            self.player.get_speed(data)

        elif method == 'Player.OnResume':
            # Update player state
            self.player.get_speed(data)
            # Restart tracking if previously tracking
            self.start_tracking()

        elif method == 'Player.OnSpeedChanged':
            # Update player state
            self.player.get_speed(data)
            # Restart tracking if previously tracking
            self.start_tracking()

        elif method == 'Player.OnStop':
            self.stop_tracking()
            self.state.reset_queue()
            # OnStop can occur before/after the next file has started playing
            # Reset state if Up Next has not requested the next file to play
            if not self.state.playing_next:
                self.state.reset()

        elif method == 'Player.OnAVChange':
            # Do not update player state as speed value is always equal to 1
            # in OnAVChange event
            # self.player.get_speed(data)
            # Restart tracking if previously tracking
            self.start_tracking()

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
