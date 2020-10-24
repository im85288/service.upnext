# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions used elsewhere in the add-on"""

from __future__ import absolute_import, division, unicode_literals
import base64
import binascii
import json
import sys
import xbmc
import xbmcaddon
import xbmcgui
import statichelper


ADDON = xbmcaddon.Addon()
KODI_VERSION = float(xbmc.getInfoLabel('System.BuildVersion')[:4])


def get_addon_info(key):
    """Return add-on information"""
    return statichelper.to_unicode(ADDON.getAddonInfo(key))


def addon_id():
    """Return add-on ID"""
    return get_addon_info('id')


def addon_path():
    """Return add-on path"""
    return get_addon_info('path')


def supports_python_api(version):
    """Return True if Kodi supports target Python API version"""
    return KODI_VERSION >= version


def get_property(key, window_id=10000):
    """Get a Window property"""
    return statichelper.to_unicode(xbmcgui.Window(window_id).getProperty(key))


def set_property(key, value, window_id=10000):
    """Set a Window property"""
    value = statichelper.from_unicode(str(value))
    return xbmcgui.Window(window_id).setProperty(key, value)


def clear_property(key, window_id=10000):
    """Clear a Window property"""
    return xbmcgui.Window(window_id).clearProperty(key)


def get_setting(key, default=None):
    """Get an add-on setting as string"""
    # We use Addon() here to ensure changes in settings are reflected instantly
    try:
        value = statichelper.to_unicode(xbmcaddon.Addon().getSetting(key))
    # Occurs when the add-on is disabled
    except RuntimeError:
        return default
    if value == '' and default is not None:
        return default
    return value


def get_setting_bool(key, default=None):
    """Get an add-on setting as boolean"""
    try:
        return xbmcaddon.Addon().getSettingBool(key)
    # On Krypton or older, or when not a boolean
    except (AttributeError, TypeError):
        value = get_setting(key, default)
        if value not in {'false', 'true'}:
            return default
        return bool(value == 'true')
    # Occurs when the add-on is disabled
    except RuntimeError:
        return default


def get_setting_int(key, default=None):
    """Get an add-on setting as integer"""
    try:
        return xbmcaddon.Addon().getSettingInt(key)
    # On Krypton or older, or when not an integer
    except (AttributeError, TypeError):
        value = get_setting(key, default)
        try:
            return int(value)
        except ValueError:
            return default
    # Occurs when the add-on is disabled
    except RuntimeError:
        return default


def get_int(obj, key, default=-1):
    """Returns a value for the given key, as integer.
       Returns default value if key is not available.
       Returns value if value cannot be converted to integer."""
    try:
        val = obj.get(key, default)
    except (AttributeError, TypeError):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return val if val else default


def encode_data(data, encoding='base64'):
    """Encode data for a notification event"""
    json_data = json.dumps(data).encode()
    if encoding == 'base64':
        encoded_data = base64.b64encode(json_data)
    elif encoding == 'hex':
        encoded_data = binascii.hexlify(json_data)
    else:
        log("Unknown payload encoding type '%s'" % encoding, level=0)
        return None
    if sys.version_info[0] > 2:
        encoded_data = encoded_data.decode('ascii')
    return encoded_data


def decode_data(encoded):
    """Decode data coming from a notification event"""
    try:
        json_data = binascii.unhexlify(encoded)
        encoding = 'hex'
    except (TypeError, binascii.Error):
        json_data = base64.b64decode(encoded)
        encoding = 'base64'

    # NOTE: With Python 3.5 and older json.loads() does not support bytes
    # or bytearray, so we convert to unicode
    return json.loads(statichelper.to_unicode(json_data)), encoding


def decode_json(data):
    """Decode JSON data coming from a notification event"""
    encoded = json.loads(data)
    if not encoded:
        return None, None
    return decode_data(encoded[0])


def event(message, data=None, sender=None, encoding='base64'):
    """Send internal notification event"""
    data = data or {}
    sender = sender or addon_id()

    encoded = encode_data(data, encoding=encoding)
    if not encoded:
        return

    jsonrpc(
        method='JSONRPC.NotifyAll',
        params=dict(
            sender='%s.SIGNAL' % sender,
            message=message,
            data=[encoded],
        )
    )


def log(msg, name=None, level=1):
    """Log information to the Kodi log"""
    log_level = get_setting_int('logLevel', level)
    debug_logging = get_global_setting('debug.showloginfo')
    set_property('logLevel', log_level)
    if not debug_logging and log_level < level:
        return
    if debug_logging:
        level = xbmc.LOGDEBUG
    # Kodi v19+ uses LOGINFO (=2) as default log level. LOGNOTICE is deprecated
    elif supports_python_api(19):
        level = xbmc.LOGINFO
    # Kodi v18 and below uses LOGNOTICE (=3) as default log level.
    else:
        level = xbmc.LOGINFO + 1

    # Convert to unicode for string formatting with Unicode literal
    msg = statichelper.to_unicode(msg)
    msg = '[{0}] {1} -> {2}'.format(addon_id(), name, msg)
    # Convert back for older Kodi versions
    xbmc.log(statichelper.from_unicode(msg), level=level)


def jsonrpc(**kwargs):
    """Perform JSONRPC calls"""
    response = not kwargs.pop('no_response', False)
    if response and 'id' not in kwargs:
        kwargs.update(id=0)
    if 'jsonrpc' not in kwargs:
        kwargs.update(jsonrpc='2.0')
    result = xbmc.executeJSONRPC(json.dumps(kwargs))
    return json.loads(result) if response else result


def get_global_setting(setting):
    """Get a Kodi setting"""
    result = jsonrpc(
        method='Settings.GetSettingValue',
        params=dict(setting=setting)
    )
    return result.get('result', {}).get('value')


def localize(string_id):
    """Return the translated string from the .po language files"""
    return ADDON.getLocalizedString(string_id)


def localize_time(time):
    """Localize time format"""
    time_format = xbmc.getRegion('time')

    # Fix a bug in Kodi v18.5 and older causing double hours
    # https://github.com/xbmc/xbmc/pull/17380
    time_format = time_format.replace('%H%H:', '%H:')

    # Strip off seconds
    time_format = time_format.replace(':%S', '')

    return time.strftime(time_format)


def is_amlogic():
    """Check whether AMLogic hardware video decoder is being used"""
    return xbmc.getInfoLabel('Player.Process(VideoDecoder)')[:3] == 'am-'
