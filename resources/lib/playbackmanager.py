# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import Monitor
from api import Api
from player import Player
from playitem import PlayItem
from state import State
from dialog import StillWatching, UpNext
from utils import addon_path, calculate_progress_steps, clear_property, event, get_setting_bool, get_setting_int, get_int,
                  log as ulog, set_property


class PlaybackManager:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state
        self.api = Api()
        self.play_item = PlayItem()
        self.state = State()
        self.player = Player()

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def launch_up_next(self):
        self.state.playing_next = True
        episode, playlist_item = self.play_item.get_next()

        if playlist_item and not get_setting_bool('enablePlaylist'):
            self.state.playing_next = False
            self.log('Playlist integration disabled', 2)

        elif not episode:
            # No episode get out of here
            self.state.playing_next = False
            self.log('Error: no episode could be found to play next...exiting', 1)

        else:
            self.log('Episode details %s' % episode, 2)
            self.state.playing_next = self.launch_popup(episode, playlist_item)
            if not self.state.playing_next and self.state.queued:
                self.api.dequeue_next_item()

        return self.state.playing_next

    def launch_popup(self, episode, playlist_item):
        episode_id = get_int(episode, 'episodeid')
        watched = (not self.state.include_watched and episode.get('playcount', 0)) or
                  (self.state.current_episode_id == episode_id and episode_id != -1)
        if watched:
            self.log('Exit launch_popup early: already watched file', 2)
            return False

        if not playlist_item:
            self.state.queued = self.api.queue_next_item(episode)

        # We have a next up episode choose mode
        if get_setting_int('simpleMode') == 0:
            next_up_page = UpNext('script-upnext-upnext-simple.xml', addon_path(), 'default', '1080i')
            still_watching_page = StillWatching('script-upnext-stillwatching-simple.xml', addon_path(), 'default', '1080i')
        else:
            next_up_page = UpNext('script-upnext-upnext.xml', addon_path(), 'default', '1080i')
            still_watching_page = StillWatching('script-upnext-stillwatching.xml', addon_path(), 'default', '1080i')

        showing_next_up_page, showing_still_watching_page = self.show_popup_and_wait(episode,
                                                                                     next_up_page,
                                                                                     still_watching_page)
        should_play_default, should_play_non_default = self.extract_play_info(next_up_page,
                                                                              showing_next_up_page,
                                                                              showing_still_watching_page,
                                                                              still_watching_page)
        if not self.state.track:
            self.log('Exit launch_popup early: disabled tracking', 2)
            return False

        play_item_option_1 = (should_play_default and self.state.play_mode == 0)
        play_item_option_2 = (should_play_non_default and self.state.play_mode == 1)
        if not play_item_option_1 and not play_item_option_2:
            self.log('Exit launch_popup early: no playback option selected', 2)
            return False

        # Signal to trakt previous episode watched
        event(message='NEXTUPWATCHEDSIGNAL', data=dict(episodeid=self.state.current_episode_id), encoding='base64')
        if playlist_item or self.state.queued:
            # Play playlist media, only skip if media has not already played through
            # Can't seek as this triggers inconsistent Kodi behaviour:
            # - Will sometimes continue playing past the end of the file preventing next file from playing
            # - Will sometimes play the next file correctly then play it again resulting in loss of UpNext state
            # - Will sometimes play the next file immediately without onPlayBackStarted triggering resulting in tracking not activating
            # - Will sometimes work just fine
            if should_play_non_default:
                self.player.playnext()

        elif self.api.has_addon_data():
            # Play add-on media
            self.api.play_addon_item()

        else:
            # Play local media
            self.api.play_kodi_item(episode)

        # Increase playcount and reset resume point
        self.api.handle_just_watched(episodeid=self.state.current_episode_id,
                                     playcount=self.state.current_playcount,
                                     reset_resume=True)

        self.log('Exit launch_popup: next file requested', 2)
        return True

    def show_popup_and_wait(self, episode, next_up_page, still_watching_page):
        try:
            play_time = self.player.getTime()
            total_time = self.player.getTotalTime()
        except RuntimeError:
            self.log('exit early because player is no longer running', 2)
            return False, False
        progress_step_size = calculate_progress_steps(total_time - play_time)
        next_up_page.set_item(episode)
        next_up_page.set_progress_step_size(progress_step_size)
        still_watching_page.set_item(episode)
        still_watching_page.set_progress_step_size(progress_step_size)
        played_in_a_row_number = get_setting_int('playedInARow')
        self.log('played in a row settings %s' % played_in_a_row_number, 2)
        self.log('played in a row %s' % self.state.played_in_a_row, 2)
        showing_next_up_page = False
        showing_still_watching_page = False
        if int(self.state.played_in_a_row) <= int(played_in_a_row_number):
            self.log('showing next up page as played in a row is %s' % self.state.played_in_a_row, 2)
            next_up_page.show()
            set_property('service.upnext.dialog', 'true')
            showing_next_up_page = True
        else:
            self.log('showing still watching page as played in a row %s' % self.state.played_in_a_row, 2)
            still_watching_page.show()
            set_property('service.upnext.dialog', 'true')
            showing_still_watching_page = True
        while (self.player.isPlaying() and (total_time - play_time > 1)
               and not next_up_page.is_cancel() and not next_up_page.is_watch_now()
               and not still_watching_page.is_still_watching() and not still_watching_page.is_cancel()):
            try:
                play_time = self.player.getTime()
                total_time = self.player.getTotalTime()
            except RuntimeError:
                if showing_next_up_page:
                    next_up_page.close()
                    showing_next_up_page = False
                if showing_still_watching_page:
                    still_watching_page.close()
                    showing_still_watching_page = False
                break

            remaining = total_time - play_time
            runtime = episode.get('runtime')
            if not self.state.pause:
                if showing_next_up_page:
                    next_up_page.update_progress_control(remaining=remaining, runtime=runtime)
                elif showing_still_watching_page:
                    still_watching_page.update_progress_control(remaining=remaining, runtime=runtime)
            Monitor().waitForAbort(0.1)
        return showing_next_up_page, showing_still_watching_page

    def extract_play_info(self, next_up_page, showing_next_up_page, showing_still_watching_page, still_watching_page):
        if showing_next_up_page:
            next_up_page.close()
            should_play_default = not next_up_page.is_cancel()
            should_play_non_default = next_up_page.is_watch_now()
        elif showing_still_watching_page:
            still_watching_page.close()
            should_play_default = still_watching_page.is_still_watching()
            should_play_non_default = still_watching_page.is_still_watching()
        else:
            # FIXME: This is a workaround until we handle this better (see comments in #142)
            return False, False

        if next_up_page.is_watch_now() or still_watching_page.is_still_watching():
            self.state.played_in_a_row = 1
        else:
            self.state.played_in_a_row += 1
        clear_property('service.upnext.dialog')
        return should_play_default, should_play_non_default
