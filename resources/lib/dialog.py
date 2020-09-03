# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import platform
import xbmcgui
import statichelper
import utils

OS_MACHINE = platform.machine()


class UpNextPopup(xbmcgui.WindowXMLDialog):
    """Class for Up Next popup state variables and methods"""

    def __init__(self, *args, **kwargs):
        self.item = kwargs.get('item')
        self.cancel = False
        self.stop = False
        self.playnow = False
        self.progress_step_size = 0
        self.current_progress_percent = 100
        self.progress_control = None

        # TODO: Figure out why this is required. Issues with iOS?
        if OS_MACHINE[0:5] == 'armv7':
            xbmcgui.WindowXMLDialog.__init__(self)
        else:
            xbmcgui.WindowXMLDialog.__init__(self, *args)
        self.log('Init: %s' % args[0], 2)

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def onInit(self):  # pylint: disable=invalid-name
        self.set_info()
        self.prepare_progress_control()

        if utils.get_setting_bool('stopAfterClose'):
            self.getControl(3013).setLabel(utils.localize(30033))  # Stop
        else:
            self.getControl(3013).setLabel(utils.localize(30034))  # Close

    def set_info(self):
        episode_info = '%(season)sx%(episode)s.' % self.item
        if self.item.get('rating') is None:
            rating = ''
        else:
            rating = str(round(float(self.item.get('rating')), 1))

        if self.item is not None:
            art = self.item.get('art')
            self.setProperty('fanart', art.get('tvshow.fanart', ''))
            self.setProperty('landscape', art.get('tvshow.landscape', ''))
            self.setProperty('clearart', art.get('tvshow.clearart', ''))
            self.setProperty('clearlogo', art.get('tvshow.clearlogo', ''))
            self.setProperty('poster', art.get('tvshow.poster', ''))
            self.setProperty('thumb', art.get('thumb', ''))
            self.setProperty('plot', self.item.get('plot', ''))
            self.setProperty('tvshowtitle', self.item.get('showtitle', ''))
            self.setProperty('title', self.item.get('title', ''))
            self.setProperty('season', str(self.item.get('season', '')))
            self.setProperty('episode', str(self.item.get('episode', '')))
            self.setProperty('seasonepisode', episode_info)
            self.setProperty('year', str(self.item.get('firstaired', '')))
            self.setProperty('rating', rating)
            self.setProperty('playcount', str(self.item.get('playcount', 0)))
            self.setProperty('runtime', str(self.item.get('runtime', '')))

    def prepare_progress_control(self):
        try:
            self.progress_control = self.getControl(3014)
        # Occurs when skin does not include progress control
        except RuntimeError:
            pass
        else:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression

    def set_item(self, item):
        self.item = item

    def set_progress_step_size(self, remaining, delta):
        """Calculate a progress step"""
        if int(remaining) == 0:  # Avoid division by zero
            self.progress_step_size = 10.0
        self.progress_step_size = delta * 100.0 / int(remaining)

    def update_progress_control(self, remaining):
        self.current_progress_percent -= self.progress_step_size
        try:
            self.progress_control = self.getControl(3014)
        # Occurs when skin does not include progress control
        except RuntimeError:
            pass
        else:
            self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression

        remaining = statichelper.from_unicode('%02d' % remaining)
        self.setProperty('remaining', remaining)

        # Run time and end time for next episode
        runtime = utils.get_int(self.item, 'runtime', 0)
        if runtime:
            runtime = datetime.timedelta(seconds=runtime)
            endtime = datetime.datetime.now() + runtime
            endtime = statichelper.from_unicode(utils.localize_time(endtime))
            self.setProperty('endtime', endtime)

    def set_cancel(self, cancel):
        self.cancel = cancel

    def is_cancel(self):
        return self.cancel

    def set_stop(self, stop):
        self.stop = stop

    def is_stop(self):
        return self.stop

    def set_playnow(self, playnow):
        self.playnow = playnow

    def is_playnow(self):
        return self.playnow

    def onFocus(self, controlId):  # pylint: disable=invalid-name
        pass

    def doAction(self):  # pylint: disable=invalid-name
        pass

    def closeDialog(self):  # pylint: disable=invalid-name
        self.close()

    def onClick(self, controlId):  # pylint: disable=invalid-name
        # Play now - Watch now / Still Watching
        if controlId == 3012:
            self.set_playnow(True)
            self.close()
        # Cancel - Close / Stop
        elif controlId == 3013:
            self.set_cancel(True)
            if utils.get_setting_bool('stopAfterClose'):
                self.set_stop(True)
            self.close()

    def onAction(self, action):  # pylint: disable=invalid-name
        if action == xbmcgui.ACTION_STOP:
            self.close()
        elif action == xbmcgui.ACTION_NAV_BACK:
            self.set_cancel(True)
            self.close()
