# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""The developer test window shows an episode from the library and the one before it"""

import popup
import script

UPCOMING = {'episodeid': 12, 'tvshowid': 3, 'season': 2, 'episode': 5, 'title': 'The Long Night',
            'showtitle': 'Slow Horses', 'plot': 'River follows a lead.', 'rating': 8.46, 'playcount': 0,
            'runtime': 2900, 'firstaired': '2023-12-01',
            'art': {'thumb': 'still-5.jpg', 'tvshow.fanart': 'fanart.jpg', 'tvshow.clearlogo': 'logo.png'}}
FINISHING = {'episodeid': 11, 'season': 2, 'episode': 4, 'title': 'Hello Goodbye', 'art': {'thumb': 'still-4.jpg'}}


def fake_library(episodes_before):
    calls = []

    def jsonrpc(**kwargs):
        calls.append(kwargs['params'])
        if 'tvshowid' in kwargs['params']:
            return {'result': {'episodes': episodes_before.pop(0)}}
        return {'result': {'episodes': [UPCOMING, dict(UPCOMING, episodeid=20, tvshowid=4)]}}
    return jsonrpc, calls


def test_a_random_episode_with_the_one_before_it(monkeypatch):
    jsonrpc, calls = fake_library([[], [FINISHING]])  # the first has no episode before it in the library
    monkeypatch.setattr(script, 'jsonrpc', jsonrpc)
    finishing, upcoming = script.library_preview()
    assert finishing == FINISHING and upcoming['tvshowid'] == 4
    assert calls[0]['sort'] == {'method': 'random'} and calls[0]['filter']['operator'] == 'greaterthan'
    assert calls[1]['filter'] == {'field': 'episode', 'operator': 'is', 'value': '4'}


def test_no_library_episode_gives_none(monkeypatch):
    monkeypatch.setattr(script, 'jsonrpc', lambda **kwargs: {'result': {'limits': {'total': 0}}})
    assert script.library_preview() is None


def test_preview_properties_as_the_popup_sets_them_and_the_finishing_episode(monkeypatch):
    monkeypatch.setattr(popup, 'get_global_setting', lambda setting: None)  # Kodi shows everything
    props = script.preview_properties(FINISHING, UPCOMING)
    assert (props['title'], props['tvshowtitle'], props['season'], props['episode']) == (
        'The Long Night', 'Slow Horses', '2', '5')
    assert (props['fanart'], props['clearlogo'], props['thumb'], props['rating']) == (
        'fanart.jpg', 'logo.png', 'still-5.jpg', '8.5')
    assert props['preview_finishing_art'] == 'still-4.jpg'
    assert (props['preview_finishing_season'], props['preview_finishing_episode'],
            props['preview_finishing_title']) == ('2', '4', 'Hello Goodbye')
    assert (props['preview_finishing_progress'], props['preview_finishing_remaining']) == ('96', '1:24')
    # No still for the finishing episode: the next one's landscape or fanart.
    assert script.preview_properties(dict(FINISHING, art={}), UPCOMING)['preview_finishing_art'] == 'fanart.jpg'


def test_preview_hides_an_unwatched_episodes_plot_and_still_as_kodi_does(monkeypatch):
    monkeypatch.setattr(popup, 'get_global_setting', lambda setting: [])  # nothing shown for unwatched items
    props = script.preview_properties(FINISHING, UPCOMING)  # UPCOMING is unwatched (playcount 0)
    assert props['plot'] == '' and props['thumb'] == 'fanart.jpg'  # the show's art in place of the still
    watched = script.preview_properties(FINISHING, dict(UPCOMING, playcount=1))
    assert watched['plot'] == 'River follows a lead.' and watched['thumb'] == 'still-5.jpg'
