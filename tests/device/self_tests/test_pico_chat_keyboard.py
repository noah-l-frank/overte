"""No-build counterexamples for original Pico entity-keyboard observation.

All entities here are synthetic. Native source is uncompiled and no headset is
used; these tests qualify validation/ownership behavior only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_chat_view import measured_keyboard, measured_view, vr_keyboard
from adapters.normal_ui import NativeUIError
from self_tests.test_native_chat_view import Boundary, RUN, TEXT


def identifier(index): return f'00000000-0000-4000-8000-{index:012x}'


def keyboard(raised=True):
    result = dict(available=True, backend='native-vr-entity-keyboard', visible=raised, instance='e' * 32,
        sequence=1, created=True, enabled=True, raised=raised, inputToHud=False,
        inputTarget=identifier(6) if raised else None, tabletScreen=identifier(6),
        focusedEntity=identifier(6), anchor=identifier(1), textDisplay=identifier(2), backPlate=identifier(3), activeLayer=0,
        keys=[dict(id=identifier(4), layer=0, pressed=False), dict(id=identifier(5), layer=1, pressed=False)],
        entities=[dict(id=identifier(n), type='Box' if n in (1, 3) else 'Text',
            parentId=None if n == 1 else identifier(1), visible=raised and n in (2, 3, 4), hostType='local')
            for n in range(1, 6)])
    return result


def boundary(raised=True):
    original = Boundary(); original.source['keyboard'] = keyboard(raised)
    def promote(value):
        value['chatViewVersion'] = 2
        value['source']['keyboard']['sequence'] = value['sequence']
    original.mutate = promote
    return original


class PicoChatKeyboardTests(unittest.TestCase):
    def test_actual_inventory_qualifies_visible_keyboard_without_qml_request(self):
        source = boundary(); source.source['ui']['keyboardRequested'] = False
        reader = source.reader(vr=True)
        value = reader.read(RUN)
        self.assertTrue(measured_view(value)['keyboard'])
        self.assertEqual(TEXT, measured_view(value)['draft'])
        self.assertEqual(5, len(value['source']['keyboard']['entities']))
        self.assertGreater(reader.read(RUN)['source']['keyboard']['sequence'], value['source']['keyboard']['sequence'])

    def test_touch_metrics_and_unavailable_keyboard_cannot_qualify_pico(self):
        for version in (1, 2):
            source = Boundary(); source.mutate = lambda v: v.update(chatViewVersion=version)
            with self.assertRaises(NativeUIError): source.reader(vr=True).read(RUN)
        source = boundary(); source.source['keyboard'] = {'available': False}
        with self.assertRaises(NativeUIError): source.reader(vr=True).read(RUN)

    def test_full_entity_inventory_must_match_actual_key_and_role_owners(self):
        for edit in (
            lambda v: v['entities'].pop(),
            lambda v: v['entities'].append(deepcopy(v['entities'][0])),
            lambda v: v['keys'].append(deepcopy(v['keys'][0])),
            lambda v: v.update(anchor=identifier(8)),
            lambda v: v.update(textDisplay=identifier(1)),
            lambda v: v['entities'][3].update(parentId=identifier(9)),
            lambda v: v['entities'][3].update(hostType='domain'),
            lambda v: v['entities'][1].update(type='Model'),
            lambda v: v['entities'][3].update(text='private'),
            lambda v: v['keys'][0].update(label='private'),
            lambda v: v.update(typedCharacters='private'),
            lambda v: v['keys'][0].update(layer=True),
            lambda v: v['keys'][0].update(id='00000000-0000-0000-0000-000000000000'),
            lambda v: v.update(activeLayer=2),
        ):
            value = keyboard(); edit(value)
            with self.subTest(edit=edit):
                with self.assertRaises(NativeUIError): vr_keyboard(value)

    def test_raised_flag_never_replaces_actual_visibility_and_ghost_keys_fail_close(self):
        value = keyboard(False)
        self.assertFalse(measured_keyboard(value))
        value['raised'] = True
        self.assertFalse(vr_keyboard(value)['visible'])
        with self.assertRaises(NativeUIError): measured_keyboard(value)
        source = boundary(False)
        source.source.update(ui={'present': False}, editorFocused=False, editorHasDraft=False)
        self.assertFalse(measured_view(source.reader(vr=True).read(RUN))['keyboard'])
        source.source['keyboard']['entities'][-1]['visible'] = True
        source.source['keyboard']['visible'] = True
        with self.assertRaises(NativeUIError): measured_view(source.reader(vr=True).read(RUN))

    def test_pressed_keys_and_inactive_layer_visibility_remain_cleanup_failures(self):
        for edit in (
            lambda v: v['keys'][0].update(pressed=True),
            lambda v: v['entities'][-1].update(visible=True),
            lambda v: v['entities'][3].update(visible=False),
            lambda v: v['entities'][1].update(visible=False),
            lambda v: v.update(enabled=False),
            lambda v: v.update(inputToHud=True),
            lambda v: v.update(inputTarget=identifier(8)),
            lambda v: v.update(tabletScreen=None),
        ):
            value = keyboard(); edit(value)
            vr_keyboard(value)  # Raw inconsistency survives acquisition.
            with self.assertRaises(NativeUIError): measured_keyboard(value)

    def test_original_owner_birth_and_query_sequence_are_pinned(self):
        for edit in ({'instance': 'f' * 32}, {'sequence': 1}):
            source = boundary(); reader = source.reader(vr=True); reader.read(RUN)
            promote = source.mutate
            def mutate(value):
                promote(value); value['source']['keyboard'].update(edit)
            source.mutate = mutate
            with self.assertRaises(NativeUIError): reader.read(RUN)

    def test_native_version_cannot_regress_after_a_v2_source(self):
        source = Boundary(); source.mutate = lambda v: v.update(chatViewVersion=2)
        reader = source.reader(); reader.read(RUN)
        source.mutate = None
        with self.assertRaises(NativeUIError): reader.read(RUN)

    def test_uncreated_keyboard_requires_no_owner_keys_entities_or_raise(self):
        value = keyboard(False)
        value.update(created=False, anchor=None, textDisplay=None, backPlate=None, keys=[], entities=[])
        self.assertFalse(measured_keyboard(value))
        value['raised'] = True
        with self.assertRaises(NativeUIError): vr_keyboard(value)

    def test_v1_reader_is_explicit_and_vr_inventory_never_accepted_as_v1(self):
        self.assertEqual(1, Boundary().reader().read(RUN)['chatViewVersion'])
        source = boundary(); source.mutate = lambda v: v.update(chatViewVersion=1)
        with self.assertRaises(NativeUIError): source.reader().read(RUN)


if __name__ == '__main__': unittest.main()
