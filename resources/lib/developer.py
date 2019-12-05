# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import Player, sleep
from .pages import set_up_developer_pages
from .utils import clear_property, get_setting, load_test_data, set_property


class Developer:
    _shared_state = {}

    def __init__(self):
        self.__dict__ = self._shared_state

    @staticmethod
    def developer_play_back():
        episode = load_test_data()
        next_up_page, next_up_page_simple, still_watching_page, still_watching_page_simple = (
            set_up_developer_pages(episode))
        window_mode = int(get_setting('windowMode'))
        if window_mode == 0:
            next_up_page.show()
        elif window_mode == 1:
            next_up_page_simple.show()
        elif window_mode == 2:
            still_watching_page.show()
        elif window_mode == 3:
            still_watching_page_simple.show()
        set_property('service.upnext.dialog', 'true')

        player = Player()
        while (player.isPlaying() and not next_up_page.is_cancel()
               and not next_up_page.is_watch_now() and not still_watching_page.is_still_watching()
               and not still_watching_page.is_cancel()):
            sleep(100)
            next_up_page.update_progress_control()
            next_up_page_simple.update_progress_control()
            still_watching_page.update_progress_control()
            still_watching_page_simple.update_progress_control()

        if window_mode == 0:
            next_up_page.close()
        elif window_mode == 1:
            next_up_page_simple.close()
        elif window_mode == 2:
            still_watching_page.close()
        elif window_mode == 3:
            still_watching_page_simple.close()
        clear_property('service.upnext.dialog')
