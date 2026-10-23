"""Synthetic UI properties exercise original status readers, never a product."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.script_manager_status import validate, manager_status, missing_error
from adapters.token_script_file_ui import metadata_fields, validate_metadata
from adapters.normal_ui import NativeUIError
from self_tests.test_normal_script_missing import URL


def observed(**changes):
    status = 'Failed to load ' + URL + ': server returned 404'
    return dict(managerSourceVersion=2, available=True,
        componentSource='file:///actual/client/resources/qml/hifi/dialogs/TabletRunningScripts.qml',
        statusText=status, labelText=status, rootVisible=True, labelVisible=True,
        errorUrl=URL,errorEpochMs=20000) | changes


def snapshot(value=None):
    return dict(fileControlsVersion=1, ready=True,
        controls=[dict(id='scripts.from-file', token='original-native-token', enabled=True,
                       manager=observed() if value is None else value)])


class ScriptManagerStatusTests(unittest.TestCase):
    def test_original_root_and_displayed_label_are_preserved_without_error_category_projection(self):
        packet = snapshot(); actual = missing_error(packet, URL)
        self.assertEqual(packet['controls'][0]['manager'], actual)
        actual['labelText'] = 'changed caller copy'
        self.assertNotEqual(actual, manager_status(packet))
        self.assertNotIn('error', manager_status(packet))

    def test_root_status_with_ignored_label_or_hidden_page_cannot_prove_display(self):
        for changes in ({'labelText': ''}, {'labelText': 'old error'}, {'rootVisible': False}, {'labelVisible': False}):
            with self.subTest(changes=changes), self.assertRaises(NativeUIError): missing_error(snapshot(observed(**changes)), URL)

    def test_foreign_url_or_loading_status_cannot_be_adopted(self):
        for text in ('Loading missing.js', 'Failed to load ' + URL + '-foreign',
                     'Failed to load ' + URL.replace('fixture.test', 'foreign.test')):
            with self.subTest(text=text), self.assertRaises(NativeUIError):
                missing_error(snapshot(observed(statusText=text, labelText=text)), URL)

    def test_compact_label_needs_actual_full_url_and_current_signal_epoch(self):
        text='Failed to load missing.js'
        actual=missing_error(snapshot(observed(statusText=text,labelText=text)),URL,after_epoch=19999)
        self.assertEqual(URL,actual['errorUrl']);self.assertEqual(text,actual['labelText'])
        for fields in ({'errorUrl':URL.replace('fixture.test','foreign.test')},
                       {'errorEpochMs':19998},{'errorUrl':'','errorEpochMs':0},
                       {'managerSourceVersion':1}):
            with self.subTest(fields=fields),self.assertRaises(NativeUIError):
                missing_error(snapshot(observed(statusText=text,labelText=text,**fields)),URL,after_epoch=19999)

    def test_actual_optional_error_suffix_is_preserved_without_inventing_it(self):
        text = 'Failed to load ' + URL
        self.assertEqual(text, missing_error(snapshot(observed(statusText=text, labelText=text)), URL)['labelText'])

    def test_unavailable_old_or_missing_extension_is_not_an_empty_measured_status(self):
        unavailable = dict(managerSourceVersion=2, available=False)
        self.assertEqual(unavailable, validate(unavailable))
        for packet in (snapshot(unavailable), dict(fileControlsVersion=1, ready=True, controls=[]),
                       dict(fileControlsVersion=1, ready=True, controls=[dict(id='scripts.from-file')])):
            with self.subTest(packet=packet), self.assertRaises(NativeUIError): manager_status(packet)

    def test_duplicate_manager_unsupported_source_and_closed_inventory_are_rejected(self):
        for fault in ('duplicate', 'closed', 'version', 'boolean-version'):
            packet = snapshot()
            if fault == 'duplicate': packet['controls'].append(deepcopy(packet['controls'][0]))
            elif fault == 'closed': packet['ready'] = False
            else: packet['fileControlsVersion'] = True if fault == 'boolean-version' else 2
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): manager_status(packet)

    def test_native_property_types_foreign_context_unknown_or_missing_fields_fail(self):
        for edit in ({'managerSourceVersion': True}, {'managerSourceVersion':1}, {'available': 1}, {'rootVisible': 1}, {'statusText': None},
                     {'labelText': 'x' * 8193}, {'labelText': 'private\0bytes'}, {'extra': True},
                     {'componentSource': 'http://foreign.test/hifi/dialogs/TabletRunningScripts.qml'},
                     {'componentSource': 'file://foreign/hifi/dialogs/TabletRunningScripts.qml'},
                     {'componentSource': observed()['componentSource'] + '?token=private'},
                     {'componentSource': 'file:///private\0/hifi/dialogs/TabletRunningScripts.qml'},
                     {'componentSource': 'qrc:/different.qml'}):
            with self.subTest(edit=edit), self.assertRaises(NativeUIError): validate(observed(**edit))
        value = observed(); del value['labelVisible']
        with self.assertRaises(NativeUIError): validate(value)

    def test_optional_source_does_not_break_old_picker_metadata_but_complete_reader_requires_it(self):
        old = dict(id='scripts.from-file', enabled=True, token='old-token')
        self.assertEqual(set(), metadata_fields(old['id'], old)); validate_metadata(old)
        new = snapshot()['controls'][0]
        self.assertEqual({'manager'}, metadata_fields(new['id'], new)); validate_metadata(new)
        new['manager']['available'] = False
        with self.assertRaises(NativeUIError): validate_metadata(new)

    def test_original_qml_signal_sets_status_but_a_broken_display_binding_still_fails(self):
        qml = (Path(__file__).resolve().parents[3] / 'interface/resources/qml/hifi/dialogs/TabletRunningScripts.qml').read_text()
        import re
        handler = re.search(r'function onScriptLoadError\(url, error\) \{([^}]+)\}', qml).group(1)
        filename=re.search(r'function filename\(url\) \{([^}]+)\}',qml).group(1)
        program = 'let root={status:"",lastLoadErrorUrl:"",lastLoadErrorEpochMs:0};root.filename=function(url){'+filename+'};const url=' + json.dumps(URL) + ',error="server returned 404";'
        program += handler + ';process.stdout.write(JSON.stringify(root));'
        completed = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, completed.returncode, completed.stderr)
        actual=json.loads(completed.stdout);status=actual['status']
        self.assertEqual(URL,actual['lastLoadErrorUrl']);self.assertGreater(actual['lastLoadErrorEpochMs'],0)
        self.assertEqual(status, missing_error(snapshot(observed(statusText=status, labelText=status,
            errorUrl=actual['lastLoadErrorUrl'],errorEpochMs=actual['lastLoadErrorEpochMs'])), URL)['labelText'])
        with self.assertRaises(NativeUIError): missing_error(snapshot(observed(statusText=status, labelText='')), URL)


if __name__ == '__main__': unittest.main()
