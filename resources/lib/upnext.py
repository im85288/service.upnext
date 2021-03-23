# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions for addons to interact with UpNext"""

from __future__ import absolute_import, division, unicode_literals
import xbmc
import xbmcgui
import utils


def log(msg, level=utils.LOGWARNING):
    utils.log(msg, name=__name__, level=level)


def create_listitem(episode):
    """Create a xbmcgui.ListItem from provided episode details"""

    kwargs = {
        'label': episode.get('title', ''),
        'label2': '',
        'path': episode.get('file', '')
    }
    if utils.supports_python_api(18):
        kwargs['offscreen'] = True

    listitem = xbmcgui.ListItem(**kwargs)
    listitem.setInfo(
        type='Video',
        infoLabels={
            'dbid': episode.get('episodeid', -1),
            'path': episode.get('file', ''),
            'title': episode.get('title', ''),
            'plot': episode.get('plot', ''),
            'tvshowtitle': episode.get('showtitle', ''),
            'season': episode.get('season', -1),
            'episode': episode.get('episode', -1),
            'rating': str(float(episode.get('rating', 0.0))),
            'premiered': episode.get('firstaired', ''),
            'dateadded': episode.get('dateadded', ''),
            'lastplayed': episode.get('lastplayed', ''),
            'playcount': episode.get('playcount', 0),
            'mediatype': 'episode'
        }
    )
    listitem.setProperty('tvshowid', str(episode.get('tvshowid', -1)))
    listitem.setArt(episode.get('art', {}))
    listitem.setProperty('isPlayable', 'true')
    listitem.setPath(episode.get('file', ''))
    if utils.supports_python_api(18):
        listitem.setIsFolder(False)

    return listitem


def send_signal(sender, upnext_info):
    """Helper function for addons to send data to UpNext"""

    # Exit if not enough addon information provided
    if not (upnext_info.get('current_episode')
            and (upnext_info.get('play_url') or upnext_info.get('play_info'))):
        log('Error: Invalid UpNext info - {0}'.format(upnext_info))
        return

    # Extract ListItem or InfoTagVideo details for use by UpNext
    for key, val in upnext_info.items():
        thumb = ''
        fanart = ''
        tvshowid = '-1'

        if isinstance(val, xbmcgui.ListItem):
            thumb = val.getArt('thumb')
            fanart = val.getArt('fanart')
            tvshowid = val.getProperty('tvshowid')
            val = val.getVideoInfoTag()

        if isinstance(val, xbmc.InfoTagVideo):
            # Use show title as substitute for missing ListItem tvshowid
            tvshowid = (
                (tvshowid if tvshowid != '-1' else val.getTVShowTitle()) or -1
            )
            firstaired = (
                val.getFirstAired()
                or val.getPremiered()
                or val.getYear()
            )
            runtime = (
                val.getDuration() if utils.supports_python_api(18) else 0
            )
            plot = val.getPlotOutline() or val.getPlot()
            rating = val.getUserRating() or int(val.getRating())

            upnext_info[key] = {
                'episodeid': val.getDbId(),
                'tvshowid': tvshowid,
                'title': val.getTitle(),
                'art': {
                    'thumb': thumb,
                    'tvshow.fanart': fanart,
                },
                'season': val.getSeason(),
                'episode': val.getEpisode(),
                'showtitle': val.getTVShowTitle(),
                'plot': plot,
                'playcount': val.getPlayCount(),
                'rating': rating,
                'firstaired': firstaired,
                'runtime': runtime
            }

    # If next episode information is not provided, fake it
    if not upnext_info.get('next_episode'):
        episode = upnext_info['current_episode']
        episode['episodeid'] = -1
        episode['art'] = {}
        # Next provided episode may not be the next consecutive episode so we
        # can't assume that the episode can simply be incremented, instead set
        # title to indicate the next episode in the UpNext popup
        # episode['episode'] = utils.get_int(episode, 'episode') + 1
        episode['title'] = utils.localize(30049)
        # Change season and episode info to empty string to avoid episode
        # formatting issues ("S-1E-1") in UpNext popup
        episode['season'] = ''
        episode['episode'] = ''
        episode['plot'] = ''
        episode['playcount'] = 0
        episode['rating'] = 0
        episode['firstaired'] = ''
        episode['runtime'] = 0
        upnext_info['next_episode'] = episode

    utils.event(
        sender=sender,
        message='upnext_data',
        data=upnext_info,
        encoding='base64'
    )
