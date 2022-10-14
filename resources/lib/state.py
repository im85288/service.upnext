# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from settings import SETTINGS
import api
import constants
import utils


class UpNextState(object):  # pylint: disable=too-many-public-methods
    """Class encapsulating all state variables and methods"""

    __slots__ = (
        # Addon data
        'data',
        'encoding',
        # Current video details
        'current_item',
        'filename',
        'total_time',
        'playcount',
        'tvshowid',
        'episodeid',
        'episode_number',
        'season_identifier',
        # Popup state variables
        'next_item',
        'popup_time',
        'popup_cue',
        'detect_time',
        'shuffle_on',
        # Tracking player state variables
        'starting',
        'tracking',
        'played_in_a_row',
        'queued',
        'playing_next',
        'keep_playing',
    )

    def __init__(self, reset=None):
        self.log('Reset' if reset else 'Init')

        # Plugin data
        self.data = None
        self.encoding = 'base64'
        # Current video details
        self.current_item = None
        self.filename = None
        self.total_time = 0
        self.playcount = 0
        self.tvshowid = constants.UNDEFINED
        self.episodeid = constants.UNDEFINED
        self.episode_number = None
        self.season_identifier = None
        # Popup state variables
        self.next_item = None
        self.popup_time = 0
        self.popup_cue = False
        self.detect_time = 0
        self.shuffle_on = False
        # Tracking player state variables
        self.starting = 0
        self.tracking = False
        self.played_in_a_row = 1
        self.queued = False
        self.playing_next = False
        self.keep_playing = False

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def reset(self):
        self.__init__(reset=True)  # pylint: disable=unnecessary-dunder-call

    def reset_item(self):
        self.current_item = None
        self.next_item = None

    def get_tracked_file(self):
        return self.filename

    def is_tracking(self):
        return self.tracking

    def set_tracking(self, filename):
        if filename:
            self.tracking = True
            self.filename = filename
            self.log('Tracking enabled: {0}'.format(filename), utils.LOGINFO)
        else:
            self.tracking = False
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
        plugin_type = self.get_plugin_type(playlist_position)

        # Next episode from plugin data
        if plugin_type:
            next_item = self.data.get('next_episode')
            source = constants.PLUGIN_TYPES[plugin_type]

            if (SETTINGS.unwatched_only
                    and utils.get_int(next_item, 'playcount') > 0):
                next_item = None
            self.log('Plugin next_episode: {0}'.format(next_item))

        # Next item from non-plugin playlist
        elif playlist_position and not self.shuffle_on:
            next_item = api.get_from_playlist(
                playlist_position,
                SETTINGS.unwatched_only
            )
            source = 'playlist'

        # Next episode from Kodi library
        else:
            current_item = api.get_from_library(
                self.episodeid,
                self.tvshowid
            )
            next_item, new_season = api.get_next_from_library(
                episode=current_item,
                tvshowid=self.tvshowid,
                unwatched_only=SETTINGS.unwatched_only,
                next_season=SETTINGS.next_season,
                random=self.shuffle_on
            )
            source = 'library'
            # Show Still Watching? popup if next episode is from next season
            if new_season:
                self.played_in_a_row = SETTINGS.played_limit

        if next_item and source:
            self.next_item = {
                'details': next_item,
                'source': source
            }
        if not self.next_item:
            return None, None

        return self.next_item['details'], self.next_item['source']

    def get_detect_time(self):
        return self.detect_time

    def _set_detect_time(self):
        # Don't use detection time period if an plugin cue point was provided,
        # or end credits detection is disabled
        if self.popup_cue or not SETTINGS.detect_enabled:
            self.detect_time = None
            return

        # Detection time period starts before normal popup time
        self.detect_time = max(
            0,
            self.popup_time - (SETTINGS.detect_period * self.total_time / 3600)
        )

    def get_popup_time(self):
        return self.popup_time

    def set_detected_popup_time(self, detected_time):
        popup_time = 0

        # Detected popup time overrides plugin data and settings
        if detected_time:
            # Force popup time to specified play time
            popup_time = detected_time

            # Enable cue point unless forced off in demo mode
            self.popup_cue = SETTINGS.demo_cue != constants.SETTING_OFF

        self.popup_time = popup_time
        self._set_detect_time()

        self.log('Popup: due at {0}s of {1}s (cue: {2})'.format(
            self.popup_time, self.total_time, self.popup_cue
        ), utils.LOGINFO)

    def set_popup_time(self, total_time):
        popup_time = 0

        # Alway use plugin data, when available
        if self.get_plugin_type():
            # Some plugins send the time from video end
            popup_duration = utils.get_int(self.data, 'notification_time', 0)
            # Some plugins send the time from video start (e.g. Netflix)
            popup_time = utils.get_int(self.data, 'notification_offset', 0)

            # Ensure popup duration is not too short
            if constants.POPUP_MIN_DURATION <= popup_duration < total_time:
                popup_time = total_time - popup_duration

            # Ensure popup time is not too close to end of playback
            if 0 < popup_time <= total_time - constants.POPUP_MIN_DURATION:
                # Enable cue point unless forced off in demo mode
                self.popup_cue = SETTINGS.demo_cue != constants.SETTING_OFF
            # Otherwise ignore popup time from plugin data
            else:
                popup_time = 0

        # Use addon settings as fallback option
        if not popup_time:
            # Time from video end
            popup_duration = SETTINGS.popup_durations[max(0, 0, *[
                duration for duration in SETTINGS.popup_durations
                if total_time > duration
            ])]

            # Ensure popup duration is not too short
            if constants.POPUP_MIN_DURATION <= popup_duration < total_time:
                popup_time = total_time - popup_duration
            # Otherwise set default popup time
            else:
                popup_time = total_time - constants.POPUP_MIN_DURATION

            # Disable cue point unless forced on in demo mode
            self.popup_cue = SETTINGS.demo_cue == constants.SETTING_ON

        self.popup_time = popup_time
        self.total_time = total_time
        self._set_detect_time()

        self.log('Popup: due at {0}s of {1}s (cue: {2})'.format(
            self.popup_time, self.total_time, self.popup_cue
        ), utils.LOGINFO)

    def process_now_playing(self, playlist_position, plugin_type, media_type):
        if plugin_type:
            current_item = self._get_plugin_now_playing()
            source = constants.PLUGIN_TYPES[plugin_type]

        elif playlist_position:
            current_item = api.get_from_playlist(playlist_position - 1)
            source = 'playlist'

            if current_item:
                if not current_item.get('showtitle'):
                    current_item['showtitle'] = constants.MIXED_PLAYLIST
                if not current_item['season']:
                    current_item['season'] = 0
                if not current_item['episode']:
                    current_item['episode'] = playlist_position

        elif media_type == 'episode':
            current_item = self._get_library_now_playing()
            source = 'library'

        else:
            current_item = None
            source = None

        if current_item and source:
            self.current_item = {
                'details': current_item,
                'source': source
            }
        if not self.current_item:
            return None

        tvshowid = self.get_tvshowid(self.current_item['details'])
        # Reset played in a row count if new show playing
        if self.tvshowid != tvshowid:
            self.log('Reset played count: tvshowid change - {0} to {1}'.format(
                self.tvshowid, tvshowid
            ))
            self.played_in_a_row = 1

        self._set_tvshowid()
        self._set_episodeid()
        self._set_episode_number()
        self._set_playcount()
        self._set_season_identifier()

        return self.current_item['details']

    def _get_plugin_now_playing(self):
        if self.data:
            # Fallback to now playing info if plugin does not provide current
            # episode details
            current_item = (
                self.data.get('current_episode')
                or api.get_now_playing(retry=SETTINGS.api_retry_attempts)
            )
        else:
            current_item = None

        self.log('Plugin current_episode: {0}'.format(current_item))
        if not current_item:
            return None

        return current_item

    def _get_library_now_playing(self):
        current_item = api.get_now_playing(retry=SETTINGS.api_retry_attempts)
        if not current_item:
            return None

        # Get current tvshowid or search in library if detail missing
        tvshowid = self.get_tvshowid(current_item)
        if tvshowid == constants.UNDEFINED:
            tvshowid = api.get_tvshowid(current_item.get('showtitle'))
            self.log('Fetched tvshowid: {0}'.format(tvshowid))
        # Now playing show not found in library
        if tvshowid == constants.UNDEFINED:
            return None
        current_item['tvshowid'] = tvshowid

        # Get current episodeid or search in library if detail missing
        episodeid = self.get_episodeid(current_item)
        if episodeid == constants.UNDEFINED:
            episodeid = api.get_episodeid(
                tvshowid,
                current_item.get('season'),
                current_item.get('episode')
            )
            self.log('Fetched episodeid: {0}'.format(episodeid))
        # Now playing episode not found in library
        if episodeid == constants.UNDEFINED:
            return None
        current_item['episodeid'] = episodeid

        return current_item

    def get_plugin_type(self, playlist_position=None):
        if self.data:
            plugin_type = constants.PLUGIN_DATA_ERROR
            if playlist_position:
                plugin_type += constants.PLUGIN_PLAYLIST
            if self.data.get('play_url'):
                plugin_type += constants.PLUGIN_PLAY_URL
            elif self.data.get('play_info'):
                plugin_type += constants.PLUGIN_PLAY_INFO
            return plugin_type
        return None

    def set_plugin_data(self, data, encoding='base64'):
        if data:
            self.log('Plugin data: {0}'.format(data))
        self.data = data
        self.encoding = encoding

    def _set_tvshowid(self):
        self.tvshowid = utils.get_int(self.current_item['details'], 'tvshowid')

    def get_tvshowid(self, item=None):
        if item:
            return utils.get_int(item, 'tvshowid')
        return self.tvshowid

    def _set_episodeid(self):
        self.episodeid = utils.get_int(
            self.current_item['details'], 'id', None
        ) or utils.get_int(self.current_item['details'], 'episodeid')

    def get_episodeid(self, item=None):
        if item:
            return utils.get_int(
                item, 'episodeid', None
            ) or utils.get_int(item, 'id')
        return self.episodeid

    def _set_episode_number(self):
        self.episode_number = utils.get_int(
            self.current_item['details'], 'episode'
        )

    def get_episode_number(self):
        return self.episode_number

    def _set_playcount(self):
        self.playcount = utils.get_int(
            self.current_item['details'], 'playcount', 0
        )

    def get_playcount(self):
        return self.playcount

    def _set_season_identifier(self):
        showtitle = self.current_item['details'].get('showtitle')
        season = self.current_item['details'].get('season')
        if not showtitle or season == constants.UNDEFINED:
            self.season_identifier = None
        else:
            if isinstance(season, (int, float)):
                season = str(season)
            self.season_identifier = '_'.join((showtitle, season))

    def get_season_identifier(self):
        return self.season_identifier
