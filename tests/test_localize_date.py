# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)

import pytest
import utils


@pytest.fixture(autouse=True)
def date_format(monkeypatch):
    monkeypatch.setattr(utils, 'getRegion', lambda name: '%d/%m/%Y')


def test_full_date_is_localized():
    assert utils.localize_date('2026-10-20') == '20/10/2026'


def test_date_with_time_is_localized():
    assert utils.localize_date('2026-10-20 21:00:00') == '20/10/2026'


@pytest.mark.parametrize('value,expected', [
    ('2026', '2026'),
    ('2026-10', '2026-10'),
    ('', ''),
    ('unknown', 'unknown'),
    ('2026-13-40', '2026-13-40'),
    (2026, '2026'),
    (None, ''),
])
def test_partial_or_missing_date_is_returned_as_text(value, expected):
    assert utils.localize_date(value) == expected
