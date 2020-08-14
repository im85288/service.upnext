# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

from __future__ import absolute_import, division, unicode_literals
from xbmc import PLAYLIST_VIDEO
from utils import event, get_setting_bool, get_setting_int, jsonrpc, log as ulog


class Api:
    """Main API class"""
    _shared_state = {}

    episode_properties = ['title',
                          'playcount',
                          'season',
                          'episode',
                          'showtitle',
                          'originaltitle',
                          'plot',
                          'votes',
                          'file',
                          'rating',
                          'ratings',
                          'userrating',
                          'resume',
                          'tvshowid',
                          'firstaired',
                          'art',
                          'streamdetails',
                          'runtime',
                          'director',
                          'writer',
                          #'cast',
                          'dateadded',
                          'lastplayed']

    tvshow_properties = ['title',
                         'studio',
                         'year',
                         'plot',
                         #'cast',
                         'rating',
                         'ratings',
                         'userrating',
                         'votes',
                         'genre',
                         'episode',
                         'season',
                         'runtime',
                         'mpaa',
                         'premiered',
                         'playcount',
                         'lastplayed',
                         'sorttitle',
                         'originaltitle',
                         'art',
                         'tag',
                         'dateadded',
                         'watchedepisodes',
                         'imdbnumber']

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
        return self.data

    def reset_addon_data(self):
        self.data = {}

    def addon_data_received(self, data, encoding='base64'):
        self.log('addon_data_received called with data %s' % data, 2)
        self.data = data
        self.encoding = encoding

    @staticmethod
    def play_kodi_item(episode):
        jsonrpc(method='Player.Open', params=dict(item=dict(episodeid=episode.get('episodeid'))))

    def queue_next_item(self, episode):
        next_item = {}
        if not self.data:
            next_item.update(episodeid=episode.get('episodeid'))
        elif self.data.get('play_url'):
            next_item.update(file=self.data.get('play_url'))

        if next_item:
            jsonrpc(method='Playlist.Add', params=dict(playlistid=PLAYLIST_VIDEO, item=next_item))

        return bool(next_item)

    @staticmethod
    def reset_queue():
        jsonrpc(method='Playlist.Remove', params=dict(playlistid=PLAYLIST_VIDEO, position=0))

    @staticmethod
    def dequeue_next_item():
        jsonrpc(method='Playlist.Remove', params=dict(playlistid=PLAYLIST_VIDEO, position=1))
        return False

    @staticmethod
    def get_next_in_playlist(position):
        result = jsonrpc(method='Playlist.GetItems', params=dict(
            playlistid=PLAYLIST_VIDEO,
            # limits are zero indexed, position is one indexed
            limits=dict(start=position, end=position+1),
            properties=['art', 'dateadded', 'episode', 'file', 'firstaired', 'lastplayed',
                        'playcount', 'plot', 'rating', 'resume', 'runtime', 'season',
                        'showtitle', 'streamdetails', 'title', 'tvshowid', 'writer'],
        ))
        item = result.get('result', {}).get('items')

        # Don't check if next item is an episode, just use it if it is there
        if not item: #item.get('type') != 'episode':
            Api.log('Playlist error, next item not found', 1)
            return None

        item = item[0]
        if not item.get('title'):
            item['title'] = item.get('label', '')
        item['episodeid'] = item.get('id', position+1)
        item['tvshowid'] = item.get('tvshowid', '-1')

        Api.log('Got details of next playlist item: %s' % item, 2)
        return item

    def play_addon_item(self):
        if self.data.get('play_url'):
            self.log('Playing the next episode directly: %(play_url)s' % self.data, 2)
            jsonrpc(method='Player.Open', params=dict(item=dict(file=self.data.get('play_url'))))
        else:
            self.log('Sending %(encoding)s data to add-on to play: %(play_info)s' % dict(encoding=self.encoding, **self.data), 2)
            event(message=self.data.get('id'), data=self.data.get('play_info'), sender='upnextprovider', encoding=self.encoding)

    def handle_addon_lookup_of_next_episode(self):
        if not self.data:
            return None
        self.log('handle_addon_lookup_of_next_episode episode returning data %(next_episode)s' % self.data, 2)
        return self.data.get('next_episode')

    def handle_addon_lookup_of_current_episode(self):
        if not self.data:
            return None
        self.log('handle_addon_lookup_of_current episode returning data %(current_episode)s' % self.data, 2)
        return self.data.get('current_episode')

    def notification_time(self, total_time=None):
        # Alway use metadata, when available
        if self.data.get('notification_time'):
            return int(self.data.get('notification_time'))

        # Some consumers send the offset when the credits start (e.g. Netflix)
        if total_time and self.data.get('notification_offset'):
            offset = int(self.data.get('notification_offset'))
            if offset < total_time:
                return total_time - offset

        # Use a customized notification time, when configured
        if total_time and get_setting_bool('customAutoPlayTime'):
            if total_time > 60 * 60:
                return get_setting_int('autoPlayTimeXL')
            if total_time > 40 * 60:
                return get_setting_int('autoPlayTimeL')
            if total_time > 20 * 60:
                return get_setting_int('autoPlayTimeM')
            if total_time > 10 * 60:
                return get_setting_int('autoPlayTimeS')
            return get_setting_int('autoPlayTimeXS')

        # Use one global default, regardless of episode length
        return get_setting_int('autoPlaySeasonTime')

    @staticmethod
    def get_now_playing():
        Api.log('Getting details of now playing media', 2)
        result = jsonrpc(method='Player.GetItem', params=dict(
            playerid=PLAYLIST_VIDEO,
            properties=['episode', 'genre', 'playcount', 'plotoutline', 'season', 'showtitle', 'tvshowid'],
        ))

        Api.log('Got details of now playing media %s' % result, 2)
        return result

    @staticmethod
    def get_next_episode_from_library(tvshowid, current_file, include_watched, episodeid):
        episode = Api.get_episode_from_library(tvshowid, episodeid)
        if not episode:
            Api.log('Library error, next episode info not found', 1)
            return None

        filters = [{'or': [{'and': [{'field': 'season', 'operator': 'is', 'value': str(episode['season'])},
                                    {'field': 'episode', 'operator': 'greaterthan', 'value': str(episode['episode'])}]},
                           {'field': 'season', 'operator': 'greaterthan', 'value': str(episode['season'])}]}]
        if not include_watched:
            filters.append({'field': 'playcount', 'operator': 'lessthan', 'value': '1'})
        filter = {'and': filters}

        result = jsonrpc(method='VideoLibrary.GetEpisodes', params=dict(
                         tvshowid=int(tvshowid),
                         properties=Api.episode_properties,
                         sort=dict(order='ascending', method='episode'),
                         limits={'start': 0, 'end': 1},
                         filter=filter
                         ))
        result = result.get('result', {}).get('episodes')

        if not result:
            Api.log('Library error, next episode info not found', 1)
            return None
        episode.update(result[0])

        Api.log('Got details of next up episode %s' % episode, 2)
        return episode

    @staticmethod
    def get_episode_from_library(tvshowid, episodeid):
        result = jsonrpc(method='VideoLibrary.GetTVShowDetails', params=dict(
                         tvshowid=int(tvshowid),
                         properties=Api.tvshow_properties
                         ))
        result = result.get('result', {}).get('tvshowdetails')

        if not result:
            Api.log('Library error, episode info not found', 1)
            return None
        episode = result

        result = jsonrpc(method='VideoLibrary.GetEpisodeDetails', params=dict(
                         episodeid=int(episodeid),
                         properties=Api.episode_properties
                         ))
        result = result.get('result', {}).get('episodedetails')

        if not result:
            Api.log('Library error, episode info not found', 1)
            return None
        episode.update(result)

        Api.log('Got details of episode %s' % episode, 2)
        return episode

    @staticmethod
    def showtitle_to_id(title):
        result = jsonrpc(method='VideoLibrary.GetTVShows', params=dict(
                         properties=['title'],
                         limits={'start': 0, 'end': 1},
                         filter={'field': 'title', 'operator': 'is', 'value': str(title)}
                         ))
        result = result.get('result', {}).get('tvshows')

        if not result:
            Api.log('Library error, tvshowid not found', 1)
            return '-1'

        return result[0].get('tvshowid')

    @staticmethod
    def get_episode_id(tvshowid, season, episode):
        filters = [{'field': 'season', 'operator': 'is', 'value': str(season)},
                   {'field': 'episode', 'operator': 'is', 'value': str(episode)}]
        filter = {'and': filters}

        result = jsonrpc(method='VideoLibrary.GetEpisodes', params=dict(
                         tvshowid=int(tvshowid),
                         properties=Api.episode_properties,
                         limits={'start': 0, 'end': 1},
                         filter=filter
                         ))

        result = result.get('result', {}).get('episodes')

        if not result:
            Api.log('Library error, episodeid not found', 1)
            return '0'

        return result[0].get('episodeid')
