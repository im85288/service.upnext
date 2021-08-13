# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import xbmc
import api
import statichelper
import utils


class UpNextPlayerState(dict):
    def __getattr__(self, name):
        try:
            return self[name]['value']
        except KeyError as error:
            raise AttributeError(error)  # pylint: disable=raise-missing-from

    def __setattr__(self, name, value):
        self.set(name, value)

    def forced(self, name):
        # If playing is forced all other player properties are also considered
        # to be forced
        forced = self.get(name, {}).get('force')
        if forced or name == 'playing':
            return forced
        return self.get('playing', {}).get('force')

    def actual(self, name):
        return self[name].get('actual')

    def set(self, name, *args, **kwargs):
        if name not in self:
            self[name] = {
                'value': None,
                'force': False,
                'actual': None
            }

        has_force = 'force' in kwargs
        has_value = bool(args)

        if has_force and has_value:
            self[name]['value'] = args[0]
            self[name]['force'] = kwargs['force']

        elif has_force and not has_value:
            self[name]['value'] = self[name].get('actual')
            self[name]['force'] = kwargs['force']

        elif self.forced(name) and not has_force and has_value:
            self[name]['actual'] = args[0]

        elif has_value:
            self[name]['value'] = args[0]
            self[name]['actual'] = args[0]


class UpNextPlayer(xbmc.Player, object):  # pylint: disable=useless-object-inheritance
    """Inbuilt player function overrides"""

    __slots__ = (
        'player_state',
    )

    def __init__(self):
        self.log('Init')

        # Used to override player state for testing
        self.player_state = UpNextPlayerState()
        self.player_state.external_player = False
        self.player_state.playing = False
        self.player_state.paused = False
        self.player_state.playing_file = None
        self.player_state.speed = 0
        self.player_state.time = 0
        self.player_state.total_time = 0
        self.player_state.next_file = None
        self.player_state.media_type = None
        self.player_state.playnext = None
        self.player_state.stop = None

        xbmc.Player.__init__(self)

    # __enter__ and __exit__ allow UpNextPlayer to be used as a contextmanager
    # to check whether video is actually playing when getting video details
    def __enter__(self):
        return True

    def __exit__(self, exc_type, exc_value, traceback):
        return exc_type == RuntimeError

    @classmethod
    def log(cls, msg, level=utils.LOGDEBUG):
        utils.log(msg, name=cls.__name__, level=level)

    def isExternalPlayer(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = (
            getattr(xbmc.Player, 'isExternalPlayer')(self)
            if utils.supports_python_api(18)
            else False
        )
        self.player_state.external_player = actual
        # Return actual value or forced value if forced
        return self.player_state.external_player

    def isPlaying(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'isPlaying')(self)
        self.player_state.playing = actual
        # Return actual value or forced value if forced
        return self.player_state.playing

    def is_paused(self):
        # Use inbuilt method to store actual value
        actual = xbmc.getCondVisibility('Player.Paused')
        self.player_state.paused = actual
        # Return actual value or forced value if forced
        return self.player_state.paused

    def get_media_type(self):
        # Use current stored value if playing forced
        if self.player_state.forced('media_type'):
            actual = self.player_state.media_type
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = self.getVideoInfoTag().getMediaType()
            actual = actual if actual else 'unknowntype'
        actual = statichelper.to_unicode(actual)
        self.player_state.media_type = actual
        # Return actual value or forced value if forced
        return self.player_state.media_type

    def getPlayingFile(self):  # pylint: disable=invalid-name
        # Use current stored value if playing forced
        if self.player_state.forced('playing_file'):
            actual = self.player_state.playing_file
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = getattr(xbmc.Player, 'getPlayingFile')(self)
        actual = statichelper.to_unicode(actual)
        self.player_state.playing_file = actual
        # Return actual value or forced value if forced
        return self.player_state.playing_file

    def get_speed(self):
        # Use current stored value if playing forced
        if self.player_state.forced('speed'):
            actual = self.player_state.speed
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = api.get_player_speed()
        self.player_state.speed = actual
        # Return actual value or forced value if forced
        return self.player_state.speed

    def getTime(self, use_infolabel=False):  # pylint: disable=invalid-name, arguments-differ
        # Use current stored value if playing forced
        if self.player_state.forced('time'):
            actual = self.player_state.time
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = (
                utils.time_to_seconds(xbmc.getInfoLabel('Player.Time'))
                if use_infolabel
                else getattr(xbmc.Player, 'getTime')(self)
            )
        self.player_state.time = actual

        # Simulate time progression if forced
        if self.player_state.forced('time'):
            now = datetime.datetime.now()

            # Change in time from previously forced time to now
            if isinstance(self.player_state.forced('time'), datetime.datetime):
                delta = self.player_state.forced('time') - now
                # No need to check actual speed, just use forced speed value
                delta = delta.total_seconds() * self.player_state.speed
            # Don't update if not previously forced
            else:
                delta = 0

            # Set new forced time
            new_time = self.player_state.time - delta
            self.player_state.set('time', new_time, force=now)

        # Return actual value or forced value if forced
        return self.player_state.time

    def getTotalTime(self, use_infolabel=False):  # pylint: disable=invalid-name, arguments-differ
        # Use current stored value if playing forced
        if self.player_state.forced('total_time'):
            actual = self.player_state.total_time
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = (
                utils.time_to_seconds(xbmc.getInfoLabel('Player.Duration'))
                if use_infolabel
                else getattr(xbmc.Player, 'getTotalTime')(self)
            )
        self.player_state.total_time = actual
        # Return actual value or forced value if forced
        return self.player_state.total_time

    def playnext(self):
        # Simulate playing next file if forced
        if (self.player_state.forced('playnext')
                or self.player_state.forced('next_file')):
            next_file = self.player_state.next_file
            self.player_state.set('next_file', None, force=True)
            self.player_state.set('playing_file', next_file, force=True)
            self.player_state.set('playing', bool(next_file), force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'playnext')(self)

    def seekTime(self, seekTime):  # pylint: disable=invalid-name
        # Set fake value if playing forced
        if self.player_state.forced('time'):
            self.player_state.set('time', seekTime, force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'seekTime')(self, seekTime)

    def stop(self):
        # Set fake value if playing forced
        if self.player_state.forced('stop'):
            self.player_state.set('playing', False, force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'stop')(self)
