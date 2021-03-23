# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import api
import utils


class UpNextState(object):  # pylint: disable=useless-object-inheritance
    """Class encapsulating all state variables and methods"""

    __slots__ = (
        # Settings state variables
        'simple_mode',
        'skin_popup',
        'show_stop_button',
        'auto_play',
        'played_limit',
        'enable_resume',
        'enable_playlist',
        'mark_watched',
        'unwatched_only',
        'next_season',
        'auto_play_delay',
        'popup_durations',
        'detect_enabled',
        'detect_period',
        'detect_level',
        'disabled',
        'enable_queue',
        'tracker_mode',
        'demo_mode',
        'demo_seek',
        'demo_cue',
        'demo_plugin',
        'detector_debug',
        'start_trigger',
        'test_episode',
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

        self.log('Reset' if reset else 'Init')

    @classmethod
    def log(cls, msg, level=utils.LOGINFO):
        utils.log(msg, name=cls.__name__, level=level)

    def reset(self):
        self.__init__(reset=True)

    def update_settings(self):
        self.simple_mode = utils.get_setting_int('simpleMode') == 0
        self.skin_popup = utils.get_setting_bool('enablePopupSkin')
        self.show_stop_button = utils.get_setting_bool('stopAfterClose')

        self.auto_play = utils.get_setting_int('autoPlayMode') == 0
        self.played_limit = (
            utils.get_setting_int('playedInARow')
            if self.auto_play and utils.get_setting_bool('enableStillWatching')
            else 0
        )

        self.enable_resume = utils.get_setting_bool('enableResume')
        self.enable_playlist = utils.get_setting_bool('enablePlaylist')

        self.mark_watched = utils.get_setting_int('markWatched')
        self.unwatched_only = not utils.get_setting_bool('includeWatched')
        self.next_season = utils.get_setting_bool('nextSeason')

        self.auto_play_delay = utils.get_setting_int('autoPlayCountdown')
        self.popup_durations = {
            3600: utils.get_setting_int('autoPlayTimeXL'),
            2400: utils.get_setting_int('autoPlayTimeL'),
            1200: utils.get_setting_int('autoPlayTimeM'),
            600: utils.get_setting_int('autoPlayTimeS'),
            0: utils.get_setting_int('autoPlayTimeXS')
        } if utils.get_setting_bool('customAutoPlayTime') else {
            0: utils.get_setting_int('autoPlaySeasonTime')
        }

        self.detect_enabled = utils.get_setting_bool('detectPlayTime')
        self.detect_period = utils.get_setting_int('detectPeriod')
        self.detect_level = utils.get_setting_int('detectLevel')

        self.disabled = utils.get_setting_bool('disableNextUp')
        utils.LOG_ENABLE_LEVEL = utils.get_setting_int('logLevel')
        self.enable_queue = utils.get_setting_bool('enableQueue')
        self.tracker_mode = utils.get_setting_int('trackerMode')

        self.demo_mode = utils.get_setting_bool('enableDemoMode')
        self.demo_seek = self.demo_mode and utils.get_setting_int('demoSeek')
        self.demo_cue = self.demo_mode and utils.get_setting_int('demoCue')
        self.demo_plugin = (
            self.demo_mode and utils.get_setting_bool('demoPlugin')
        )

        self.detector_debug = utils.get_setting_bool('detectorDebug')
        self.start_trigger = utils.get_setting_bool('startTrigger')
        self.test_episode = None

    def get_tracked_file(self):
        return self.filename

    def is_disabled(self):
        return self.disabled

    def is_tracking(self):
        return self.track

    def set_tracking(self, filename):
        if filename:
            self.track = True
            self.filename = filename
            self.log('Tracking enabled: {0}'.format(filename))
        else:
            self.track = False
            self.filename = None
            self.log('Tracking disabled')

    def reset_queue(self):
        if self.queued:
            self.queued = api.reset_queue()

    def get_next(self):
        """Get next video to play, based on current video source"""

        if self.test_episode:
            return self.test_episode, 'library'

        next_item = None
        source = None
        position = api.get_playlist_position()
        has_addon_data = self.has_addon_data()

        # Next episode from addon data
        if has_addon_data:
            next_item = self.data.get('next_episode')
            if has_addon_data == 2:
                source = 'addon_play_url'
            elif has_addon_data == 3:
                source = 'addon_play_info'
            else:
                source = 'addon_missing_data'
            if position:
                source += '_playlist'

            if (self.unwatched_only
                    and utils.get_int(next_item, 'playcount') > 0):
                next_item = None
            self.log('Addon next_episode: {0}'.format(next_item))

        # Next item from non-addon playlist
        elif position and not self.shuffle:
            next_item = api.get_next_in_playlist(
                position,
                self.unwatched_only
            )
            source = 'playlist'

        # Next episode from Kodi library
        else:
            next_item, new_season = api.get_next_from_library(
                self.episodeid,
                self.tvshowid,
                self.unwatched_only,
                self.next_season,
                self.shuffle
            )
            source = 'library'
            # Show Still Watching? popup if next episode is from next season
            if new_season:
                self.played_in_a_row = self.played_limit

        return next_item, source

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
            self.popup_time - self.detect_period
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

        # Use addon settings for duration
        popup_duration = self.popup_durations[max(0, 0, *[
            idx for idx in self.popup_durations
            if total_time > idx
        ])]
        # Disable cue point unless forced on in demo mode
        self.popup_cue = self.demo_cue == 1
        if 0 < popup_duration < total_time:
            self.popup_time = total_time - popup_duration
        else:
            self.popup_time = 0

    def set_detected_popup_time(self, play_time):
        # Force popup time to specified play time
        self.popup_time = play_time
        # Enable cue point unless forced off in demo mode
        self.popup_cue = self.demo_cue != 2

    def process_now_playing(self, is_playlist, has_addon_data, media_type):
        if has_addon_data:
            item = self.get_addon_now_playing()
        elif is_playlist:
            item = self.get_playlist_now_playing()
        elif media_type == 'episode':
            item = self.get_library_now_playing()
        else:
            item = None

        if not item:
            return None

        showtitle = item.get('showtitle')
        season = item.get('season')
        if not showtitle or not season or season == -1:
            self.season_identifier = None
        else:
            self.season_identifier = '_'.join((str(showtitle), str(season)))

        return item

    def get_addon_now_playing(self):
        item = self.data.get('current_episode') if self.data else None
        self.log('Addon current_episode: {0}'.format(item))
        if not item:
            return None

        tvshowid = utils.get_int(item, 'tvshowid')

        # Reset played in a row count if new show playing
        if self.tvshowid != tvshowid:
            self.log('Reset played count: tvshowid change - {0} to {1}'.format(
                self.tvshowid, tvshowid
            ))
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
            self.log('Fetched tvshowid: {0}'.format(tvshowid))
        # Now playing show not found in library
        if tvshowid == -1:
            return None

        # Reset played in a row count if new show playing
        if self.tvshowid != tvshowid:
            self.log('Reset played count: tvshowid change - {0} to {1}'.format(
                self.tvshowid, tvshowid
            ))
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
            self.log('Fetched episodeid: {0}'.format(self.episodeid))
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
            self.log('Addon data: {0}'.format(data))
        self.data = data
        self.encoding = encoding
