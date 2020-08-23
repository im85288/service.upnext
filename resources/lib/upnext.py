# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import InfoTagVideo
from xbmcgui import ListItem
from utils import event, log as ulog


def log(msg, level=2):
    ulog(msg, name=__name__, level=level)


def send_signal(sender, upnext_info):
    """Helper function for plugins to send up next data to UpNext"""
    # Exit if not enough addon information provided
    info_check = (
        (upnext_info.get('play_url') or upnext_info.get('play_info'))
        and upnext_info.get('current_episode')
    )
    if not info_check:
        log('Sending invalid Up Next info: %s' % upnext_info, 1)
        return

    # Extract ListItem or InfoTagVideo details for use by Up Next
    for key, val in upnext_info.items():
        thumb = ''
        fanart = ''
        if isinstance(val, ListItem):
            thumb = val.getArt('thumb')
            fanart = val.getArt('fanart')
            val = val.getVideoInfoTag()

        if isinstance(val, InfoTagVideo):
            upnext_info[key] = dict(
                episodeid=val.getDbId(),
                # Use show title as substitute for missing ListItem tvshowid
                tvshowid=val.getTVShowTitle() or -1,
                title=val.getTitle(),
                art={
                    'thumb': thumb,
                    'tvshow.fanart': fanart,
                },
                season=val.getSeason(),
                episode=val.getEpisode(),
                showtitle=val.getTVShowTitle(),
                plot=val.getPlotOutline() or val.getPlot(),
                playcount=val.getPlayCount(),
                rating=val.getUserRating() or int(val.getRating()),
                firstaired=(
                    val.getFirstAired()
                    or val.getPremiered()
                    or val.getYear()
                ),
                runtime=val.getDuration()
            )

    # If next episode information is not provided, fake it
    if not upnext_info.get('next_episode'):
        episode = upnext_info['current_episode']
        episode['episodeid'] = -1
        episode['art'] = {}
        # Next provided episode may not be the next consecutive episode so we
        # can't assume that the episode can simply be incremented, instead set
        # title to indicate the next episode in the Up Next popup
        # from utils import get_int
        # episode['episode'] = get_int(episode, 'episode') + 1
        # TODO: Change to localised string variable for translation purposes
        episode['title'] = 'Next episode'
        # Change season and episode info to empty string to avoid episode
        # formatting issues ("S-1E-1") in Up Next popup
        episode['season'] = ''
        episode['episode'] = ''
        episode['plot'] = ''
        episode['playcount'] = 0
        episode['rating'] = 0
        episode['firstaired'] = ''
        episode['runtime'] = 0
        upnext_info['next_episode'] = episode

    event(
        sender=sender,
        message='upnext_data',
        data=upnext_info,
        encoding='base64'
    )
