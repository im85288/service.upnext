# -*- coding: utf-8 -*-
# Copyright: (c) 2019, Dag Wieers (@dagwieers) <dag@wieers.com>
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
''' This file implements the Kodi xbmcgui module, either using stubs or alternative functionality '''

# pylint: disable=invalid-name,too-many-arguments,unused-argument

from __future__ import absolute_import, division, print_function, unicode_literals
from random import randint
from xbmc import InfoTagVideo
from xbmcextra import kodi_to_ansi, __KODI_MATRIX__

ACTION_NAV_BACK = 92
ACTION_STOP = 13
NOTIFICATION_INFO = 'info'


class Control(object):  # pylint: disable=too-few-public-methods
    ''' A reimplementation of the xbmcgui Control class '''

    def __init__(self):
        ''' A stub constructor for the xbmcgui Control class '''
        self.Id = randint(0, 9999)
        self.x = 0
        self.y = 0
        self.width = 0
        self.height = 0

    def getId(self):
        ''' A stub implementation for the xbmcgui Control class getId() method '''
        return self.Id


class ControlLabel(Control):  # pylint: disable=too-many-instance-attributes
    ''' A reimplementation of the xbmcgui ControlLabel class '''

    def __init__(self, x, y, width, height, label, font='font13',
                 textColor='0xFFFFFFFF', disabledColor='0xFFF3300F',
                 alignment=0, hasPath=False, angle=0):
        ''' A stub constructor for the xbmcgui ControlLabel class '''
        super(ControlLabel, self).__init__()
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.label = label
        self.label2 = ''
        self.font = font
        self.textColor = textColor
        self.disabledColor = disabledColor
        self.shadowColor = '0xFF000000'
        self.focusedColor = '0xFF00FFFF'
        self.alignment = alignment
        self.hasPath = hasPath
        self.angle = angle

    def getLabel(self):
        ''' A stub implementation for the xbmcgui ControlLabel class getLabel() method '''
        return self.label

    def setLabel(self, label, font='font13', textColor='0xFFFFFFFF',
                 disabledColor='0xFFF3300F', shadowColor='0xFF000000',
                 focusedColor='0xFF00FFFF', label2=''):
        ''' A stub implementation for the xbmcgui ControlLabel class setLabel() method '''
        self.label = label
        self.label2 = label2
        self.font = font
        self.textColor = textColor
        self.disabledColor = disabledColor
        self.shadowColor = '0xFF000000'
        self.focusedColor = '0xFF00FFFF'


class ControlProgress(Control):
    ''' A reimplementation of the xbmcgui ControlProgress class '''

    def __init__(self):
        ''' A stub constructor for the xbmcgui ControlLabel class '''
        super(ControlProgress, self).__init__()
        self._percentage = 0.0

    def setPercent(self, percent):
        self._percentage = max(0.0, min(100.0, percent))

    def getPercentage(self):
        return self._percentage


class Dialog(object):
    ''' A reimplementation of the xbmcgui Dialog class '''

    def __init__(self):
        ''' A stub constructor for the xbmcgui Dialog class '''

    @staticmethod
    def notification(heading, message, icon=None, time=None, sound=None):
        ''' A working implementation for the xbmcgui Dialog class notification() method '''
        heading = kodi_to_ansi(heading)
        message = kodi_to_ansi(message)
        print('\033[37;44;1mNOTIFICATION:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (heading, message))

    @staticmethod
    def ok(heading, line1, line2=None, line3=None):
        ''' A stub implementation for the xbmcgui Dialog class ok() method '''
        heading = kodi_to_ansi(heading)
        line1 = kodi_to_ansi(line1)
        print('\033[37;44;1mOK:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (heading, line1))

    @staticmethod
    def info(listitem):
        ''' A stub implementation for the xbmcgui Dialog class info() method '''

    @staticmethod
    def multiselect(heading, options, autoclose=0, preselect=None, useDetails=False):  # pylint: disable=useless-return
        ''' A stub implementation for the xbmcgui Dialog class multiselect() method '''
        if preselect is None:
            preselect = []
        heading = kodi_to_ansi(heading)
        print('\033[37;44;1mMULTISELECT:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (heading, ', '.join(options)))
        return None

    @staticmethod
    def yesno(heading, line1, line2=None, line3=None, nolabel=None, yeslabel=None, autoclose=0):
        ''' A stub implementation for the xbmcgui Dialog class yesno() method '''
        heading = kodi_to_ansi(heading)
        line1 = kodi_to_ansi(line1)
        print('\033[37;44;1mYESNO:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (heading, line1))
        return True

    @staticmethod
    def textviewer(heading, text=None, usemono=None):
        ''' A stub implementation for the xbmcgui Dialog class textviewer() method '''
        heading = kodi_to_ansi(heading)
        text = kodi_to_ansi(text)
        print('\033[37;44;1mTEXTVIEWER:\033[35;49;1m [%s]\n\033[37;1m%s\033[39;0m' % (heading, text))

    @staticmethod
    def browseSingle(type, heading, shares, mask=None, useThumbs=None, treatAsFolder=None, default=None):  # pylint: disable=redefined-builtin
        ''' A stub implementation for the xbmcgui Dialog class browseSingle() method '''
        print('\033[37;44;1mBROWSESINGLE:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (type, heading))
        return 'special://masterprofile/addon_data/script.module.inputstreamhelper/'


class DialogProgress(object):
    ''' A reimplementation of the xbmcgui DialogProgress '''

    def __init__(self):
        ''' A stub constructor for the xbmcgui DialogProgress class '''
        self.percentage = 0

    @staticmethod
    def close():
        ''' A stub implementation for the xbmcgui DialogProgress class close() method '''
        print()

    @staticmethod
    def create(heading, line1, line2=None, line3=None):
        ''' A stub implementation for the xbmcgui DialogProgress class create() method '''
        heading = kodi_to_ansi(heading)
        line1 = kodi_to_ansi(line1)
        print('\033[37;44;1mPROGRESS:\033[35;49;1m [%s] \033[37;1m%s\033[39;0m' % (heading, line1))

    @staticmethod
    def iscanceled():
        ''' A stub implementation for the xbmcgui DialogProgress class iscanceled() method '''

    def update(self, percentage, line1=None, line2=None, line3=None):
        ''' A stub implementation for the xbmcgui DialogProgress class update() method '''
        if (percentage - 5) < self.percentage:
            return
        self.percentage = percentage
        line1 = kodi_to_ansi(line1)
        line2 = kodi_to_ansi(line2)
        line3 = kodi_to_ansi(line3)
        if line1 or line2 or line3:
            print('\033[37;44;1mPROGRESS:\033[35;49;1m [%d%%] \033[37;1m%s\033[39;0m' % (percentage, line1 or line2 or line3))
        else:
            print('\033[1G\033[37;44;1mPROGRESS:\033[35;49;1m [%d%%]\033[39;0m' % (percentage), end='')


class DialogBusy(object):
    ''' A reimplementation of the xbmcgui DialogBusy '''

    def __init__(self):
        ''' A stub constructor for the xbmcgui DialogBusy class '''

    @staticmethod
    def close():
        ''' A stub implementation for the xbmcgui DialogBusy class close() method '''

    @staticmethod
    def create():
        ''' A stub implementation for the xbmcgui DialogBusy class create() method '''


class ListItem(object):
    ''' A reimplementation of the xbmcgui ListItem class '''

    def __init__(self, label='', label2='', iconImage='', thumbnailImage='', path='', offscreen=False):
        ''' A stub constructor for the xbmcgui ListItem class '''
        self.label = kodi_to_ansi(label)
        self.label2 = kodi_to_ansi(label2)
        self.path = path
        self._info = {
            'type': None,
            'infoLabels': InfoTagVideo(),
            'art': {},
            'properties': {}
        }

    @staticmethod
    def addContextMenuItems(items, replaceItems=False):
        ''' A stub implementation for the xbmcgui ListItem class addContextMenuItems() method '''
        return

    @staticmethod
    def addStreamInfo(stream_type, stream_values):
        ''' A stub implementation for the xbmcgui LitItem class addStreamInfo() method '''
        return

    def getArt(self, key):
        ''' A stub implementation for the xbmcgui ListItem class getArt() method '''
        return self._info['art'].get(key, '')

    def setArt(self, values):
        ''' A stub implementation for the xbmcgui ListItem class setArt() method '''
        self._info['art'] = values

    @staticmethod
    def setContentLookup(enable):
        ''' A stub implementation for the xbmcgui ListItem class setContentLookup() method '''
        return

    def getVideoInfoTag(self):
        ''' A stub implementation for the xbmcgui ListItem class getVideoInfoTag() method '''
        return self._info['infoLabels']

    def setInfo(self, type, infoLabels):  # pylint: disable=redefined-builtin
        ''' A stub implementation for the xbmcgui ListItem class setInfo() method '''
        self._info['infoLabels'] = InfoTagVideo(infoLabels)

    @staticmethod
    def setIsFolder(is_folder):
        ''' A stub implementation for the xbmcgui ListItem class setIsFolder() method '''
        return

    @staticmethod
    def setMimeType(mimetype):
        ''' A stub implementation for the xbmcgui ListItem class setMimeType() method '''
        return

    def setPath(self, path):
        ''' A stub implementation for the xbmcgui ListItem class setPath() method '''
        self.path = path

    def getProperty(self, key):
        ''' A stub implementation for the xbmcgui ListItem class getProperty() method '''
        return self._info['properties'].get(key, '')

    def setProperty(self, key, value):
        ''' A stub implementation for the xbmcgui ListItem class setProperty() method '''
        self._info['properties'][key] = value

    @staticmethod
    def setSubtitles(subtitleFiles):
        ''' A stub implementation for the xbmcgui ListItem class setSubtitles() method '''
        return


class Window(object):
    ''' A reimplementation of the xbmcgui Window '''

    __window_properties__ = {}

    def __init__(self, existingwindowId=-1):
        ''' A stub constructor for the xbmcgui Window class '''
        self.__window_properties__ = {}
        try:
            getattr(self, 'onInit')()
        except (AttributeError, TypeError):
            pass

    def clearProperty(self, key):
        ''' A stub implementation for the xbmcgui Window class clearProperty() method '''
        self.__window_properties__.pop(key, '')

    def close(self):
        ''' A stub implementation for the xbmcgui Window class close() method '''

    @staticmethod
    def getControl(controlID):
        ''' A stub implementation for the xbmcgui Window class getControl() method '''
        if controlID == 3014:
            return ControlProgress()
        return ControlLabel(0, 0, 10, 10, 'Label')

    def getProperty(self, key):
        ''' A stub implementation for the xbmcgui Window class getProperty() method '''
        if not isinstance(key, str if __KODI_MATRIX__ else (str, unicode)):  # noqa: F821; pylint: disable=undefined-variable,useless-suppression
            raise TypeError('Property name is not str or unicode')
        return self.__window_properties__.get(key, '')

    def setProperty(self, key, value):
        ''' A stub implementation for the xbmcgui Window class setProperty() method '''
        if not isinstance(key, str if __KODI_MATRIX__ else (str, unicode)):  # noqa: F821; pylint: disable=undefined-variable,useless-suppression
            raise TypeError('Property name is not str or unicode')
        if not isinstance(value, str if __KODI_MATRIX__ else (str, unicode)):  # noqa: F821; pylint: disable=undefined-variable,useless-suppression
            raise TypeError('Property value is not str or unicode')
        self.__window_properties__[key] = value

    def show(self):
        ''' A stub implementation for the xbmcgui Window class show() method '''


class WindowXML(Window):
    ''' A reimplementation of the xbmcgui WindowXML '''

    def __init__(
            self, xmlFilename, scriptPath,
            defaultSkin="Default", defaultRes="720p", isMedia=False
    ):
        ''' A stub constructor for the xbmcgui WindowXML class '''
        super(WindowXML, self).__init__()


class WindowXMLDialog(WindowXML):
    ''' A reimplementation of the xbmcgui WindowXMLDialog '''

    def __init__(
            self, xmlFilename, scriptPath,
            defaultSkin="Default", defaultRes="720p"
    ):
        ''' A stub constructor for the xbmcgui WindowXMLDialog class '''
        super(WindowXMLDialog, self).__init__(
            xmlFilename, scriptPath, defaultSkin, defaultRes
        )
