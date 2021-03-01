# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import xbmc
import api
import dialog
import utils


class PlaybackManager(object):  # pylint: disable=useless-object-inheritance
    """Controller for UpNext popup and playback of next episode"""

    __slots__ = ('player', 'state', 'popup', 'sigterm')

    def __init__(self, player, state):
        self.player = player
        self.state = state
        self.popup = None
        self.sigterm = False
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def launch_upnext(self):
        episode, source = self.state.get_next()

        # No episode get out of here
        if not episode:
            self.log('Exiting: no next episode', 2)
            return False

        # Show popup and get new playback state
        play_next, keep_playing = self.launch_popup(episode, source)
        self.state.playing_next = play_next

        # Dequeue and stop playback if not playing next file
        if not play_next and self.state.queued:
            self.state.queued = api.dequeue_next_item()
        if not keep_playing:
            self.log('Stopping playback', 2)
            self.player.stop()
        # Relaunch popup if shuffle enabled to get new random episode
        elif self.state.shuffle and not play_next:
            return self.launch_upnext()

        self.sigterm = False
        self.log('Exit', 2)
        return True

    def launch_popup(self, episode, source=None):
        episodeid = utils.get_int(episode, 'episodeid')

        # Checked if next episode has been watched and if it should be skipped
        if self.state.unwatched_only and self.state.playcount:
            self.log('Exit launch_popup early: video already watched', 2)
            play_next = False
            keep_playing = True
            return play_next, keep_playing

        # Add next file to playlist if existing playlist is not being used
        if source != 'playlist':
            self.state.queued = api.queue_next_item(self.state.data, episode)

        # Only use Still Watching? popup if played limit has been reached
        if self.state.played_limit:
            show_upnext = self.state.played_limit > self.state.played_in_a_row
        # Don't show Still Watching? popup if played limit is zero, unless
        # played in a row count has been set to zero for testing
        else:
            show_upnext = self.state.played_limit != self.state.played_in_a_row
        # Allow auto play if enabled in settings and showing UpNext popup
        auto_play = self.state.auto_play and show_upnext

        self.log('Played in a row setting: %s' % self.state.played_limit, 2)
        self.log('Played in a row: %s' % self.state.played_in_a_row, 2)

        # Filename for dialog XML
        filename = 'script-upnext{0}{1}{2}.xml'.format(
            '-upnext' if show_upnext else '-stillwatching',
            '-simple' if self.state.simple_mode else '',
            '' if utils.get_setting_bool('enablePopupSkin') else '-original'
        )
        # Create Kodi dialog to show UpNext or Still Watching? popup
        self.popup = dialog.UpNextPopup(
            filename,
            utils.addon_path(),
            'default',
            '1080i',
            item=episode,
            shuffle=self.state.shuffle if source == 'library' else None
        )

        # Show popup and check that it has not been terminated early
        abort_popup = not self.show_popup_and_wait(auto_play)

        if abort_popup:
            self.log('Exit launch_popup early: tracked video not playing', 2)
            play_next = False
            # Stop if Still Watching? popup was shown to prevent unwanted
            # playback that can occur if fast forwarding through popup
            keep_playing = show_upnext
            self.remove_popup()
            return play_next, keep_playing

        # Update new playback state details
        shuffle_start = not self.state.shuffle and self.popup.is_shuffle()
        self.state.shuffle = self.popup.is_shuffle()
        auto_play = auto_play and not self.popup.is_cancel()
        play_now = self.popup.is_playnow()

        # Update played in a row count
        self.state.played_in_a_row = (
            self.state.played_in_a_row + 1
            if auto_play else 1
        )

        if shuffle_start:
            self.log('Exit launch_popup early: shuffle requested', 2)
            play_next = False
            keep_playing = True
            self.remove_popup()
            return play_next, keep_playing

        if not auto_play and not play_now:
            self.log('Exit launch_popup early: playback not selected', 2)
            play_next = False
            # Keep playing if NAV_BACK or Cancel button was clicked on popup
            # Stop playing if Stop button was clicked on popup
            keep_playing = self.popup.is_cancel() and not self.popup.is_stop()
            self.remove_popup()
            return play_next, keep_playing

        # Close dialog once we are done with it
        self.remove_popup()

        # Request playback of next file based on source and type
        has_addon_data = self.state.has_addon_data()
        # Primary method is to play next playlist item
        if source == 'playlist' or self.state.queued:
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
            if play_now or (auto_play and self.state.popup_cue):
                # xbmc.Player().playnext() does not allow for control of resume
                # PlayMedia builtin can't target now playing playlist
                # PlayMedia('',[playoffset=xx],[resume],[noresume])
                # JSON Player.Open is too slow (further testing required)
                api.play_playlist_item(
                    position='next',
                    resume=self.state.enable_resume
                )
                # Stick to playnext() for now, without possibility for resuming
                # self.player.playnext()

        # Fallback addon playback method, used if addon provides play_info
        elif has_addon_data:
            api.play_addon_item(self.state.data, self.state.encoding)

        # Fallback library playback method, not normally used
        else:
            api.play_kodi_item(episode, self.state.enable_resume)

        # Signal to trakt previous episode watched
        utils.event(
            message='NEXTUPWATCHEDSIGNAL',
            data={'episodeid': self.state.episodeid},
            encoding='base64'
        )

        # Determine playback method. Used for logging purposes
        msg = 'Playback requested: using{0}{1}{2} method'
        msg = msg.format(
            ' play_now' if play_now else
            ' auto_play_on_cue' if (auto_play and self.state.popup_cue) else
            ' auto_play',
            ' play_url' if (has_addon_data == 2) else
            ' play_info' if (has_addon_data == 3) else
            ' missing_addon_data' if (has_addon_data == 1) else
            ' library' if (isinstance(episodeid, int) and episodeid != -1) else
            ' file',
            ' playlist' if source == 'playlist' else
            ' queue' if self.state.queued else
            ' direct'
        )
        self.log(msg, 2)

        play_next = True
        keep_playing = True
        return play_next, keep_playing

    def show_popup_and_wait(self, auto_play):
        # Get video details, exit if no video playing
        with self.player as check_fail:
            total_time = self.player.getTotalTime()
            play_time = self.player.getTime()
            check_fail = False
        if check_fail:
            popup_done = False
            return popup_done

        # If cue point was provided then UpNext will auto play after a fixed
        # delay time, rather than waiting for the end of the file
        if auto_play and self.state.popup_cue:
            popup_duration = self.state.auto_play_delay
            if popup_duration:
                popup_start = max(play_time, self.state.get_popup_time())
                total_time = min(popup_start + popup_duration, total_time)

        if not self.show_popup():
            popup_done = False
            return popup_done

        monitor = xbmc.Monitor()
        # Current file can stop, or next file can start, while update loop is
        # running. Check state and abort popup update if required
        while (not monitor.abortRequested()
               and self.player.isPlaying()
               and isinstance(self.popup, dialog.UpNextPopup)
               and not self.state.starting
               and self.state.playing
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

        return popup_done

    def show_popup(self):
        if not self.popup:
            return False

        with self.popup:
            self.popup.show()
            utils.set_property('service.upnext.dialog', 'true')
            return True

    def remove_popup(self, terminate=False):
        if not self.popup:
            return

        if terminate or self.sigterm:
            self.sigterm = True
            return

        with self.popup:
            self.popup.close()
            utils.clear_property('service.upnext.dialog')
