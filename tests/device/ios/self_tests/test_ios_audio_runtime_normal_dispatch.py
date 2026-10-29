"""Actual held Audio owners and typed calls; native/OS/PCM are host models.

The complete14 component routes through IOSAudioRuntime, without Installed
admission, independent acoustic/peer evidence or process/SDK retirement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import VERSION
from ios.adapters.audio_pcm_lease import INPUT_ORIGIN_PROFILE
from ios.adapters.audio_session_owners import register_scope,ensure_released
from ios.self_tests.test_ios_audio_authorized_start import StartDomain
from ios.self_tests.test_ios_audio_normal_journey import AudioNormalJourneyTests
from ios.self_tests.test_ios_audio_required_runtime_close_join import RequiredClosePCMModel


class AudioRuntimeNormalDispatchTests(unittest.TestCase):
    def domain(self):
        s=StartDomain(self);d=s.d;parent=d.parent
        parent.close_evidence=lambda owner:d.runtime.close_recording_evidence('owned',owner)
        register_scope(d.runtime.adapter,'owned',parent.binding,parent.run,parent.root)
        return s

    @staticmethod
    def call(parent,ticket=None):
        return dict(contractVersion=VERSION,runId=parent.run,fixtureUrl=parent.fixture_url,
            ticket=ticket,verb='record-start',inputs={})

    @staticmethod
    def idle(d):
        return deepcopy((d.source_reads,d.session.queries,d.m.counter,d.m.phase_sequence,d.m.actions))

    def test_runtime_dispatches_all14_auth_background_strict_PCM_and_latest_close_without_end_admission(self):
        lease,retired,closed,model,runtime=AudioNormalJourneyTests.run_normal_journey(self,
            pcm_model=RequiredClosePCMModel,pcm_profile=INPUT_ORIGIN_PROFILE,
            close_evidence=True,runtime_pcm=True,runtime_dispatch=True)
        self.assertEqual(2,lease.version);self.assertEqual(INPUT_ORIGIN_PROFILE,lease.profile)
        self.assertEqual(3,retired['recording']['cycle']);self.assertEqual(5,closed['recording']['cycle'])
        self.assertEqual(1,model.count('feature-recorded-audio-observe'));self.assertFalse(model.memory)
        callback=lease.snapshot()['packet']['source']['inputOrigin']
        self.assertTrue(callback['available'])
        for flag in ('physicalADCQualified','acousticQualified','peerQualified','resamplerHistoryQualified'):
            self.assertIs(False,callback[flag])
        before=deepcopy((model.commands,model.model.actions))
        with self.assertRaises(NativeUIError):ensure_released(runtime.adapter,'test-only')
        self.assertEqual(before,(model.commands,model.model.actions))

    def test_foreign_run_or_fixture_or_owner_store_refuses_before_phase_native_or_input(self):
        s=self.domain();d=s.d;parent=d.parent
        call=self.call(parent,d.m.ticket);before=self.idle(d);saved=parent.store.read()
        for field,value in (('runId','a'*32),('fixtureUrl',parent.fixture_url.replace('controlled.invalid','foreign.invalid'))):
            wrong=deepcopy(call);wrong[field]=value
            with self.assertRaises((NativeUIError,ValueError)):d.runtime.normal_act('owned',parent,wrong)
        # The actual runtime state_path accepts only this original root here;
        # use a different original owner store, not an adapter factory result.
        old=parent.store;parent.store=PrivateFeatureState(old.path.with_name('foreign-recording-owner.json'))
        try:
            with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call)
        finally:parent.store=old
        self.assertEqual(before,self.idle(d));self.assertEqual(saved,parent.store.read())

    def test_missing_or_foreign_scope_refuses_before_native_and_does_not_recreate_scope(self):
        s=self.domain();d=s.d;parent=d.parent;call=self.call(parent,d.m.ticket)
        scope=PrivateFeatureState(parent.store.path.with_name('ios-audio-scope.json'))
        original=scope.read();before=self.idle(d)
        scope.path.unlink()
        with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call)
        self.assertFalse(scope.path.exists());self.assertEqual(before,self.idle(d))
        foreign=deepcopy(original);foreign['runId']='a'*32;scope.write(foreign,None)
        with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call)
        self.assertEqual(foreign,scope.read());self.assertEqual(before,self.idle(d))
        self.assertEqual([],parent.state['operations']);self.assertIsNone(parent.state['pending'])

    def test_unknown_PCM_profile_refuses_before_phase_or_native_without_responsibility_birth(self):
        s=self.domain();d=s.d;parent=d.parent;call=self.call(parent,d.m.ticket)
        before=self.idle(d);paths={path:path.read_bytes() for path in d.f.root.iterdir() if path.is_file()}
        for profile in (False,'unknown-profile',1):
            with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call,pcm_profile=profile)
        self.assertEqual(before,self.idle(d))
        self.assertEqual(paths,{path:path.read_bytes() for path in d.f.root.iterdir() if path.is_file()})

    def test_stale_ticket_refuses_before_authorization_or_input_instead_of_reusing_old_result(self):
        s=self.domain();d=s.d;parent=d.parent;call=self.call(parent,d.m.ticket)
        d.m.add_phase('record-start','a'*32);actions=deepcopy(d.m.actions);reads=d.source_reads
        with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call)
        self.assertEqual(actions,d.m.actions);self.assertEqual(reads,d.source_reads)
        self.assertEqual([],parent.state['operations']);self.assertIsNone(parent.state['pending'])

    def test_lost_delivered_start_return_resolves_same_original_through_runtime_without_second_click(self):
        s=self.domain();d=s.d;parent=d.parent;call=self.call(parent,d.m.ticket);d.m.loss=True
        with self.assertRaises(NativeUIError):d.runtime.normal_act('owned',parent,call)
        self.assertEqual(1,d.m.actions.count('audio.record'));self.assertIsNotNone(parent.state['pending'])
        state=PrivateFeatureState(d.f.root/'ios-audio-authorized-starts.json').read()
        self.assertIsNotNone(state)
        before=deepcopy(parent.state['pending']['inputs']);d.m.loss=False
        result=d.runtime.normal_act('owned',parent,call)
        self.assertEqual('capturing',result['state']['phase']);self.assertEqual(1,d.m.actions.count('audio.record'))
        self.assertIsNone(parent.state['pending']);self.assertEqual(before,parent.state['operations'][-1]['inputs'])
        self.assertEqual(result['original'],parent.state['operations'][-1]['after'])


    def test_lost_home_return_recovers_original_background_child_before_parent_live_guard_without_second_home(self):
        from ios.self_tests.audio_background_domain import AudioBackgroundDomain,TICKET
        b=AudioBackgroundDomain(self);parent=b.parent
        parent.close_evidence=lambda owner:b.runtime.close_recording_evidence('test-only',owner)
        register_scope(b.runtime.adapter,'test-only',parent.binding,parent.run,parent.root)
        call=dict(contractVersion=VERSION,runId=parent.run,fixtureUrl=parent.fixture_url,
            ticket=TICKET,verb='background-resume',inputs={})
        b.fault='lost-home'
        with self.assertRaisesRegex(OSError,'lost ordinary OS return'):
            b.runtime.normal_act('test-only',parent,call)
        self.assertFalse(b.f.process['foreground']);self.assertEqual(['mobile: backgroundApp'],b.inputs)
        self.assertIsNone(parent.state['background']);before=deepcopy(b.m.actions)
        b.fault=None;result=b.runtime.normal_act('test-only',parent,call)
        self.assertTrue(b.f.process['foreground']);self.assertEqual('backgrounded',result['state']['error'])
        self.assertEqual(['mobile: backgroundApp','mobile: activateApp'],b.inputs)
        self.assertEqual(before,b.m.actions);self.assertIsNotNone(parent.state['background']['after'])
        parent.bound()


if __name__=='__main__':unittest.main()
