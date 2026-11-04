"""Existing normal owner composition under explicit shared weak-object UI2.

These qualify the GUI-model fixture, not Source8, Raw4 or native Qt execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest

from adapters.pico4.lifecycle_source import current_editor
from self_tests.pico_lifecycle_ui2_fixture import normal_ui2_sources,SharedWeakUi2
from self_tests import test_pico_lifecycle_chat as chat_fixture
from self_tests import test_pico_lifecycle_background_owner as background_fixture


class LifecycleUi2NormalSourceTests(unittest.TestCase):
    def test_existing_normal_create_world_back_chat_source_constructors_select_ui2_before_first_observation(self):
        with normal_ui2_sources():
            fixture=chat_fixture.LifecycleChatTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
            fixture.owner.open_chat();fixture.owner.focus_chat();fixture.owner.type_chat()
        self.assertIs(type(fixture.native.ui),SharedWeakUi2)
        self.assertTrue(fixture.owner.source._field_bindings)
        self.assertTrue(fixture.joined.world.source._field_bindings)
        self.assertTrue(fixture.fixture.owner.source._field_bindings)
        packet=json.loads(fixture.owner.source.last_raw);editor=current_editor(packet)
        self.assertEqual(2,packet['lifecycleUiVersion']);self.assertEqual('chat',editor['kind'])
        objects=fixture.native.ui.widget(fixture.native.ui.rows[-1])
        self.assertEqual(fixture.native.ui.registry.identity(objects.field,fixture.native.ui.window,objects.context),
            editor['fieldBinding']['pendingFieldToken'])
        self.assertEqual([],fixture.widgets.sent);self.assertNotEqual(editor['fieldId'],editor['fieldBinding']['pendingFieldToken'])

    def test_existing_background_owner_keeps_ui1_internal_history_and_ui2_original_world_on_same_normal_return(self):
        with normal_ui2_sources():
            fixture=background_fixture.LifecycleBackgroundOwnerTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
            fixture.owner.run_owned()
        self.assertEqual(['lifecycle.background','app.launch'],fixture.inputs)
        packet=fixture.owner.packet(fixture.owner.state['final'])['ui']
        self.assertEqual(2,packet['lifecycleUiVersion']);self.assertFalse(current_editor(packet)['focused'])
        self.assertEqual('linked',current_editor(packet)['fieldBinding']['status'])
        self.assertTrue(fixture.history.frames)
        self.assertTrue(all('fieldBinding' not in row['editor'] for row in fixture.history.frames))
