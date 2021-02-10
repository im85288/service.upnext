# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import api
import upnext
import utils


class UpNextState(object):  # pylint: disable=useless-object-inheritance
    """Class encapsulating all state variables and methods"""

    __slots__ = (
        # Settings state variables
        'disabled',
        'simple_mode',
        'auto_play',
        'enable_playlist',
        'unwatched_only',
        'played_limit',
        'auto_play_delay',
        'detect_enabled',
        'detect_always',
        'demo_mode',
        'demo_seek',
        'demo_cue',
        'demo_plugin',
        # Addon data
        'data',
        'encoding',
        # Current file details
        'filename',
        'tvshowid',
        'episodeid',
        'season_identifier',
        'episode',
        'playcount',
        # Popup state variables
        'popup_time',
        'popup_cue',
        'detect_time',
        # Tracking player state variables
        'starting',
        'playing',
        'track',
        'shuffle',
        'played_in_a_row',
        'queued',
        'playing_next',
    )

    def __init__(self, reset=None):
        # Settings state variables
        self.update_settings()
        # Addon data
        self.data = None
        self.encoding = 'base64'
        # Current file details
        self.filename = None
        self.tvshowid = None
        self.episodeid = None
        self.season_identifier = None
        self.episode = None
        self.playcount = 0
        # Popup state variables
        self.popup_time = 0
        self.popup_cue = False
        self.detect_time = 0
        # Tracking player state variables
        self.starting = 0
        self.playing = False
        self.track = False
        self.shuffle = False
        self.played_in_a_row = 1
        self.queued = False
        self.playing_next = False

        self.log('Reset' if reset else 'Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def reset(self):
        self.__init__(reset=True)

    def update_settings(self):
        self.disabled = utils.get_setting_bool('disableNextUp')
        self.simple_mode = utils.get_setting_int('simpleMode') == 0
        self.auto_play = utils.get_setting_int('autoPlayMode') == 0
        self.enable_playlist = utils.get_setting_bool('enablePlaylist')
        self.unwatched_only = not utils.get_setting_bool('includeWatched')
        self.played_limit = utils.get_setting_int('playedInARow')
        self.auto_play_delay = utils.get_setting_int('autoPlayCountdown')
        self.detect_enabled = utils.get_setting_bool('detectPlayTime')
        self.detect_always = (
            self.detect_enabled and utils.get_setting_bool('detectAlways')
        )
        self.demo_mode = utils.get_setting_bool('enableDemoMode')
        self.demo_seek = self.demo_mode and utils.get_setting_int('demoSeek')
        self.demo_cue = self.demo_mode and utils.get_setting_int('demoCue')
        self.demo_plugin = (
            self.demo_mode and utils.get_setting_bool('demoPlugin')
        )

    def get_tracked_file(self):
        return self.filename

    def is_disabled(self):
        return self.disabled

    def is_tracking(self):
        return self.track

    def set_tracking(self, filename):
        if filename:
            msg = 'Tracking enabled: {0}'.format(filename)
        else:
            msg = 'Tracking disabled'
        self.log(msg, 2)
        self.track = bool(filename)
        self.filename = filename if filename else None

    def reset_queue(self):
        if self.queued:
            self.queued = api.reset_queue()

    def get_next(self):
        """Get next episode to play, based on current video source"""

        episode = None
        source = None
        position = api.get_playlist_position()
        has_addon_data = self.has_addon_data()

        # Next video from addon data
        if has_addon_data:
            episode = self.data.get('next_episode')
            source = 'addon' if not position else 'playlist'
            self.log('Addon next_episode: {0}'.format(episode), 2)

        # Next video from non-addon playlist
        elif position and not self.shuffle:
            episode = api.get_next_in_playlist(position)
            source = 'playlist'

        # Next video from Kodi library
        else:
            episode, new_season = api.get_next_from_library(
                self.episodeid,
                self.tvshowid,
                self.unwatched_only,
                self.shuffle
            )
            source = 'library'
            # Show Still Watching? popup if next episode is from next season
            if new_season:
                self.played_in_a_row = self.played_limit

        return episode, source

    def get_detect_time(self):
        # Don't use detection time period if an addon cue point was provided,
        # or end credits detection is disabled
        if self.popup_cue or not self.detect_enabled:
            return None
        return self.detect_time

    def set_detect_time(self):
        # Detection time period starts before normal popup time
        self.detect_time = max(
            0,
            self.popup_time - utils.get_setting_int('detectPeriod')
        )

    def get_popup_time(self):
        return self.popup_time

    def set_popup_time(self, total_time):
        # Alway use addon data, when available
        if self.has_addon_data():
            # Some addons send the time from video end
            popup_duration = utils.get_int(self.data, 'notification_time')
            if 0 < popup_duration < total_time:
                # Enable cue point unless forced off in demo mode
                self.popup_cue = self.demo_cue != 2
                self.popup_time = total_time - popup_duration
                return

            # Some addons send the time from video start (e.g. Netflix)
            popup_time = utils.get_int(self.data, 'notification_offset')
            if 0 < popup_time < total_time:
                # Enable cue point unless forced off in demo mode
                self.popup_cue = self.demo_cue != 2
                self.popup_time = popup_time
                return

        # Use a customized notification time, when configured
        if utils.get_setting_bool('customAutoPlayTime'):
            if total_time > 60 * 60:
                duration_setting = 'autoPlayTimeXL'
            elif total_time > 40 * 60:
                duration_setting = 'autoPlayTimeL'
            elif total_time > 20 * 60:
                duration_setting = 'autoPlayTimeM'
            elif total_time > 10 * 60:
                duration_setting = 'autoPlayTimeS'
            else:
                duration_setting = 'autoPlayTimeXS'

        # Use one global default, regardless of episode length
        else:
            duration_setting = 'autoPlaySeasonTime'

        # Use addon settings for duration
        popup_duration = utils.get_setting_int(duration_setting)
        # Disable cue point unless forced on in demo mode
        self.popup_cue = self.demo_cue == 1
        if 0 < popup_duration < total_time:
            self.popup_time = total_time - popup_duration
        else:
            self.popup_time = 0

    def set_detected_popup_time(self, time):
        # Force popup time to specified time
        self.popup_time = time
        # Enable cue point unless forced off in demo mode
        self.popup_cue = self.demo_cue != 2

    def process_now_playing(self, is_playlist, has_addon_data, media_type):
        item = (
            self.get_addon_now_playing() if has_addon_data
            else self.get_playlist_now_playing() if is_playlist
            else self.get_library_now_playing() if media_type == 'episode'
            else None
        )
        if not item:
            return None

        # Force use of addon data method if demo plugin mode is enabled
        if not has_addon_data and self.demo_plugin:
            next_episode, source = self.get_next()

            if source == 'library':
                next_dbid = next_episode.get('episodeid')
                current_episode = upnext.create_listitem(item)
                next_episode = upnext.create_listitem(next_episode)

                addon_id = utils.addon_id()
                upnext_info = {
                    'current_episode': current_episode,
                    'next_episode': next_episode,
                    'play_url': 'plugin://{0}/?play={1}'.format(
                        addon_id,
                        next_dbid
                    )
                }
                upnext.send_signal(addon_id, upnext_info)

        showtitle = item.get('showtitle')
        season = item.get('season')
        if not showtitle or not season or season == -1:
            self.season_identifier = None
        else:
            self.season_identifier = '_'.join((str(showtitle), str(season)))

        return item

    def get_addon_now_playing(self):
        item = self.data.get('current_episode') if self.data else None
        self.log('Addon current_episode: {0}'.format(item), 2)
        if not item:
            return None

        tvshowid = utils.get_int(item, 'tvshowid')

        # Reset play count if new show playing
        if self.tvshowid != tvshowid:
            msg = 'Reset played count: tvshowid change from {0} to {1}'
            msg = msg.format(
                self.tvshowid,
                tvshowid
            )
            self.log(msg, 2)
            self.tvshowid = tvshowid
            self.played_in_a_row = 1

        self.episodeid = utils.get_int(item, 'episodeid')
        self.episode = utils.get_int(item, 'episode')
        self.playcount = utils.get_int(item, 'playcount', 0)

        return item

    def get_library_now_playing(self):
        item = api.get_now_playing()
        if not item:
            return None

        # Get current tvshowid or search in library if detail missing
        tvshowid = utils.get_int(item, 'tvshowid')
        if tvshowid == -1:
            title = item.get('showtitle')
            tvshowid = api.get_tvshowid(title)
            self.log('Fetched tvshowid: %s' % tvshowid, 2)
        # Now playing show not found in library
        if tvshowid == -1:
            return None

        # Reset play count if new show playing
        if self.tvshowid != tvshowid:
            msg = 'Reset played count: tvshowid change from {0} to {1}'
            msg = msg.format(
                self.tvshowid,
                tvshowid
            )
            self.log(msg, 2)
            self.tvshowid = tvshowid
            self.played_in_a_row = 1

        # Get current episodeid or search in library if detail missing
        self.episodeid = utils.get_int(item, 'id')
        if self.episodeid == -1:
            self.episodeid = api.get_episodeid(
                tvshowid,
                item.get('season'),
                item.get('episode')
            )
            self.log('Fetched episodeid: %s' % self.episodeid, 2)
        # Now playing episode not found in library
        if self.episodeid == -1:
            return None

        self.episode = utils.get_int(item, 'episode')
        self.playcount = utils.get_int(item, 'playcount', 0)

        return item

    def get_playlist_now_playing(self):
        item = api.get_now_playing()
        if not item:
            return None

        self.tvshowid = utils.get_int(item, 'tvshowid')
        self.episodeid = utils.get_int(item, 'id')
        self.episode = utils.get_int(item, 'episode')
        self.playcount = utils.get_int(item, 'playcount', 0)

        return item

    def has_addon_data(self):
        if self.data:
            if self.data.get('play_url'):
                return 2
            if self.data.get('play_info'):
                return 3
            return 1
        return 0

    def set_addon_data(self, data, encoding='base64'):
        if data:
            self.log('Addon data: %s' % data, 2)
        self.data = data
        self.encoding = encoding
