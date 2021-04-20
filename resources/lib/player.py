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
        return self[name].get('force')

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


class UpNextPlayer(xbmc.Player):
    """Inbuilt player function overrides"""

    def __init__(self):
        self.log('Init')

        # Used to override player state for testing
        self.state = UpNextPlayerState()
        self.state.external_player = False
        self.state.playing = False
        self.state.paused = False
        self.state.playing_file = None
        self.state.speed = 0
        self.state.time = 0
        self.state.total_time = 0
        self.state.next_file = None
        self.state.media_type = None
        self.state.playnext = None
        self.state.stop = None

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
        self.state.external_player = actual
        # Return actual value or forced value if forced
        return self.state.external_player

    def isPlaying(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'isPlaying')(self)
        self.state.playing = actual
        # Return actual value or forced value if forced
        return self.state.playing

    def is_paused(self):
        # Use inbuilt method to store actual value
        actual = xbmc.getCondVisibility('Player.Paused')
        self.state.paused = actual
        # Return actual value or forced value if forced
        return self.state.paused

    def get_media_type(self):
        # Use current stored value if playing forced
        if self.state.forced('playing') or self.state.forced('media_type'):
            actual = self.state.media_type
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = self.getVideoInfoTag().getMediaType()
            actual = actual if actual else 'unknowntype'
        actual = statichelper.to_unicode(actual)
        self.state.media_type = actual
        # Return actual value or forced value if forced
        return self.state.media_type

    def getPlayingFile(self):  # pylint: disable=invalid-name
        # Use current stored value if playing forced
        if self.state.forced('playing') or self.state.forced('playing_file'):
            actual = self.state.playing_file
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = getattr(xbmc.Player, 'getPlayingFile')(self)
        actual = statichelper.to_unicode(actual)
        self.state.playing_file = actual
        # Return actual value or forced value if forced
        return self.state.playing_file

    def get_speed(self):
        # Use current stored value if playing forced
        if self.state.forced('playing') or self.state.forced('speed'):
            actual = self.state.speed
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = api.get_player_speed()
        self.state.speed = actual
        # Return actual value or forced value if forced
        return self.state.speed

    def getTime(self, use_infolabel=False):  # pylint: disable=invalid-name, arguments-differ
        # Use current stored value if playing forced
        if self.state.forced('playing') or self.state.forced('time'):
            actual = self.state.time
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = (
                utils.time_to_seconds(xbmc.getInfoLabel('VideoPlayer.Time'))
                if use_infolabel
                else getattr(xbmc.Player, 'getTime')(self)
            )
        self.state.time = actual

        # Simulate time progression if forced
        if self.state.forced('time'):
            now = datetime.datetime.now()

            # Change in time from previously forced time to now
            if isinstance(self.state.forced('time'), datetime.datetime):
                delta = (self.state.forced('time') - now).total_seconds()
                # No need to check actual speed, just use forced speed value
                delta = delta * self.state.speed
            # Don't update if not previously forced
            else:
                delta = 0

            # Set new forced time
            new_time = self.state.time - delta
            self.state.set('time', new_time, force=now)

        # Return actual value or forced value if forced
        return self.state.time

    def getTotalTime(self):  # pylint: disable=invalid-name
        # Use current stored value if playing forced
        if self.state.forced('playing') or self.state.forced('total_time'):
            actual = self.state.total_time
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = getattr(xbmc.Player, 'getTotalTime')(self)
        self.state.total_time = actual
        # Return actual value or forced value if forced
        return self.state.total_time

    def playnext(self):
        # Simulate playing next file if forced
        if (self.state.forced('playing')
                or self.state.forced('playnext')
                or self.state.forced('next_file')):
            next_file = self.state.next_file
            self.state.set('next_file', None, force=True)
            self.state.set('playing_file', next_file, force=True)
            self.state.set('playing', bool(next_file), force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'playnext')(self)

    def seekTime(self, seekTime):  # pylint: disable=invalid-name
        # Set fake value if playing forced
        if self.state.forced('playing') or self.state.forced('time'):
            self.state.set('time', seekTime, force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'seekTime')(self, seekTime)

    def stop(self):
        # Set fake value if playing forced
        if self.state.forced('playing') or self.state.forced('stop'):
            self.state.set('playing', False, force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'stop')(self)
