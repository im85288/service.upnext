# -*- coding: utf-8 -*-
# GNU General Public License v2.0 (see COPYING or https://www.gnu.org/licenses/gpl-2.0.txt)
"""resources/settings.xml (Kodi's version 1 settings format) against the strings and the code"""

import glob
import re
from xml.etree import ElementTree
import polib
import pytest
from skip import AUTO_SKIP_SETTINGS

ROOT = ElementTree.parse('resources/settings.xml').getroot()
SETTINGS = ROOT.findall('.//setting')
IDS = [setting.get('id') for setting in SETTINGS]
ENGLISH = {int(entry.msgctxt[1:]): entry.msgid
           for entry in polib.pofile('resources/language/resource.language.en_gb/strings.po')}


def test_new_settings_format():
    assert ROOT.get('version') == '1'
    assert [section.get('id') for section in ROOT.findall('section')] == ['service.upnext']
    assert len(IDS) == len(set(IDS))


@pytest.mark.parametrize('setting', SETTINGS, ids=IDS)
def test_every_setting_has_a_label_and_help_in_english(setting):
    # Kodi shows the help in the settings window's help area, which was empty in the old format (#395)
    assert int(setting.get('label')) in ENGLISH
    assert int(setting.get('help')) in ENGLISH


def test_category_group_and_option_labels_exist():
    labels = [element.get('label') for element in ROOT.iter() if element.tag in ('category', 'group', 'option')]
    missing = [label for label in labels if label and int(label) not in ENGLISH]
    assert not missing


def test_labels_stay_short():
    # Skins such as Arctic Fuse 3 cut long labels off; the explanation belongs in the help text
    long_labels = {setting.get('id'): ENGLISH[int(setting.get('label'))] for setting in SETTINGS
                   if len(re.sub(r'\[/?COLOR[^\]]*\]', '', ENGLISH[int(setting.get('label'))])) > 36}
    assert not long_labels


def test_dependencies_and_parents_name_real_settings():
    for setting in SETTINGS:
        assert setting.get('parent') in (None, *IDS)
        for dependency in setting.iter('dependency'):
            assert dependency.get('setting') in IDS
            assert dependency.get('type') in ('enable', 'visible')


def test_every_setting_the_code_reads_exists():
    used = set()
    for path in glob.glob('resources/lib/*.py'):
        with open(path, encoding='utf-8') as handle:
            used.update(re.findall(r"get_setting(?:_bool|_int)?\('(\w+)'", handle.read()))
    # skip.py reads the auto-skip settings through a lookup table
    used.update(AUTO_SKIP_SETTINGS.values())
    assert used and not used - set(IDS)


def test_translations_keep_label_markup_out_of_help():
    # 30651 was a grey separator label and is now Binge mode's help text
    for path in glob.glob('resources/language/*/strings.po'):
        for entry in polib.pofile(path):
            if entry.msgctxt == '#30651':
                assert '[COLOR' not in entry.msgid + entry.msgstr, path
