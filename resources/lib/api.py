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
    # 'originaltitle',  # Not used
    'plot',
    # 'votes',  # Not used
    'file',
    'rating',
    # 'ratings',  # Not used, slow
    # 'userrating',  # Not used
    'resume',
    'tvshowid',
    'firstaired',
    'art',
    # 'streamdetails',  # Not used, slow
    'runtime',
    # 'director',  # Not used
    # 'writer',  # Not used
    # 'cast',  # Not used, slow
    'dateadded',
    'lastplayed',
]
EPISODE_ART_SUBSTITUTES = {
    'poster': ('season.poster', 'tvshow.poster'),
    'fanart': ('season.fanart', 'tvshow.fanart'),
    'landscape': ('season.landscape', 'tvshow.landscape'),
    'clearart': ('season.clearart', 'tvshow.clearart'),
    'banner': ('season.banner', 'tvshow.banner'),
    'clearlogo': ('season.clearlogo', 'tvshow.clearlogo'),
}

TVSHOW_PROPERTIES = [
    'title',
    'studio',
    'year',
    'plot',
    # 'cast',  # Not used, slow
    'rating',
    # 'ratings',  # Not used, slow
    # 'userrating',  # Not used
    # 'votes',  # Not used
    'genre',
    'episode',
    'season',
    'runtime',
    'mpaa',
    'premiered',
    'playcount',
    'lastplayed',
    # 'sorttitle',  # Not used
    # 'originaltitle',  # Not used
    'art',
    # 'tag',  # Not used, slow
    'dateadded',
    'watchedepisodes',
    # 'imdbnumber',  # Not used
]

PLAYER_PLAYLIST = {
    'video': xbmc.PLAYLIST_VIDEO,  # 1
    'audio': xbmc.PLAYLIST_MUSIC   # 0
}

_QUERY_LIMITS = {
    'start': 0,
    'end': constants.UNDEFINED
}
_QUERY_LIMIT_ONE = {
    'start': 0,
    'end': 1
}

_FILTER_NOT_FILE = {
    'field': 'filename',
    'operator': 'isnot',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}
_FILTER_NOT_PATH = {
    'field': 'path',
    'operator': 'isnot',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}
_FILTER_NOT_FILEPATH = {
    'or': [
        _FILTER_NOT_FILE,
        _FILTER_NOT_PATH
    ]
}

_FILTER_SEARCH_TVSHOW = {
    'field': 'title',
    'operator': 'is',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}
_FILTER_INPROGRESS = {
    'field': 'inprogress',
    'operator': 'true',
    'value': ''
}

_FILTER_WATCHED = {
    'field': 'playcount',
    'operator': 'greaterthan',
    'value': '0'
}
_FILTER_UNWATCHED = {
    'field': 'playcount',
    'operator': 'lessthan',
    'value': '1'
}

_FILTER_REGULAR_SEASON = {
    'field': 'season',
    'operator': 'greaterthan',
    'value': '0'
}
_FILTER_THIS_SEASON = {
    'field': 'season',
    'operator': 'is',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}
_FILTER_NEXT_SEASON = {
    'field': 'season',
    'operator': 'greaterthan',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}

_FILTER_THIS_EPISODE = {
    'field': 'episode',
    'operator': 'is',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}
_FILTER_NEXT_EPISODE = {
    'field': 'episode',
    'operator': 'greaterthan',
    'value': constants.VALUE_TO_STR[constants.UNDEFINED]
}

_FILTER_SEARCH_EPISODE = {
    'and': [
        _FILTER_THIS_SEASON,
        _FILTER_THIS_EPISODE
    ]
}
_FILTER_CURRENT_EPISODE = {
    'and': [
        _FILTER_REGULAR_SEASON,
        {
            'or': [
                _FILTER_INPROGRESS,
                _FILTER_WATCHED
            ]
        }
    ]
}
_FILTER_UPNEXT_EPISODE = {
    'and': [
        _FILTER_THIS_SEASON,
        _FILTER_NEXT_EPISODE
    ]
}
_FILTER_UPNEXT_EPISODE_SEASON = {
    'or': [
        _FILTER_UPNEXT_EPISODE,
        _FILTER_NEXT_SEASON
    ]
}
_FILTER_UNWATCHED_UPNEXT_EPISODE_SEASON = {
    'and': [
        _FILTER_UNWATCHED,
        _FILTER_UPNEXT_EPISODE_SEASON
    ]
}

_SORT_LASTPLAYED = {
    'method': 'lastplayed',
    'order': 'descending'
}
_SORT_EPISODE = {
    'method': 'episode',
    'order': 'ascending'
}
_SORT_RANDOM = {
    'method': 'random'
}


_CACHE = {
    'playerid': None,
    'playlistid': None
}


def cache_invalidate():
    _CACHE.update(_CACHE.fromkeys(_CACHE))


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
        else constants.UNDEFINED
    )

    if play_url:
        next_item.update(file=play_url)

    elif episode and episodeid != constants.UNDEFINED:
        next_item.update(episodeid=episodeid)

    if next_item:
        log('Adding to queue: {0}'.format(next_item))
        utils.jsonrpc(
            method='Playlist.Add',
            params={'playlistid': get_playlistid(), 'item': next_item},
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
        params={'playlistid': get_playlistid(), 'position': 0},
        no_response=True
    )
    return False


def dequeue_next_item():
    """Function to remove the 2nd item from the playlist, used by the UpNext
       queue for the next video to be played"""

    log('Removing unplayed next item from queue')
    utils.jsonrpc(
        method='Playlist.Remove',
        params={'playlistid': get_playlistid(), 'position': 1},
        no_response=True
    )
    return False


def play_playlist_item(position=0, resume=False):
    """Function to play episode in playlist"""

    if position == 'next':
        position = get_playlist_position()
    log('Playing from playlist position: {0}'.format(position))

    # JSON Player.Open can be too slow but is needed if resuming is enabled
    # Unfortunately resuming from a playlist item does not seem to work...
    utils.jsonrpc(
        method='Player.Open',
        params={
            'item': {'playlistid': get_playlistid(), 'position': position}
        },
        options={'resume': resume},
        no_response=True
    )


def get_playlist_position():
    """Function to get current playlist playback position, where the first item
       in the playlist is position 1"""

    # Use actual playlistid rather than xbmc.PLAYLIST_VIDEO as Kodi sometimes
    # plays video content in a music playlist
    playlistid = get_playlistid()
    if playlistid is None:
        return None

    playlist = xbmc.PlayList(playlistid)
    playlist_size = playlist.size()
    # Use 1 based index value for playlist position
    position = playlist.getposition() + 1

    # A playlist with only one element has no next item
    # PlayList().getposition() starts counting from zero
    if playlist_size > 1 and position < playlist_size:
        log('playlistid: {0}, position - {1}/{2}'.format(
            playlistid, position, playlist_size
        ))
        return position
    return None


def get_from_playlist(position, unwatched_only=False):
    """Function to get details of item in playlist"""

    result = utils.jsonrpc(
        method='Playlist.GetItems',
        params={
            'playlistid': get_playlistid(),
            # limits are zero indexed, position is one indexed
            'limits': {
                'start': position,
                'end': -1 if unwatched_only else position + 1
            },
            'properties': EPISODE_PROPERTIES
        }
    )
    items = result.get('result', {}).get('items')

    # Get first unwatched item in the list of playlist entries
    if unwatched_only and items:
        position_offset, item = next(
            (
                (idx, item) for idx, item in enumerate(items)
                if utils.get_int(item, 'playcount') < 1
            ),
            (0, None)
        )
        position += position_offset
    # Or just get the first item in the list of playlist entries
    else:
        item = items[0] if items else None

    # Don't check if item is an episode, just use it if it is there
    if not item:  # item.get('type') != 'episode':
        log('No item in playlist at position {0}'.format(position),
            utils.LOGWARNING)
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
    if utils.get_int(item, 'season') == constants.UNDEFINED:
        item['season'] = ''
    if utils.get_int(item, 'episode') == constants.UNDEFINED:
        item['episode'] = ''

    # Store current playlist position for later use
    item['playlist_position'] = position

    log('Item in playlist at position {0}: {1}'.format(position, item))
    return item


def play_plugin_item(data, encoding, resume=False):
    """Function to play next plugin item, either using JSONRPC Player.Open or
       by passthrough back to the plugin"""

    play_url = data.get('play_url')
    if play_url:
        log('Playing from plugin - {0}'.format(play_url))
        utils.jsonrpc(
            method='Player.Open',
            params={'item': {'file': play_url}},
            options={'resume': resume},
            no_response=True
        )
        return

    play_info = data.get('play_info')
    if play_info:
        log('Sending as {0} to plugin - {1}'.format(encoding, play_info))
        utils.event(
            message=data.get('id'),
            data=play_info,
            sender='upnextprovider',
            encoding=encoding
        )
        return

    log('No plugin data available for playback', utils.LOGWARNING)


def get_playerid(retry=3):
    """Function to get active player playerid"""

    # We don't need to get playerid every time, cache and reuse instead
    if _CACHE['playerid'] is not None:
        return _CACHE['playerid']

    # Sometimes Kodi gets confused and uses a music playlist for video content,
    # so get the first active player instead, default to video player. Wait 1s
    # and retry in case of delay in getting response.
    attempts_left = 1 + retry
    while attempts_left > 0:
        result = utils.jsonrpc(method='Player.GetActivePlayers').get('result')

        if result:
            break

        attempts_left -= 1
        if attempts_left > 0:
            utils.wait(2)
    else:
        log('No active player', utils.LOGWARNING)
        _CACHE['playerid'] = None
        return None

    result = [
        player for player in result
        if player.get('type', 'video') in PLAYER_PLAYLIST
    ]

    playerid = (
        utils.get_int(result[0], 'playerid') if result
        else constants.UNDEFINED
    )

    if playerid == constants.UNDEFINED:
        log('No active player', utils.LOGWARNING)
        _CACHE['playerid'] = None
        return None

    log('Selected playerid: {0}'.format(playerid))
    _CACHE['playerid'] = playerid
    return playerid


def get_playlistid():
    """Function to get playlistid of active player"""

    # We don't need to get playlistid every time, cache and reuse instead
    if _CACHE['playlistid'] is not None:
        return _CACHE['playlistid']

    result = utils.jsonrpc(
        method='Player.GetProperties',
        params={
            'playerid': get_playerid(),
            'properties': ['playlistid'],
        }
    )
    playlistid = utils.get_int(
        result.get('result', {}), 'playlistid', PLAYER_PLAYLIST['video']
    )

    log('Selected playlistid: {0}'.format(playlistid))
    _CACHE['playlistid'] = playlistid
    return playlistid


def get_player_speed():
    """Function to get speed of active player"""

    result = utils.jsonrpc(
        method='Player.GetProperties',
        params={
            'playerid': get_playerid(),
            'properties': ['speed'],
        }
    )
    result = utils.get_int(result.get('result', {}), 'speed', 1)

    return result


def get_now_playing(properties=None, retry=3):
    """Function to get detail of currently playing item"""

    # Retry in case of delay in getting response.
    attempts_left = 1 + retry
    while attempts_left > 0:
        result = utils.jsonrpc(
            method='Player.GetItem',
            params={
                'playerid': get_playerid(retry=retry),
                'properties': (
                    EPISODE_PROPERTIES if properties is None else properties
                ),
            }
        )
        result = result.get('result', {}).get('item')

        if result:
            break

        attempts_left -= 1
        if attempts_left > 0:
            utils.wait(2)
    else:
        log('Now playing item info not found', utils.LOGWARNING)
        return None

    log('Now playing: {0}'.format(result))
    return result


def get_next_from_library(episode=constants.UNDEFINED,
                          tvshowid=None,
                          unwatched_only=False,
                          next_season=True,
                          random=False):
    """Function to get show and next episode details from Kodi library"""

    if not episode or episode == constants.UNDEFINED:
        log('No next episode found, current episode not in library',
            utils.LOGWARNING)
        episode = None
        new_season = False
        return episode, new_season

    (path, filename) = os.path.split(episode['file'])
    _FILTER_NOT_FILE['value'] = filename
    _FILTER_NOT_PATH['value'] = path
    filters = [
        # Check that both next filename and path are different to current
        # to deal with different file naming schemes e.g.
        # Season 1/Episode 1.mkv
        # Season 1/Episode 1/video.mkv
        # Season 1/Episode 1-2-3.mkv
        _FILTER_NOT_FILEPATH
    ]

    if unwatched_only:
        # Exclude watched episodes
        filters.append(_FILTER_UNWATCHED)

    if not random:
        current_season = str(episode['season'])
        _FILTER_THIS_SEASON['value'] = current_season
        _FILTER_NEXT_SEASON['value'] = current_season
        _FILTER_NEXT_EPISODE['value'] = str(episode['episode'])
        # Next episode in current season or first episode in next season
        filters.append(
            _FILTER_UPNEXT_EPISODE_SEASON if next_season
            else _FILTER_UPNEXT_EPISODE
        )

    filters = {'and': filters}

    if not tvshowid:
        tvshowid = episode.get('tvshowid', constants.UNDEFINED)

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params={
            'tvshowid': tvshowid,
            'properties': EPISODE_PROPERTIES,
            'sort': (
                _SORT_RANDOM if random
                else _SORT_EPISODE
            ),
            'limits': _QUERY_LIMIT_ONE,
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
        log('Episode info not found in library', utils.LOGWARNING)
        return None
    episode = result

    if not tvshowid:
        tvshowid = episode.get('tvshowid', constants.UNDEFINED)

    result = utils.jsonrpc(
        method='VideoLibrary.GetTVShowDetails',
        params={
            'tvshowid': tvshowid,
            'properties': TVSHOW_PROPERTIES
        }
    )
    result = result.get('result', {}).get('tvshowdetails')

    if not result:
        log('Show info not found in library', utils.LOGWARNING)
        return None
    result.update(episode)

    log('Episode from library: {0}'.format(result))
    return result


def get_tvshowid(title):
    """Function to search Kodi library for tshowid by title"""

    _FILTER_SEARCH_TVSHOW['value'] = title
    result = utils.jsonrpc(
        method='VideoLibrary.GetTVShows',
        params={
            'properties': [],
            'limits': _QUERY_LIMIT_ONE,
            'filter': _FILTER_SEARCH_TVSHOW
        }
    )
    result = result.get('result', {}).get('tvshows')

    if not result:
        log('tvshowid not found in library', utils.LOGWARNING)
        return constants.UNDEFINED

    return utils.get_int(result[0], 'tvshowid')


def get_episodeid(tvshowid, season, episode):
    """Function to search Kodi library for episodeid by tvshowid, season, and
       episode"""

    _FILTER_THIS_SEASON['value'] = str(season)
    _FILTER_THIS_EPISODE['value'] = str(episode)

    result = utils.jsonrpc(
        method='VideoLibrary.GetEpisodes',
        params={
            'tvshowid': tvshowid,
            'properties': [],
            'limits': _QUERY_LIMIT_ONE,
            'filter': _FILTER_SEARCH_EPISODE
        }
    )
    result = result.get('result', {}).get('episodes')

    if not result:
        log('episodeid not found in library', utils.LOGWARNING)
        return constants.UNDEFINED

    return utils.get_int(result[0], 'episodeid')


def handle_just_watched(episodeid, playcount,
                        reset_playcount=False, reset_resume=True):
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


def get_upnext_from_library(limit=25):
    """Function to get in-progress and next episode details from Kodi library"""

    _QUERY_LIMITS['end'] = limit
    inprogress = utils.jsonrpc(
        method='VideoLibrary.GetTVShows',
        params={
            'properties': [],
            'sort': _SORT_LASTPLAYED,
            'limits': _QUERY_LIMITS,
            'filter': _FILTER_INPROGRESS
        }
    )
    inprogress = inprogress.get('result', {}).get('tvshows', [])

    upnext_episodes = []
    for tvshow in inprogress:
        current_episode = utils.jsonrpc(
            method='VideoLibrary.GetEpisodes',
            params={
                'tvshowid': tvshow['tvshowid'],
                'properties': EPISODE_PROPERTIES,
                'sort': _SORT_LASTPLAYED,
                'limits': _QUERY_LIMIT_ONE,
                'filter': _FILTER_CURRENT_EPISODE
            }
        )
        current_episode = current_episode.get('result', {}).get('episodes')

        if not current_episode:
            continue
        if current_episode[0]['resume']['position']:
            upnext_episode = current_episode
        else:
            current_season = str(current_episode[0]['season'])
            _FILTER_THIS_SEASON['value'] = current_season
            _FILTER_NEXT_SEASON['value'] = current_season
            _FILTER_NEXT_EPISODE['value'] = str(current_episode[0]['episode'])

            upnext_episode = utils.jsonrpc(
                method='VideoLibrary.GetEpisodes',
                params={
                    'tvshowid': tvshow['tvshowid'],
                    'properties': EPISODE_PROPERTIES,
                    'sort': _SORT_EPISODE,
                    'limits': _QUERY_LIMIT_ONE,
                    'filter': _FILTER_UNWATCHED_UPNEXT_EPISODE_SEASON
                }
            )
            upnext_episode = upnext_episode.get('result', {}).get('episodes')

        if not upnext_episode:
            continue

        art = upnext_episode[0].get('art')
        if art:
            art_types = frozenset(art.keys())
            for art_type, art_substitutes in EPISODE_ART_SUBSTITUTES.items():
                if art_type in art_types:
                    continue
                for art_substitute in art_substitutes:
                    if art_substitute in art_types:
                        art[art_type] = art[art_substitute]
                        break
            upnext_episode[0]['art'] = art

        upnext_episodes += upnext_episode

    return upnext_episodes
