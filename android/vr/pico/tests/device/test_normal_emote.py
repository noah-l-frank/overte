"""Actual Pico Emote wrapper with explicit native/Qt/OpenXR boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
import json
import unittest
from unittest.mock import patch
import uuid
import test_normal_scripts as sources
from self_tests.test_token_emote_ui import EmoteBoundary
from adapters.token_emote_ui import TokenEmoteUI,snapshot as validate_emote
from adapters.pico4.navigation import validate_snapshot


class PicoEmoteTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.instance,self.native=self.fixture.instance,self.fixture.native
        self.widget=EmoteBoundary();self.widget.instance=self.native.bridge_id;self.widget.generation=self.native.generation
        self.native.opened=True;self.before_input=None;self.fault=None;self.intents=[]
        original=self.widget.capture
        def capture():
            value=original();value['emoteControlsVersion']=2
            for row in value['controls']:row['token']=str(uuid.uuid5(uuid.NAMESPACE_URL,row['token']))
            return value
        self.widget.capture=capture
        snapshot_original=self.native.snapshot;write_original=self.native.write_debug_app_file
        def snapshot():
            value=snapshot_original();actual=self.widget.capture()
            value.update(emoteControlsVersion=2,emoteSourceSequence=actual['scope']['sourceSequence'],
                controls=deepcopy(actual['controls']),elapsedMs=actual['scope']['elapsedMs'],
                lastCommandSequence=self.widget.command_sequence)
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            if self.fault=='missing':value.pop('emoteControlsVersion');value.pop('emoteSourceSequence')
            if self.fault=='version':value['emoteControlsVersion']=True
            return value
        self.snapshot=snapshot
        def write(target,package,path,raw):
            if path!='files/overte-e2e/navigation-ui-command.json':return write_original(target,package,path,raw)
            command=json.loads(raw)
            if self.before_input:self.before_input()
            actual=self.widget.capture();row=next(r for r in actual['controls'] if r['id']==command['controlId'])
            valid=(row['token']==command['controlToken'] and command['sequence']==self.widget.command_sequence+1
                and command['bridgeId']==self.widget.instance and command['generation']==self.widget.generation)
            self.native.inputs.append(deepcopy(command))
            if valid:
                if command['action']=='scroll':self.widget.scroll(command['controlId'],command['direction'],token=row['token'])
                else:self.widget.activate(command['controlId'],token=row['token'])
            self.native.sequence=self.widget.command_sequence
            self.native.status=dict(schemaVersion=1,bridgeId=self.native.bridge_id,commandId=command['commandId'],
                sequence=command['sequence'],performed=valid,error='' if valid else 'control-unavailable',processId=123,
                updatedEpochMs=self.native.epoch_milliseconds(target))
        for boundary in (patch.object(self.native,'snapshot',side_effect=snapshot),
                         patch.object(self.native,'write_debug_app_file',side_effect=write),
                         patch('adapters.token_emote_ui.TokenEmoteUI',partial(TokenEmoteUI,
                             monotonic=lambda:self.widget.clock,sleep=self.widget.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        self.flow=self.instance._emote_controls(self.native.target,self.intents.append)

    def test_real_wrapper_reaches_retained_chooser_and_all_ten_buttons_without_effect_verdicts(self):
        from adapters.token_emote_ui import NAMES
        self.flow.open()
        for name in NAMES:self.flow.play(name)
        self.assertTrue(self.widget.page);self.assertEqual('Love',self.widget.active)
        self.flow.cancel();self.flow.close()
        self.assertFalse(self.widget.page);self.assertEqual('',self.widget.active)
        self.assertIn('down',self.widget.actions)
        self.assertEqual(list(range(1,len(self.native.inputs)+1)),[r['sequence'] for r in self.native.inputs])
        self.assertTrue(all(set(row)<= {'controlId','action','sequence','instance','generation','direction','original'} for row in self.intents))
        self.assertFalse(any(c.startswith('feature.emotes.') for c in self.instance.capabilities(self.native.target)))

    def test_ignored_ordinary_entry_and_scroll_never_retry_the_same_input(self):
        self.widget.fault='ignored'
        with self.assertRaises(RuntimeError):self.flow.open()
        self.assertEqual(['emote.entry'],self.widget.actions)
        self.widget.fault=None;self.flow.open();self.widget.fault='ignored-scroll'
        count=len(self.native.inputs)
        with self.assertRaises(RuntimeError):self.flow.play('Love')
        self.assertEqual(count+1,len(self.native.inputs));self.assertEqual('',self.widget.active)

    def test_changed_original_token_or_page_cannot_be_recaptured_for_delivery(self):
        self.flow.open();reference=self.flow.capture();self.widget.active='Love'
        with self.assertRaises(RuntimeError):self.flow.io.activate('emote.play.Crying',reference=reference)
        self.assertEqual(1,len(self.native.inputs))
        self.before_input=lambda:setattr(self.widget,'generation',str(uuid.uuid4()))
        with self.assertRaises(RuntimeError):self.flow.play('Crying')
        self.assertNotIn('emote.play.Crying',self.widget.actions)

    def test_missing_boolean_version_foreign_candidate_and_unsafe_schema_fail_closed(self):
        for fault in ('missing','version'):
            self.fault=fault
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):self.flow.capture()
        self.fault=None;self.native.digest='f'*64
        with self.assertRaises(RuntimeError):self.flow.open()
        self.assertEqual([],self.native.inputs)

    def test_v1_shared_snapshot_stays_strict_and_version_downgrade_is_refused(self):
        value=self.widget.capture();validate_emote(value)
        value['emoteControlsVersion']=1
        with self.assertRaises(RuntimeError):validate_emote(value)
        self.flow.capture();self.fault='version'
        with self.assertRaises(RuntimeError):self.flow.capture()

    def test_native_pico_decoder_refuses_unknown_emote_state_and_reused_source_cursors(self):
        value=self.snapshot();validate_snapshot(value,123,self.native.epoch_milliseconds(self.native.target))
        value['controls'][0]['expected']=True
        with self.assertRaises(RuntimeError):validate_snapshot(value,123,self.native.epoch_milliseconds(self.native.target))
        self.flow.capture();original=self.widget.capture
        self.widget.capture=lambda:dict(original(),scope=self.flow.previous['scope'])
        with self.assertRaises(RuntimeError):self.flow.capture()

    def test_durable_source_factory_uses_existing_lock_candidate_and_actual_vr_binding(self):
        from adapters.pico4.emote_sources import PicoEmoteSources
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        before=len(self.native.inputs)
        with lock.held():
            owner=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            self.assertIsInstance(owner,PicoEmoteSources)
            self.assertEqual(self.native.bridge_id,owner.binding['sessionId']);self.assertEqual(123,owner.pid)
            self.assertEqual(lock,owner.lock);self.assertEqual([],owner.frames)
        self.assertEqual(before,len(self.native.inputs))
        foreign=ScriptSourceLock(seam.root/'foreign.lock')
        with foreign.held(),self.assertRaises(ValueError):
            self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,foreign)

    def test_source_transcript_survives_base_cleanup_and_prevents_success(self):
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            owner=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner.save();original=owner.store.read()
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertEqual(original,owner.store.read())

    def test_durable_inputs_factory_requires_original_primary_source_and_retains_ownership(self):
        from adapters.pico4.emote_inputs import PicoEmoteInputs
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_emote_sources import SourcesTests
        seam=SourcesTests();seam.setUp();self.addCleanup(seam.doCleanups)
        path=self.instance._script_journey().state_path(self.native.target)
        lock=ScriptSourceLock(path.with_name('script-sources.lock'))
        with lock.held():
            source=self.instance._emote_sources(self.native.target,seam.phase,'primary',seam.root,lock)
            owner=self.instance._emote_inputs(self.native.target,source)
            self.assertIsInstance(owner,PicoEmoteInputs);self.assertIs(source,owner.source)
            owner.save();original=owner.store.read()
            actor=self.instance._emote_sources(self.native.target,seam.phase,'actor',seam.root,lock)
            with self.assertRaises(ValueError):self.instance._emote_inputs(self.native.target,actor)
        with self.assertRaises(ValueError):self.instance.cleanup(self.native.target)
        self.assertFalse(self.native.running);self.assertEqual(original,owner.store.read())


if __name__=='__main__':unittest.main()
