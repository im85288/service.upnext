# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import Monitor
from api import Api
from player import UpNextPlayer
from playitem import PlayItem
from state import State
from dialog import StillWatching, UpNext
from utils import (addon_path, clear_property, event, get_setting_bool,
                   get_setting_int, get_int, log as ulog, set_property)


class PlaybackManager:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.play_item = PlayItem()
        self.state = State()
        self.player = UpNextPlayer()

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def launch_up_next(self):
        episode, playlist_item = self.play_item.get_next()

        # Shouldn't get here if playlist setting is disabled, but just in case
        if playlist_item and not get_setting_bool('enablePlaylist'):
            self.log('Playlist integration disabled', 2)

        # No episode get out of here
        elif not episode:
            self.log('Error: no episode to play next...exiting', 1)

        else:
            self.log('Episode details: %s' % episode, 2)
            self.state.playing_next = self.launch_popup(episode, playlist_item)
            # Dequeue and stop playback if not playing next file
            if not self.state.playing_next:
                self.log('Stopping playback', 2)
                if self.state.queued:
                    self.state.queued = self.api.dequeue_next_item()
                self.player.stop()

    def launch_popup(self, episode, playlist_item):
        episodeid = get_int(episode, 'episodeid')
        watched = not self.state.include_watched and episode.get('playcount', 0)
        if (episodeid != -1 and self.state.episodeid == episodeid or
                watched):
            self.log('Exit launch_popup early: already watched file', 2)
            return False

        # Add next file to playlist if existing playlist is not being used
        if not playlist_item:
            self.state.queued = self.api.queue_next_item(episode)

        played_in_a_row_number = get_setting_int('playedInARow')
        show_next_up = self.state.played_in_a_row < played_in_a_row_number

        self.log('Played in a row setting: %s' % played_in_a_row_number, 2)
        self.log('Played in a row: {0}, showing {1} page'.format(
            self.state.played_in_a_row,
            'next up' if show_next_up else 'still watching'), 2)

        filename = 'script-upnext{0}{1}.xml'.format(
            '-upnext' if show_next_up else '-stillwatching',
            '-simple' if get_setting_int('simpleMode') == 0 else '')
        if show_next_up:
            dialog = UpNext(filename, addon_path(), 'default', '1080i')
        else:
            dialog = StillWatching(filename, addon_path(), 'default', '1080i')
        dialog.set_item(episode)

        abort_popup = not self.show_popup_and_wait(dialog)
        dialog.close()
        clear_property('service.upnext.dialog')

        if abort_popup:
            self.log('Exit launch_popup early: current file not playing', 2)
            return False

        auto_play, play_now = self.extract_play_info(dialog)
        if not auto_play and not play_now:
            self.log('Exit launch_popup early: no playback option selected', 2)
            return False

        if playlist_item or self.state.queued:
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
            if play_now:
                self.player.playnext()

        elif self.api.has_addon_data():
            # Play add-on media
            self.api.play_addon_item()

        else:
            # Play local media
            self.api.play_kodi_item(episode)

        # Signal to trakt previous episode watched
        event(message='NEXTUPWATCHEDSIGNAL',
              data=dict(episodeid=self.state.episodeid),
              encoding='base64')

        # Increase playcount and reset resume point
        self.api.handle_just_watched(episodeid=self.state.episodeid,
                                     playcount=self.state.playcount,
                                     reset_resume=True)

        self.log('Up Next playback: next file requested', 2)
        return True

    def show_popup_and_wait(self, dialog):
        if not self.player.isPlaying():
            return False

        is_upnext = isinstance(dialog, UpNext)

        total_time = self.player.getTotalTime()
        remaining = total_time - self.player.getTime()

        dialog.set_progress_step_size(remaining)
        dialog.show()
        set_property('service.upnext.dialog', 'true')

        monitor = Monitor()
        while not monitor.abortRequested():
            # Current file can stop or next file can start while loop is running
            # Abort popup update
            if not self.player.isPlaying() or self.state.starting:
                return False

            remaining = total_time - self.player.getTime()
            if remaining <= 1 or dialog.is_cancel():
                break
            if is_upnext and dialog.is_watch_now():
                break
            if not is_upnext and dialog.is_still_watching():
                break

            if self.state.pause:
                pass

            dialog.update_progress_control(remaining, total_time)
            wait_time = min(0.5, remaining - 1)
            monitor.waitForAbort(wait_time)
        return True

    def extract_play_info(self, dialog):
        if isinstance(dialog, UpNext):
            auto_play = not dialog.is_cancel() and self.state.play_mode == 0
            play_now = dialog.is_watch_now()
        else:
            auto_play = False
            play_now = dialog.is_still_watching()

        if play_now:
            self.state.played_in_a_row = 1
        else:
            self.state.played_in_a_row += 1

        return auto_play, play_now
