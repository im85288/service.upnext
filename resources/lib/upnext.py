# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from platform import machine
import xbmc
import xbmcgui
from . import utils
from .statichelper import from_unicode

ACTION_PLAYER_STOP = 13
ACTION_NAV_BACK = 92
OS_MACHINE = machine()


class UpNext(xbmcgui.WindowXMLDialog):
    item = None
    cancel = False
    watchnow = False
    progress_step_size = 0
    current_progress_percent = 100

    def __init__(self, *args, **kwargs):
        self.action_exitkeys_id = [10, 13]
        self.progress_control = None
        if OS_MACHINE[0:5] == 'armv7':
            xbmcgui.WindowXMLDialog.__init__(self)
        else:
            xbmcgui.WindowXMLDialog.__init__(self, *args, **kwargs)

    def onInit(self):  # pylint: disable=invalid-name
        self.set_info()
        self.prepare_progress_control()

        if utils.settings('stopAfterClose') == 'true':
            self.getControl(3013).setLabel(utils.localize(30033))  # Stop
        else:
            self.getControl(3013).setLabel(utils.localize(30034))  # Close

    def set_info(self):
        episode_info = '%(season)sx%(episode)s.' % self.item
        if self.item.get('rating') is not None:
            rating = round(float(self.item.get('rating')), 1)
        else:
            rating = None

        if self.item is not None:
            art = self.item.get('art')
            self.setProperty('fanart', from_unicode(art.get('tvshow.fanart', '')))
            self.setProperty('landscape', from_unicode(art.get('tvshow.landscape', '')))
            self.setProperty('clearart', from_unicode(art.get('tvshow.clearart', '')))
            self.setProperty('clearlogo', from_unicode(art.get('tvshow.clearlogo', '')))
            self.setProperty('poster', from_unicode(art.get('tvshow.poster', '')))
            self.setProperty('thumb', from_unicode(art.get('thumb', '')))
            self.setProperty('plot', from_unicode(self.item.get('plot', '')))
            self.setProperty('tvshowtitle', from_unicode(self.item.get('showtitle', '')))
            self.setProperty('title', from_unicode(self.item.get('title', '')))
            self.setProperty('season', from_unicode(str(self.item.get('season', ''))))
            self.setProperty('episode', from_unicode(str(self.item.get('episode', ''))))
            self.setProperty('seasonepisode', from_unicode(episode_info))
            self.setProperty('year', from_unicode(str(self.item.get('firstaired', ''))))
            self.setProperty('rating', from_unicode(rating))
            self.setProperty('playcount', from_unicode(self.item.get('playcount', '')))

    def prepare_progress_control(self):
        self.progress_control = self.getControl(3014)
        if self.progress_control is not None:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, progress_step_size):
        self.progress_step_size = progress_step_size

    def update_progress_control(self, endtime=None):
        self.current_progress_percent = self.current_progress_percent - self.progress_step_size
        self.progress_control = self.getControl(3014)
        if self.progress_control is not None:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member
        if endtime:
            self.setProperty('endtime', from_unicode(str(endtime)))

    def set_cancel(self, cancel):
        self.cancel = cancel

    def is_cancel(self):
        return self.cancel

    def set_watch_now(self, watchnow):
        self.watchnow = watchnow

    def is_watch_now(self):
        return self.watchnow

    def onFocus(self, controlId):  # pylint: disable=invalid-name
        pass

    def doAction(self):  # pylint: disable=invalid-name
        pass

    def closeDialog(self):  # pylint: disable=invalid-name
        self.close()

    def onClick(self, controlId):  # pylint: disable=invalid-name
        if controlId == 3012:  # Watch now
            self.set_watch_now(True)
            self.close()
        elif controlId == 3013:  # Close / Stop
            self.set_cancel(True)
            if utils.settings('stopAfterClose') == 'true':
                xbmc.Player().stop()
            self.close()

    def onAction(self, action):  # pylint: disable=invalid-name
        if action == ACTION_PLAYER_STOP:
            self.close()
        elif action == ACTION_NAV_BACK:
            self.set_cancel(True)
            self.close()
