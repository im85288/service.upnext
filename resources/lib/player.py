# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import Player
from utils import log as ulog


class UpNextPlayer(Player):
    """Service class for playback monitoring"""

    def __init__(self):
        # Used to override player state for testing
        self.__player_state = dict(
            override=False,
            external_player=False,
            playing=False,
            playing_file='',
            time=0,
            total_time=0,
            next_file=''
        )
        Player.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def isExternalPlayer(self):  # pylint: disable=invalid-name
        if not self.__player_state.get('override'):
            actual = getattr(Player, 'isExternalPlayer')(self)
            self.__player_state['external_player'] = actual
        return self.__player_state.get('external_player')

    def isPlaying(self):  # pylint: disable=invalid-name
        if not self.__player_state.get('override'):
            actual = getattr(Player, 'isPlaying')(self)
            self.__player_state['playing'] = actual
        return self.__player_state.get('playing')

    def getPlayingFile(self):  # pylint: disable=invalid-name
        if not self.__player_state.get('override'):
            actual = getattr(Player, 'getPlayingFile')(self)
            self.__player_state['playing_file'] = actual
        return self.__player_state.get('playing_file')

    def getTime(self):  # pylint: disable=invalid-name
        if not self.__player_state.get('override'):
            actual = getattr(Player, 'getTime')(self)
            self.__player_state['time'] = actual
        return self.__player_state.get('time')

    def getTotalTime(self):  # pylint: disable=invalid-name
        if not self.__player_state.get('override'):
            actual = getattr(Player, 'getTotalTime')(self)
            self.__player_state['total_time'] = actual
        return self.__player_state.get('total_time')

    def playnext(self):
        if self.__player_state.get('override'):
            next_file = self.__player_state.get('next_file')
            self.__player_state['playing_file'] = next_file
            self.__player_state['next_file'] = ''
            self.__player_state['playing'] = bool(next_file)
            return None
        return getattr(Player, 'playnext')(self)

    def stop(self):
        if self.__player_state.get('override'):
            self.__player_state['playing'] = False
            return None
        return getattr(Player, 'stop')(self)
