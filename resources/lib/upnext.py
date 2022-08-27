# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions for video plugins to interact with UpNext"""

from __future__ import absolute_import, division, unicode_literals
import xbmc
import xbmcgui
import constants
import utils


def log(msg, level=utils.LOGWARNING):
    utils.log(msg, name=__name__, level=level)


def _copy_episode_details(upnext_data):
    # If next episode information is not provided, fake it
    if not upnext_data.get('next_episode'):
        episode = upnext_data['current_episode']
        episode['episodeid'] = constants.UNDEFINED
        episode['art'] = {}
        # Next provided episode may not be the next consecutive episode so we
        # can't assume that the episode can simply be incremented, instead set
        # title to indicate the next episode in the UpNext popup
        # episode['episode'] = utils.get_int(episode, 'episode') + 1
        episode['title'] = utils.localize(constants.NEXT_STRING_ID)
        # Change season and episode info to empty string to avoid episode
        # formatting issues ("S-1E-1") in UpNext popup
        episode['season'] = ''
        episode['episode'] = ''
        episode['plot'] = ''
        episode['playcount'] = 0
        episode['rating'] = 0
        episode['firstaired'] = ''
        episode['runtime'] = 0
        upnext_data['next_episode'] = episode

    # If current episode information is not provided, fake it
    elif not upnext_data.get('current_episode'):
        episode = upnext_data['next_episode']
        episode['episodeid'] = constants.UNDEFINED
        episode['art'] = {}
        episode['title'] = ''
        episode['season'] = ''
        episode['episode'] = ''
        episode['plot'] = ''
        episode['playcount'] = 0
        episode['rating'] = 0
        episode['firstaired'] = ''
        episode['runtime'] = 0
        upnext_data['current_episode'] = episode

    return upnext_data


def create_listitem(episode):
    """Create a xbmcgui.ListItem from provided episode details"""

    show_title = episode.get('showtitle', '')
    episode_title = episode.get('title', '')
    file_path = episode.get('file', '')
    season = episode.get('season', '')
    episode_number = episode.get('episode', '')
    season_episode = (
        '{0}x{1}'.format(season, episode_number) if season and episode_number
        else episode_number
    )
    label_tokens = [show_title, season_episode, episode_title]

    kwargs = {
        'label': ' - '.join(token for token in label_tokens if token),
        'path': file_path
    }
    if utils.supports_python_api(18):
        kwargs['offscreen'] = True

    listitem = xbmcgui.ListItem(**kwargs)
    listitem.setInfo(
        type='Video',
        infoLabels={
            'dbid': episode.get('episodeid', constants.UNDEFINED),
            'path': file_path,
            'title': episode_title,
            'plot': episode.get('plot', ''),
            'tvshowtitle': show_title,
            'season': season or constants.UNDEFINED,
            'episode': episode_number or constants.UNDEFINED,
            'rating': str(float(episode.get('rating', 0.0))),
            'aired': episode.get('firstaired', ''),
            'premiered': episode.get('firstaired', ''),
            'year': utils.get_year(episode.get('firstaired', '')),
            'dateadded': episode.get('dateadded', ''),
            'lastplayed': episode.get('lastplayed', ''),
            'playcount': episode.get('playcount', 0),
            'mediatype': 'episode'
        }
    )

    resume = episode.get('resume', {})
    listitem.setProperty('resumetime', str(resume.get('position')))
    listitem.setProperty('totaltime', str(resume.get('total')))

    listitem.setProperty(
        'tvshowid', str(episode.get('tvshowid', constants.UNDEFINED))
    )

    listitem.setArt(episode.get('art', {}))

    listitem.setProperty('isPlayable', 'true')
    listitem.setPath(file_path)
    if utils.supports_python_api(18):
        listitem.setIsFolder(False)

    return listitem


def send_signal(sender, upnext_info):
    """Helper function for video plugins to send data to UpNext"""

    # Exit if not enough information provided by video plugin
    required_episode_info = ['current_episode', 'next_episode']
    required_plugin_info = ['play_url', 'play_info']
    if not (any(info in upnext_info for info in required_episode_info)
            and any(info in upnext_info for info in required_plugin_info)):
        log('Invalid UpNext info - {0}'.format(upnext_info), utils.LOGWARNING)
        return

    # Extract ListItem or InfoTagVideo details for use by UpNext
    upnext_data = {}
    for key, val in upnext_info.items():
        thumb = ''
        fanart = ''
        tvshowid = str(constants.UNDEFINED)

        if key in required_plugin_info:
            upnext_data[key] = val
            continue

        if isinstance(val, xbmcgui.ListItem):
            thumb = val.getArt('thumb')
            fanart = val.getArt('fanart')
            tvshowid = val.getProperty('tvshowid')
            val = val.getVideoInfoTag()

        if not isinstance(val, xbmc.InfoTagVideo):
            continue

        # Use show title as substitute for missing ListItem tvshowid
        tvshowid = (
            tvshowid if tvshowid != str(constants.UNDEFINED)
            else val.getTVShowTitle()
        ) or constants.UNDEFINED
        # Fallback for available date information
        firstaired = val.getFirstAired() or val.getPremiered() or val.getYear()
        # Runtime used to evaluate endtime in UpNext popup, if available
        runtime = val.getDuration() if utils.supports_python_api(18) else 0
        # Prefer outline over full plot for UpNext popup
        plot = val.getPlotOutline() or val.getPlot()
        # Prefer user rating over scraped rating
        rating = val.getUserRating() or val.getRating()

        upnext_data[key] = {
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

    upnext_data = _copy_episode_details(upnext_data)

    utils.event(
        sender=sender,
        message='upnext_data',
        data=upnext_data,
        encoding='base64'
    )
