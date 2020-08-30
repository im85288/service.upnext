# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from datetime import datetime
from xbmc import Player
from utils import log as ulog


class UpNextPlayer(Player):
    """Service class for playback monitoring"""

    def __init__(self):
        # Used to override player state for testing
        self.player_state = dict(
            force=False,
            external_player={'value': False, 'force': False},
            playing={'value': False, 'force': False},
            paused={'value': False, 'force': False},
            playing_file={'value': '', 'force': False},
            time={'value': 0, 'force': False},
            total_time={'value': 0, 'force': False},
            next_file={'value': '', 'force': False},
            playnext={'force': False},
            stop={'force': False}
        )
        Player.__init__(self)
        self.log('Init', 2)

    @classmethod
    def log(cls, msg, level=2):
        ulog(msg, name=cls.__name__, level=level)

    def isExternalPlayer(self):  # pylint: disable=invalid-name
        if not (
            self.player_state['force']
            or self.player_state['external_player']['force']
        ):
            actual = getattr(Player, 'isExternalPlayer')(self)
            self.player_state['external_player']['value'] = actual
        return self.player_state['external_player']['value']

    def isPlaying(self):  # pylint: disable=invalid-name
        if not (
            self.player_state['force']
            or self.player_state['playing']['force']
        ):
            actual = getattr(Player, 'isPlaying')(self)
            self.player_state['playing']['value'] = actual
        return self.player_state['playing']['value']

    def getPlayingFile(self):  # pylint: disable=invalid-name
        if not (
            self.player_state['force']
            or self.player_state['playing_file']['force']
        ):
            actual = getattr(Player, 'getPlayingFile')(self)
            self.player_state['playing_file']['value'] = actual
        return self.player_state['playing_file']['value']

    def getTime(self):  # pylint: disable=invalid-name
        if not (
            self.player_state['force']
            or self.player_state['time']['force']
        ):
            actual = getattr(Player, 'getTime')(self)
            self.player_state['time']['value'] = actual
        elif self.player_state['paused']['value']:
            self.player_state['time']['force'] = datetime.now()
        elif isinstance(self.player_state['time']['force'], datetime):
            now = datetime.now()
            delta = self.player_state['time']['force'] - now
            return self.player_state['time']['value'] - delta.total_seconds()
        else:
            self.player_state['time']['force'] = datetime.now()

        return self.player_state['time']['value']

    def getTotalTime(self):  # pylint: disable=invalid-name
        if not (
            self.player_state['force']
            or self.player_state['total_time']['force']
        ):
            actual = getattr(Player, 'getTotalTime')(self)
            self.player_state['total_time']['value'] = actual
        return self.player_state['total_time']['value']

    def playnext(self):
        if (
            self.player_state['force']
            or self.player_state['playnext']['force']
        ):
            next_file = self.player_state['next_file']['value']
            self.player_state['playing_file']['value'] = next_file
            self.player_state['next_file']['value'] = ''
            self.player_state['playing']['value'] = bool(next_file)
            return None
        return getattr(Player, 'playnext')(self)

    def stop(self):
        if (
            self.player_state['force']
            or self.player_state['stop']['force']
        ):
            self.player_state['playing']['value'] = False
            return None
        return getattr(Player, 'stop')(self)
