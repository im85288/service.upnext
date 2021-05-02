# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Implements helper functions to interact with the Kodi library, player and
   playlist"""

from __future__ import absolute_import, division, unicode_literals
import os.path
import xbmc
import constants
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

PLAYER_TYPES = {
    'video': xbmc.PLAYLIST_VIDEO,  # 1
    'audio': xbmc.PLAYLIST_MUSIC   # 0
}


def log(msg, level=utils.LOGDEBUG):
    """Log wrapper"""

    utils.log(msg, name=__name__, level=level)


def play_kodi_item(episode, resume=False):
    """Function to directly play a file from the Kodi library"""

    log('Playing from library: {0}'.format(episode))
    utils.jsonrpc(
        method='Player.Open',
        params={'item': {'episodeid': utils.get_int(episode, 'episodeid')}},
        options={'resume': resume},
        no_response=True
    )


def queue_next_item(data=None, episode=None):
    """Function to add next episode to the UpNext queue"""

    next_item = {}
    play_url = data.get('play_url') if data else None
    episodeid = (
        utils.get_int(episode, 'episodeid') if episode
        else constants.UNKNOWN_DATA
    )

    if play_url:
        next_item.update(file=play_url)

    elif episode and episodeid != constants.UNKNOWN_DATA:
        next_item.update(episodeid=episodeid)

    if next_item:
        log('Adding to queue: {0}'.format(next_item))
        utils.jsonrpc(
            method='Playlist.Add',
            params={'playlistid': get_player_id(), 'item': next_item},
            no_response=True
        )
    else:
        log('Nothing added to queue')

    return bool(next_item)


def reset_queue():
    """Function to remove the 1st item from the playlist, used by the UpNext
       queue for the video that was just played"""

    log('Removing previously played item from queue')
    utils.jsonrpc(
        method='Playlist.Remove',
        params={'playlistid': get_player_id(), 'position': 0},
        no_response=True
    )
    return False


def dequeue_next_item():
    """Function to remove the 2nd item from the playlist, used by the UpNext
       queue for the next video to be played"""

    log('Removing unplayed next item from queue')
    utils.jsonrpc(
        method='Playlist.Remove',
        params={'playlistid': get_player_id(), 'position': 1},
        no_response=True
    )
    return False


def play_playlist_item(position=0, resume=False):
    """Function to play episode in playlist"""

    log('Playing from playlist position: {0}'.format(position))
    if position == 'next':
        position = get_playlist_position()

    # JSON Player.Open can be too slow but is needed if resuming is enabled
    # Unfortunately resuming from a playlist item does not seem to work...
    utils.jsonrpc(
        method='Player.Open',
        params={'item': {'playlistid': get_player_id(), 'position': position}},
        options={'resume': resume},
        no_response=True
    )


def get_playlist_position():
    """Function to get current playlist playback position, where the first item
       in the playlist is position 1"""

    # Use actual playerid rather than xbmc.PLAYLIST_VIDEO as Kodi may sometimes
    # play video content in a music playlist
    playlist_id = get_player_id(player_id_cache=[None])
    if playlist_id is None:
        return None

    playlist = xbmc.PlayList(playlist_id)
    playlist_size = playlist.size()
    # Use 1 based index value for playlist position
    position = playlist.getposition() + 1

    # A playlist with only one element has no next item
    # PlayList().getposition() starts counting from zero
    if playlist_size > 1 and position < playlist_size:
        log('playlistid: {0}, position - {1}/{2}'.format(
            playlist_id, position, playlist_size
        ))
        return position
    return None


def get_next_in_playlist(position, unwatched_only=False):
    """Function to get details of next episode in playlist"""

    result = utils.jsonrpc(
        method='Playlist.GetItems',
        params={
            'playlistid': get_player_id(),
            # limits are zero indexed, position is one indexed
            'limits': {
                'start': position,
                'end': -1 if unwatched_only else position + 1
            },
            'properties': EPISODE_PROPERTIES
        }
    )
    items = result.get('result', {}).get('items')

    # Get first unwatched item in the list of remaining playlist entries
    if unwatched_only and items:
        position_offset, item = next(
            (
                (idx, item) for idx, item in enumerate(items)
                if utils.get_int(item, 'playcount') < 1
            ),
            (0, None)
        )
        position += position_offset
    # Or just get the first item in the list of remaining playlist entries
    else:
        item = items[0] if items else None

    # Don't check if next item is an episode, just use it if it is there
    if not item:  # item.get('type') != 'episode':
        log('Error: no next item found in playlist', utils.LOGWARNING)
        return None

    # Playlist item may not have had video info details set
    # Try and populate required details if missing
    if not item.get('title'):
        item['title'] = item.get('label', '')
    item['episodeid'] = utils.get_int(
        item, 'episodeid',
        utils.get_int(item, 'id')
    )
    item['tvshowid'] = utils.get_int(item, 'tvshowid')
    # If missing season/episode, change to empty string to avoid episode
    # formatting issues ("S-1E-1") in UpNext popup
    if utils.get_int(item, 'season') == constants.UNKNOWN_DATA:
        item['season'] = ''
    if utils.get_int(item, 'episode') == constants.UNKNOWN_DATA:
        item['episode'] = ''

    # Store current playlist position for later use
    item['playlist_position'] = position

    log('Next item in playlist at position {0}: {1}'.format(position, item))
    return item


def play_addon_item(data, encoding, resume=False):
    """Function to play next addon item, either using JSONRPC Player.Open or by
       passthrough back to the addon"""

    play_url = data.get('play_url')
    if play_url:
        log('Playing from addon - {0}'.format(play_url))
        utils.jsonrpc(
            method='Player.Open',
            params={'item': {'file': play_url}},
            options={'resume': resume},
            no_response=True
        )
        return

    play_info = data.get('play_info')
    if play_info:
        log('Sending as {0} to addon - {1}'.format(encoding, play_info))
        utils.event(
            message=data.get('id'),
            data=play_info,
            sender='upnextprovider',
            encoding=encoding
        )
        return

    log('Error: no addon data available for playback', utils.LOGWARNING)


def get_player_id(player_type=None, player_id_cache=[None]):   # pylint: disable=dangerous-default-value
    """Function to get active player ID"""

    # We don't need to actually get playerid everytime, cache and reuse instead
    if player_id_cache[0] is not None:
        return player_id_cache[0]

    # Sometimes Kodi gets confused and uses a music playlist for video content,
    # so we use the first active player id instead.
    result = utils.jsonrpc(
        method='Player.GetActivePlayers'
    )
    result = result.get('result', [{}])
    if player_type:
        result = [
            player for player in result if player.get('type') == player_type
        ]
    else:
        result = [
            player for player in result if player.get('type') in PLAYER_TYPES
        ]

    if not result:
        log('Error: no active player', utils.LOGWARNING)
        return None

    player_id = result[0].get('playerid')
    player_id_cache[0] = player_id
    return player_id


def get_player_speed():
    """Function to get speed of active player"""

    result = utils.jsonrpc(
        method='Player.GetProperties',
        params={
            'playerid': get_player_id(),
            'properties': ['speed'],
        }
    )
    result = utils.get_int(result.get('result', {}), 'speed', 1)

    return result


def get_now_playing():
    """Function to get detail of currently playing item"""

    result = utils.jsonrpc(
        method='Player.GetItem',
        params={
            'playerid': get_player_id(),
            'properties': EPISODE_PROPERTIES,
        }
    )
    result = result.get('result', {}).get('item')

    if not result:
        log('Error: now playing item info not found', utils.LOGWARNING)
        return None

    log('Now playing: {0}'.format(result))
    return result


def get_next_from_library(
        episodeid=constants.UNKNOWN_DATA,
        tvshowid=None,
        unwatched_only=False,
        next_season=True,
        random=False,
        episode=None
):
    """Function to get show and next episode details from Kodi library"""

    episode = episode.copy() if episode else get_from_library(episodeid)

    if not episode:
        log('Error: no next episode found, current episode not in library',
            utils.LOGWARNING)
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
        # Next episode in current season
        episode_filter = {'and': [
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
        ]}
        # Next episode in next season
        if next_season:
            episode_filter = [
                episode_filter,
                {
                    'field': 'season',
                    'operator': 'greaterthan',
                    'value': str(episode['season'])
                }
            ]
            episode_filter = {'or': episode_filter}
        filters.append(episode_filter)

    filters = {'and': filters}

    if not tvshowid:
        tvshowid = episode.get('tvshowid', constants.UNKNOWN_DATA)

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
        log('No next episode found in library')
        episode = None
        new_season = False
        return episode, new_season

    log('Next episode from library: {0}'.format(result[0]))
    new_season = not random and episode['season'] != result[0]['season']
    episode.update(result[0])
    return episode, new_season


def get_from_library(episodeid, tvshowid=None):
    """Function to get show and episode details from Kodi library"""

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params={
            'episodeid': episodeid,
            'properties': EPISODE_PROPERTIES
        }
    )
    result = result.get('result', {}).get('episodedetails')

    if not result:
        log('Error: episode info not found in library', utils.LOGWARNING)
        return None
    episode = result

    if not tvshowid:
        tvshowid = episode.get('tvshowid', constants.UNKNOWN_DATA)

    result = utils.jsonrpc(
        method='VideoLibrary.GetTVShowDetails',
        params={
            'tvshowid': tvshowid,
            'properties': TVSHOW_PROPERTIES
        }
    )
    result = result.get('result', {}).get('tvshowdetails')

    if not result:
        log('Error: show info not found in library', utils.LOGWARNING)
        return None
    result.update(episode)

    log('Episode from library: {0}'.format(result))
    return result


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
        log('Error: tvshowid not found in library', utils.LOGWARNING)
        return constants.UNKNOWN_DATA

    return utils.get_int(result[0], 'tvshowid')


def get_episodeid(tvshowid, season, episode):
    """Function to search Kodi library for episodeid by tvshowid, season, and
       episode"""

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
        log('Error: episodeid not found in library', utils.LOGWARNING)
        return constants.UNKNOWN_DATA

    return utils.get_int(result[0], 'episodeid')


def handle_just_watched(
        episodeid,
        playcount,
        reset_playcount=False,
        reset_resume=True
):
    """Function to update playcount and resume point of just watched video"""

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodeDetails',
        params={
            'episodeid': episodeid,
            'properties': ['playcount', 'resume'],
        }
    )
    result = result.get('result', {}).get('episodedetails')

    if result:
        actual_playcount = utils.get_int(result, 'playcount', 0)
        actual_resume = utils.get_int(result.get('resume'), 'position', 0)
    else:
        return

    params = {}

    # If Kodi has not updated playcount then UpNext will
    if reset_playcount:
        playcount = -1
    if reset_playcount or actual_playcount == playcount:
        playcount += 1
        params['playcount'] = playcount

    # If resume point has been saved then reset it
    if actual_resume and reset_resume:
        params['resume'] = {'position': 0}

    # Only update library if playcount or resume point needs to change
    if params:
        params['episodeid'] = episodeid
        utils.jsonrpc(
            method='VideoLibrary.SetEpisodeDetails',
            params=params,
            no_response=True
        )

    log('Library update: id - {0}{1}{2}{3}'.format(
        episodeid,
        ', playcount - {0} to {1}'.format(actual_playcount, playcount)
        if 'playcount' in params else '',
        ', resume - {0} to 0'.format(actual_resume)
        if 'resume' in params else '',
        '' if params else ', no change'
    ), utils.LOGDEBUG)
