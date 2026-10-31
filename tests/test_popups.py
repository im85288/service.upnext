# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Button and remote behaviour shared by both popups"""

import pytest
import popup
import stillwatching
import upnext
from test_playbackmanager import Stub

CONFIRMED = {
    upnext.UpNext: lambda page: page.is_watch_now(),
    stillwatching.StillWatching: lambda page: page.is_still_watching(),
}


def make_popup(popup_class):
    page = object.__new__(popup_class)
    page.closed = 0
    page.properties = {}
    page.percents = []
    page.close = lambda: setattr(page, 'closed', page.closed + 1)
    page.setProperty = page.properties.__setitem__
    page.getControl = lambda control: Stub(setPercent=page.percents.append)
    return page


@pytest.fixture(params=[upnext.UpNext, stillwatching.StillWatching])
def page(request):
    return make_popup(request.param)


def test_both_popups_share_the_base_class():
    assert issubclass(upnext.UpNext, popup.Popup) and issubclass(stillwatching.StillWatching, popup.Popup)


def test_main_button_confirms_and_closes(page):
    page.onClick(3012)
    assert CONFIRMED[type(page)](page)
    assert not page.is_cancel() and not page.is_dismissed()
    assert page.closed == 1


def test_close_button_cancels_without_dismissing(page):
    page.onClick(3013)
    assert page.is_cancel() and not page.is_dismissed()
    assert not CONFIRMED[type(page)](page)
    assert page.closed == 1


def test_back_dismisses(page):
    page.onAction(popup.ACTION_NAV_BACK)
    assert page.is_cancel() and page.is_dismissed()
    assert page.closed == 1


def test_stop_action_only_closes(page):
    page.onAction(popup.ACTION_PLAYER_STOP)
    assert not page.is_cancel() and not page.is_dismissed()
    assert page.closed == 1


def test_other_clicks_and_actions_are_ignored(page):
    page.onClick(10)
    page.onAction(7)
    assert page.closed == 0


def test_progress_control_and_countdown(page):
    page.set_progress_step_size(10)
    page.update_progress_control(remaining=5)
    assert page.percents == [90] and page.properties['remaining'] == '05'
    page.update_progress_control(remaining=0, progress=150)
    assert page.percents[-1] == 100 and page.properties['remaining'] == '00'


def test_base_popup_needs_a_main_button_action():
    with pytest.raises(NotImplementedError):
        make_popup(popup.Popup).onClick(3012)


@pytest.mark.parametrize('popup_class', [upnext.UpNext, stillwatching.StillWatching])
@pytest.mark.parametrize('stop_after_close,label', [(True, 30033), (False, 30034)])
def test_on_init_fills_in_the_episode_and_progress(monkeypatch, popup_class, stop_after_close, label):
    monkeypatch.setattr(upnext, 'get_setting_bool', lambda key: stop_after_close if key == 'stopAfterClose' else False)
    monkeypatch.setattr(upnext, 'localize', lambda string_id: string_id)
    page = popup_class()  # the real constructor, through Popup.__init__
    assert page.action_exitkeys_id == [10, 13] and page.progress_control is None
    labels, percents, properties = [], [], {}
    page.setProperty = properties.__setitem__
    page.getControl = lambda control: Stub(setPercent=percents.append, setLabel=labels.append)
    page.set_item({'title': 'Pilot', 'season': 1, 'episode': 2, 'art': {'thumb': 'thumb.jpg'}})
    page.onInit()
    assert (properties['title'], properties['seasonepisode'], properties['thumb']) == ('Pilot', '1x2.', 'thumb.jpg')
    assert percents == [100]
    # Only Up Next labels its Close button, as Stop when stopping after close is enabled
    assert labels == ([label] if popup_class is upnext.UpNext else [])


@pytest.mark.parametrize('direct_button', [False, True])
def test_playback_focus_navigates_into_existing_skin_controls(direct_button):
    page = make_popup(upnext.UpNext)
    added, focused = [], []
    target = object()

    def control(identifier):
        if identifier == 20 and direct_button:
            raise RuntimeError('Skin has a direct button')
        return target

    page.getControl = control
    page.addControl = added.append
    page.setFocus = focused.append
    page.prepare_playback_controls()
    assert added == focused == [page.playback_control]
    assert page.playback_control.navigation == (target,) * 4


@pytest.mark.parametrize('use_action', [False, True])
def test_opening_playback_controls_neither_advances_nor_cancels(monkeypatch, use_action):
    page = make_popup(upnext.UpNext)
    commands = []
    page.playback_control = Stub(getId=lambda: 9000)
    monkeypatch.setattr(upnext, 'executebuiltin', commands.append)
    if use_action:
        page.onAction(upnext.ACTION_SHOW_OSD)
    else:
        page.onClick(9000)
    assert page.closed == 0
    assert commands == ['ActivateWindow(videoosd)']
    assert not page.is_cancel() and not page.is_dismissed() and not page.is_watch_now()


@pytest.mark.parametrize('focus', [3012, 3013])
def test_up_from_a_popup_button_returns_focus_to_playback_controls(focus):
    page = make_popup(upnext.UpNext)
    page.playback_control = Stub(getId=lambda: 9000)
    page.getFocusId = lambda: focus
    selected = []
    page.setFocus = selected.append
    page.onAction(upnext.ACTION_MOVE_UP)
    assert selected == [page.playback_control]
    assert page.closed == 0 and not page.is_cancel() and not page.is_watch_now()


def test_up_on_neutral_focus_leaves_navigation_to_kodi():
    page = make_popup(upnext.UpNext)
    page.playback_control = Stub(getId=lambda: 9000)
    page.getFocusId = lambda: 9000
    page.setFocus = lambda _: pytest.fail('Neutral focus must allow Kodi navigation')
    page.onAction(upnext.ACTION_MOVE_UP)
    assert page.closed == 0


def test_reopened_popup_restores_neutral_focus(monkeypatch):
    page = make_popup(upnext.UpNext)
    page.playback_control = Stub(getId=lambda: 9000)
    selected = []
    page.setFocus = selected.append
    page.addControl = lambda _: pytest.fail('Do not add a second focus target')
    monkeypatch.setattr(upnext, 'get_setting_bool', lambda key: key == 'selectOpensPlaybackControls')
    monkeypatch.setattr(upnext, 'localize', lambda value: value)
    page.getControl = lambda _: Stub(setPercent=lambda _: None, setLabel=lambda _: None)
    page.onInit()
    assert selected == [page.playback_control] and page.playback_dialog_id == 13001


def test_hidden_popup_returns_after_controls_close_without_cancelling(monkeypatch):
    page = make_popup(upnext.UpNext)
    page.playback_control = Stub(getId=lambda: 9000)
    page.playback_dialog_id = 13001
    events = []
    page.show = lambda: events.append('show')
    monkeypatch.setattr(upnext, 'executebuiltin', lambda command: events.append(command))
    clock = [0.0]
    monkeypatch.setattr(upnext, 'monotonic', lambda: clock[0])
    visible = {'Window.IsVisible(videoosd)': False, 'Window.IsVisible(13001)': False}
    monkeypatch.setattr(upnext, 'getCondVisibility', visible.__getitem__)
    page.open_playback_controls()
    page.restore_after_playback_controls()  # GUI activation is asynchronous
    assert events == ['ActivateWindow(videoosd)']
    visible['Window.IsVisible(videoosd)'] = True
    clock[0] = 1
    page.restore_after_playback_controls()
    visible['Window.IsVisible(videoosd)'] = False
    clock[0] = 2
    page.restore_after_playback_controls()
    assert events[-1] == 'show' and not page.is_cancel() and not page.is_watch_now()
    page.restore_after_playback_controls()
    assert events.count('show') == 1


def test_control_return_does_not_reopen_a_dismissed_popup(monkeypatch):
    page = make_popup(upnext.UpNext)
    page.playback_dialog_id = 13001
    page.controls_pending = page.controls_seen = True
    page.cancel = True
    page.show = lambda: pytest.fail('Cancelled popup must remain closed')
    monkeypatch.setattr(upnext, 'getCondVisibility', lambda _: False)
    page.restore_after_playback_controls()
