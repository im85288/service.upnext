# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import binascii
import inspect
import json
import xbmc
import xbmcaddon
import xbmcgui


def addon_path():
    return xbmcaddon.Addon().getAddonInfo('path')


def kodi_version():
    return xbmc.getInfoLabel('System.BuildVersion')[:2]


def addon_name():
    return xbmcaddon.Addon().getAddonInfo('name').upper()


def addon_version():
    return xbmcaddon.Addon().getAddonInfo('version')


def window(key, value=None, clear=False, window_id=10000):
    the_window = xbmcgui.Window(window_id)

    if clear:
        the_window.clearProperty(key)
    elif value is not None:
        if key.endswith('.json'):

            key = key.replace('.json', "")
            value = json.dumps(value)

        elif key.endswith('.bool'):

            key = key.replace('.bool', "")
            value = "true" if value else "false"

        the_window.setProperty(key, value)
    else:
        result = the_window.getProperty(key.replace('.json', "").replace('.bool', ""))

        if result:
            if key.endswith('.json'):
                result = json.loads(result)
            elif key.endswith('.bool'):
                result = result in ("true", "1")

        return result
    return None


def settings(setting, value=None):

    addon = xbmcaddon.Addon()

    if value is None:
        result = addon.getSetting(setting.replace('.bool', ""))

        if result and setting.endswith('.bool'):
            result = result in ("true", "1")

        return result

    if setting.endswith('.bool'):

        setting = setting.replace('.bool', '')
        value = "true" if value else "false"

    addon.setSetting(setting, value)
    return None


def event(method, data=None, source_id=None):

    """ Data is a dictionary.
    """
    data = data or {}
    source_id = source_id or xbmcaddon.Addon().getAddonInfo('id')
    xbmc.executebuiltin('NotifyAll(%s.SIGNAL, %s, %s)' %
                        (source_id, method, '\\"[\\"{0}\\"]\\"'.format(binascii.hexlify(json.dumps(data)))))


def decode_data(data):
    data = json.loads(data)
    if data:
        return json.loads(binascii.unhexlify(data[0]))
    return None


def log(title, msg, level=1):
    log_level = int(settings("logLevel"))
    window('logLevel', str(log_level))
    if log_level >= level:
        if log_level == 2:  # inspect.stack() is expensive
            try:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg), level=xbmc.LOGNOTICE)
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg.encode('utf-8')), level=xbmc.LOGNOTICE)
        else:
            try:
                xbmc.log(title + " -> " + str(msg), level=xbmc.LOGNOTICE)
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + str(msg.encode('utf-8')), level=xbmc.LOGNOTICE)


def load_test_data():
    test_episode = {"episodeid": 12345678, "tvshowid": 12345678, "title": "Garden of Bones", "art": {}}
    test_episode["art"]["tvshow.poster"] = "https://fanart.tv/fanart/tv/121361/tvposter/game-of-thrones-521441fd9b45b.jpg"
    test_episode["art"]["thumb"] = "https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-556979e5eda6b.jpg"
    test_episode["art"]["tvshow.fanart"] = "https://fanart.tv/fanart/tv/121361/showbackground/game-of-thrones-4fd5fa8ed5e1b.jpg"
    test_episode["art"]["tvshow.landscape"] = "https://fanart.tv/detailpreview/fanart/tv/121361/tvthumb/game-of-thrones-4f78ce73d617c.jpg"
    test_episode["art"]["tvshow.clearart"] = "https://fanart.tv/fanart/tv/121361/clearart/game-of-thrones-4fa1349588447.png"
    test_episode["art"]["tvshow.clearlogo"] = "https://fanart.tv/fanart/tv/121361/hdtvlogo/game-of-thrones-504c49ed16f70.png"
    test_episode["plot"] = "Lord Baelish arrives at Renly's camp just before he faces off against Stannis. Daenerys and her company are welcomed "\
                           " into the city of Qarth. Arya, Gendry, and Hot Pie find themselves imprisoned at Harrenhal."
    test_episode["showtitle"] = "Game of Thrones"
    test_episode["playcount"] = 1
    test_episode["season"] = 2
    test_episode["episode"] = 4
    test_episode["seasonepisode"] = "2x4."
    test_episode["rating"] = "8.9"
    test_episode["firstaired"] = "23/04/2012"
    return test_episode


def unicode_to_ascii(text):
    return text.encode('ascii', 'replace')


def calculate_progress_steps(period):
    return (100.0 / int(period)) / 10


class JSONRPC(object):
    id = 1
    jsonrpc = "2.0"
    params = None

    def __init__(self, method, **kwargs):
        self.method = method
        for arg in kwargs:
            self.arg = kwargs[arg]

    def _query(self):
        query = {
            'jsonrpc': self.jsonrpc,
            'id': self.id,
            'method': self.method,
        }
        if self.params is not None:
            query['params'] = self.params
        return json.dumps(query)

    def execute(self, params=None):
        self.params = params
        return json.loads(xbmc.executeJSONRPC(self._query()))
