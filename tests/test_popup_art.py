# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Popup images fall back to other art, and unwatched episodes follow Kodi's spoiler setting"""

import pytest
import popup
import upnext
from test_popups import make_popup

LIBRARY_ART = {  # what VideoLibrary.GetEpisodeDetails returns for an episode
    'thumb': 'still.jpg', 'season.poster': 'season-poster.jpg', 'tvshow.poster': 'show-poster.jpg',
    'tvshow.fanart': 'show-fanart.jpg', 'tvshow.landscape': 'show-landscape.jpg',
    'tvshow.clearart': 'show-clearart.png', 'tvshow.clearlogo': 'show-logo.png',
}


def test_show_art_is_used_first():
    assert popup.popup_art(LIBRARY_ART) == {
        'fanart': 'show-fanart.jpg', 'landscape': 'show-landscape.jpg', 'clearart': 'show-clearart.png',
        'clearlogo': 'show-logo.png', 'poster': 'show-poster.jpg', 'thumb': 'still.jpg',
    }


def test_missing_show_art_falls_back_to_the_season():
    art = {'thumb': 'still.jpg', 'season.poster': 'season-poster.jpg', 'season.fanart': 'season-fanart.jpg',
           'season.landscape': 'season-landscape.jpg', 'tvshow.landscape': ''}
    images = popup.popup_art(art)
    assert (images['poster'], images['fanart'], images['landscape']) == (
        'season-poster.jpg', 'season-fanart.jpg', 'season-landscape.jpg')


def test_add_on_art_without_the_tvshow_prefix_is_used():
    art = {'thumb': 'still.jpg', 'fanart': 'fanart.jpg', 'landscape': 'landscape.jpg', 'poster': 'poster.jpg',
           'clearlogo': 'logo.png', 'clearart': 'clearart.png'}
    assert popup.popup_art(art) == dict(art)


def test_no_art_gives_empty_images():
    assert popup.popup_art({}) == dict.fromkeys(('fanart', 'landscape', 'clearart', 'clearlogo', 'poster', 'thumb'), '')


@pytest.mark.parametrize('art,expected', [
    (LIBRARY_ART, 'show-landscape.jpg'),
    ({'thumb': 'still.jpg', 'tvshow.fanart': 'show-fanart.jpg'}, 'show-fanart.jpg'),
    ({'thumb': 'still.jpg'}, ''),
])
def test_hidden_thumbnail_is_replaced_by_show_art(art, expected):
    assert popup.popup_art(art, show_thumb=False)['thumb'] == expected


@pytest.mark.parametrize('setting,playcount,expected', [
    ([0, 1, 2], 0, (True, True)),      # Kodi's default shows everything
    ([0], 0, (False, False)),          # plots and thumbnails of unwatched episodes hidden
    ([0, 1], 0, (True, False)),
    ([0, 2], None, (False, True)),     # no play count counts as unwatched
    ([], 2, (True, True)),             # watched episodes are never hidden
    (None, 0, (True, True)),           # setting not available
])
def test_spoilers_follow_kodi(monkeypatch, setting, playcount, expected):
    calls = []
    monkeypatch.setattr(popup, 'get_global_setting', lambda name: calls.append(name) or setting)
    item = {} if playcount is None else {'playcount': playcount}
    assert popup.spoilers_allowed(item) == expected
    assert calls == ([] if playcount else ['videolibrary.showunwatchedplots'])


@pytest.mark.parametrize('media_type,setting,expected', [
    ('episode', [0], (False, False)),
    ('movie', [0], (True, True)),       # movie plots allowed, episode ones not
    ('movie', [1, 2], (False, True)),   # Kodi never hides movie thumbnails
    ('unknown', [], (True, True)),      # plain files from a playlist have no library details to hide
])
def test_spoilers_follow_the_item_type(monkeypatch, media_type, setting, expected):
    monkeypatch.setattr(popup, 'get_global_setting', lambda name: setting)
    assert popup.spoilers_allowed({'type': media_type, 'playcount': 0}) == expected


@pytest.mark.parametrize('setting,plot,thumb', [
    ([0, 1, 2], 'A plot.', 'still.jpg'),
    ([0], '', 'show-landscape.jpg'),
])
def test_popup_properties(monkeypatch, setting, plot, thumb):
    monkeypatch.setattr(popup, 'get_global_setting', lambda name: setting)
    page = make_popup(upnext.UpNext)
    page.set_item({'art': LIBRARY_ART, 'plot': 'A plot.', 'playcount': 0, 'season': 1, 'episode': 2, 'title': 'Pilot'})
    page.set_info()
    assert (page.properties['plot'], page.properties['thumb']) == (plot, thumb)
    assert (page.properties['fanart'], page.properties['poster']) == ('show-fanart.jpg', 'show-poster.jpg')


def test_get_global_setting(monkeypatch):
    import utils  # pylint: disable=import-outside-toplevel
    calls = []

    def jsonrpc(**kwargs):
        calls.append(kwargs)
        return {'result': {'value': [0, 1]}} if kwargs['params']['setting'] == 'videolibrary.showunwatchedplots' else {}

    monkeypatch.setattr(utils, 'jsonrpc', jsonrpc)
    assert utils.get_global_setting('videolibrary.showunwatchedplots') == [0, 1]
    assert utils.get_global_setting('no.such.setting') is None
    assert calls[0] == {'method': 'Settings.GetSettingValue', 'params': {'setting': 'videolibrary.showunwatchedplots'}}
