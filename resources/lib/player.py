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
        self.state = dict(
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
        if not self.state['external_player']['force']:
            actual = getattr(Player, 'isExternalPlayer')(self)
            self.state['external_player']['value'] = actual
        return self.state['external_player']['value']

    def isPlaying(self):  # pylint: disable=invalid-name
        if not self.state['playing']['force']:
            actual = getattr(Player, 'isPlaying')(self)
            self.state['playing']['value'] = actual
        return self.state['playing']['value']

    def getPlayingFile(self):  # pylint: disable=invalid-name
        if not self.state['playing_file']['force']:
            actual = getattr(Player, 'getPlayingFile')(self)
            self.state['playing_file']['value'] = actual
        return self.state['playing_file']['value']

    def getTime(self):  # pylint: disable=invalid-name
        if not self.state['time']['force']:
            actual = getattr(Player, 'getTime')(self)
            self.state['time']['value'] = actual
        elif self.state['paused']['value']:
            self.state['time']['force'] = datetime.now()
        elif isinstance(self.state['time']['force'], datetime):
            now = datetime.now()
            delta = self.state['time']['force'] - now
            self.state['time']['force'] = now
            self.state['time']['value'] -= delta.total_seconds()
        else:
            self.state['time']['force'] = datetime.now()
        return self.state['time']['value']

    def getTotalTime(self):  # pylint: disable=invalid-name
        if not self.state['total_time']['force']:
            actual = getattr(Player, 'getTotalTime')(self)
            self.state['total_time']['value'] = actual
        return self.state['total_time']['value']

    def playnext(self):
        if self.state['playnext']['force']:
            next_file = self.state['next_file']['value']
            self.state['playing_file']['value'] = next_file
            self.state['next_file']['value'] = ''
            self.state['playing']['value'] = bool(next_file)
        else:
            getattr(Player, 'playnext')(self)

    def stop(self):
        if self.state['stop']['force']:
            self.state['playing']['value'] = False
        else:
            getattr(Player, 'stop')(self)
