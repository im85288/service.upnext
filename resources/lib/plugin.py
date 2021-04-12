# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext plugin handler"""

from __future__ import absolute_import, division, unicode_literals
import xbmcplugin
import api
import constants
import upnext

try:
    from urllib.parse import parse_qs
except ImportError:
    from urlparse import parse_qs


def generate_data(current_episode, addon_id, state=None):
    if state:
        next_episode, source = state.get_next()
        if source != 'library':
            return None
    else:
        next_episode, _ = api.get_next_from_library(episode=current_episode)

    if not next_episode:
        return None

    next_dbid = next_episode.get('episodeid')
    current_episode = upnext.create_listitem(current_episode)
    next_episode = upnext.create_listitem(next_episode)

    upnext_info = {
        'current_episode': current_episode,
        'next_episode': next_episode,
        'play_url': 'plugin://{0}/?play={1}'.format(addon_id, next_dbid)
    }
    return upnext_info


def handler(argv):
    base_url = argv[0]
    addon_id = base_url[len('plugin://'):-1]
    addon_handle = int(argv[1])
    # Query string in form ?field1=value1&field2=value2&field3=value3...
    args = parse_qs(argv[2][1:])

    dbid = int(args.get('play', [constants.UNKNOWN_DATA])[0])
    if dbid == constants.UNKNOWN_DATA:
        return False

    current_episode = api.get_from_library(dbid)
    if not current_episode:
        xbmcplugin.setResolvedUrl(
            addon_handle, False, upnext.create_listitem({})
        )
        return False

    upnext_info = generate_data(current_episode, addon_id)
    if not upnext_info:
        xbmcplugin.setResolvedUrl(
            addon_handle, False, upnext.create_listitem({})
        )
        return False

    xbmcplugin.setResolvedUrl(
        addon_handle, True, upnext_info['current_episode']
    )
    upnext.send_signal(addon_id, upnext_info)
    return True
