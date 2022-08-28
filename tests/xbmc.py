# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
''' This file implements the Kodi xbmc module, either using stubs or alternative functionality '''

# pylint: disable=invalid-name,no-self-use

from __future__ import absolute_import, division, print_function, unicode_literals
import os
import json
import random
import sys
import threading
import time
from datetime import datetime
from weakref import WeakValueDictionary
from xbmcextra import global_settings, import_language, __KODI_MATRIX__
from dummydata import LIBRARY
from statichelper import to_unicode


if __KODI_MATRIX__:
    LOGDEBUG = 0
    LOGINFO = 1
    LOGWARNING = 2
    LOGERROR = 3
    LOGFATAL = 4
    LOGNONE = 5
    _LOG_LEVELS = {
        LOGDEBUG: 'DEBUG',
        LOGINFO: 'INFO',
        LOGWARNING: 'WARNING',
        LOGERROR: 'ERROR',
        LOGFATAL: 'FATAL',
        LOGNONE: 'NONE'
    }
else:
    LOGDEBUG = 0
    LOGINFO = 1
    LOGNOTICE = 2
    LOGWARNING = 3
    LOGERROR = 4
    LOGSEVERE = 5
    LOGFATAL = 6
    LOGNONE = 7
    _LOG_LEVELS = {
        LOGDEBUG: 'DEBUG',
        LOGINFO: 'INFO',
        LOGNOTICE: 'NOTICE',
        LOGWARNING: 'WARNING',
        LOGERROR: 'ERROR',
        LOGSEVERE: 'SEVERE',
        LOGFATAL: 'FATAL',
        LOGNONE: 'NONE'
    }

PLAYLIST_MUSIC = 0
PLAYLIST_VIDEO = 1
_PLAYLIST_TYPE = random.randint(PLAYLIST_MUSIC, PLAYLIST_VIDEO)
_PLAYER_TYPES = [
    [dict(type='audio', playerid=PLAYLIST_MUSIC)],
    [dict(type='video', playerid=PLAYLIST_VIDEO)],
]
_PLAYLIST = {
    PLAYLIST_MUSIC: dict(position=0, playlist=[dict(file='dummy')]),
    PLAYLIST_VIDEO: dict(position=0, playlist=[dict(file='dummy')]),
}

_INFO_LABELS = {
    'System.BuildVersion': '18.9' if __KODI_MATRIX__ else '19.0',
    'Player.Process(VideoWidth)': '1,920',
    'Player.Process(VideoHeight)': '1,080',
    'Player.Process(VideoDAR)': '1.78'
}

_REGIONS = {
    'datelong': '%A, %d %B %Y',
    'dateshort': '%Y-%m-%d',
    'time': '%I:%M %p'
}

_GLOBAL_SETTINGS = global_settings()
_PO = import_language(language=_GLOBAL_SETTINGS.get('locale.language'))


class Keyboard(object):
    ''' A stub implementation of the xbmc Keyboard class '''

    def __init__(self, line='', heading=''):
        ''' A stub constructor for the xbmc Keyboard class '''

    def doModal(self, autoclose=0):
        ''' A stub implementation for the xbmc Keyboard class doModal() method '''

    def isConfirmed(self):
        ''' A stub implementation for the xbmc Keyboard class isConfirmed() method '''
        return True

    def getText(self):
        ''' A stub implementation for the xbmc Keyboard class getText() method '''
        return 'test'


class Monitor(object):
    ''' A stub implementation of the xbmc Monitor class '''

    __slots__ = ('__weakref__', )

    _instances = WeakValueDictionary()
    _aborted = threading.Event()

    def __new__(cls):
        ''' A stub constructor for the xbmc Monitor class '''

        self = super(Monitor, cls).__new__(cls)

        if not cls._instances:
            abort_timer = threading.Thread(target=self._timer)  # pylint: disable=protected-access
            abort_timer.daemon = True
            abort_timer.start()

        key = id(self)
        cls._instances[key] = self
        return self

    def __del__(self):
        key = id(self)
        if key in Monitor._instances:
            del Monitor._instances[key]
        else:
            log('Monitor instance <{0}> already deleted'.format(key), LOGDEBUG)

    def _timer(self):
        abort_times = [90, 120]
        abort_time = abort_times[random.randint(0, len(abort_times) - 1)]
        log('Test exit in {0}s'.format(abort_time), LOGINFO)

        Monitor._aborted.wait(abort_time)
        Monitor._aborted.set()
        try:
            sys.exit()
        except SystemExit:
            pass

    def abortRequested(self):
        ''' A stub implementation for the xbmc Monitor class abortRequested() method '''
        return Monitor._aborted.is_set()

    def waitForAbort(self, timeout=None):
        ''' A stub implementation for the xbmc Monitor class waitForAbort() method '''
        try:
            Monitor._aborted.wait(timeout)
        except KeyboardInterrupt:
            Monitor._aborted.set()
            try:
                sys.exit()
            except SystemExit:
                pass
        except SystemExit:
            Monitor._aborted.set()

        return Monitor._aborted.is_set()


class Player(object):
    ''' A stub implementation of the xbmc Player class '''
    is_playing = False
    file = ''
    time = 0.0
    duration = 0

    def __init__(self):
        ''' A stub constructor for the xbmc Player class '''
        self._count = 0

    def play(self, item='', listitem=None, windowed=False, startpos=-1):  # pylint: disable=unused-argument
        ''' A stub implementation for the xbmc Player class play() method '''
        Player.file = item
        Player.is_playing = True
        Player.time = 0.0
        Player.duration = 0

    def playnext(self):
        ''' A stub implementation for the xbmc Player class playnext() method '''
        return

    def stop(self):
        ''' A stub implementation for the xbmc Player class stop() method '''
        Player.file = ''
        Player.is_playing = False
        Player.time = 0.0
        Player.duration = 0

    def isExternalPlayer(self):
        ''' A stub implementation for the xbmc Player class isExternalPlayer() method '''
        return False

    def getPlayingFile(self):
        ''' A stub implementation for the xbmc Player class getPlayingFile() method '''
        if not Player.is_playing:
            raise Exception
        return Player.file

    def isPlaying(self):
        ''' A stub implementation for the xbmc Player class isPlaying() method '''
        # Return correct value four times out of five
        if random.randint(1, 5) == 5:
            return False
        return Player.is_playing

    def seekTime(self, seekTime):  # pylint: disable=unused-argument
        ''' A stub implementation for the xbmc Player class seekTime() method '''
        return

    def showSubtitles(self, bVisible):  # pylint: disable=unused-argument
        ''' A stub implementation for the xbmc Player class showSubtitles() method '''
        return

    def getTotalTime(self):
        ''' A stub implementation for the xbmc Player class getTotalTime() method '''
        if not Player.is_playing:
            raise Exception
        return Player.duration

    def getTime(self):
        ''' A stub implementation for the xbmc Player class getTime() method '''
        if not Player.is_playing:
            raise Exception
        return Player.time

    def getVideoInfoTag(self):
        ''' A stub implementation for the xbmc Player class getVideoInfoTag() method '''
        return InfoTagVideo()


class PlayList(object):
    ''' A stub implementation of the xbmc PlayList class '''

    def __init__(self, playList):
        ''' A stub constructor for the xbmc PlayList class '''
        self.playlist_type = playList

    def getposition(self):
        ''' A stub implementation for the xbmc PlayList class getposition() method '''
        return _PLAYLIST[self.playlist_type]['position']

    def size(self):
        ''' A stub implementation for the xbmc PlayList class size() method '''
        return len(_PLAYLIST[self.playlist_type]['playlist'])


class InfoTagVideo(object):
    ''' A stub implementation of the xbmc InfoTagVideo class '''

    def __init__(self, tags=None):
        ''' A stub constructor for the xbmc InfoTagVideo class '''
        self._tags = tags if tags else {}

    def getDbId(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getDbId() method '''
        return self._tags.get('dbid', -1)

    def getTitle(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getTitle() method '''
        return self._tags.get('title', '')

    def getSeason(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getSeason() method '''
        return self._tags.get('season', -1)

    def getEpisode(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getEpisode() method '''
        return self._tags.get('episode', -1)

    def getTVShowTitle(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getTVShowTitle() method '''
        return self._tags.get('tvshowtitle', '')

    def getFirstAired(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getFirstAired() method '''
        return self._tags.get('aired', '')

    def getPremiered(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getPremiered() method '''
        return self._tags.get('premiered', '')

    def getYear(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getYear() method '''
        return self._tags.get('year', 1900)

    def getDuration(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getDuration() method '''
        return self._tags.get('duration', 0)

    def getPlotOutline(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getPlotOutline() method '''
        return self._tags.get('plotoutline', '')

    def getPlot(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getPlot() method '''
        return self._tags.get('plot', '')

    def getUserRating(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getUserRating() method '''
        return self._tags.get('userrating', 0)

    def getPlayCount(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getPlayCount() method '''
        return self._tags.get('playcount', 0)

    def getRating(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getRating() method '''
        return self._tags.get('rating', 0.0)

    def getMediaType(self):
        ''' A stub implementation for the xbmc InfoTagVideo class getMediaType() method '''
        return self._tags.get('mediatype', '')


class RenderCapture(object):
    ''' A stub implementation of the xbmc RenderCapture class '''

    def __init__(self):
        ''' A stub constructor for the xbmc RenderCapture class '''
        self._width = 0
        self._height = 0

    def capture(self, width, height):
        ''' A stub implementation for the xbmc RenderCapture class capture() method '''
        self._width = width
        self._height = height

    def getImage(self, msecs=None):  # pylint: disable=unused-argument
        ''' A stub implementation for the xbmc RenderCapture class getImage() method '''
        return bytearray((
            random.getrandbits(8) if i % 4 != 3 else 255
            for i in range(self._width * self._height * 4)
        ))


def executebuiltin(string, wait=False):  # pylint: disable=unused-argument
    ''' A stub implementation of the xbmc executebuiltin() function '''
    return


def _filter_walker(filter_object, seeking):
    for level in filter_object:
        if isinstance(filter_object, dict) and filter_object[level] == seeking:
            return filter_object
        if isinstance(level, dict):
            found = _filter_walker(level, seeking)
            if found:
                return found
        elif isinstance(filter_object[level], (dict, list)):
            found = _filter_walker(filter_object[level], seeking)
            if found:
                return found
    return None


def _application_getproperties(params):
    if params.get('properties') == ['version']:
        return json.dumps(dict(
            id=1,
            jsonrpc='2.0',
            result=dict(version=dict(major=(19 if __KODI_MATRIX__ else 18)))
        ))
    return False


def _settings_getsettingvalue(params):
    key = params.get('setting')
    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(value=_GLOBAL_SETTINGS.get(key))
    ))


def _player_getactiveplayers(params):  # pylint: disable=unused-argument
    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=_PLAYER_TYPES[_PLAYLIST_TYPE]
    ))


def _player_getproperties(params):
    if params.get('properties') == ['speed']:
        return json.dumps(dict(
            id=1,
            jsonrpc='2.0',
            result=dict(speed=random.randint(0, 1))
        ))
    if params.get('properties') == ['playlistid']:
        return json.dumps(dict(
            id=1,
            jsonrpc='2.0',
            result=dict(playlistid=_PLAYLIST_TYPE)
        ))
    return False


def _player_getitem(params):  # pylint: disable=unused-argument
    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(item=LIBRARY['episodes'][0])
    ))


def _videolibrary_gettvshows(params):
    tvshow_filter = params.get('filter')
    if not tvshow_filter:
        return False

    filter_field = tvshow_filter.get('field')
    filter_operator = tvshow_filter.get('operator')
    filter_value = tvshow_filter.get('value')
    if filter_field != 'title' or filter_operator != 'is':
        return False

    tvshowid = LIBRARY['tvshows'].get(filter_value, {}).get('tvshowid')

    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(tvshows=[dict(tvshowid=tvshowid)])
    ))


def _videolibrary_getepisodes(params):
    episode_filter = params.get('filter', {})
    tvshowid = params.get('tvshowid')
    if tvshowid is None or not episode_filter:
        return False

    season = _filter_walker(episode_filter, 'season')
    episode_number = _filter_walker(episode_filter, 'episode')
    if not season or not episode_number:
        return False

    episodes = [
        episode for episode in LIBRARY['episodes']
        if episode['tvshowid'] == tvshowid
        and episode['season'] == int(season.get('value'))
        and episode['episode'] >= int(episode_number.get('value'))
    ]
    if episode_number.get('operator') == 'greaterthan':
        episodes = episodes[1:]

    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(episodes=episodes)
    ))


def _videolibrary_getepisodedetails(params):
    episodeid = params.get('episodeid')
    if episodeid is None:
        return False

    episodes = [
        episode for episode in LIBRARY['episodes']
        if episode['episodeid'] == episodeid
    ]

    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(episodedetails=episodes[0] if episodes else {})
    ))


def _videolibrary_gettvshowdetails(params):
    tvshowid = params.get('tvshowid')
    if tvshowid is None:
        return False

    tvshows = [
        details for _, details in LIBRARY['tvshows'].items()
        if details['tvshowid'] == tvshowid
    ]

    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        result=dict(tvshowdetails=tvshows[0] if tvshows else {})
    ))


def _jsonrpc_notifyall(params):
    for ref in Monitor._instances.valuerefs():  # pylint: disable=protected-access
        notification_handler = getattr(ref(), 'onNotification', None)
        if callable(notification_handler):
            message = params.get('message')
            if not message:
                return False

            announcers = [
                name for name, details in _JSONRPC_announcer_map.items()
                if message in details.get('messages')
            ]
            announcer = announcers[0] if announcers else 'Other'

            thread = threading.Thread(target=notification_handler, args=(
                params.get('sender'),
                '{0}.{1}'.format(announcer, message),
                json.dumps(params.get('data'))
            ))
            thread.daemon = True
            thread.start()

    return True


def _player_open(params):
    item = params['item']
    item_file = None
    if 'playlistid' in item:
        _PLAYLIST[item['playlistid']]['position'] = item['position']
        item = _PLAYLIST[item['playlistid']]['playlist'][item['position']]

    if 'file' in item:
        itemid = -1
        item_file = item['file']
    elif 'episodeid' in item:
        itemid = item['episodeid']
        item_file = json.loads(_videolibrary_getepisodedetails({
            'episodeid': itemid
        }))['result']['episodedetails'].get('file')

    if item_file:
        player = Player()
        player.play(item_file)
        _jsonrpc_notifyall({
            'sender': 'xbmc',
            'message': 'OnPlay',
            'data': {
                'item': {
                    'id': itemid,
                    'title': '',
                    'type': 'episode',
                },
                'player': {
                    'playerid': _PLAYLIST_TYPE,
                    'speed': 1
                }
            }
        })
        _jsonrpc_notifyall({
            'sender': 'xbmc',
            'message': 'OnStop',
            'data': {
                'end': True,
                'item': {
                    'id': itemid,
                    'title': '',
                    'type': 'episode',
                }
            }
        })
        _jsonrpc_notifyall({
            'sender': 'xbmc',
            'message': 'OnAVStart',
            'data': {
                'item': {
                    'id': itemid,
                    'title': '',
                    'type': 'episode',
                },
                'player': {
                    'playerid': _PLAYLIST_TYPE,
                    'speed': 1
                }
            }
        })
    return True


def _playlist_add(params):
    _PLAYLIST[params['playlistid']]['playlist'] += [params['item']]
    return True


def _playlist_remove(params):
    playlistid = params['playlistid']
    position = params['position']
    playlist = _PLAYLIST[playlistid]['playlist']
    _PLAYLIST[playlistid]['playlist'] = (
        playlist[:position] + playlist[position + 1:]
    )
    return True


_JSONRPC_methods = {
    'Application.GetProperties': _application_getproperties,
    'Settings.GetSettingValue': _settings_getsettingvalue,
    'Player.GetActivePlayers': _player_getactiveplayers,
    'Player.GetProperties': _player_getproperties,
    'Player.GetItem': _player_getitem,
    'VideoLibrary.GetTVShows': _videolibrary_gettvshows,
    'VideoLibrary.GetEpisodes': _videolibrary_getepisodes,
    'VideoLibrary.GetEpisodeDetails': _videolibrary_getepisodedetails,
    'VideoLibrary.GetTVShowDetails': _videolibrary_gettvshowdetails,
    'JSONRPC.NotifyAll': _jsonrpc_notifyall,
    'Player.Open': _player_open,
    'Playlist.Add': _playlist_add,
    'Playlist.Remove': _playlist_remove
}

_JSONRPC_announcer_map = {
    'Player': {'flag': 0x001, 'messages': ['OnAVChange', 'OnAVStart', 'OnPause', 'OnPlay', 'OnResume', 'OnSeek', 'OnSpeedChanged', 'OnStop']},
    'Playlist': {'flag': 0x002, 'messages': []},
    'GUI': {'flag': 0x004, 'messages': []},
    'System': {'flag': 0x008, 'messages': []},
    'VideoLibrary': {'flag': 0x010, 'messages': []},
    'AudioLibrary': {'flag': 0x020, 'messages': []},
    'Application': {'flag': 0x040, 'messages': []},
    'Input': {'flag': 0x080, 'messages': []},
    'PVR': {'flag': 0x100, 'messages': []},
    'Other': {'flag': 0x200, 'messages': ['upnext_credits_detected', 'upnext_data', 'upnext_trigger']},
    'Info': {'flag': 0x400, 'messages': []}
}


def executeJSONRPC(jsonrpccommand):
    ''' A reimplementation of the xbmc executeJSONRPC() function '''
    command = json.loads(jsonrpccommand)
    method = _JSONRPC_methods.get(command.get('method')) if command else None
    params = command.get('params', {}) if command else {}

    return_val = method(params) if callable(method) else False
    if return_val is True:
        return json.dumps(dict(
            id=1,
            jsonrpc='2.0',
            result='OK'
        ))
    if return_val:
        return return_val

    log("executeJSONRPC does not implement method '{method}'".format(**command), LOGERROR)
    return json.dumps(dict(
        id=1,
        jsonrpc='2.0',
        error=dict(code=-1, message='Not implemented')
    ))


def getCondVisibility(string):
    ''' A reimplementation of the xbmc getCondVisibility() function '''
    if string == 'system.platform.android':
        return False
    return True


def getInfoLabel(key):
    ''' A reimplementation of the xbmc getInfoLabel() function '''
    return _INFO_LABELS.get(key, '')


def getLocalizedString(msgctxt):
    ''' A reimplementation of the xbmc getLocalizedString() function '''
    for entry in _PO:
        if entry.msgctxt == '#%s' % msgctxt:
            return entry.msgstr or entry.msgid
    if int(msgctxt) >= 30000:
        log('Unable to translate #{msgctxt}'.format(msgctxt=msgctxt), LOGERROR)
    return '<Untranslated>'


def getRegion(key):
    ''' A reimplementation of the xbmc getRegion() function '''
    return _REGIONS.get(key)


def log(msg, level=LOGDEBUG):
    ''' A reimplementation of the xbmc log() function '''

    now = datetime.now()
    thread_id = threading.current_thread().ident
    level_name = _LOG_LEVELS[level]
    component = 'general'
    level_colour = '\033[32;1m'  # green FG, bold
    msg_colour = '\033[37m'  # white FG
    reset_colour = '\033[39;0m'

    if LOGERROR <= level <= LOGFATAL:
        level_colour = '\033[31;1m'  # red FG, bold
    elif level == LOGWARNING:
        level_colour = '\033[33;1m'  # yellow FG, bold
    elif level == LOGDEBUG:
        level_colour = '\033[90;1m'  # grey FG, bold
        msg_colour = '\033[90m'  # grey FG

    print('{time} T:{thread_id}\t{level_colour}{level_name:>8} <{component}>: {msg_colour}{msg}{reset_colour}'.format(
        time=now,
        thread_id=thread_id,
        level_colour=level_colour,
        level_name=level_name,
        component=component,
        reset_colour=reset_colour,
        msg_colour=msg_colour,
        msg=to_unicode(msg)
    ))
    if level == LOGFATAL:
        raise Exception(msg)


def setContent(self, content):  # pylint: disable=unused-argument
    ''' A stub implementation of the xbmc setContent() function '''
    return


def sleep(seconds):
    ''' A reimplementation of the xbmc sleep() function '''
    time.sleep(seconds)


# translatePath and makeLegalFilename have been moved to xbmcvfs in Kodi 19+
# but currently still available in xbmc
if not __KODI_MATRIX__ or True:  # pylint: disable=condition-evals-to-constant
    def translatePath(path):
        ''' A stub implementation of the xbmc translatePath() function '''
        if path.startswith('special://home'):
            return path.replace('special://home', os.path.join(os.getcwd(), 'tests/'))
        if path.startswith('special://masterprofile'):
            return path.replace('special://masterprofile', os.path.join(os.getcwd(), 'tests/userdata/'))
        if path.startswith('special://profile'):
            return path.replace('special://profile', os.path.join(os.getcwd(), 'tests/userdata/'))
        if path.startswith('special://userdata'):
            return path.replace('special://userdata', os.path.join(os.getcwd(), 'tests/userdata/'))
        return path

    def makeLegalFilename(path):
        ''' A stub implementation of the xbmc makeLegalFilename() function '''
        return os.path.normpath(path)
