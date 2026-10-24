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
