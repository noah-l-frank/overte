"""Execute real owner/preview/readers with explicit UI/OS/audio host seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.audio_preview import AudioPreview
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_page_owner import PicoAudioPageOwner
from adapters.pico4.audio_pages import PicoAudioPages
from adapters.recorded_preview_evidence import RecordedPreviewEvidence
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_audio_ui import TokenAudioUI
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_audio_preview import Boundary as PreviewBoundary,BINDING as BASE_BINDING
from self_tests.test_pico_audio_pages import Boundary as PageBoundary,row,BRIDGE
from self_tests.test_pico_audio_settings_source import Boundary as SettingsBoundary,RUN
from self_tests.test_pico_lifecycle_source import Boundary as UiBoundary
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class Boundary(PreviewBoundary):
    def __init__(self,path,*,peak=False,muted=False,lifetime=False):
        super().__init__();self.shown=self.opened=False;self.origin_peak=self.peak=peak;self.muted=muted
        self.pages=PageBoundary();self.settings=SettingsBoundary();self.ui=UiBoundary();self.ui.rows=[];self.ui.raised=False
        self.sequence=0;self.entry_inputs=0;self.fault_effect='';self.entry_lost=False;self.retain_page=False;self.record_starts={}
        self.binding=dict(BASE_BINDING,sessionId=BRIDGE);self.path=path;self.lock=ScriptSourceLock(path/'script-sources.lock')
        self.instance=self.generation=BRIDGE;self.pages_mutate=None
        self.lifetime=lifetime;self.callback_events={};self.retained_capacity=0
        original=self.native.mutate
        def native(packet):
            original(packet);packet.update(capturedEpochMs=self.epoch(),requestedEpochMs=self.epoch());packet['animation']={};packet['animationFence']={}
        self.native.mutate=native
        self.native_reader=self.native.reader();self.native_reader.clock_ms=self.epoch
        self.native_reader.monotonic=lambda:self.clock;self.native_reader.sleep=self.sleep;self.native_reader.guard=self.guard
        self.evidence=RecordedPreviewEvidence(self.evidence_send,lambda:json.dumps(self.preview_value),self.files_get,self.epoch,self.guard,123,
            monotonic=lambda:self.clock,sleep=self.sleep)
        self.preview=AudioPreview(PrivateFeatureState(path/'preview.json'),self.binding,RUN,
            lambda intent:TokenAudioUI(self,lambda *args:(intent(*args),self.intent(*args)),monotonic=lambda:self.clock,sleep=self.sleep),
            self.native_reader,self.evidence,self.guard,self.lock,monotonic=lambda:self.clock,sleep=self.sleep)
        outer=self
        class Transport(FakeTransport):
            def stage(self,envelope,profile):
                value=super().stage(envelope,profile);operation=envelope['commands'][0]['operation']
                if outer.fault_effect!='controller-ack-only':
                    if operation=='tablet.open':outer.shown=True
                    elif outer.opened:
                        outer.opened=False
                        if not outer.retain_page:
                            outer.pages.originals[0].update(pageAlive=False,visible=False,current=False,attached=False)
                            if outer.fault_effect!='peak-not-restored':outer.peak=outer.origin_peak
                        else:outer.pages.originals[0].update(visible=False,current=False)
                    else:outer.shown=False
                return value
            def read_status(self,**options):
                value=super().read_status(**options);value['updatedEpochMs']=outer.epoch();return value
        self.transport=Transport();session_path=path/'session';session_path.mkdir(mode=0o700)
        self.session=PicoOpenXrAdapterSession(self.transport,'explicit-audio-boundary',session_path);self.session.begin(self.binding['processIdentity'])
    def epoch(self):return 20000+round(self.clock*1000)
    def capture(self):
        self.pages.time=self.clock;self.pages.open=self.shown;self.pages.current=self.pages.originals[0]['id'] if self.opened else ''
        value=json.loads(self.pages.read());value.update(audioControlsVersion=1,lastCommandSequence=self.sequence)
        if self.opened:
            original=super().capture();value['controls']=[dict(row,focused=False,token=str(uuid.UUID(hex=row['token']))) for row in original['controls']]
        elif self.shown:
            value['controls']=[dict(id='audio.entry',token=BRIDGE,enabled=True,focused=False,inputReady=True)]
        if self.pages_mutate:self.pages_mutate(value)
        return value
    def activate(self,identifier,**options):
        if identifier=='audio.entry':
            self.entry_inputs+=1;self.sequence+=1
            if self.fault_effect!='entry-ack-only':
                self.opened=True;self.peak=True;original=row();original.update(originalPeakValuesEnabled=self.origin_peak,firstObservedEpochMs=self.epoch())
                self.pages.originals.append(original)
            if self.entry_lost:raise NativeUIError('Explicit response lost after original entry input')
        else:
            if identifier=='audio.record' and not self.active:self.record_starts[self.cycle+1]=self.epoch()
            try:super().activate(identifier,**options)
            finally:
                if identifier=='audio.record':self.clock+=.002
            self.sequence+=1
    def scroll(self,*args,**options):super().scroll(*args,**options);self.sequence+=1
    def started(self):return self.record_starts.get(self.cycle,self.epoch())
    def evidence_send(self,command):
        super().evidence_send(command)
        if self.preview_value and 'capturedEpochMs' in self.preview_value:
            self.preview_value.update(requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch())
    def complete_callback(self):
        # Explicit original-source boundary publication. Native callback timing
        # and actual lease destruction are independently checked by real Qt.
        self.callback_events[self.cycle]=dict(enteredEpochMs=self.epoch(),completedEpochMs=self.epoch(),retiredEpochMs=self.epoch(),retired=True)
    def owner(self):
        def setting_send(request):
            self.settings.time=self.clock;self.settings.source.update(inputPeakValuesEnabled=self.peak)
            self.settings.source['properties'].update(muted=self.muted,mutedHMD=self.muted)
            self.settings.source['native'].update(muted=self.muted,previewCycle=self.cycle,previewActive=self.active)
            self.settings.send(request)
            if self.lifetime:
                from self_tests.test_audio_preview_lifetime import sample
                value=sample(self.cycle)
                for callback in value['deferred']['callbacks']:
                    callback['registeredEpochMs']=self.record_starts[callback['cycle']]
                    callback.update(self.callback_events.get(callback['cycle'],{}))
                value.update(previewBufferCapacityBytes=self.retained_capacity)
                self.settings.value.update(audioSettingsVersion=2);self.settings.value['source']['previewLifetime']=value
        source=self.settings.reader();source.send=setting_send;source.clock_ms=self.epoch;source.monotonic=lambda:self.clock;source.sleep=self.sleep;source.guard=self.guard;source.source_lock=self.lock
        def ui_send(request):
            self.ui.shown=self.shown;self.ui.home=self.shown and not self.opened;self.ui.send(request);self.ui.value['capturedEpochMs']=self.epoch()
        ui=self.ui.source();ui.send=ui_send;ui.clock_ms=self.epoch;ui.monotonic=lambda:self.clock;ui.sleep=self.sleep;ui.guard=self.guard;ui.source_lock=self.lock
        pages=PicoAudioPages(lambda:json.dumps(self.capture()),self.epoch,self.guard,123,BRIDGE,self.lock,monotonic=lambda:self.clock,sleep=self.sleep)
        route=TokenAudioUI(self,lambda *_:None,monotonic=lambda:self.clock,sleep=self.sleep)
        return PicoAudioPageOwner(self.path/'audio-page-owner.json',RUN,self.binding,pages,source,ui,self.preview,self.session,route,self.lock)


class AudioPageOwnerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup);self.path=Path(self.directory.name)
        self.boundary=Boundary(self.path);self.flow=self.boundary.owner()
    def opened(self):
        self.flow.prepare();self.flow.tablet();self.flow.open_audio()
    def rejected(self):
        self.opened();self.flow.claim_preview();self.flow.action('mute');self.flow.action('record')
    def test_normal_entry_muted_rejection_restore_original_peak_exit_and_retained_context(self):
        self.rejected();self.flow.action('restore');self.flow.release();self.flow.close_page();actual=self.flow.close_tablet()
        self.assertEqual('closed',actual['phase']);self.assertFalse(actual['fullAudioQualified']);self.assertTrue(actual['contextAlive'])
        self.assertFalse(actual['pageAlive']);self.assertFalse(actual['inputPeakValuesEnabled']);self.assertTrue(actual['journalsRetained'])
        self.assertEqual(1,self.boundary.entry_inputs);self.assertEqual(3,len(self.boundary.transport.envelopes));self.assertEqual(1,self.boundary.cycle)
        self.assertEqual(['audio.mute','audio.record','audio.mute'],[a for a in self.boundary.actions if a.startswith('audio.')])
        self.assertFalse(self.boundary.muted);self.assertEqual({},self.boundary.files);self.assertGreaterEqual(self.boundary.clock,12)
        self.assertTrue(self.flow.store.path.exists());self.assertTrue(self.flow.preview.store.path.exists())
        with self.flow.lock.held():self.assertEqual(3,len(self.flow.state['streams']))
    def native_closed(self):
        directory=self.path/'lifetime';directory.mkdir(mode=0o700);self.boundary=Boundary(directory,lifetime=True);self.flow=self.boundary.owner()
        self.rejected();self.flow.action('restore');self.flow.release();self.flow.close_page();self.flow.close_tablet()
        return deepcopy(self.boundary.actions),len(self.boundary.transport.envelopes)
    def test_native_callback_release_requires_original_events_then_three_second_quiet(self):
        actions,streams=self.native_closed();original=self.flow.report()
        self.assertFalse(original['nativeDeferredFunctorsRetired']);self.assertFalse(original['nativeResourceMatchesBaseline'])
        self.assertEqual([],original['nativeDeferredQuietWindows']);native_sleep=self.boundary.sleep;publications=0
        def emit(seconds):
            nonlocal publications
            native_sleep(seconds);publications+=1
            if publications==2:self.boundary.complete_callback()
        self.flow.settings.sleep=emit;result=self.flow.await_deferred()
        self.assertTrue(result['nativeDeferredFunctorsRetired']);self.assertTrue(result['nativeResourceMatchesBaseline'])
        self.assertEqual(['closed'],result['nativeDeferredQuietWindows']);self.assertFalse(result['fullAudioQualified'])
        self.assertEqual(actions,self.boundary.actions);self.assertEqual(streams,len(self.boundary.transport.envelopes))
        recovered=self.boundary.owner();self.assertEqual(result,recovered.report());self.assertTrue(recovered.store.path.exists())
    def test_normal_v2_recipe_joins_actual_release_without_more_input(self):
        from adapters.pico4.audio_page_owner import run_normal_audio_page
        directory=self.path/'v2';directory.mkdir(mode=0o700);native=Boundary(directory,lifetime=True);flow=native.owner()
        def publish(seconds):
            native.sleep(seconds)
            if not native.shown and native.cycle==1 and 1 not in native.callback_events:native.complete_callback()
        flow.settings.sleep=publish;result=run_normal_audio_page(flow)
        self.assertEqual('closed',result['phase']);self.assertEqual(['closed'],result['nativeDeferredQuietWindows'])
        self.assertTrue(result['nativeResourceMatchesBaseline']);self.assertFalse(result['fullAudioQualified'])
        self.assertEqual(3,len(native.transport.envelopes));self.assertEqual(1,native.actions.count('audio.record'))
    def test_changed_resource_during_native_final_quiet_leaves_no_completed_window(self):
        self.native_closed();self.boundary.complete_callback();native_sleep=self.boundary.sleep
        def retain(seconds):native_sleep(seconds);self.boundary.retained_capacity=65536
        self.flow.settings.sleep=retain
        with self.assertRaises(NativeUIError):self.flow.await_deferred()
        self.assertEqual([],self.flow.report()['nativeDeferredQuietWindows']);self.assertEqual(2,len(self.flow.state['quiet']))
        self.assertTrue(self.flow.store.path.exists())

    def test_elapsed_due_time_empty_pcm_and_stopped_ui_never_retire_a_native_callback(self):
        actions,streams=self.native_closed();self.boundary.sleep(60)
        # Keep publication frozen pending even after the actual requested due
        # time. Only native-source events can complete the wait.
        with self.assertRaises(NativeUIError):self.flow.await_deferred()
        self.assertFalse(self.flow.report()['nativeDeferredFunctorsRetired']);self.assertEqual('closed',self.flow.state['phase'])
        self.assertEqual(actions,self.boundary.actions);self.assertEqual(streams,len(self.boundary.transport.envelopes))
        self.assertTrue(self.flow.store.path.exists());self.assertTrue(self.flow.preview.store.path.exists())
    def test_retired_callback_with_retained_allocation_does_not_restore_original_resources(self):
        self.native_closed();self.boundary.complete_callback();self.boundary.retained_capacity=65536
        with self.assertRaises(NativeUIError):self.flow.await_deferred()
        result=self.flow.report();self.assertTrue(result['nativeDeferredFunctorsRetired']);self.assertFalse(result['nativeResourceMatchesBaseline'])
        self.assertEqual([],result['nativeDeferredQuietWindows']);self.assertFalse(result['fullAudioQualified'])
    def test_legacy_lifetime_missing_never_becomes_an_empty_native_owner(self):
        self.rejected();self.flow.action('restore');self.flow.release();self.flow.close_page();self.flow.close_tablet()
        with self.assertRaises(NativeUIError):self.flow.await_deferred()
        self.assertIsNone(self.flow.report()['nativeDeferredFunctorsRetired']);self.assertIsNone(self.flow.report()['nativeResourceMatchesBaseline'])

    def test_entry_ack_without_original_page_is_unresolved_and_never_repeated(self):
        self.flow.prepare();self.flow.tablet();self.boundary.fault_effect='entry-ack-only'
        with self.assertRaises(NativeUIError):self.flow.open_audio()
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(1,self.boundary.entry_inputs);self.assertEqual('opening',self.flow.state['phase'])
    def test_lost_entry_response_recovers_only_actual_original_page_and_cursor(self):
        self.flow.prepare();self.flow.tablet();self.boundary.entry_lost=True
        with self.assertRaises(NativeUIError):self.flow.open_audio()
        recovered=self.boundary.owner();actual=recovered.reconcile()
        self.assertEqual('opened',actual['phase']);self.assertEqual(1,self.boundary.entry_inputs)
    def test_controller_ack_without_tablet_or_neutral_never_authorizes_normal_entry(self):
        self.flow.prepare();self.boundary.fault_effect='controller-ack-only'
        with self.assertRaises(NativeUIError):self.flow.tablet()
        self.assertEqual(1,len(self.boundary.transport.envelopes));self.assertEqual(0,self.boundary.entry_inputs)
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(1,len(self.boundary.transport.envelopes))
    def test_lost_preview_muted_input_recovers_original_pending_once_without_second_toggle(self):
        self.opened();self.flow.claim_preview();self.boundary.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.flow.action('mute')
        self.boundary.input_fault='';self.boundary.transform=lambda value:value
        recovered=self.boundary.owner();recovered.reconcile()
        self.assertTrue(self.boundary.muted);self.assertEqual(1,self.boundary.actions.count('audio.mute'))
    def test_hidden_original_page_cannot_stand_in_for_real_destruction_and_peak_restore(self):
        self.rejected();self.flow.action('restore');self.flow.release();self.boundary.retain_page=True
        with self.assertRaises(NativeUIError):self.flow.close_page()
        self.assertTrue(self.boundary.peak);self.assertEqual('back-issued',self.flow.state['phase'])
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(2,len(self.boundary.transport.envelopes))
    def test_lost_native_release_response_is_inspected_without_second_release(self):
        self.rejected();self.flow.action('restore');self.boundary.fail_release=True
        with self.assertRaises(NativeUIError):self.flow.release()
        self.boundary.fail_release=False;recovered=self.boundary.owner();recovered.reconcile()
        self.assertEqual('released',recovered.state['phase'])
        self.assertEqual(1,len([c for c in self.boundary.evidence_commands if c['action'].endswith('release')]))
    def test_enabled_original_peak_and_muted_original_are_restored_through_same_flow(self):
        from adapters.pico4.audio_page_owner import run_normal_audio_page
        directory=self.path/'enabled';directory.mkdir(mode=0o700);native=Boundary(directory,peak=True,muted=True)
        actual=run_normal_audio_page(native.owner())
        self.assertTrue(actual['inputPeakValuesEnabled']);self.assertTrue(native.muted);self.assertEqual(1,native.cycle)
        self.assertEqual(['home','closed'],actual['originalQuietWindows'])
    def test_old_native_terminal_cycle_cannot_borrow_the_normal_record_start_fence(self):
        self.opened();self.flow.claim_preview();self.flow.action('mute');self.boundary.started=lambda:18000
        with self.assertRaises(NativeUIError):self.flow.action('record')
        with self.assertRaises(NativeUIError):self.flow.reconcile()
        self.assertEqual(1,self.boundary.actions.count('audio.record'));self.assertTrue(self.flow.store.path.exists())
    def test_destroyed_page_without_actual_peak_restore_cannot_finish_close(self):
        self.rejected();self.flow.action('restore');self.flow.release();self.boundary.fault_effect='peak-not-restored'
        with self.assertRaises(NativeUIError):self.flow.close_page()
        self.assertFalse(self.boundary.pages.originals[0]['pageAlive']);self.assertTrue(self.boundary.peak)
        self.assertEqual('back-issued',self.flow.state['phase'])
    def test_final_result_copy_and_guard_native_jump_are_included_before_success(self):
        self.flow.prepare();self.flow.tablet();original=self.flow.report
        def late():
            result=original();self.boundary.clock+=2;return result
        with patch.object(self.flow,'report',side_effect=late):
            with self.assertRaises(NativeUIError):self.flow.open_audio()
        self.assertEqual(1,self.boundary.entry_inputs);self.assertEqual('opened',self.flow.state['phase'])
        # The persisted effect is historical; a new fresh read precedes claim.
        recovered=self.boundary.owner();recovered.claim_preview();self.assertEqual('claimed',recovered.state['phase'])

    def test_native_clock_jump_in_last_guard_cannot_hide_aged_return_with_frozen_host_clock(self):
        self.flow.prepare();self.flow.tablet();original_report=self.flow.report;original_epoch=self.boundary.epoch;reported=False;offset=0
        def report():
            nonlocal reported
            result=original_report();reported=True;return result
        def guard():
            nonlocal offset
            if reported:offset=2000
            return True
        self.boundary.epoch=lambda:original_epoch()+offset
        self.flow.settings.clock_ms=self.boundary.epoch;self.flow.settings.guard=guard
        with patch.object(self.flow,'report',side_effect=report):
            with self.assertRaises(NativeUIError):self.flow.open_audio()
        self.assertEqual('opened',self.flow.state['phase']);self.assertEqual(1,self.boundary.entry_inputs)
    def test_reconstructed_closed_owner_requires_new_three_second_quiet_and_resets_observation_gaps(self):
        from adapters.pico4.audio_page_owner import run_normal_audio_page
        run_normal_audio_page(self.flow);before=(len(self.boundary.actions),len(self.boundary.transport.envelopes));started=self.boundary.clock
        recovered=self.boundary.owner();ordinary_sleep=recovered.settings.sleep;calls=0
        def gap(amount):
            nonlocal calls
            calls+=1;ordinary_sleep(amount+(1 if calls==3 else 0))
        recovered.settings.sleep=gap;result=recovered.quiet('closed')
        self.assertGreaterEqual(self.boundary.clock-started,4.5);self.assertEqual(before,(len(self.boundary.actions),len(self.boundary.transport.envelopes)))
        self.assertEqual(['home','closed','closed'],result['originalQuietWindows'])

    def test_changed_original_context_stays_owned_before_any_preview_input(self):
        self.opened();self.boundary.pages.originals[0]['contextId']='9'*32
        with self.assertRaises(NativeUIError):self.flow.claim_preview()
        self.assertIsNone(self.boundary.preview.store.read());self.assertTrue(self.flow.store.path.exists())


if __name__=='__main__':unittest.main()
