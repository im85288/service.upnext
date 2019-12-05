# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from .stillwatching import StillWatching
from .upnext import UpNext
from .utils import addon_path, calculate_progress_steps, get_setting


def set_up_pages():
    if get_setting('simpleMode') == '0':
        next_up_page = UpNext('script-upnext-upnext-simple.xml', addon_path(), 'default', '1080i')
        still_watching_page = StillWatching('script-upnext-stillwatching-simple.xml', addon_path(), 'default', '1080i')
    else:
        next_up_page = UpNext('script-upnext-upnext.xml', addon_path(), 'default', '1080i')
        still_watching_page = StillWatching('script-upnext-stillwatching.xml', addon_path(), 'default', '1080i')
    return next_up_page, still_watching_page


def set_up_developer_pages(episode):
    next_up_page_simple = UpNext('script-upnext-upnext-simple.xml', addon_path(), 'default', '1080i')
    still_watching_page_simple = StillWatching('script-upnext-stillwatching-simple.xml', addon_path(), 'default', '1080i')
    next_up_page = UpNext('script-upnext-upnext.xml', addon_path(), 'default', '1080i')
    still_watching_page = StillWatching('script-upnext-stillwatching.xml', addon_path(), 'default', '1080i')
    next_up_page.set_item(episode)
    next_up_page_simple.set_item(episode)
    still_watching_page.set_item(episode)
    still_watching_page_simple.set_item(episode)
    notification_time = get_setting('autoPlaySeasonTime')
    progress_step_size = calculate_progress_steps(notification_time)
    next_up_page.set_progress_step_size(progress_step_size)
    next_up_page_simple.set_progress_step_size(progress_step_size)
    still_watching_page.set_progress_step_size(progress_step_size)
    still_watching_page_simple.set_progress_step_size(progress_step_size)
    return next_up_page, next_up_page_simple, still_watching_page, still_watching_page_simple
