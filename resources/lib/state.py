# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import api
import constants
import utils


class UpNextState(object):  # pylint: disable=useless-object-inheritance,too-many-public-methods
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
        # Addon data
        'data',
        'encoding',
        # Current file details
        'item',
        'filename',
        'tvshowid',
        'episodeid',
        'season_identifier',
        'episode',
        'playcount',
        # Popup state variables
        'next_item',
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
        self.log('Reset' if reset else 'Init')

        # Settings state variables
        if not reset:
            self.update_settings()
        # Addon data
        self.data = None
        self.encoding = 'base64'
        # Current file details
        self.item = None
        self.filename = None
        self.tvshowid = constants.UNKNOWN_DATA
        self.episodeid = constants.UNKNOWN_DATA
        self.season_identifier = None
        self.episode = None
        self.playcount = 0
        # Popup state variables
        self.next_item = None
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

    @staticmethod
    def set_log_level(level=None):
        if level is None:
            level = utils.get_setting_int('logLevel', echo=False)
        utils.LOG_ENABLE_SETTING = level

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def reset(self):
        self.__init__(reset=True)

    def update_settings(self):
        self.set_log_level()
        utils.log('Loading...', 'Settings', level=utils.LOGDEBUG)
        utils.log(
            'logLevel: {0}'.format(utils.LOG_ENABLE_SETTING),
            'Settings',
            level=utils.LOGDEBUG
        )

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
            self.log('Tracking enabled: {0}'.format(filename), utils.LOGINFO)
        else:
            self.track = False
            self.filename = None
            self.log('Tracking disabled')

    def reset_queue(self):
        if self.queued:
            self.queued = api.reset_queue()

    def get_next(self):
        """Get next video to play, based on current video source"""

        next_item = None
        source = None
        playlist_position = api.get_playlist_position()
        addon_type = self.get_addon_type(playlist_position)

        # Next episode from addon data
        if addon_type:
            next_item = self.data.get('next_episode')
            source = constants.ADDON_TYPES[addon_type]

            if (self.unwatched_only
                    and utils.get_int(next_item, 'playcount') > 0):
                next_item = None
            self.log('Addon next_episode: {0}'.format(next_item))

        # Next item from non-addon playlist
        elif playlist_position and not self.shuffle:
            next_item = api.get_next_in_playlist(
                playlist_position,
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

        if next_item and source:
            self.next_item = {
                'item': next_item,
                'source': source
            }
        if not self.next_item:
            return None, None

        return self.next_item['item'], self.next_item['source']

    def get_detect_time(self):
        return self.detect_time

    def _set_detect_time(self):
        # Don't use detection time period if an addon cue point was provided,
        # or end credits detection is disabled
        if self.popup_cue or not self.detect_enabled:
            self.detect_time = None
            return

        # Detection time period starts before normal popup time
        self.detect_time = max(0, self.popup_time - self.detect_period)

    def get_popup_time(self):
        return self.popup_time

    def set_popup_time(self, total_time=0, detected_time=0):
        popup_time = 0

        # Detected popup time overrides addon data and settings
        if detected_time:
            # Force popup time to specified play time
            popup_time = detected_time

            # Enable cue point unless forced off in demo mode
            self.popup_cue = self.demo_cue != constants.SETTING_FORCED_OFF

        # Alway use addon data, when available
        elif self.get_addon_type():
            # Some addons send the time from video end
            popup_duration = utils.get_int(self.data, 'notification_time', 0)
            # Some addons send the time from video start (e.g. Netflix)
            popup_time = utils.get_int(self.data, 'notification_offset', 0)

            # Ensure popup duration is not too short
            if constants.POPUP_MIN_DURATION <= popup_duration < total_time:
                popup_time = total_time - popup_duration

            # Ensure popup time is not too close to end of playback
            if 0 < popup_time <= total_time - constants.POPUP_MIN_DURATION:
                # Enable cue point unless forced off in demo mode
                self.popup_cue = self.demo_cue != constants.SETTING_FORCED_OFF
            # Otherwise ignore popup time from addon data
            else:
                popup_time = 0

        # Use addon settings as fallback option
        if not popup_time:
            # Time from video end
            popup_duration = self.popup_durations[max(0, 0, *[
                duration for duration in self.popup_durations
                if total_time > duration
            ])]

            # Ensure popup duration is not too short
            if constants.POPUP_MIN_DURATION <= popup_duration < total_time:
                popup_time = total_time - popup_duration
            # Otherwise set default popup time
            else:
                popup_time = total_time - constants.POPUP_MIN_DURATION

            # Disable cue point unless forced on in demo mode
            self.popup_cue = self.demo_cue == constants.SETTING_FORCED_ON

        self.popup_time = popup_time
        self._set_detect_time()

        self.log('Popup due at {0}s of {1}s'.format(
            self.popup_time, total_time
        ), utils.LOGINFO)

    def process_now_playing(self, playlist_position, addon_type, media_type):
        if addon_type:
            item = self._get_addon_now_playing()
            source = constants.ADDON_TYPES[addon_type]

        elif playlist_position:
            item = api.get_now_playing()
            source = 'playlist'

        elif media_type == 'episode':
            item = self._get_library_now_playing()
            source = 'library'

        else:
            item = None
            source = None

        if item and source:
            self.item = {
                'item': item,
                'source': source
            }
        if not self.item:
            return None

        tvshowid = self.get_tvshowid(self.item['item'])
        # Reset played in a row count if new show playing
        if self.tvshowid != tvshowid:
            self.log('Reset played count: tvshowid change - {0} to {1}'.format(
                self.tvshowid, tvshowid
            ))
            self.played_in_a_row = 1

        self._set_tvshowid()
        self._set_episodeid()
        self._set_episode()
        self._set_playcount()
        self._set_season_identifier()

        return self.item['item']

    def _get_addon_now_playing(self):
        if self.data:
            # Fallback to now playing info if addon does not provide current
            # episode details
            item = self.data.get('current_episode', api.get_now_playing())
        else:
            item = None

        self.log('Addon current_episode: {0}'.format(item))
        if not item:
            return None

        return item

    def _get_library_now_playing(self):
        item = api.get_now_playing()
        if not item:
            return None

        # Get current tvshowid or search in library if detail missing
        tvshowid = self.get_tvshowid(item)
        if tvshowid == constants.UNKNOWN_DATA:
            tvshowid = api.get_tvshowid(item.get('showtitle'))
            self.log('Fetched tvshowid: {0}'.format(tvshowid))
        # Now playing show not found in library
        if tvshowid == constants.UNKNOWN_DATA:
            return None
        item['tvshowid'] = tvshowid

        # Get current episodeid or search in library if detail missing
        episodeid = self.get_episodeid(item)
        if episodeid == constants.UNKNOWN_DATA:
            episodeid = api.get_episodeid(
                tvshowid,
                item.get('season'),
                item.get('episode')
            )
            self.log('Fetched episodeid: {0}'.format(episodeid))
        # Now playing episode not found in library
        if episodeid == constants.UNKNOWN_DATA:
            return None
        item['episodeid'] = episodeid

        return item

    def get_addon_type(self, playlist_position=None):
        if self.data:
            addon_type = constants.ADDON_DATA_ERROR
            if playlist_position:
                addon_type += constants.ADDON_PLAYLIST
            if self.data.get('play_url'):
                addon_type += constants.ADDON_PLAY_URL
            elif self.data.get('play_info'):
                addon_type += constants.ADDON_PLAY_INFO
            return addon_type
        return None

    def set_addon_data(self, data, encoding='base64'):
        if data:
            self.log('Addon data: {0}'.format(data))
        self.data = data
        self.encoding = encoding

    def _set_tvshowid(self):
        self.tvshowid = utils.get_int(self.item['item'], 'tvshowid')

    def get_tvshowid(self, item=None):
        if item:
            return utils.get_int(item, 'tvshowid')
        return self.tvshowid

    def _set_episodeid(self):
        self.episodeid = utils.get_int(
            self.item['item'], 'episodeid',
            utils.get_int(self.item['item'], 'id')
        )

    def get_episodeid(self, item=None):
        if item:
            return utils.get_int(
                item, 'episodeid',
                utils.get_int(item, 'id')
            )
        return self.episodeid

    def _set_episode(self):
        self.episode = utils.get_int(self.item['item'], 'episode')

    def get_episode(self):
        return self.episode

    def _set_playcount(self):
        self.playcount = utils.get_int(self.item['item'], 'playcount', 0)

    def get_playcount(self):
        return self.playcount

    def _set_season_identifier(self):
        showtitle = self.item['item'].get('showtitle')
        season = self.item['item'].get('season')
        if not showtitle or not season or season == constants.UNKNOWN_DATA:
            self.season_identifier = None
        else:
            self.season_identifier = '_'.join((str(showtitle), str(season)))

    def get_season_identifier(self):
        return self.season_identifier
