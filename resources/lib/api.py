# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
import os.path
from xbmc import PlayList, PLAYLIST_VIDEO
from utils import (event, get_setting_bool, get_setting_int, get_int, jsonrpc,
                   log as ulog)


class Api:
    """Main API class"""
    _shared_state = {}

    episode_properties = [
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

    tvshow_properties = [
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

    def __init__(self):
        """Constructor for Api class"""
        self.__dict__ = self._shared_state
        self.data = {}
        self.encoding = 'base64'

    @classmethod
    def log(cls, msg, level=2):
        """Log wrapper"""
        ulog(msg, name=cls.__name__, level=level)

    def has_addon_data(self):
        if self.data:
            if self.data.get('play_info'):
                return 2
            return 1
        return 0

    def reset_addon_data(self):
        self.data = {}

    def addon_data_received(self, data, encoding='base64'):
        self.log('Up Next addon_data_received: %s' % data, 2)
        self.data = data
        self.encoding = encoding

    @staticmethod
    def play_kodi_item(episode):
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

    def queue_next_item(self, episode):
        next_item = {}
        if not self.data:
            next_item.update(episodeid=get_int(episode, 'episodeid'))
        elif self.data.get('play_url'):
            next_item.update(file=self.data.get('play_url'))

        if next_item:
            jsonrpc(
                method='Playlist.Add',
                params=dict(playlistid=PLAYLIST_VIDEO, item=next_item)
            )

        return bool(next_item)

    @staticmethod
    def reset_queue():
        Api.log('Up Next queue: removing previously played item', 2)
        jsonrpc(
            method='Playlist.Remove',
            params=dict(playlistid=PLAYLIST_VIDEO, position=0)
        )
        return False

    @staticmethod
    def dequeue_next_item():
        Api.log('Up Next queue: removing unplayed next item', 2)
        jsonrpc(
            method='Playlist.Remove',
            params=dict(playlistid=PLAYLIST_VIDEO, position=1)
        )
        return False

    @staticmethod
    def get_playlist_position():
        playlist = PlayList(PLAYLIST_VIDEO)
        position = playlist.getposition()
        # A playlist with only one element has no next item
        # PlayList().getposition() starts counting from zero
        if playlist.size() > 1 and position < (playlist.size() - 1):
            # Return 1 based index value
            return position + 1
        return None

    @staticmethod
    def get_next_in_playlist(position):
        result = jsonrpc(
            method='Playlist.GetItems',
            params=dict(
                playlistid=PLAYLIST_VIDEO,
                # limits are zero indexed, position is one indexed
                limits=dict(start=position, end=position + 1),
                properties=Api.episode_properties
            )
        )
        item = result.get('result', {}).get('items')

        # Don't check if next item is an episode, just use it if it is there
        if not item:  # item.get('type') != 'episode':
            Api.log('Playlist error: next item not found', 1)
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

        Api.log('Got details of next playlist item: %s' % item, 2)
        return item

    def play_addon_item(self):
        data = self.data.get('play_url')
        if data:
            msg = 'Playing the next episode directly: {0}'.format(data)
            self.log(msg, 2)
            jsonrpc(
                method='Player.Open',
                params=dict(item=dict(file=data))
            )
        else:
            msg = 'Sending {encoding} data to add-on to play: {play_info}'
            msg = msg.format(dict(encoding=self.encoding, **self.data))
            self.log(msg, 2)
            event(
                message=self.data.get('id'),
                data=self.data.get('play_info'),
                sender='upnextprovider',
                encoding=self.encoding
            )

    def handle_addon_lookup_of_next_episode(self):
        if not self.data:
            return None
        data = self.data.get('next_episode')
        self.log('handle_addon_lookup_of_next_episode: {0}'.format(data), 2)
        return data

    def handle_addon_lookup_of_current_episode(self):
        if not self.data:
            return None
        data = self.data.get('current_episode')
        self.log('handle_addon_lookup_of_current_episode: {0}'.format(data), 2)
        return data

    def calc_popup_time(self, total_time):
        # Alway use metadata, when available
        popup_duration = get_int(self.data, 'notification_time')
        if 0 < popup_duration < total_time:
            cue = True
            return total_time - popup_duration, cue

        # Some consumers send the offset when the credits start (e.g. Netflix)
        popup_time = get_int(self.data, 'notification_offset')
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

    @staticmethod
    def get_now_playing():
        result = jsonrpc(
            method='Player.GetItem',
            params=dict(
                playerid=PLAYLIST_VIDEO,
                properties=Api.episode_properties,
            )
        )
        result = result.get('result', {}).get('item')

        if not result:
            Api.log('Player error: now playing media info not found', 1)
            return None

        Api.log('Got details of now playing media: %s' % result, 2)
        return result

    @staticmethod
    def get_next_episode_from_library(tvshowid, episodeid, unwatched_only):
        episode = Api.get_episode_from_library(tvshowid, episodeid)
        if not episode:
            Api.log('Library error: next episode info not found', 1)
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
                properties=Api.episode_properties,
                sort=dict(order='ascending', method='episode'),
                limits={'start': 0, 'end': 1},
                filter=filters
            )
        )
        result = result.get('result', {}).get('episodes')

        if not result:
            Api.log('Library error: next episode info not found', 1)
            episode = None
            new_season = False
            return episode, new_season

        new_season = episode.get('season') != result[0].get('season')
        episode.update(result[0])

        Api.log('Got details of next up episode: %s' % episode, 2)
        return episode, new_season

    @staticmethod
    def get_episode_from_library(tvshowid, episodeid):
        result = jsonrpc(
            method='VideoLibrary.GetTVShowDetails',
            params=dict(
                tvshowid=tvshowid,
                properties=Api.tvshow_properties
            )
        )
        result = result.get('result', {}).get('tvshowdetails')

        if not result:
            Api.log('Library error: episode info not found', 1)
            return None
        episode = result

        result = jsonrpc(
            method='VideoLibrary.GetEpisodeDetails',
            params=dict(
                episodeid=episodeid,
                properties=Api.episode_properties
            )
        )
        result = result.get('result', {}).get('episodedetails')

        if not result:
            Api.log('Library error: episode info not found', 1)
            return None
        episode.update(result)

        Api.log('Got details of episode: %s' % episode, 2)
        return episode

    @staticmethod
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
            Api.log('Library error: tvshowid not found', 1)
            return -1

        return get_int(result[0], 'tvshowid')

    @staticmethod
    def get_episodeid(tvshowid, season, episode):
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
                properties=Api.episode_properties,
                limits={'start': 0, 'end': 1},
                filter=filters
            )
        )
        result = result.get('result', {}).get('episodes')

        if not result:
            Api.log('Library error: episodeid not found', 1)
            return -1

        return get_int(result[0], 'episodeid')

    @staticmethod
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

        msg = 'Library update: id: {0}, playcount change from {1} to {2}'
        msg = msg.format(episodeid, current_playcount, playcount)
        Api.log(msg, 2)
        jsonrpc(method='VideoLibrary.SetEpisodeDetails', params=params)
