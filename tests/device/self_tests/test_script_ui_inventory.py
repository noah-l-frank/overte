"""Synthetic original UI inventories verify readers, never native rendering."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.script_ui_inventory import validate, ui_state
from adapters.normal_ui import NativeUIError
from self_tests.test_script_manager_status import observed


def picker(**changes):
    return dict(componentSource='qrc:/qml/dialogs/NativeFileBrowser.qml', visible=True,
                closing=False, requestId='', errorText='') | changes


def inventory(managers=None, pickers=None, **changes):
    return dict(inventoryVersion=1, complete=True, managers=[] if managers is None else managers,
                pickers=[] if pickers is None else pickers, tabletPresent=True, tabletShown=True) | changes


def snapshot(value):
    return dict(fileControlsVersion=1, ready=True, controls=[], scriptInventory=value)


class ScriptUiInventoryTests(unittest.TestCase):
    def test_complete_empty_inventory_measures_closed_ui_without_an_input_carrier(self):
        self.assertEqual(dict(open=False, picker=False, manager=None, pickerSource=None, systemPending=False),
                         ui_state(snapshot(inventory())))

    def test_original_manager_remains_readable_when_picker_suppresses_from_file_input(self):
        manager = observed(); original = snapshot(inventory([manager], [picker()]))
        state = ui_state(original)
        self.assertTrue(state['open']); self.assertTrue(state['picker'])
        self.assertEqual(manager, state['manager']); self.assertEqual(picker(), state['pickerSource'])
        self.assertEqual([], original['controls'])
        state['manager']['labelText'] = 'caller changed'
        self.assertEqual(manager, ui_state(original)['manager'])

    def test_hidden_retained_root_is_not_reopened_by_its_old_error(self):
        self.assertEqual(False, ui_state(snapshot(inventory([observed(rootVisible=False, labelVisible=False)])))['open'])
        self.assertIsNone(ui_state(snapshot(inventory([observed(rootVisible=False, labelVisible=False)])))['manager'])

    def test_retained_offscreen_geometry_does_not_override_original_hidden_tablet(self):
        state = ui_state(snapshot(inventory([observed()], [picker()], tabletShown=False)))
        self.assertFalse(state['open']); self.assertFalse(state['picker']); self.assertIsNone(state['manager'])

    def test_absent_proxy_is_a_read_only_lookup_not_permission_to_create_one(self):
        self.assertFalse(ui_state(snapshot(inventory(tabletPresent=False, tabletShown=False)))['open'])
        with self.assertRaises(NativeUIError):
            ui_state(snapshot(inventory([observed()], tabletPresent=False, tabletShown=False)))

    def test_one_visible_original_root_can_coexist_with_a_hidden_old_root(self):
        old = observed(rootVisible=False, labelVisible=False, statusText='old', labelText='old')
        current = observed(statusText='actual root', labelText='actual label')
        self.assertEqual(current, ui_state(snapshot(inventory([old, current])))['manager'])

    def test_root_and_label_disagreement_is_preserved_instead_of_repaired(self):
        manager = observed(statusText='current callback', labelText='old displayed message')
        self.assertEqual(manager, ui_state(snapshot(inventory([manager])))['manager'])

    def test_incomplete_unavailable_old_or_missing_sources_are_never_closed_success(self):
        values = [snapshot(inventory(complete=False)), dict(fileControlsVersion=1, ready=True, controls=[]),
                  snapshot(inventory([dict(managerSourceVersion=1, available=False)]))]
        for value in values:
            with self.subTest(value=value), self.assertRaises(NativeUIError): ui_state(value)

    def test_overflow_and_partial_scans_cannot_prove_absence(self):
        for value in (inventory(complete=False, managers=[observed()]),
                      inventory(managers=[observed()] * 17), inventory(pickers=[picker()] * 17)):
            with self.subTest(value=value), self.assertRaises(NativeUIError): validate(value)

    def test_duplicate_visible_managers_pickers_and_orphan_picker_fail(self):
        for value in (inventory([observed(), observed()]), inventory([observed()], [picker(), picker()]),
                      inventory([], [picker()]), inventory([observed(rootVisible=False, labelVisible=False)], [picker()])):
            with self.subTest(value=value), self.assertRaises(NativeUIError): ui_state(snapshot(value))

    def test_closing_ack_does_not_hide_still_visible_picker(self):
        actual = ui_state(snapshot(inventory([observed()], [picker(closing=True)])))
        self.assertTrue(actual['picker']); self.assertTrue(actual['pickerSource']['closing'])

    def test_hidden_picker_with_outstanding_system_request_is_not_clean(self):
        actual = ui_state(snapshot(inventory(pickers=[picker(visible=False, requestId='original-request')])))
        self.assertFalse(actual['open']); self.assertFalse(actual['picker']); self.assertTrue(actual['systemPending'])

    def test_foreign_or_missing_picker_context_and_wrong_property_types_fail(self):
        for changes in ({'visible': 1}, {'closing': 'false'}, {'requestId': None}, {'errorText': None},
                        {'errorText': 'private\0data'}, {'requestId': 'x' * 4097}, {'extra': False},
                        {'componentSource': 'https://foreign.test/dialogs/NativeFileBrowser.qml'},
                        {'componentSource': 'file://foreign/dialogs/NativeFileBrowser.qml'},
                        {'componentSource': 'qrc:/qml/dialogs/NativeFileBrowser.qml?token=private'},
                        {'componentSource': 'qrc:/qml/dialogs/NativeFileBrowser.qml#'},
                        {'componentSource': 'qrc:/different.qml'}):
            with self.subTest(changes=changes), self.assertRaises(NativeUIError): validate(inventory(pickers=[picker(**changes)]))
        row = picker(); del row['closing']
        with self.assertRaises(NativeUIError): validate(inventory(pickers=[row]))

    def test_unknown_versions_shape_and_inconsistent_label_visibility_fail(self):
        for changes in ({'inventoryVersion': True}, {'inventoryVersion': 2}, {'complete': 1}, {'managers': None},
                        {'pickers': {}}, {'unknown': []}, {'tabletShown': 1}, {'tabletPresent': 1}, {'tabletPresent': False}):
            value = inventory() | changes
            with self.subTest(changes=changes), self.assertRaises(NativeUIError): validate(value)
        with self.assertRaises(NativeUIError): validate(inventory([observed(rootVisible=False, labelVisible=True)]))
        original = inventory(); del original['complete']
        with self.assertRaises(NativeUIError): validate(original)

    def test_not_ready_or_wrong_owning_inventory_version_cannot_qualify_ui(self):
        for edit in ({'ready': False}, {'ready': 1}, {'fileControlsVersion': True}, {'fileControlsVersion': 2}):
            value = snapshot(inventory()) | edit
            with self.subTest(edit=edit), self.assertRaises(NativeUIError): ui_state(value)


if __name__ == '__main__': unittest.main()
