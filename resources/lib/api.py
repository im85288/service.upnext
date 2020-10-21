# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import os.path
from xbmc import PlayList, PLAYLIST_VIDEO
from utils import (
    event, get_setting_bool, get_setting_int, get_int, jsonrpc, log as ulog
)


EPISODE_PROPERTIES = [
    'title',
    'playcount',
    'season',
    'episode',
    'showtitle',
    # 'originaltitle',
    'plot',
    # 'votes',
    'file',
    'rating',
    # 'ratings',
    # 'userrating',
    'resume',
    'tvshowid',
    'firstaired',
    'art',
    'streamdetails',
    'runtime',
    # 'director',
    'writer',
    # 'cast',
    'dateadded',
    'lastplayed'
]

TVSHOW_PROPERTIES = [
    'title',
    'studio',
    'year',
    'plot',
    # 'cast',
    'rating',
    # 'ratings',
    # 'userrating',
    # 'votes',
    'genre',
    'episode',
    'season',
    'runtime',
    'mpaa',
    'premiered',
    'playcount',
    'lastplayed',
    # 'sorttitle',
    # 'originaltitle',
    'art',
    'tag',
    'dateadded',
    'watchedepisodes',
    # 'imdbnumber'
]


def log(msg, level=2):
    """Log wrapper"""
    ulog(msg, name=__name__, level=level)


def play_kodi_item(episode):
    log('Library: playing - {0}'.format(episode), 2)
    jsonrpc(
        method='Player.Open',
        params=dict(
            item=dict(
                episodeid=get_int(episode, 'episodeid')
            )
        ),
        # Disable resuming, playback from start
        # TODO: Add setting to control playback from start or resume point
        options=dict(
            resume=False
        )
    )


def queue_next_item(data, episode):
    next_item = {}
    if not data:
        next_item.update(episodeid=get_int(episode, 'episodeid'))
    elif data.get('play_url'):
        next_item.update(file=data.get('play_url'))

    if next_item:
        log('Queue: adding - {0}'.format(next_item), 2)
        jsonrpc(
            method='Playlist.Add',
            params=dict(playlistid=PLAYLIST_VIDEO, item=next_item)
        )
    else:
        log('Queue: nothing added', 2)

    return bool(next_item)


def reset_queue():
    log('Queue: removing previously played item', 2)
    jsonrpc(
        method='Playlist.Remove',
        params=dict(playlistid=PLAYLIST_VIDEO, position=0)
    )
    return False


def dequeue_next_item():
    log('Queue: removing unplayed next item', 2)
    jsonrpc(
        method='Playlist.Remove',
        params=dict(playlistid=PLAYLIST_VIDEO, position=1)
    )
    return False


def get_playlist_position():
    playlist = PlayList(PLAYLIST_VIDEO)
    position = playlist.getposition()
    # A playlist with only one element has no next item
    # PlayList().getposition() starts counting from zero
    if playlist.size() > 1 and position < (playlist.size() - 1):
        # Return 1 based index value
        return position + 1
    return None


def get_next_in_playlist(position):
    result = jsonrpc(
        method='Playlist.GetItems',
        params=dict(
            playlistid=PLAYLIST_VIDEO,
            # limits are zero indexed, position is one indexed
            limits=dict(start=position, end=position + 1),
            properties=EPISODE_PROPERTIES
        )
    )
    item = result.get('result', {}).get('items')

    # Don't check if next item is an episode, just use it if it is there
    if not item:  # item.get('type') != 'episode':
        log('Playlist: error - next item not found', 1)
        return None
    item = item[0]

    # Playlist item may not have had video info details set
    # Try and populate required details if missing
    if not item.get('title'):
        item['title'] = item.get('label', '')
    item['episodeid'] = get_int(item, 'id')
    item['tvshowid'] = get_int(item, 'tvshowid')
    # If missing season/episode, change to empty string to avoid episode
    # formatting issues ("S-1E-1") in Up Next popup
    if get_int(item, 'season') == -1:
        item['season'] = ''
    if get_int(item, 'episode') == -1:
        item['episode'] = ''

    log('Playlist: next item - %s' % item, 2)
    return item


def play_addon_item(data, encoding):
    data = data.get('play_url')
    if data:
        log('Addon: playing - {0}'.format(data), 2)
        jsonrpc(
            method='Player.Open',
            params=dict(item=dict(file=data))
        )
    else:
        msg = 'Addon: sending - ({encoding}) {play_info}'
        msg = msg.format(dict(encoding=encoding, **data))
        log(msg, 2)
        event(
            message=data.get('id'),
            data=data.get('play_info'),
            sender='upnextprovider',
            encoding=encoding
        )


def get_popup_time(data, total_time):
    # Alway use metadata, when available
    popup_duration = get_int(data, 'notification_time')
    if 0 < popup_duration < total_time:
        cue = True
        return total_time - popup_duration, cue

    # Some consumers send the offset when the credits start (e.g. Netflix)
    popup_time = get_int(data, 'notification_offset')
    if 0 < popup_time < total_time:
        cue = True
        return popup_time, cue

    # Use a customized notification time, when configured
    if get_setting_bool('customAutoPlayTime'):
        if total_time > 60 * 60:
            duration_setting = 'autoPlayTimeXL'
        elif total_time > 40 * 60:
            duration_setting = 'autoPlayTimeL'
        elif total_time > 20 * 60:
            duration_setting = 'autoPlayTimeM'
        elif total_time > 10 * 60:
            duration_setting = 'autoPlayTimeS'
        else:
            duration_setting = 'autoPlayTimeXS'

    # Use one global default, regardless of episode length
    else:
        duration_setting = 'autoPlaySeasonTime'

    cue = False
    return total_time - get_setting_int(duration_setting), cue


def get_now_playing():
    result = jsonrpc(
        method='Player.GetItem',
        params=dict(
            playerid=PLAYLIST_VIDEO,
            properties=EPISODE_PROPERTIES,
        )
    )
    result = result.get('result', {}).get('item')

    if not result:
        log('Player: error - now playing item info not found', 1)
        return None

    log('Player: now playing - %s' % result, 2)
    return result


def get_next_from_library(tvshowid, episodeid, unwatched_only):
    episode = get_from_library(tvshowid, episodeid)
    if not episode:
        log('Library: error - next episode info not found', 1)
        episode = None
        new_season = False
        return episode, new_season

    (path, filename) = os.path.split(str(episode['file']))
    filters = [
        {'or': [
            # Next episode in current season
            {'and': [
                {
                    'field': 'season',
                    'operator': 'is',
                    'value': str(episode['season'])
                },
                {
                    'field': 'episode',
                    'operator': 'greaterthan',
                    'value': str(episode['episode'])
                }
            ]},
            # Next episode in next season
            # TODO: Make next season search optional
            {
                'field': 'season',
                'operator': 'greaterthan',
                'value': str(episode['season'])
            }
        ]},
        # Check that both next filename and path are different to current
        # to deal with different file naming schemes e.g.
        # Season 1/Episode 1.mkv
        # Season 1/Episode 1/video.mkv
        # Season 1/Episode 1-2-3.mkv
        {'or': [
            {
                'field': 'filename',
                'operator': 'isnot',
                'value': filename
            },
            {
                'field': 'path',
                'operator': 'isnot',
                'value': path
            }
        ]}
    ]
    if unwatched_only:
        # Exclude watched episodes
        filters.append({
            'field': 'playcount',
            'operator': 'lessthan',
            'value': '1'
        })
    filters = {'and': filters}

    result = jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params=dict(
            tvshowid=tvshowid,
            properties=EPISODE_PROPERTIES,
            sort=dict(order='ascending', method='episode'),
            limits={'start': 0, 'end': 1},
            filter=filters
        )
    )
    result = result.get('result', {}).get('episodes')

    if not result:
        log('Library: error - next episode info not found', 1)
        episode = None
        new_season = False
        return episode, new_season

    new_season = episode.get('season') != result[0].get('season')
    episode.update(result[0])

    log('Library: next episode - %s' % episode, 2)
    return episode, new_season


def get_from_library(tvshowid, episodeid):
    result = jsonrpc(
        method='VideoLibrary.GetTVShowDetails',
        params=dict(
            tvshowid=tvshowid,
            properties=TVSHOW_PROPERTIES
        )
    )
    result = result.get('result', {}).get('tvshowdetails')

    if not result:
        log('Library: error - episode info not found', 1)
        return None
    episode = result

    result = jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params=dict(
            episodeid=episodeid,
            properties=EPISODE_PROPERTIES
        )
    )
    result = result.get('result', {}).get('episodedetails')

    if not result:
        log('Library: error - episode info not found', 1)
        return None
    episode.update(result)

    log('Library: episode - %s' % episode, 2)
    return episode


def get_tvshowid(title):
    result = jsonrpc(
        method='VideoLibrary.GetTVShows',
        params=dict(
            properties=['title'],
            limits={'start': 0, 'end': 1},
            filter={
                'field': 'title',
                'operator': 'is',
                'value': str(title)
            }
        )
    )
    result = result.get('result', {}).get('tvshows')

    if not result:
        log('Library: error - tvshowid not found', 1)
        return -1

    return get_int(result[0], 'tvshowid')


def get_episodeid(tvshowid, season, episode):
    """Search Kodi library for episodeid by tvshowid, season, and episode"""
    filters = [
        {
            'field': 'season',
            'operator': 'is',
            'value': str(season)
        },
        {
            'field': 'episode',
            'operator': 'is',
            'value': str(episode)
        }
    ]
    filters = {'and': filters}

    result = jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params=dict(
            tvshowid=tvshowid,
            properties=EPISODE_PROPERTIES,
            limits={'start': 0, 'end': 1},
            filter=filters
        )
    )
    result = result.get('result', {}).get('episodes')

    if not result:
        log('Library: error - episodeid not found', 1)
        return -1

    return get_int(result[0], 'episodeid')


def handle_just_watched(episodeid, playcount=0, reset_resume=True):
    result = jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params=dict(
            episodeid=episodeid,
            properties=['playcount'],
        )
    )
    result = result.get('result', {}).get('episodedetails')

    if result:
        current_playcount = get_int(result, 'playcount', 0)
    else:
        return
    if current_playcount <= playcount:
        playcount += 1

    params = dict(
        episodeid=episodeid,
        playcount=playcount
    )
    if reset_resume:
        params['resume'] = dict(position=0)

    msg = 'Library: update - id: {0}, playcount change from {1} to {2}'
    msg = msg.format(episodeid, current_playcount, playcount)
    log(msg, 2)
    jsonrpc(method='VideoLibrary.SetEpisodeDetails', params=params)
