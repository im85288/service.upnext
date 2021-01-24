# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions to interact with Kodi library, player and playlist"""

from __future__ import absolute_import, division, unicode_literals
import os.path
import xbmc
import utils


EPISODE_PROPERTIES = [
    'title',
    'playcount',
    'season',
    'episode',
    'showtitle',
    # 'originaltitle', # Not used
    'plot',
    # 'votes', # Not used
    'file',
    'rating',
    # 'ratings', # Not used, slow
    # 'userrating', # Not used
    'resume',
    'tvshowid',
    'firstaired',
    'art',
    # 'streamdetails', # Not used, slow
    'runtime',
    # 'director', # Not used
    # 'writer', # Not used
    # 'cast', # Not used, slow
    'dateadded',
    'lastplayed'
]

TVSHOW_PROPERTIES = [
    'title',
    'studio',
    'year',
    'plot',
    # 'cast', # Not used, slow
    'rating',
    # 'ratings', # Not used, slow
    # 'userrating', # Not used
    # 'votes', # Not used
    'genre',
    'episode',
    'season',
    'runtime',
    'mpaa',
    'premiered',
    'playcount',
    'lastplayed',
    # 'sorttitle', # Not used
    # 'originaltitle', # Not used
    'art',
    # 'tag', # Not used, slow
    'dateadded',
    'watchedepisodes',
    # 'imdbnumber' # Not used
]


def log(msg, level=2):
    """Log wrapper"""
    utils.log(msg, name=__name__, level=level)


def play_kodi_item(episode):
    """Function to directly play a file from the Kodi library"""
    log('Playing from library: {0}'.format(episode), 2)
    utils.jsonrpc(
        method='Player.Open',
        params={'item': {'episodeid': utils.get_int(episode, 'episodeid')}},
        # Disable resuming, playback from start
        # TODO: Add setting to control playback from start or resume point
        options={'resume': False},
        no_response=True
    )


def queue_next_item(data=None, episode=None):
    """Function to add next episode to the UpNext queue"""
    next_item = {}
    play_url = data.get('play_url') if data else None
    episodeid = utils.get_int(episode, 'episodeid') if episode else None

    if play_url:
        next_item.update(file=play_url)

    elif episode and episodeid != -1:
        next_item.update(episodeid=episodeid)

    if next_item:
        log('Adding to queue: {0}'.format(next_item), 2)
        utils.jsonrpc(
            method='Playlist.Add',
            params={'playlistid': xbmc.PLAYLIST_VIDEO, 'item': next_item},
            no_response=True
        )
    else:
        log('Nothing added to queue', 2)

    return bool(next_item)


def reset_queue():
    """Function to remove the 1st item from the playlist, used by UpNext queue"""
    log('Removing previously played item from queue', 2)
    utils.jsonrpc(
        method='Playlist.Remove',
        params={'playlistid': xbmc.PLAYLIST_VIDEO, 'position': 0},
        no_response=True
    )
    return False


def dequeue_next_item():
    """Function to remove the 2nd item from the playlist, used by UpNext queue"""
    log('Removing unplayed next item from queue', 2)
    utils.jsonrpc(
        method='Playlist.Remove',
        params={'playlistid': xbmc.PLAYLIST_VIDEO, 'position': 1},
        no_response=True
    )
    return False


def get_playlist_position():
    """Function to get current playlist playback position"""
    playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
    position = playlist.getposition()
    # A playlist with only one element has no next item
    # PlayList().getposition() starts counting from zero
    if playlist.size() > 1 and position < (playlist.size() - 1):
        # Return 1 based index value
        return position + 1
    return None


def get_next_in_playlist(position):
    """Function to get details of next episode in playlist"""
    result = utils.jsonrpc(
        method='Playlist.GetItems',
        params={
            'playlistid': xbmc.PLAYLIST_VIDEO,
            # limits are zero indexed, position is one indexed
            'limits': {'start': position, 'end': position + 1},
            'properties': EPISODE_PROPERTIES
        }
    )
    item = result.get('result', {}).get('items')

    # Don't check if next item is an episode, just use it if it is there
    if not item:  # item.get('type') != 'episode':
        log('Error: no next item found in playlist', 1)
        return None
    item = item[0]

    # Playlist item may not have had video info details set
    # Try and populate required details if missing
    if not item.get('title'):
        item['title'] = item.get('label', '')
    item['episodeid'] = utils.get_int(item, 'id')
    item['tvshowid'] = utils.get_int(item, 'tvshowid')
    # If missing season/episode, change to empty string to avoid episode
    # formatting issues ("S-1E-1") in UpNext popup
    if utils.get_int(item, 'season') == -1:
        item['season'] = ''
    if utils.get_int(item, 'episode') == -1:
        item['episode'] = ''

    log('Next item in playlist: %s' % item, 2)
    return item


def play_addon_item(data, encoding):
    """Function to play next addon item, either directly or by passthrough to addon"""
    if data.get('play_url'):
        data = data.get('play_url')
        log('Playing from addon - {0}'.format(data), 2)
        utils.jsonrpc(
            method='Player.Open',
            params={'item': {'file': data}},
            no_response=True
        )
    elif data.get('play_info'):
        msg = 'Sending to addon - ({0}) {play_info}'
        msg = msg.format(encoding, **data)
        log(msg, 2)
        utils.event(
            message=data.get('id'),
            data=data.get('play_info'),
            sender='upnextprovider',
            encoding=encoding
        )
    else:
        log('Error: no addon data available for playback', 1)


def get_player_id(player_type=None):
    """Function to get active player ID"""
    result = utils.jsonrpc(
        method='Player.GetActivePlayers',
    )
    result = result.get('result', [{}])
    result = [
        player.get('playerid') for player in result
        if player.get('type') in (
            {player_type} if player_type else {'video', 'audio', 'picture'}
        )
    ]

    if not result:
        log('Error: no active player', 1)
        return None

    log('playerid: %s' % result[0], 2)
    return result[0]


def get_now_playing():
    """Function to get detail of currently playing item"""
    result = utils.jsonrpc(
        method='Player.GetItem',
        params={
            'playerid': get_player_id('video'),
            'properties': EPISODE_PROPERTIES,
        }
    )
    result = result.get('result', {}).get('item')

    if not result:
        log('Error: now playing item info not found', 1)
        return None

    log('Now playing: %s' % result, 2)
    return result


def get_next_from_library(tvshowid, episodeid, unwatched_only, random=False):
    """Function to get show and next episode details from Kodi library"""
    episode = get_from_library(tvshowid, episodeid)
    if not episode:
        log('Error: next episode info not found in library', 1)
        episode = None
        new_season = False
        return episode, new_season

    (path, filename) = os.path.split(episode['file'])
    filters = [
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
    if not random:
        filters.append(
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
            ]}
        )
    filters = {'and': filters}

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params={
            'tvshowid': tvshowid,
            'properties': EPISODE_PROPERTIES,
            'sort': (
                {'method': 'random'} if random
                else {'order': 'ascending', 'method': 'episode'}
            ),
            'limits': {'start': 0, 'end': 1},
            'filter': filters
        }
    )
    result = result.get('result', {}).get('episodes')

    if not result:
        log('Error: next episode info not found in library', 1)
        episode = None
        new_season = False
        return episode, new_season

    new_season = not random and episode['season'] != result[0]['season']
    episode.update(result[0])

    log('Next episode from library: %s' % episode, 2)
    return episode, new_season


def get_from_library(tvshowid, episodeid):
    """Function to get show and episode details from Kodi library"""
    result = utils.jsonrpc(
        method='VideoLibrary.GetTVShowDetails',
        params={
            'tvshowid': tvshowid,
            'properties': TVSHOW_PROPERTIES
        }
    )
    result = result.get('result', {}).get('tvshowdetails')

    if not result:
        log('Error: show info not found in library', 1)
        return None
    episode = result

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params={
            'episodeid': episodeid,
            'properties': EPISODE_PROPERTIES
        }
    )
    result = result.get('result', {}).get('episodedetails')

    if not result:
        log('Error: episode info not found in library', 1)
        return None
    episode.update(result)

    log('Episode from library: %s' % episode, 2)
    return episode


def get_tvshowid(title):
    """Function to search Kodi library for tshowid by title"""
    result = utils.jsonrpc(
        method='VideoLibrary.GetTVShows',
        params={
            'properties': ['title'],
            'limits': {'start': 0, 'end': 1},
            'filter': {
                'field': 'title',
                'operator': 'is',
                'value': title
            }
        }
    )
    result = result.get('result', {}).get('tvshows')

    if not result:
        log('Error: tvshowid not found in library', 1)
        return -1

    return utils.get_int(result[0], 'tvshowid')


def get_episodeid(tvshowid, season, episode):
    """Function to search Kodi library for episodeid by tvshowid, season, and episode"""
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

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params={
            'tvshowid': tvshowid,
            'properties': EPISODE_PROPERTIES,
            'limits': {'start': 0, 'end': 1},
            'filter': filters
        }
    )
    result = result.get('result', {}).get('episodes')

    if not result:
        log('Error: episodeid not found in library', 1)
        return -1

    return utils.get_int(result[0], 'episodeid')


def handle_just_watched(episodeid, playcount=0, reset_resume=True):
    """Function to update playcount and resume point of just watched video"""
    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params={
            'episodeid': episodeid,
            'properties': ['playcount'],
        }
    )
    result = result.get('result', {}).get('episodedetails')

    if result:
        current_playcount = utils.get_int(result, 'playcount', 0)
        current_resume = result.get('resume', {}).get('position')
    else:
        return

    params = {'episodeid': episodeid}
    msg = 'Library update: id - {0}'

    # If Kodi has not increased playcount then UpNext will
    if current_playcount == playcount:
        playcount += 1
        params['playcount'] = playcount
        msg += ', playcount - {1} to {2}'

    # If resume point has been saved then reset it
    if current_resume and reset_resume:
        params['resume'] = {'position': 0}
        msg += ', resume - {3} to {4}'

    # Only update library if playcount or resume point needs to change
    if len(params) == 1:
        msg += ', no change'
    else:
        utils.jsonrpc(
            method='VideoLibrary.SetEpisodeDetails',
            params=params,
            no_response=True
        )

    msg = msg.format(
        episodeid,
        current_playcount,
        playcount,
        current_resume,
        0 if reset_resume else current_resume
    )
    log(msg, 2)
