# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import datetime
import exceptions
import platform
import xbmcgui
import statichelper
import utils

OS_MACHINE = platform.machine()


class UpNextPopup(xbmcgui.WindowXMLDialog):
    """Class for Up Next popup state variables and methods"""

    def __init__(self, *args, **kwargs):
        # Set info here rather than onInit to avoid dialog update flash
        self.item = kwargs.get('item')
        self.set_info()
        self.cancel = False
        self.stop = False
        self.playnow = False
        self.countdown_total_time = None
        self.current_progress_percent = 100
        self.progress_control = None

        # TODO: Figure out why this is required. Issues with iOS?
        if OS_MACHINE[0:5] == 'armv7':
            xbmcgui.WindowXMLDialog.__init__(self)
        else:
            xbmcgui.WindowXMLDialog.__init__(self, *args)
        self.log('Init - %s' % args[0], 2)

    def __enter__(self):
        return True

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type == exceptions.AttributeError:
            return True

    @classmethod
    def log(cls, msg, level=2):
        utils.log(msg, name=cls.__name__, level=level)

    def onInit(self):  # pylint: disable=invalid-name
        try:
            self.progress_control = self.getControl(3014)
        # Occurs when skin does not include progress control
        except RuntimeError:
            self.progress_control = None
        else:
            self.update_progress_control()

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

    def set_item(self, item):
        self.item = item

    def update_progress(self, remaining):
        # Run time and end time for next episode
        runtime = utils.get_int(self.item, 'runtime', 0)
        if runtime:
            runtime = datetime.timedelta(seconds=runtime)
            endtime = datetime.datetime.now() + runtime
            endtime = statichelper.from_unicode(utils.localize_time(endtime))
            self.setProperty('endtime', endtime)

        # Remaining time countdown for current episode
        remaining_str = statichelper.from_unicode('%02d' % remaining)
        self.setProperty('remaining', remaining_str)

        if not self.progress_control:
            return

        # Set total countdown time on initial progress update
        if remaining and self.countdown_total_time is None:
            self.countdown_total_time = remaining
        # Calculate countdown progress on subsequent updates
        elif remaining:
            percent = 100 * remaining / self.countdown_total_time
            self.current_progress_percent = min(100, max(0, percent))

        self.update_progress_control()

    def update_progress_control(self):
        self.progress_control.setPercent(self.current_progress_percent)  # pylint: disable=no-member,useless-suppression

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
            self.set_stop(True)
            self.close()
        elif action == xbmcgui.ACTION_NAV_BACK:
            self.set_cancel(True)
            self.close()
