"""Normal record/cancel/complete composition with explicit original boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_capture_owner import PicoAudioCaptureOwner
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from self_tests.test_pico_audio_page_owner import Boundary


class AudioCaptureOwnerTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup);self.path=Path(self.directory.name)
        self.native=Boundary(self.path,lifetime=True);self.parent=self.native.owner()
        self.parent.prepare();self.parent.tablet();self.parent.open_audio();self.parent.claim_preview()
        self.journal=Journal(clock=self.native.epoch);generated=self.journal.register('audio')
        self.journal.runs[self.parent.run]=self.journal.runs.pop(generated)
        test=self
        class PhaseClient(Client):
            def request(self,path,*args,phase_nonce=None,**kwargs):
                test.assertEqual('/runs/'+test.parent.run+'/phase',path)
                return test.journal.phase(test.parent.run,phase_nonce)
        self.client=PhaseClient('http://127.0.0.1:9876/feature-fixture/v1','a'*64)
        self.source=PhaseFixtureReader(self.client,self.parent.run,'audio',epoch_ms=self.native.epoch,monotonic=lambda:self.native.clock)
        self.start_ticket=self.activate('record-start')
        self.owner=self.capture_owner()
    def capture_owner(self,cycle=1):
        return PicoAudioCaptureOwner(self.path/f'audio-capture-cycle-{cycle:02d}.json',self.parent,self.source)
    def activate(self,verb,inputs=None):
        ticket=uuid.uuid4().hex;self.journal.activate(self.parent.run,ticket,verb,{} if inputs is None else inputs);return ticket
    def start(self):self.owner.prepare();return self.owner.start()
    def cancel(self):self.activate('record-cancel');return self.owner.cancel()
    def test_normal_cancel_and_original_pcm_are_retained_with_original_start_ticket(self):
        self.assertEqual('capturing',self.start()['phase']);actual=self.cancel();self.assertEqual('cancelled',actual['state']['phase'])
        actual=self.owner.retain_originals();self.assertEqual('retained',actual['phase']);self.assertEqual(self.start_ticket,actual['sourceTicket'])
        self.assertTrue(actual['originalPcmRetained']);self.assertFalse(actual['independentAcousticObserved']);self.assertFalse(actual['fullAudioQualified'])
        self.assertEqual(2,self.native.actions.count('audio.record'));self.assertEqual(1,actual['nativeQuietWindows'])
        for kind in ('input','sink'):
            record=self.owner.state['artifacts'][kind]
            self.assertEqual(self.native.files['recorded-preview-'+kind+'.pcm16le'],self.owner.read_file(record))
        restored=self.capture_owner();self.assertEqual(actual,restored.report());self.assertTrue(restored.store.path.exists())
    def test_muted_rejection_then_normal_unmute_and_multiple_captures_preserve_original_cycles(self):
        self.parent.action('mute');self.parent.action('record');self.parent.action('restore')
        self.activate('record-start');second=self.capture_owner(2);second.prepare();second.start()
        self.activate('record-cancel');second.cancel();second.retain_originals()
        original={kind:second.read_file(value) for kind,value in second.state['artifacts'].items()}
        self.activate('record-start');third=self.capture_owner(3);third.prepare();third.start()
        self.activate('await-completion');self.native.auto_complete=True;third.await_completion();third.retain_originals()
        self.assertEqual(3,third.report()['cycle']);self.assertEqual(2,second.report()['cycle'])
        for kind,value in second.state['artifacts'].items():self.assertEqual(original[kind],second.read_file(value))
        with self.assertRaises(NativeUIError):self.parent.release()
        self.assertEqual(2,self.native.actions.count('audio.mute'))
        self.assertEqual([1,2],[value['history']['cycle'] for value in self.parent.preview.owned()['cycles']])

    def test_normal_mute_interrupt_and_unmute_recovery_preserve_actual_cancelled_cycle(self):
        self.start();self.activate('mute',dict(enabled=True));result=self.owner.mute_interrupt()
        self.assertEqual('cancelled',result['state']['phase']);self.assertEqual('microphone-muted',result['state']['error']);self.assertTrue(result['state']['muted'])
        self.activate('mute',dict(enabled=False));result=self.owner.restore_mute();self.assertFalse(result['state']['muted'])
        result=self.owner.retain_originals();self.assertTrue(result['originalPcmRetained']);self.assertEqual(1,self.native.actions.count('audio.record'))
        self.assertEqual(2,self.native.actions.count('audio.mute'));self.assertFalse(result['fullAudioQualified'])
    def test_lost_unmute_restore_recovers_original_action_once(self):
        self.start();self.activate('mute',dict(enabled=True));self.owner.mute_interrupt()
        self.activate('mute',dict(enabled=False));self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.owner.restore_mute()
        self.native.input_fault='';self.native.transform=lambda value:value
        recovered=self.capture_owner();result=recovered.reconcile();self.assertFalse(result['state']['muted'])
        self.assertEqual('terminal',result['phase']);self.assertEqual(2,self.native.actions.count('audio.mute'))
    def test_historical_v1_continues_its_original_cancel_without_acquiring_new_mute_authority(self):
        from adapters.script_journey.history import pack,unpack
        self.owner.prepare();disk=deepcopy(self.owner.disk);value=unpack(disk['payload'])[0];value.pop('restoreOperation');value.pop('terminalSource')
        disk.update(audioCaptureOwnerVersion=1,payload=pack([value]));self.owner.store.write(disk,self.owner.disk)
        legacy=self.capture_owner();self.assertEqual(1,legacy.version);legacy.start()
        self.activate('mute',dict(enabled=True))
        with self.assertRaises(NativeUIError):legacy.mute_interrupt()
        self.assertEqual(0,self.native.actions.count('audio.mute'))
        self.activate('record-cancel');legacy.cancel();legacy.retain_originals()
        self.assertEqual(1,legacy.store.read()['audioCaptureOwnerVersion']);self.assertTrue(legacy.report()['originalPcmRetained'])

    def test_terminal_event_before_actual_cancel_fence_cannot_borrow_ordinary_input(self):
        self.start();self.activate('record-cancel');original=self.native.publish
        def stale(phase,*args,**kwargs):
            original(phase,*args,**kwargs)
            if phase=='cancelled':self.native.events[-1]['publishedEpochMs']=self.native.started()+1
        self.native.publish=stale
        with self.assertRaises(NativeUIError):self.owner.cancel()
        with self.assertRaises(NativeUIError):self.owner.reconcile()
        self.assertEqual('cancel-issued',self.owner.state['phase']);self.assertEqual(2,self.native.actions.count('audio.record'))

    def test_lost_mute_interruption_is_read_back_without_a_second_toggle(self):
        self.start();self.activate('mute',dict(enabled=True));self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.owner.mute_interrupt()
        self.native.input_fault='';self.native.transform=lambda value:value
        recovered=self.capture_owner();result=recovered.reconcile();self.assertTrue(result['state']['muted'])
        self.assertEqual('microphone-muted',result['state']['error']);self.assertEqual(1,self.native.actions.count('audio.mute'))

    def test_actual_completion_keeps_distinct_original_input_and_sink_without_synthetic_wav(self):
        self.start();self.activate('await-completion');self.native.auto_complete=True
        result=self.owner.await_completion();self.assertEqual('completed',result['state']['phase'])
        self.assertEqual(['capturing','playing','draining','completed'],result['state']['history'])
        result=self.owner.retain_originals();self.assertTrue(result['originalPcmRetained']);self.assertEqual(1,self.native.actions.count('audio.record'))
        self.assertNotEqual(self.owner.read_file(self.owner.state['artifacts']['input']),self.owner.read_file(self.owner.state['artifacts']['sink']))
    def test_read_only_observation_follows_actual_capture_progress_and_automatic_terminal(self):
        initial=self.start();self.native.publish('capturing',24000);self.native.files['recorded-preview-input.pcm16le']=b'\x20\0'*12000
        actual=self.owner.observe();self.assertGreater(actual['state']['recordedFrames'],initial['state']['recordedFrames'])
        self.native.complete();self.native.sleep(.01);actual=self.owner.observe()
        self.assertEqual('terminal',actual['phase']);self.assertEqual('completed',actual['state']['phase'])
        self.assertEqual(1,self.native.actions.count('audio.record'));self.assertEqual(self.start_ticket,actual['sourceTicket'])

    def test_lost_start_recovers_only_original_delivery_without_resending(self):
        self.owner.prepare();self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.owner.start()
        self.native.input_fault='';self.native.transform=lambda value:value
        recovered=self.capture_owner();self.assertEqual('capturing',recovered.reconcile()['phase'])
        self.assertEqual(1,self.native.actions.count('audio.record'))
    def test_wrong_current_phase_or_changed_start_ticket_cannot_send_start(self):
        self.owner.prepare();self.activate('record-cancel')
        with self.assertRaises(NativeUIError):self.owner.start()
        self.assertEqual(0,self.native.actions.count('audio.record'))
        self.activate('record-start')
        with self.assertRaises(NativeUIError):self.owner.start()
        self.assertEqual(0,self.native.actions.count('audio.record'))
    def test_old_native_start_epoch_cannot_borrow_new_fixture_ticket(self):
        self.owner.prepare();self.native.started=lambda:18000
        with self.assertRaises(NativeUIError):self.owner.start()
        self.assertEqual('start-issued',self.owner.state['phase']);self.assertEqual(1,self.native.actions.count('audio.record'))
    def test_parent_muted_recipe_cannot_take_input_after_capture_handoff(self):
        self.owner.prepare()
        with self.assertRaises(NativeUIError):self.parent.action('mute')
        self.assertEqual(0,self.native.actions.count('audio.mute'));self.assertEqual('claimed',self.parent.state['phase'])

    def test_start_epoch_between_prepare_and_final_preinput_fence_is_stale(self):
        self.owner.prepare();self.native.sleep(1);self.native.started=lambda:20500
        with self.assertRaises(NativeUIError):self.owner.start()
        self.assertEqual('start-issued',self.owner.state['phase']);self.assertEqual(1,self.native.actions.count('audio.record'))
    def test_orphan_original_blocks_new_owner_before_ordinary_input(self):
        orphan=self.path/f'audio-capture-original-{self.parent.run}-01-input.pcm16le';orphan.write_bytes(b'owned')
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(0,self.native.actions.count('audio.record'));self.assertEqual(b'owned',orphan.read_bytes())

    def test_lost_cancel_reconciles_original_terminal_event_without_second_press(self):
        self.start();self.activate('record-cancel');self.native.input_fault='lost-result'
        with self.assertRaises(NativeUIError):self.owner.cancel()
        self.native.input_fault='';self.native.transform=lambda value:value
        recovered=self.capture_owner();self.assertEqual('terminal',recovered.reconcile()['phase']);self.assertEqual(2,self.native.actions.count('audio.record'))
    def test_original_file_mutation_never_becomes_saved_evidence(self):
        self.start();self.cancel();self.owner.retain_originals();record=self.owner.state['artifacts']['input'];path=self.path/record['name']
        raw=path.read_bytes();path.write_bytes(bytes(reversed(raw)))
        with self.assertRaises(NativeUIError):self.capture_owner()
        self.assertTrue(self.owner.store.path.exists());self.assertTrue(self.parent.store.path.exists())
    def test_lost_original_writer_leaves_its_opened_intent_and_never_overwrites_or_replays(self):
        self.start();self.cancel();original=self.owner.save
        def interrupted(state):
            original(state)
            if any(value['phase']=='opened' for value in state['artifacts'].values()):raise NativeUIError('Explicit writer boundary interruption')
        with patch.object(self.owner,'save',side_effect=interrupted):
            with self.assertRaises(NativeUIError):self.owner.retain_originals()
        recovered=self.capture_owner();self.assertEqual('reading',recovered.state['phase'])
        self.assertEqual('opened',recovered.state['artifacts']['input']['phase'])
        path=self.path/recovered.state['artifacts']['input']['name'];self.assertTrue(path.exists());self.assertEqual(b'',path.read_bytes())
        with self.assertRaises(NativeUIError):recovered.retain_originals()
        self.assertEqual(2,self.native.actions.count('audio.record'));self.assertTrue(path.exists())
    def test_matching_bytes_after_original_path_replacement_are_not_the_original_file(self):
        self.start();self.cancel();self.owner.retain_originals();record=self.owner.state['artifacts']['input'];path=self.path/record['name']
        raw=path.read_bytes();replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):self.capture_owner()

    def test_waiting_for_original_completion_never_delivers_another_record_input(self):
        self.start();self.activate('await-completion')
        with self.assertRaises(NativeUIError):self.owner.await_completion()
        self.assertEqual('awaiting',self.owner.state['phase']);self.assertEqual(1,self.native.actions.count('audio.record'))
        self.native.complete();recovered=self.capture_owner();self.assertEqual('terminal',recovered.reconcile()['phase'])
    def test_final_copy_native_age_is_included_and_retained_fact_remains_recoverable(self):
        self.owner.prepare();original=self.owner.report
        def late():value=original();self.native.clock+=2;return value
        with patch.object(self.owner,'report',side_effect=late):
            with self.assertRaises(NativeUIError):self.owner.start()
        self.assertEqual('capturing',self.owner.state['phase']);self.assertEqual(1,self.native.actions.count('audio.record'))
        self.assertEqual('capturing',self.capture_owner().report()['phase'])


if __name__=='__main__':unittest.main()
