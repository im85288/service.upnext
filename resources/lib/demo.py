# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements UpNext demo mode functions used for runtime testing UpNext"""

from __future__ import absolute_import, division, unicode_literals
from settings import SETTINGS
import constants
import plugin
import upnext
import utils


def log(msg, level=utils.LOGDEBUG):
    utils.log(msg, name=__name__, level=level)


def handle_demo_mode(player, state, now_playing_item, called=[False]):  # pylint: disable=dangerous-default-value
    if not SETTINGS.demo_mode or called[0]:
        called[0] = False
        return

    utils.notification('UpNext demo mode', 'Active')
    log('Active')

    # Force use of plugin data method if demo plugin mode is enabled
    if state.get_plugin_type() is None and SETTINGS.demo_plugin:
        addon_id = utils.get_addon_id()
        upnext_info = plugin.generate_library_plugin_data(
            now_playing_item, addon_id, state
        )
        if upnext_info:
            log('Plugin data sent')
            called[0] = True
            upnext.send_signal(addon_id, upnext_info)

    # Seek to 15s before end of video
    if SETTINGS.demo_seek == constants.DEMO_SEEK_15S:
        seek_time = player.getTotalTime() - 15
    # Seek to popup start time
    elif SETTINGS.demo_seek == constants.DEMO_SEEK_POPUP_TIME:
        seek_time = state.get_popup_time()
    # Seek to detector start time
    elif SETTINGS.demo_seek == constants.DEMO_SEEK_DETECT_TIME:
        seek_time = state.get_detect_time() or state.get_popup_time()
    else:
        return

    with player as check_fail:
        log('Seeking to end')
        player.seekTime(seek_time)

        # Seek workaround required for AML HW decoder on certain problematic
        # H.265 encodes to avoid buffer desync and playback hangs
        utils.wait(3)
        if player.getTime() <= seek_time:
            log('Seek workaround')
            player.seekTime(seek_time + 3)

        check_fail = False
    if check_fail:
        log('Error: demo seek, nothing playing', utils.LOGWARNING)
