# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import sys
import json
from xbmc import executeJSONRPC, log as xlog, LOGDEBUG, LOGNOTICE
from xbmcaddon import Addon
from xbmcgui import Window
from .statichelper import from_unicode, to_unicode

ADDON = Addon()


def get_addon_info(key):
    ''' Return addon information '''
    return to_unicode(ADDON.getAddonInfo(key))


def addon_id():
    ''' Return add-on ID '''
    return get_addon_info('id')


def addon_path():
    ''' Return add-on path '''
    return get_addon_info('path')


def get_property(key, window_id=10000):
    ''' Get a Window property '''
    return to_unicode(Window(window_id).getProperty(key))


def set_property(key, value, window_id=10000):
    ''' Set a Window property '''
    return Window(window_id).setProperty(key, from_unicode(str(value)))


def clear_property(key, window_id=10000):
    ''' Clear a Window property '''
    return Window(window_id).clearProperty(key)


def get_setting(key, default=None):
    ''' Get an add-on setting '''
    # We use Addon() here to ensure changes in settings are reflected instantly
    try:
        value = to_unicode(Addon().getSetting(key))
    except RuntimeError:  # Occurs when the add-on is disabled
        return default
    if value == '' and default is not None:
        return default
    return value


def encode_data(data, encoding='base64'):
    ''' Encode data for a notification event '''
    json_data = json.dumps(data).encode()
    if encoding == 'base64':
        from base64 import b64encode
        encoded_data = b64encode(json_data)
    elif encoding == 'hex':
        from binascii import hexlify
        encoded_data = hexlify(json_data)
    else:
        log("Unknown payload encoding type '%s'" % encoding, level=0)
        return None
    if sys.version_info[0] > 2:
        encoded_data = encoded_data.decode('ascii')
    return encoded_data


def decode_data(encoded):
    ''' Decode data coming from a notification event '''
    encoding = 'base64'
    from binascii import Error, unhexlify
    try:
        json_data = unhexlify(encoded)
    except (TypeError, Error):
        from base64 import b64decode
        json_data = b64decode(encoded)
    else:
        encoding = 'hex'
    # NOTE: With Python 3.5 and older json.loads() does not support bytes or bytearray, so we convert to unicode
    return json.loads(to_unicode(json_data)), encoding


def decode_json(data):
    encoded = json.loads(data)
    if not encoded:
        return None, None
    return decode_data(encoded[0])


def event(message, data=None, sender=None, encoding='base64'):
    ''' Send internal notification event '''
    data = data or {}
    sender = sender or addon_id()

    encoded = encode_data(data, encoding=encoding)
    if not encoded:
        return

    jsonrpc(method='JSONRPC.NotifyAll', params=dict(
        sender='%s.SIGNAL' % sender,
        message=message,
        data=[encoded],
    ))


def log(msg, name=None, level=1):
    ''' Log information to the Kodi log '''
    log_level = int(get_setting('logLevel', level))
    debug_logging = get_global_setting('debug.showloginfo')
    set_property('logLevel', log_level)
    if not debug_logging and log_level < level:
        return
    level = LOGDEBUG if debug_logging else LOGNOTICE
    xlog('[%s] %s -> %s' % (addon_id(), name, from_unicode(msg)), level=level)


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
    return json.loads(executeJSONRPC(json.dumps(kwargs)))


def get_global_setting(setting):
    ''' Get a Kodi setting '''
    result = jsonrpc(method='Settings.GetSettingValue', params=dict(setting=setting))
    return result.get('result', {}).get('value')


def localize(string_id):
    ''' Return the translated string from the .po language files, optionally translating variables '''
    return ADDON.getLocalizedString(string_id)
