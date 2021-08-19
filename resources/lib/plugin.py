# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext plugin handler"""

from __future__ import absolute_import, division, unicode_literals
import xbmcplugin
import api
import constants
import upnext

try:
    from urllib.parse import parse_qs, urlparse
except ImportError:
    from urlparse import parse_qs, urlparse


def generate_library_plugin_data(current_episode, addon_id, state=None):
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


def parse_plugin_url(url):
    if not url:
        return None, None
    parsed_url = urlparse(url)
    if parsed_url.scheme != 'plugin':
        return None, None
    return parsed_url, parse_qs(parsed_url.query)


def handler(argv):
    plugin_url, args = parse_plugin_url(argv[0] + argv[2])
    if not plugin_url:
        return False

    dbid = int(args.get('play', [constants.UNDEFINED])[0])
    if dbid == constants.UNDEFINED:
        return False

    current_episode = api.get_from_library(dbid)
    if not current_episode:
        xbmcplugin.setResolvedUrl(
            int(argv[1]), False, upnext.create_listitem({})
        )
        return False

    upnext_info = generate_library_plugin_data(
        current_episode=current_episode,
        addon_id=plugin_url.netloc
    )
    if not upnext_info:
        xbmcplugin.setResolvedUrl(
            int(argv[1]), False, upnext.create_listitem({})
        )
        return False

    xbmcplugin.setResolvedUrl(
        int(argv[1]), True, upnext_info['current_episode']
    )
    upnext.send_signal(plugin_url.netloc, upnext_info)
    return True
