# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import xbmc
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

    __slots__ = ('state',)

    def __init__(self):
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
        self.log('Init', 2)

    # __enter__ and __exit__ allow UpNextPlayer to be used as a contextmanager
    # to check whether video is actually playing when getting video details
    def __enter__(self):
        return True

    def __exit__(self, exc_type, exc_value, traceback):
        return exc_type == RuntimeError

    @classmethod
    def log(cls, msg, level=2):
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
        if self.state.playing and not self.state.actual('playing'):
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
        if self.state.playing and not self.state.actual('playing'):
            actual = self.state.playing_file
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = getattr(xbmc.Player, 'getPlayingFile')(self)
        actual = statichelper.to_unicode(actual)
        self.state.playing_file = actual
        # Return actual value or forced value if forced
        return self.state.playing_file

    def get_speed(self):  # pylint: disable=too-many-branches
        # There must be a better way to do this...
        if xbmc.getCondVisibility('Player.Playing'):
            self.state.speed = float(xbmc.getInfoLabel('Player.PlaySpeed'))
        elif xbmc.getCondVisibility('Player.Forwarding'):
            if xbmc.getCondVisibility('Player.Forwarding2x'):
                self.state.speed = 2
            elif xbmc.getCondVisibility('Player.Forwarding4x'):
                self.state.speed = 4
            elif xbmc.getCondVisibility('Player.Forwarding8x'):
                self.state.speed = 8
            elif xbmc.getCondVisibility('Player.Forwarding16x'):
                self.state.speed = 16
            elif xbmc.getCondVisibility('Player.Forwarding32x'):
                self.state.speed = 32
        elif xbmc.getCondVisibility('Player.Rewinding'):
            if xbmc.getCondVisibility('Player.Rewinding2x'):
                self.state.speed = -2
            elif xbmc.getCondVisibility('Player.Rewinding4x'):
                self.state.speed = -4
            elif xbmc.getCondVisibility('Player.Rewinding8x'):
                self.state.speed = -8
            elif xbmc.getCondVisibility('Player.Rewinding16x'):
                self.state.speed = -16
            elif xbmc.getCondVisibility('Player.Rewinding32x'):
                self.state.speed = -32
        else:
            self.state.speed = 0
        return self.state.speed

    def getTime(self, use_infolabel=False):  # pylint: disable=invalid-name, arguments-differ
        # Use current stored value if playing forced
        if self.state.playing and not self.state.actual('playing'):
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

            # Don't update if paused
            if self.is_paused():
                delta = 0
            # Change in time from previously forced time to now
            elif isinstance(self.state.forced('time'), datetime.datetime):
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
        if self.state.playing and not self.state.actual('playing'):
            actual = self.state.total_time
        # Use inbuilt method to store actual value if playing not forced
        else:
            actual = getattr(xbmc.Player, 'getTotalTime')(self)
        self.state.total_time = actual
        # Return actual value or forced value if forced
        return self.state.total_time

    def playnext(self):
        # Simulate playing next file if forced
        if self.state.forced('playnext'):
            next_file = self.state.next_file
            self.state.set('next_file', None, force=True)
            self.state.set('playing_file', next_file, force=True)
            self.state.set('playing', bool(next_file), force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'playnext')(self)

    def stop(self):
        # Set fake value if forced
        if self.state.forced('stop'):
            self.state.set('playing', False, force=True)
        # Use inbuilt method if not forced
        else:
            getattr(xbmc.Player, 'stop')(self)
