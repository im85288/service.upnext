# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import dialog
import utils


class UpNextPlaybackManager(object):  # pylint: disable=useless-object-inheritance
    """Controller for UpNext popup and playback of next item"""

    __slots__ = ('player', 'state', 'popup', 'running', 'sigstop', 'sigterm')

    def __init__(self, player, state):
        self.player = player
        self.state = state
        self.popup = None
        self.running = False
        self.sigstop = False
        self.sigterm = False
        self.log('Init')

    @classmethod
    def log(cls, msg, level=utils.LOGINFO):
        utils.log(msg, name=cls.__name__, level=level)

    def create_popup(self, next_item, source=None):
        # Only use Still Watching? popup if played limit has been reached
        if self.state.played_limit:
            show_upnext = self.state.played_limit > self.state.played_in_a_row
        # Don't show Still Watching? popup if played limit is zero, unless
        # played in a row count has been set to zero for testing
        else:
            show_upnext = self.state.played_limit != self.state.played_in_a_row

        self.log('Auto played in a row: {0} of {1}'.format(
            self.state.played_in_a_row, self.state.played_limit
        ))

        # Filename for dialog XML
        filename = 'script-upnext{0}{1}{2}.xml'.format(
            '-upnext' if show_upnext else '-stillwatching',
            '-simple' if self.state.simple_mode else '',
            '' if self.state.skin_popup else '-original'
        )

        self.popup = dialog.UpNextPopup(
            filename,
            utils.get_addon_path(),
            'default',
            '1080i',
            item=next_item,
            shuffle=self.state.shuffle if source == 'library' else None,
            stop_button=self.state.show_stop_button
        )

        return self.get_popup_state(show_upnext=show_upnext)

    def display_popup(self, popup_state):
        # Get video details, exit if no video playing
        with self.player as check_fail:
            total_time = self.player.getTotalTime()
            play_time = self.player.getTime()
            check_fail = False
        if check_fail:
            return self.get_popup_state(popup_state, done=False)

        # If cue point was provided then UpNext will auto play after a fixed
        # delay time, rather than waiting for the end of the file
        if popup_state['play_on_cue']:
            popup_duration = self.state.auto_play_delay
            if popup_duration:
                popup_start = max(play_time, self.state.get_popup_time())
                total_time = min(popup_start + popup_duration, total_time)

        if not self.show_popup():
            return self.get_popup_state(popup_state, done=False)

        monitor = xbmc.Monitor()
        # Current file can stop, or next file can start, while update loop is
        # running. Check state and abort popup update if required
        while (not monitor.abortRequested()
               and self.player.isPlaying()
               and isinstance(self.popup, dialog.UpNextPopup)
               and not self.state.starting
               and self.state.playing
               and not self.sigstop
               and not self.sigterm):
            remaining = total_time - self.player.getTime()
            self.popup.update_progress(round(remaining))

            # Decrease wait time and increase loop speed to try and avoid
            # missing the end of video when fast forwarding
            wait_time = 0.1 / max(1, self.player.get_speed())
            remaining -= wait_time

            # If end of file or user has closed popup then exit update loop
            if (remaining <= 1
                    or self.popup.is_cancel()
                    or self.popup.is_playnow()):
                popup_done = True
                break

            monitor.waitForAbort(min(wait_time, remaining))
        else:
            popup_done = False

        # Free resources
        del monitor

        return self.get_popup_state(popup_state, done=popup_done)

    def get_popup_state(self, old_state=None, **kwargs):
        default_state = old_state if old_state else {
            'auto_play': self.state.auto_play,
            'cancel': False,
            'done': False,
            'play_now': False,
            'play_on_cue': self.state.auto_play and self.state.popup_cue,
            'show_upnext': False,
            'shuffle': False,
            'shuffle_start': False,
            'stop': False
        }

        for keyword in kwargs:
            if keyword in default_state:
                default_state[keyword] = kwargs[keyword]

        if not self.popup:
            return default_state

        with self.popup as check_fail:
            current_state = {
                'auto_play': (
                    self.state.auto_play
                    and default_state['show_upnext']
                    and not self.popup.is_cancel()
                    and not self.popup.is_playnow()
                ),
                'cancel': self.popup.is_cancel(),
                'done': default_state['done'],
                'play_now': self.popup.is_playnow(),
                'play_on_cue': (
                    self.state.auto_play
                    and default_state['show_upnext']
                    and not self.popup.is_cancel()
                    and not self.popup.is_playnow()
                    and self.state.popup_cue
                ),
                'show_upnext': default_state['show_upnext'],
                'shuffle': self.popup.is_shuffle(),
                'shuffle_start': (
                    not self.state.shuffle
                    and self.popup.is_shuffle()
                ),
                'stop': self.popup.is_stop()
            }
            check_fail = False
        if check_fail:
            return default_state
        return current_state

    def play_next_video(self, next_item, source, popup_state):
        # Primary method is to play next playlist item
        if source[-len('playlist'):] == 'playlist' or self.state.queued:
            # Can't just seek to end of file as this triggers inconsistent Kodi
            # behaviour:
            # - Will sometimes continue playing past the end of the file
            #   preventing next file from playing
            # - Will sometimes play the next file correctly then play it again
            #   resulting in loss of UpNext state
            # - Will sometimes play the next file immediately without
            #   onPlayBackStarted firing resulting in tracking not activating
            # - Will sometimes work just fine
            # Can't just wait for next file to play as VideoPlayer closes all
            # video threads when the current file finishes
            if popup_state['play_now'] or popup_state['play_on_cue']:
                api.play_playlist_item(
                    # Use previously stored next playlist position if available
                    position=next_item.get('playlist_position', 'next'),
                    resume=self.state.enable_resume
                )

        # Fallback addon playback method, used if addon provides play_info
        elif source[:len('addon')] == 'addon':
            api.play_addon_item(
                self.state.data,
                self.state.encoding,
                self.state.enable_resume
            )

        # Fallback library playback method, not normally used
        else:
            api.play_kodi_item(next_item, self.state.enable_resume)

        # Determine playback method. Used for logging purposes
        self.log('Playback requested: {0}, from {1}{2}'.format(
            popup_state, source, ' using queue' if self.state.queued else ''
        ), utils.LOGDEBUG)

    def remove_popup(self):
        if not self.popup:
            return

        with self.popup:
            self.popup.close()
            utils.clear_property('service.upnext.dialog')

        del self.popup
        self.popup = None

    def run(self, next_item, source=None):
        self.log('Started')
        self.running = True

        # Add next file to playlist if existing playlist is not being used
        if self.state.enable_queue and source[-len('playlist'):] != 'playlist':
            self.state.queued = api.queue_next_item(self.state.data, next_item)

        # Create Kodi dialog to show UpNext or Still Watching? popup
        popup_state = self.create_popup(next_item, source)
        # Display popup and update state of controls
        popup_state = self.display_popup(popup_state)
        # Close dialog once we are done with it
        self.remove_popup()

        # Update played in a row count if auto_play otherwise reset
        self.state.played_in_a_row = (
            self.state.played_in_a_row + 1 if popup_state['auto_play'] else 1
        )

        # Update shuffle state
        self.state.shuffle = popup_state['shuffle']

        # Signal to Trakt that current item has been watched
        utils.event(
            message='NEXTUPWATCHEDSIGNAL',
            data={'episodeid': self.state.get_episodeid()},
            encoding='base64'
        )

        # Popup closed prematurely
        if not popup_state['done']:
            self.log('Exiting: popup force closed')

        # Shuffle start request
        elif popup_state['shuffle_start']:
            self.log('Exiting: shuffle requested')
            popup_state['done'] = False

        elif not (popup_state['auto_play'] or popup_state['play_now']):
            self.log('Exiting: playback not selected')
            popup_state['done'] = False

        if not popup_state['done']:
            # Reset signals
            self.sigstop = False
            self.sigterm = False
            self.running = False

            play_next = False
            # Stop playing if Stop button was clicked on popup, or if Still
            # Watching? popup was shown (to prevent unwanted playback that can
            # occur if fast forwarding through popup), or if starting shuffle
            keep_playing = (
                not popup_state['stop']
                and (
                    popup_state['show_upnext']
                    or popup_state['shuffle_start']
                )
            )
            return play_next, keep_playing

        # Request playback of next file based on source and type
        self.play_next_video(next_item, source, popup_state)

        # Reset signals
        self.log('Stopped')
        self.sigstop = False
        self.sigterm = False
        self.running = False

        play_next = True
        keep_playing = True
        return play_next, keep_playing

    def show_popup(self):
        if not self.popup:
            return False

        with self.popup:
            self.popup.show()
            utils.set_property('service.upnext.dialog', 'true')
            return True

    def start(self, called=[False]):  # pylint: disable=dangerous-default-value
        # Exit if playbackmanager previously requested
        if called[0]:
            return False
        # Stop any existing playbackmanager
        self.stop()
        called[0] = True

        next_item, source = self.state.get_next()
        # No next item to play, get out of here
        if not next_item:
            self.log('Exiting: no next item to play')
            called[0] = False
            return False

        # Show popup and get new playback state
        play_next, keep_playing = self.run(next_item, source)
        self.state.playing_next = play_next

        # Dequeue and stop playback if not playing next file
        if not play_next and self.state.queued:
            self.state.queued = api.dequeue_next_item()
        if not keep_playing:
            self.log('Stopping playback')
            self.player.stop()
        # Relaunch popup if shuffle enabled to get new random episode
        elif self.state.shuffle and not play_next:
            called[0] = False
            return self.start()

        called[0] = False
        return True

    def stop(self, terminate=False):
        if terminate:
            self.sigterm = self.running
        else:
            self.sigstop = self.running

        if terminate:
            self.remove_popup()
