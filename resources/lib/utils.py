# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from binascii import hexlify, unhexlify
import json
import xbmc
import xbmcaddon
import xbmcgui
from .statichelper import from_unicode, to_unicode

ADDON = xbmcaddon.Addon()
ADDON_ID = to_unicode(ADDON.getAddonInfo('id'))
ADDON_PATH = to_unicode(ADDON.getAddonInfo('path'))


def window(key, value=None, clear=False, window_id=10000):
    ''' Get or set Window properties '''
    the_window = xbmcgui.Window(window_id)

    if clear:
        the_window.clearProperty(key)
    elif value is None:
        result = to_unicode(the_window.getProperty(key.replace('.json', '').replace('.bool', '')))

        if result:
            if key.endswith('.json'):
                result = json.loads(result)
            elif key.endswith('.bool'):
                result = bool(result in ('true', '1'))
        return result
    else:
        if key.endswith('.json'):

            key = key.replace('.json', '')
            value = json.dumps(value)

        elif key.endswith('.bool'):

            key = key.replace('.bool', '')
            value = 'true' if value else 'false'

        the_window.setProperty(key, from_unicode(str(value)))
    return None


def settings(setting, value=None):
    ''' Get or set add-on settings '''
    if value is None:
        result = to_unicode(ADDON.getSetting(setting.replace('.bool', '')))

        if result and setting.endswith('.bool'):
            result = bool(result in ('true', '1'))

        return result

    if setting.endswith('.bool'):

        setting = setting.replace('.bool', '')
        value = 'true' if value else 'false'

    ADDON.setSetting(setting, from_unicode(value))
    return None


def event(message, data=None, sender=None):
    ''' Send internal notification event '''
    data = data or {}
    sender = sender or ADDON_ID
    jsonrpc(method='JSONRPC.NotifyAll', params=dict(
        sender='%s.SIGNAL' % sender,
        message=message,
        data=[to_unicode(hexlify(json.dumps(data).encode()))],
    ))


def decode_data(data):
    ''' Decode data coming from a notification event '''
    data = json.loads(data)
    if data:
        return to_unicode(json.loads(unhexlify(data[0])))
    return None


def log(msg, name=None, level=1):
    ''' Log information to the Kodi log '''
    log_level = int(settings('logLevel'))
    window('logLevel', log_level)
    if log_level < level:
        return
    xbmc.log('[%s] %s -> %s' % (ADDON_ID, name, from_unicode(msg)), level=xbmc.LOGNOTICE)


def load_test_data():
    ''' Load test data for developer mode '''
    test_episode = {'episodeid': 12345678, 'tvshowid': 12345678, 'title': 'Garden of Bones', 'art': {}}
    test_episode['art']['tvshow.poster'] = 'https://fanart.tv/fanart/tv/121361/tvposter/game-of-thrones-521441fd9b45b.jpg'
    test_episode['art']['thumb'] = 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-556979e5eda6b.jpg'
    test_episode['art']['tvshow.fanart'] = 'https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-4fd5fa8ed5e1b.jpg'
    test_episode['art']['tvshow.landscape'] = 'https://fanart.tv/detailpreview/fanart/tv/121361/tvthumb/game-of-thrones-4f78ce73d617c.jpg'
    test_episode['art']['tvshow.clearart'] = 'https://fanart.tv/fanart/tv/121361/clearart/game-of-thrones-4fa1349588447.png'
    test_episode['art']['tvshow.clearlogo'] = 'https://fanart.tv/fanart/tv/121361/hdtvlogo/game-of-thrones-504c49ed16f70.png'
    test_episode['plot'] = 'Lord Baelish arrives at Renly\'s camp just before he faces off against Stannis. Daenerys and her company are welcomed '\
                           ' into the city of Qarth. Arya, Gendry, and Hot Pie find themselves imprisoned at Harrenhal.'
    test_episode['showtitle'] = 'Game of Thrones'
    test_episode['playcount'] = 1
    test_episode['season'] = 2
    test_episode['episode'] = 4
    test_episode['seasonepisode'] = '2x4.'
    test_episode['rating'] = '8.9'
    test_episode['firstaired'] = '23/04/2012'
    return test_episode


def calculate_progress_steps(period):
    ''' Calculate a progress step '''
    if int(period) == 0:  # Avoid division by zero
        return 10.0
    return (100.0 / int(period)) / 10


def jsonrpc(**kwargs):
    ''' Perform JSONRPC calls '''
    if 'id' not in kwargs:
        kwargs.update(id=1)
    if 'jsonrpc' not in kwargs:
        kwargs.update(jsonrpc='2.0')
    return json.loads(xbmc.executeJSONRPC(json.dumps(kwargs)))
