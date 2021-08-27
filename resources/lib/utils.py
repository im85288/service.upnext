# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions used elsewhere in the addon"""

from __future__ import absolute_import, division, unicode_literals
import base64
import binascii
import json
import sys
import threading
import dateutil.parser
import xbmc
import xbmcaddon
import xbmcgui
import constants
import statichelper


class Profiler(object):  # pylint: disable=useless-object-inheritance
    """Class used to profile a block of code"""

    __slots__ = ('_profiler', )

    from cProfile import Profile
    from pstats import Stats
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO
    from functools import wraps

    def __init__(self):
        self._profiler = self.Profile()
        self._profiler.enable()

    @classmethod
    def profile(cls, func):
        """Decorator used to profile function calls"""

        @cls.wraps(func)
        def wrapper(*args, **kwargs):
            """Wrapper to create a new Profiler instance, run the function being
               profiled, print out profiler result to the log, and return result of
               function call"""

            profiler = cls()
            result = func(*args, **kwargs)
            profiler.disable()

            name = getattr(func, '__qualname__', None)
            if name:
                # If __qualname__ is available (Python 3.3+) then use it
                pass

            elif args and getattr(args[0], func.__name__, None):
                if isinstance(args[0], type):
                    class_name = args[0].__name__
                else:
                    class_name = args[0].__class__.__name__
                name = '{0}.{1}'.format(class_name, func.__name__)

            elif (func.__class__
                  and not isinstance(func.__class__, type)
                  and func.__class__.__name__ != 'function'):
                name = '{0}.{1}'.format(func.__class__.__name__, func.__name__)

            elif func.__module__:
                name = '{0}.{1}'.format(func.__module__, func.__name__)

            else:
                name = func.__name__

            log(profiler.get_stats(), name=name, level=LOGDEBUG)

            return result

        return wrapper

    def disable(self):
        self._profiler.disable()

    def enable(self):
        self._profiler.enable()

    def get_stats(self, flush=True):
        self.disable()

        output_stream = self.StringIO()
        self.Stats(
            self._profiler,
            stream=output_stream
        ).sort_stats('cumulative').print_stats(20)
        output = output_stream.getvalue()
        output_stream.close()

        if flush:
            self._profiler = self.Profile()
        self.enable()

        return output


ADDON = xbmcaddon.Addon(constants.ADDON_ID)
_KODI_VERSION = float(xbmc.getInfoLabel('System.BuildVersion').split()[0])


def get_addon(addon_id=None):
    """Return addon instance"""

    if addon_id:
        return xbmcaddon.Addon(addon_id)
    return xbmcaddon.Addon()


def get_addon_info(key):
    """Return addon information"""

    return statichelper.to_unicode(ADDON.getAddonInfo(key))


def get_addon_id():
    """Return addon ID"""

    return get_addon_info('id')


def get_addon_path():
    """Return addon path"""

    return get_addon_info('path')


def supports_python_api(version):
    """Return True if Kodi supports target Python API version"""

    return _KODI_VERSION >= version


def get_property(key, window_id=constants.WINDOW_HOME):
    """Get a Window property"""

    return statichelper.to_unicode(xbmcgui.Window(window_id).getProperty(key))


def set_property(key, value, window_id=constants.WINDOW_HOME):
    """Set a Window property"""

    value = statichelper.from_unicode(str(value))
    return xbmcgui.Window(window_id).setProperty(key, value)


def clear_property(key, window_id=constants.WINDOW_HOME):
    """Clear a Window property"""

    return xbmcgui.Window(window_id).clearProperty(key)


def get_setting(key, default='', echo=True):
    """Get an addon setting as string"""

    value = default
    try:
        value = ADDON.getSetting(key)
        value = statichelper.to_unicode(value)
    # Occurs when the addon is disabled
    except RuntimeError:
        value = default

    if echo:
        log(msg='{0}: {1}'.format(key, value), name='Settings', level=LOGDEBUG)
    return value


def get_setting_bool(key, default=None, echo=True):
    """Get an addon setting as boolean"""

    value = default
    try:
        value = bool(ADDON.getSettingBool(key))
    # On Krypton or older, or when not a boolean
    except (AttributeError, TypeError):
        value = get_setting(key, echo=False)
        value = constants.BOOL_STRING_VALUES.get(value.lower(), default)
    # Occurs when the addon is disabled
    except RuntimeError:
        value = default

    if echo:
        log(msg='{0}: {1}'.format(key, value), name='Settings', level=LOGDEBUG)
    return value


def get_setting_int(key, default=None, echo=True):
    """Get an addon setting as integer"""

    value = default
    try:
        value = ADDON.getSettingInt(key)
    # On Krypton or older, or when not an integer
    except (AttributeError, TypeError):
        value = get_setting(key, echo=False)
        value = get_int(value, default=default, strict=True)
    # Occurs when the addon is disabled
    except RuntimeError:
        value = default

    if echo:
        log(msg='{0}: {1}'.format(key, value), name='Settings', level=LOGDEBUG)
    return value


def get_int(obj, key=None, default=-1, strict=False):
    """Returns an object or value for the given key in object, as an integer.
       Returns default value if key or object is not available.
       Returns value if value cannot be converted to integer."""

    try:
        val = obj.get(key, default) if key else obj
    except (AttributeError, TypeError):
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default if strict or not val else val


def encode_data(data, encoding='base64'):
    """Encode data for a notification event"""

    encode_methods = {
        'hex': binascii.hexlify,
        'base64': base64.b64encode
    }
    encode_method = encode_methods.get(encoding)

    if not encode_method:
        log('Unknown payload encoding type: {0}'.format(encoding),
            level=LOGWARNING)
        return None

    try:
        json_data = json.dumps(data).encode()
        encoded_data = encode_method(json_data)
    except (TypeError, ValueError, binascii.Error):
        log('{0} encode error: {1}'.format(encoding, data), level=LOGWARNING)
        return None

    if sys.version_info[0] > 2:
        encoded_data = encoded_data.decode('ascii')

    return encoded_data


def decode_data(encoded_data, compat_mode=True):
    """Decode JSON data coming from a notification event"""

    decoded_json = None
    decoded_data = None
    encoding = None

    # Compatibility with Addon Signals which wraps serialised data in square
    # brackets to generate an array/list
    if compat_mode:
        try:
            encoded_data = json.loads(encoded_data)[0]
        except (IndexError, TypeError, ValueError):
            encoded_data = None

    if encoded_data:
        decode_methods = {
            'hex': binascii.unhexlify,
            'base64': base64.b64decode
        }

        for encoding, decode_method in decode_methods.items():
            try:
                decoded_json = decode_method(encoded_data)
                break
            except (TypeError, binascii.Error):
                pass
        else:
            encoding = None

    if decoded_json:
        try:
            # NOTE: With Python 3.5 and older json.loads() does not support
            # bytes or bytearray, so we convert to unicode
            decoded_json = statichelper.to_unicode(decoded_json)
            decoded_data = json.loads(decoded_json)
        except (TypeError, ValueError):
            pass

    return decoded_data, encoding


def event(message, data=None, sender=None, encoding='base64'):
    """Send internal notification event"""

    data = data or {}
    sender = sender or get_addon_id()

    encoded_data = encode_data(data, encoding=encoding)
    if not encoded_data:
        return

    jsonrpc(
        method='JSONRPC.NotifyAll',
        params={
            'sender': '{0}.SIGNAL'.format(sender),
            'message': message,
            'data': [encoded_data],
        }
    )


# Log levels                      | v18 | v19
LOGDEBUG = xbmc.LOGDEBUG        # |  0  |  0
LOGINFO = xbmc.LOGINFO          # |  1  |  1
# LOGNOTICE = xbmc.LOGNOTICE    # |  2  |  Deprecated
LOGWARNING = xbmc.LOGWARNING    # |  3  |  2
LOGERROR = xbmc.LOGERROR        # |  4  |  3
# LOGSEVERE = xbmc.LOGSEVERE    # |  5  |  Deprecated
LOGFATAL = xbmc.LOGFATAL        # |  6  |  4
LOGNONE = xbmc.LOGNONE          # |  7  |  5

LOG_ENABLE_SETTING = get_setting_int('logLevel', echo=False)
MIN_LOG_LEVEL = LOGINFO if supports_python_api(19) else LOGINFO + 1


def log(msg, name=__name__, level=LOGINFO):
    """Log information to the Kodi log"""

    # Log everything
    if LOG_ENABLE_SETTING == constants.LOG_ENABLE_DEBUG:
        log_enable = level != LOGNONE
    # Only log important messages
    elif LOG_ENABLE_SETTING == constants.LOG_ENABLE_INFO:
        log_enable = LOGDEBUG < level < LOGNONE
    # Log nothing
    else:
        log_enable = False

    if not log_enable:
        return

    # Force minimum required log level to display in Kodi event log
    if level < MIN_LOG_LEVEL:  # pylint: disable=consider-using-max-builtin
        level = MIN_LOG_LEVEL

    # Convert to unicode for string formatting with Unicode literal
    msg = statichelper.to_unicode(msg)
    msg = '[{0}] {1} -> {2}'.format(get_addon_id(), name, msg)
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
        params={'setting': setting}
    )
    return result.get('result', {}).get('value')


def localize(string_id):
    """Return the translated string from the .po language files"""

    return ADDON.getLocalizedString(string_id)


def get_year(date_string):
    """Extract year from a date string. Returns year, or input if unable to
    parse"""

    try:
        date_object = dateutil.parser.parse(date_string)
        return date_object.year
    except ValueError:
        return date_string


def localize_date(date_string):
    """Localize date format"""

    date_format = xbmc.getRegion('dateshort')

    try:
        date_object = dateutil.parser.parse(date_string)
    except ValueError:
        return None, date_string

    return date_object, date_object.strftime(date_format)


def localize_time(time_object):
    """Localize time format"""

    time_format = xbmc.getRegion('time')

    # Fix a bug in Kodi v18.5 and older causing double hours
    # https://github.com/xbmc/xbmc/pull/17380
    time_format = time_format.replace('%H%H:', '%H:')

    # Strip off seconds
    time_format = time_format.replace(':%S', '')

    return time_object.strftime(time_format)


def notification(
        heading, message,
        icon=xbmcgui.NOTIFICATION_INFO, time=5000, sound=False
):
    """Display a notification in Kodi with notification sound off by default"""

    xbmcgui.Dialog().notification(heading, message, icon, time, sound)


def create_lock():
    return threading.Lock()


def create_event():
    return threading.Event()


def run_threaded(target, delay=None, args=None, kwargs=None):
    """Executes the target in a separate thread or timer"""

    if args is None:
        args = ()

    if kwargs is None:
        kwargs = {}

    if delay is not None:
        thread = threading.Timer(delay, target, args=args, kwargs=kwargs)
    else:
        thread = threading.Thread(target=target, args=args, kwargs=kwargs)
    # Daemon threads may not work in Kodi, but enable it anyway
    thread.daemon = True
    thread.start()
    return thread


def time_to_seconds(time_str):
    """Convert a time string in the format hh:mm:ss to seconds as an integer"""

    seconds = 0

    time_split = time_str.split(':')
    try:
        seconds += int(time_split[-1])
        seconds += int(time_split[-2]) * 60
        seconds += int(time_split[-3]) * 3600
    except (IndexError, ValueError):
        pass

    return seconds


def wait(timeout=None):
    if timeout:
        return xbmc.Monitor().waitForAbort(timeout)
    return xbmc.Monitor().waitForAbort()


def calc_wait_time(end_time=None, start_time=0, rate=None):
    if not end_time or not rate or rate < 1:
        return None

    return max(0, (end_time - start_time) // rate)
