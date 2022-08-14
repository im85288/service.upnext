# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""This is the actual UpNext plugin handler"""

from __future__ import absolute_import, division, unicode_literals
import xbmcgui
import xbmcplugin
import api
import constants
import upnext
import utils

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
        next_episode, _ = api.get_next_from_library(current_episode.copy())

    if not next_episode:
        return None

    next_dbid = next_episode.get('episodeid')
    current_episode = upnext.create_listitem(current_episode)
    next_episode = upnext.create_listitem(next_episode)

    upnext_info = {
        'current_episode': current_episode,
        'next_episode': next_episode,
        'play_url': 'plugin://{0}/play/?dbid={1}'.format(addon_id, next_dbid)
    }
    return upnext_info


def generate_listing(addon_handle, addon_id, items):  # pylint: disable=unused-argument
    listing = []
    for item in items:
        content = PLUGIN_CONTENT.get(item)
        if not content:
            continue

        url = 'plugin://{0}{1}'.format(addon_id, item)
        listitem = xbmcgui.ListItem(
            label=content.get('label', ''), path=url, offscreen=True
        )
        if 'art' in content:
            listitem.setArt(content.get('art'))
        is_folder = content.get('content_type') != 'action'

        listing += ((url, listitem, is_folder),)

    return listing


def generate_next_episodes_list(addon_handle, addon_id, **kwargs):  # pylint: disable=unused-argument
    pass


def generate_next_movies_list(addon_handle, addon_id, **kwargs):  # pylint: disable=unused-argument
    pass


def generate_next_media_list(addon_handle, addon_id, **kwargs):  # pylint: disable=unused-argument
    pass


def open_settings(addon_handle, addon_id, **kwargs):  # pylint: disable=unused-argument
    utils.get_addon(addon_id).openSettings()
    return True


def parse_plugin_url(url):
    if not url:
        return None, None, None

    parsed_url = urlparse(url)
    addon_type = parsed_url.scheme
    if addon_type != 'plugin':
        return None, None, None

    addon_id = parsed_url.netloc
    addon_path = parsed_url.path.rstrip('/') or '/'
    addon_args = parse_qs(parsed_url.query)

    return addon_id, addon_path, addon_args


def play_media(addon_handle, addon_id, **kwargs):
    dbid = int(kwargs.get('dbid', [constants.UNDEFINED])[0])
    if dbid == constants.UNDEFINED:
        return False

    current_episode = api.get_from_library(dbid)
    upnext_info = generate_library_plugin_data(
        current_episode=current_episode,
        addon_id=addon_id
    ) if current_episode else None

    if upnext_info:
        resolved = True
        upnext.send_signal(addon_id, upnext_info)
    else:
        resolved = False
        upnext_info = {'current_episode': upnext.create_listitem({})}

    xbmcplugin.setResolvedUrl(
        addon_handle, resolved, upnext_info['current_episode']
    )
    return resolved


def run(argv):
    addon_handle = int(argv[1])
    addon_id, addon_path, addon_args = parse_plugin_url(argv[0] + argv[2])
    content = PLUGIN_CONTENT.get(addon_path)
    if not content:
        return False

    content_type = content.get('content_type')
    content_items = content.get('items')
    content_handler = content.get('handler')

    if content_type == 'action' and content_handler:
        return content_handler(addon_handle, addon_id, **addon_args)

    if content_handler:
        content_items = content_handler(addon_handle, addon_id, **addon_args)
    elif content_items:
        content_items = generate_listing(addon_handle, addon_id, content_items)

    if content_type and content_items:
        xbmcplugin.setContent(addon_handle, content_type)
        listing_complete = xbmcplugin.addDirectoryItems(
            addon_handle, content_items, len(content_items)
        )
    else:
        listing_complete = False

    xbmcplugin.endOfDirectory(
        addon_handle, listing_complete, updateListing=False, cacheToDisc=True
    )
    return listing_complete


PLUGIN_CONTENT = {
    '/': {
        'label': 'Home',
        'content_type': 'files',
        'items': [
            '/next_episodes',
            '/next_movies',
            '/next_media',
            '/settings',
        ],
    },
    '/next_episodes': {
        'label': 'In-progress and Next-up Episodes',
        'art': {
            'icon': 'DefaultInProgressShows.png',
        },
        'content_type': 'episodes',
        'handler': generate_next_episodes_list,
    },
    '/next_movies': {
        'label': 'In-progress and Next-up Movies',
        'art': {
            'icon': 'DefaultMovies.png',
        },
        'content_type': 'movies',
        'handler': generate_next_movies_list,
    },
    '/next_media': {
        'label': 'In-progress and Next-up Media',
        'art': {
            'icon': 'DefaultVideo.png'
        },
        'content_type': 'videos',
        'handler': generate_next_media_list,
    },
    '/settings': {
        'label': 'Settings',
        'art': {
            'icon': 'DefaultAddonProgram.png'
        },
        'content_type': 'action',
        'handler': open_settings,
    },
    '/play': {
        'content_type': 'action',
        'handler': play_media,
    },
}
