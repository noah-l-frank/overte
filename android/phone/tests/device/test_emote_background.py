"""Real background ownership with synthetic OS/SDK/native boundaries only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone'),str(ROOT/'tests/device/self_tests')]
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from overte_phone_emote_background import PhoneEmoteBackground
from test_emote_effects import EffectsModel
from test_emote_sources import RUN


class Model(EffectsModel):
    def __init__(self,root):
        super().__init__(root);self.foreground=True;self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.normal_inputs=[];self.ignore='';self.lose='';self.native_changed=True;self.os_unavailable=False
        self.foreign=False;self.background_native_accesses=0;self.source_lost=False

    def normal_feature_runtime(self,*args,**kwargs):
        if not self.foreground:
            self.background_native_accesses+=1
            raise NativeUIError('Synthetic foreground-only source unavailable')
        ui,service,binding,guard,installed=super().normal_feature_runtime(*args,**kwargs)
        return ui,service,binding,lambda:guard() and self.foreground,installed

    def native_send(self,request):
        if not self.foreground:
            self.background_native_accesses+=1
            raise NativeUIError('Synthetic native getter unavailable in background')
        super().native_send(request);self.value['lifecycle']=deepcopy(self.lifecycle)
        if self.source_lost:raise NativeUIError('Synthetic lost original read result')

    def _emote_lifecycle_status(self,_selector,binding):
        if self.os_unavailable:raise NativeUIError('Synthetic original OS unavailable')
        observed=deepcopy(self.binding)
        if self.foreign:observed['processIdentity']='32:19'
        return dict(binding=observed,foreground=self.foreground,running=True,appState=4 if self.foreground else 3)

    def invoke(self,_selector,operation,values):
        assert values=={} and operation in ('lifecycle.background','app.launch');self.normal_inputs.append(operation)
        if operation!=self.ignore:
            if operation=='lifecycle.background':
                self.foreground=False
                if self.native_changed:self.lifecycle['backgrounds']+=1
            else:
                self.foreground=True
                if self.native_changed:self.lifecycle['activations']+=1
        if self.lose==operation:raise NativeUIError('Synthetic lost ordinary input return')
        return {'performed':True}

    def owner(self):
        phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.epoch,monotonic=lambda:self.clock)
        return PhoneEmoteBackground(self,'synthetic-selector',phase,self.lock,artifact_root=self.root,
            monotonic=lambda:self.clock,sleep=self.sleep)


class PhoneEmoteBackgroundTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-emote-background-');self.addCleanup(temporary.cleanup)
        self.model=Model(Path(temporary.name))

    def test_ordinary_home_and_activation_require_original_os_and_native_lifecycle_then_retire_metadata(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');self.assertEqual({'performed':True},owner.act(call))
            self.assertEqual('observed',owner.state['phase']);self.assertFalse(owner.state['background']['foreground'])
            self.assertTrue(owner.state['foreground']['foreground']);self.assertLess(owner.store.path.stat().st_size,65536)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)
            current=m.owner();current.retire();self.assertIsNone(current.store.read())
            self.assertIsNotNone(owner.sources.read()) # Source originals are not the background input lease.
        self.assertEqual(0,m.background_native_accesses)

    def test_lost_home_return_reconstructs_in_background_without_native_access_or_second_home(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertFalse(m.foreground);self.assertEqual('background-issued',owner.state['phase'])
            m.lose='';current=m.owner();current.act(call)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);current.retire()
        self.assertEqual(0,m.background_native_accesses)

    def test_lost_activation_return_reconstructs_original_foreground_and_does_not_launch_twice(self):
        m=self.model;m.lose='app.launch'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertTrue(m.foreground);self.assertEqual('foreground-issued',owner.state['phase'])
            m.lose='';current=m.owner();current.act(call);current.retire()
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_ignored_home_ack_cannot_be_success_or_repeated_after_reconstruction(self):
        m=self.model;m.ignore='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
            self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_ignored_activation_ack_cannot_be_success_or_repeated_after_reconstruction(self):
        m=self.model;m.ignore='app.launch'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.assertEqual(0,m.background_native_accesses)

    def test_os_transition_without_actual_native_background_and_activation_is_not_success(self):
        m=self.model;m.native_changed=False
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual('observing',owner.state['phase']);self.assertIsNotNone(owner.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_active_animation_baseline_does_not_hide_an_extra_restore_input_in_background(self):
        m=self.model;m.start('Waving')
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertIsNone(owner.store.read())
        self.assertEqual([],m.normal_inputs);self.assertEqual([],m.controls.input_requests)

    def test_changed_candidate_process_or_missing_os_evidence_prevents_an_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            m.foreign=True
            with self.assertRaises(NativeUIError):m.owner()
            m.foreign=False;m.os_unavailable=True
            with self.assertRaises(NativeUIError):m.owner()
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_changed_or_missing_primary_header_cannot_authorize_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            owner.sources.discard(owner.sources.read());current=m.owner();m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_lost_final_source_result_keeps_pending_originals_without_repeating_os_inputs(self):
        m=self.model;original=m.invoke
        def lose_after_activation(*args):
            value=original(*args)
            if args[1]=='app.launch':m.source_lost=True
            return value
        m.invoke=lose_after_activation
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.act(call)
            self.assertIsNotNone(current.sources.read());self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_failed_pre_input_journal_write_cannot_issue_home_or_succeed_on_same_object_retry(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');writer=owner.store.write
            owner.store.write=lambda *_args:(_ for _ in ()).throw(OSError('Synthetic interrupted journal write'))
            with self.assertRaises((NativeUIError,OSError)):owner.act(call)
            owner.store.write=writer
            with self.assertRaises(NativeUIError):owner.act(call)
        self.assertEqual([],m.normal_inputs)

    def test_foreign_ticket_cannot_resume_an_existing_owned_input(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();other=m.call('background-resume')
            with self.assertRaises(NativeUIError):current.act(other)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_changed_actual_fixture_phase_cannot_activate_an_old_background_call(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();m.call('close');m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertFalse(m.foreground);self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_new_fixture_birth_with_same_ticket_cannot_borrow_old_background_authority(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();m.journal.phase_instance='8'*32;m.lose=''
            with self.assertRaises(NativeUIError):current.act(call)
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_unresolved_ordinary_emote_input_blocks_a_new_background_action(self):
        m=self.model;m.widgets.tablet=False;m.input_fault='lost-sdk'
        from overte_phone_emote_inputs import PhoneEmoteInputs
        with m.lock.held(),patch('overte_phone_emote_inputs.PhoneScriptUI',side_effect=m.tablet):
            inputs=PhoneEmoteInputs(m.source())
            with self.assertRaises(NativeUIError):inputs.act(m.call('open'))
            self.assertEqual('issuing',inputs.state['current']['phase'])
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call('background-resume'))
            self.assertIsNone(owner.store.read())
        self.assertEqual([],m.normal_inputs)

    def test_corrupt_or_missing_originals_in_background_cannot_authorize_activation(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            from overte_phone_script_history import unpack
            from overte_phone_emote_originals import PhoneEmoteOriginals
            header=owner.state['beforeHeader'];state=unpack(header['payload'])[0]
            originals=PhoneEmoteOriginals(m.root,m.binding,RUN,'primary',lambda:True,lambda *_args:False)
            entries=originals.manifest(state['manifests'][0]);originals.path(originals.expand(entries[0])).unlink()
            with self.assertRaises((NativeUIError,OSError)):m.owner()
        self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_failed_final_journal_write_resumes_only_original_reads_without_os_redelivery(self):
        m=self.model
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume');writer=owner.store.write
            from overte_phone_script_history import unpack
            def fail_observed(value,previous):
                if unpack(value['payload'])[0]['phase']=='observed':raise OSError('Synthetic lost final commit')
                return writer(value,previous)
            owner.store.write=fail_observed
            with self.assertRaises((NativeUIError,OSError)):owner.act(call)
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner();current.act(call);current.retire()
        self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_original_replay_has_no_native_transport_and_retains_original_clocks(self):
        m=self.model
        with m.lock.held():
            source=m.source();m.call('background-resume');frame=source.read();before=list(m.calls)
            from overte_phone_emote_sources import PhoneEmoteSources
            state,frames=PhoneEmoteSources.archive(source.previous,phase=source.phase,artifact_root=m.root,
                binding=m.binding,guard=lambda:True,monotonic=lambda:m.clock)
            self.assertEqual(before,m.calls);self.assertEqual(frame,frames[-1]);self.assertEqual('ready',state['phase'])

    def test_retirement_refuses_unobserved_background_and_preserves_original_ownership(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            owner=m.owner();call=m.call('background-resume')
            with self.assertRaises(NativeUIError):owner.act(call)
            current=m.owner()
            with self.assertRaises(NativeUIError):current.retire()
            self.assertIsNotNone(current.store.read())
        self.assertEqual(['lifecycle.background'],m.normal_inputs)


if __name__=='__main__':unittest.main()
