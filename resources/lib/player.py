# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import json
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

    def set(self, name, *args, **kwargs):
        if name not in self:
            self[name] = dict(
                value=None,
                force=False,
                actual=None
            )

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
        self.state.playnext = None
        self.state.stop = None

        xbmc.Player.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def isExternalPlayer(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'isExternalPlayer')(self)
        self.state.external_player = actual
        # Return actual value or forced value if forced
        return self.state.external_player

    def isPlaying(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'isPlaying')(self)
        self.state.playing = actual
        # Return actual value or forced value if forced
        return self.state.playing

    def isPaused(self):  # pylint: disable=invalid-name
        return self.state.paused

    def getPlayingFile(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'getPlayingFile')(self)
        actual = statichelper.to_unicode(actual)
        self.state.playing_file = actual
        # Return actual value or forced value if forced
        return self.state.playing_file

    def getSpeed(self, data=None):  # pylint: disable=invalid-name
        if data:
            data = json.loads(data)
            self.state.speed = data['player']['speed']
            self.state.paused = not bool(self.state.speed)
        return self.state.speed

    def getTime(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
        actual = getattr(xbmc.Player, 'getTime')(self)
        self.state.time = actual

        # Simulate time progression if forced
        if self.state.forced('time'):
            now = datetime.datetime.now()

            # Don't update if paused
            if self.isPaused():
                delta = 0
            # Change in time from previously forced time to now
            elif isinstance(self.state.forced('time'), datetime.datetime):
                delta = (self.state.forced('time') - now).total_seconds()
            # Don't update if not previously forced
            else:
                delta = 0

            # Set new forced time
            new_time = self.state.time - delta
            self.state.set('time', new_time, force=now)

        # Return actual value or forced value if forced
        return self.state.time

    def getTotalTime(self):  # pylint: disable=invalid-name
        # Use inbuilt method to store actual value
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
