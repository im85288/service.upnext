# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import constants
import file_utils
import utils


class UpNextSettings(object):
    """Class containing all addon settings"""

    __slots__ = (
        # Settings state variables
        'api_retry_attempts',
        'auto_play',
        'auto_play_delay',
        'demo_cue',
        'demo_mode',
        'demo_plugin',
        'demo_seek',
        'detect_enabled',
        'detect_level',
        'detect_matches',
        'detect_mismatches',
        'detect_period',
        'detect_significance',
        'detector_data_limit',
        'detector_debug',
        'detector_debug_save',
        'detector_filter',
        'detector_resize_method',
        'detector_save_path',
        'detector_threads',
        'disabled',
        'enable_playlist',
        'enable_queue',
        'enable_resume',
        'mark_watched',
        'next_season',
        'played_limit',
        'popup_accent_colour',
        'popup_durations',
        'popup_position',
        'show_stop_button',
        'simple_mode',
        'skin_popup',
        'start_delay',
        'start_trigger',
        'unwatched_only',
    )

    def __init__(self):
        self.update()

    def __getitem__(self, name):
        return getattr(self, name, None)

    def __setitem__(self, name, value):
        return setattr(self, name, value)

    def __delitem__(self, name):
        return delattr(self, name)

    def __contains__(self, item):
        return hasattr(self, item)

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name='Settings', level=level)

    def update(self):
        self.log('Loading...')
        utils.ADDON = utils.get_addon(constants.ADDON_ID)
        utils.LOG_ENABLE_SETTING = utils.get_setting_int('logLevel')
        utils.DEBUG_LOG_ENABLE = utils.get_global_setting('debug.showloginfo')

        self.simple_mode = utils.get_setting_bool('simpleMode')
        self.show_stop_button = utils.get_setting_bool('stopAfterClose')
        self.skin_popup = utils.get_setting_bool('enablePopupSkin')
        self.popup_position = constants.POPUP_POSITIONS.get(
            utils.get_setting_int('popupPosition', default=0)
        )

        accent_colour = constants.POPUP_ACCENT_COLOURS.get(
            utils.get_setting_int('popupAccentColour', default=0)
        )
        if not accent_colour:
            accent_colour = hex(
                (utils.get_setting_int('popupCustomAccentColourA') << 24)
                + (utils.get_setting_int('popupCustomAccentColourR') << 16)
                + (utils.get_setting_int('popupCustomAccentColourG') << 8)
                + utils.get_setting_int('popupCustomAccentColourB')
            )[2:]
        self.popup_accent_colour = accent_colour

        self.auto_play = utils.get_setting_int('autoPlayMode') == 1
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
            3600: utils.get_setting_int('autoPlayTimeXL'),  # > 60 minutes
            2400: utils.get_setting_int('autoPlayTimeL'),   # > 40 minutes
            1200: utils.get_setting_int('autoPlayTimeM'),   # > 20 minutes
            600: utils.get_setting_int('autoPlayTimeS'),    # > 10 minutes
            0: utils.get_setting_int('autoPlayTimeXS')      # < 10 minutes
        } if utils.get_setting_bool('customAutoPlayTime') else {
            0: utils.get_setting_int('autoPlaySeasonTime')
        }

        self.detect_enabled = utils.get_setting_bool('detectPlayTime')
        self.detect_period = utils.get_setting_int('detectPeriod')

        self.start_delay = utils.get_setting_int('startDelay')
        self.disabled = utils.get_setting_bool('disableNextUp')
        self.api_retry_attempts = utils.get_setting_int('apiRetryAttempts')
        self.enable_queue = utils.get_setting_bool('enableQueue')

        # Create valid directory here so that it can be used whenever settings
        # are changed rather than only when a module is imported i.e. on addon
        # start/restart
        self.detector_save_path = file_utils.make_legal_path(
            utils.get_setting('detectorSavePath')
        )
        self.detector_threads = utils.get_setting_int('detectorThreads')
        data_limit = utils.get_setting_int('detectorDataLimit')
        self.detector_data_limit = data_limit - data_limit % 8
        self.detector_filter = utils.get_setting_bool('detectorFilter')
        self.detector_resize_method = constants.PIL_RESIZE_METHODS.get(
            utils.get_setting_int('detectorResizeMethod', default=1)
        )
        self.detect_level = utils.get_setting_int('detectLevel')
        self.detect_significance = utils.get_setting_int('detectSignificance')
        self.detect_matches = utils.get_setting_int('detectMatches')
        self.detect_mismatches = utils.get_setting_int('detectMismatches')

        self.demo_mode = utils.get_setting_bool('enableDemoMode')
        self.demo_seek = self.demo_mode and utils.get_setting_int('demoSeek')
        self.demo_cue = self.demo_mode and utils.get_setting_int('demoCue')
        self.demo_plugin = (
            self.demo_mode and utils.get_setting_bool('demoPlugin')
        )

        self.detector_debug = utils.get_setting_bool('detectorDebug')
        self.detector_debug_save = (
            self.detector_save_path
            and utils.get_setting_bool('detectorDebugSave')
        )
        self.start_trigger = utils.get_setting_bool('startTrigger')


SETTINGS = UpNextSettings()
