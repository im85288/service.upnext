# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""Translations must load in Kodi and keep the English label formatting"""

import re
from pathlib import Path

import polib
import pytest

LANGUAGES = Path(__file__).resolve().parent.parent / 'resources' / 'language'
# Kodi only reads a folder named after one of its language add-ons (resource.language.<id>).
# Add a new translation's id here after checking Kodi has that language add-on.
KODI_LANGUAGES = {
    'cs_cz', 'de_de', 'el_gr', 'en_gb', 'es_es', 'fi_fi', 'fr_fr', 'hi_in', 'hr_hr', 'hu_hu', 'it_it',
    'ja_jp', 'ko_kr', 'nl_nl', 'pl_pl', 'pt_br', 'ro_ro', 'ru_ru', 'sk_sk', 'sv_se', 'zh_cn', 'zh_tw',
}
# Kodi label tags and info labels; a missing closing tag runs its formatting into the rest of the label
MARKUP = re.compile(r'\$INFO\[[^\]]*\]|\$ADDON\[[^\]]*\]|\[/?(?:B|I|UPPERCASE|LOWERCASE|CAPITALIZE)\]|\[/?COLOR[^\]]*\]')
FOLDERS = sorted(path for path in LANGUAGES.iterdir() if path.is_dir())


def strings(folder):
    # polib also reads entries whose msgid or msgstr is wrapped over several lines
    return {entry.msgctxt: (entry.msgid, entry.msgstr) for entry in polib.pofile(str(folder / 'strings.po'))}


@pytest.mark.parametrize('folder', FOLDERS, ids=lambda folder: folder.name)
def test_folder_is_a_kodi_language(folder):
    assert folder.name.startswith('resource.language.')
    assert folder.name[len('resource.language.'):] in KODI_LANGUAGES


@pytest.mark.parametrize('folder', FOLDERS, ids=lambda folder: folder.name)
def test_translations_keep_the_label_markup(folder):
    english = strings(LANGUAGES / 'resource.language.en_gb')
    different = [msgctxt for msgctxt, (_, msgstr) in strings(folder).items()
                 if msgstr and msgctxt in english
                 and sorted(MARKUP.findall(msgstr)) != sorted(MARKUP.findall(english[msgctxt][0]))]
    assert not different
