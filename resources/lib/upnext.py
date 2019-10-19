# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from platform import machine
import xbmc
import xbmcgui
from . import utils

ACTION_PLAYER_STOP = 13
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

    def set_info(self):
        episode_info = str(self.item['season']) + 'x' + str(self.item['episode']) + '.'
        if self.item['rating'] is not None:
            rating = str(round(float(self.item['rating']), 1))
        else:
            rating = None

        if self.item is not None:
            self.setProperty(
                'fanart', self.item['art'].get('tvshow.fanart', ''))
            self.setProperty(
                'landscape', self.item['art'].get('tvshow.landscape', ''))
            self.setProperty(
                'clearart', self.item['art'].get('tvshow.clearart', ''))
            self.setProperty(
                'clearlogo', self.item['art'].get('tvshow.clearlogo', ''))
            self.setProperty(
                'poster', self.item['art'].get('tvshow.poster', ''))
            self.setProperty(
                'thumb', self.item['art'].get('thumb', ''))
            self.setProperty(
                'plot', self.item['plot'])
            self.setProperty(
                'tvshowtitle', self.item['showtitle'])
            self.setProperty(
                'title', self.item['title'])
            self.setProperty(
                'season', str(self.item['season']))
            self.setProperty(
                'episode', str(self.item['episode']))
            self.setProperty(
                'seasonepisode', episode_info)
            self.setProperty(
                'year', str(self.item['firstaired']))
            self.setProperty(
                'rating', rating)
            self.setProperty(
                'playcount', str(self.item['playcount']))

    def prepare_progress_control(self):
        # noinspection PyBroadException
        try:
            self.progress_control = self.getControl(3014)
            if self.progress_control is not None:
                self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member
        except Exception:  # pylint: disable=broad-except
            pass

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, progress_step_size):
        self.progress_step_size = progress_step_size

    def update_progress_control(self, endtime=None):
        # noinspection PyBroadException
        try:
            self.current_progress_percent = self.current_progress_percent - self.progress_step_size
            self.progress_control = self.getControl(3014)
            if self.progress_control is not None:
                self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member
            if endtime:
                self.setProperty('endtime', str(endtime))
        except Exception:  # pylint: disable=broad-except
            pass

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
        if controlId == 3012:
            # watch now
            self.set_watch_now(True)
            self.close()
        elif controlId == 3013:
            # cancel
            self.set_cancel(True)
            if utils.settings("stopAfterClose") == "true":
                xbmc.Player().stop()
            self.close()

    def onAction(self, action):  # pylint: disable=invalid-name
        if action == ACTION_PLAYER_STOP:
            self.close()
