import xbmc
import xbmcgui
import xbmcaddon
import inspect
import sys
if sys.version_info < (2, 7):
    import simplejson as json
else:
    import json


def addon_id():
    return "service.upnext"


def kodi_version():
    return xbmc.getInfoLabel('System.BuildVersion')[:2]


def addon_name():
    return xbmcaddon.Addon(addon_id()).getAddonInfo('name').upper()


def addon_version():
    return xbmcaddon.Addon(addon_id()).getAddonInfo('version')


def window(key, value=None, clear=False, window_id=10000):
    window = xbmcgui.Window(window_id)

    if clear:
        window.clearProperty(key)
    elif value is not None:
        if key.endswith('.json'):

            key = key.replace('.json', "")
            value = json.dumps(value)

        elif key.endswith('.bool'):

            key = key.replace('.bool', "")
            value = "true" if value else "false"

        window.setProperty(key, value)
    else:
        result = window.getProperty(key.replace('.json', "").replace('.bool', ""))

        if result:
            if key.endswith('.json'):
                result = json.loads(result)
            elif key.endswith('.bool'):
                result = result in ("true", "1")

        return result


def settings(setting, value=None):

    addon = xbmcaddon.Addon(addon_id())

    if value is not None:
        if setting.endswith('.bool'):

            setting = setting.replace('.bool', "")
            value = "true" if value else "false"

        addon.setSetting(setting, value)
    else:
        result = addon.getSetting(setting.replace('.bool', ""))

        if result and setting.endswith('.bool'):
            result = result in ("true", "1")

        return result


def logMsg(title, msg, level=1):
    logLevel = int(settings("logLevel"))
    WINDOW = xbmcgui.Window(10000)
    WINDOW.setProperty('logLevel', str(logLevel))
    if logLevel >= level:
        if logLevel == 2:  # inspect.stack() is expensive
            try:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg),level=xbmc.LOGNOTICE)
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + inspect.stack()[1][3] + " : " + str(msg.encode('utf-8')),level=xbmc.LOGNOTICE)
        else:
            try:
                xbmc.log(title + " -> " + str(msg),level=xbmc.LOGNOTICE)
            except UnicodeEncodeError:
                xbmc.log(title + " -> " + str(msg.encode('utf-8')),level=xbmc.LOGNOTICE)


def unicodetoascii(text):

    TEXT = (text.
            replace('\xe2\x80\x99', "'").
            replace('\xc3\xa9', 'e').
            replace('\xe2\x80\x90', '-').
            replace('\xe2\x80\x91', '-').
            replace('\xe2\x80\x92', '-').
            replace('\xe2\x80\x93', '-').
            replace('\xe2\x80\x94', '-').
            replace('\xe2\x80\x94', '-').
            replace('\xe2\x80\x98', "'").
            replace('\xe2\x80\x9b', "'").
            replace('\xe2\x80\x9c', '"').
            replace('\xe2\x80\x9c', '"').
            replace('\xe2\x80\x9d', '"').
            replace('\xe2\x80\x9e', '"').
            replace('\xe2\x80\x9f', '"').
            replace('\xe2\x80\xa6', '...').
            replace('\xe2\x80\xb2', "'").
            replace('\xe2\x80\xb3', "'").
            replace('\xe2\x80\xb4', "'").
            replace('\xe2\x80\xb5', "'").
            replace('\xe2\x80\xb6', "'").
            replace('\xe2\x80\xb7', "'").
            replace('\xe2\x81\xba', "+").
            replace('\xe2\x81\xbb', "-").
            replace('\xe2\x81\xbc', "=").
            replace('\xe2\x81\xbd', "(").
            replace('\xe2\x81\xbe', ")")
            )
    return TEXT
