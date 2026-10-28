"""Actual normal Close/WAL/byte ownership; native Audio/SDK remain models.

No native gate execution, acoustic output, peer receipt or whole Audio claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.recorded_preview_evidence import INPUT,SINK
from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests import test_ios_audio_pcm_lease as pcm_fixture
from ios.self_tests import test_ios_audio_normal_journey as normal_fixture
from ios.self_tests.audio_background_domain import AudioBackgroundDomain


class ClosePCMModel(pcm_fixture.PCMModel):
    """Declared native producer with real private tap files and fresh queries."""
    def __init__(self,model):
        super().__init__(model)
        self.native_root=model.owner.root/'declared-native-pcm-files';self.native_root.mkdir(mode=0o700)
        self.lose_close=False;self.race=None;self.keep_close_memory=False
    def source(self):
        value=super().source()
        for name,raw in self.files.items():
            path=self.native_root/name;path.write_bytes(raw);path.chmod(0o600)
        return value
    def send(self,command):
        if command['schemaVersion']==2:
            self.commands.append(deepcopy(command));m=self.model;m.tick()
            if self.race=='cycle':
                m.cycle+=1;m.recorded['cycle']=m.cycle;m.recorded['startedEpochMs']+=1
            elif self.race=='instance':m.native_instance='b'*32
            expected=dict(instance=m.native_instance,cycle=m.recorded['cycle'],startedEpochMs=m.recorded['startedEpochMs'])
            files=any((self.native_root/name).exists() or (self.native_root/name).is_symlink() for name in (INPUT,SINK))
            admitted=command['expected']==expected and not m.active and not files
            if admitted and not self.keep_close_memory:self.memory=False
            self.packet=dict(schemaVersion=1,requestId=command['commandId'],released=admitted)
            if self.lose_close:raise NativeUIError('Declared lost guarded release return after native delivery')
            return
        answer=super().send(command)
        if command['action']=='feature-recorded-audio-release' and not self.keep_file:
            for name in (INPUT,SINK):
                path=self.native_root/name
                if path.exists():path.unlink()
        if command['action']=='feature-recorded-audio-files':
            self.packet['files']=[dict(name=name,exists=(self.native_root/name).exists() or (self.native_root/name).is_symlink()) for name in (INPUT,SINK)]
        return answer


class AudioNormalCloseEvidenceTests(unittest.TestCase):
    def domain(self,*,owned=True):
        b=AudioBackgroundDomain(self,pages=True,prepare_recording=owned);m=b.m;parent=b.parent
        if not owned:
            m.add_phase('open','3'*32);parent.act(m.ticket,'open')
        else:
            m.add_phase('record-cancel','5'*32);parent.act(m.ticket,'record-cancel')
        model=ClosePCMModel(m);original=b.runtime._sources
        def source(selector):
            value=original(selector)
            value['observer']=SimpleNamespace(recorded_preview_observer=lambda:model.reader()[1])
            return value
        b.runtime._sources=source
        parent.close_evidence=lambda owner:b.runtime.close_recording_evidence('test-only',owner)
        m.add_phase('close','6'*32)
        return b,model
    def close(self,b):return b.parent.act(b.m.ticket,'close')
    def guarded_count(self,model):return sum(row['schemaVersion']==2 for row in model.commands)
    def test_full_fourteen_normal_actions_retire_later_owned_cycles_without_second_observe(self):
        case=normal_fixture.AudioNormalJourneyTests();self.addCleanup(case.doCleanups)
        lease,retired,closed,model=case.run_normal_journey(pcm_model=ClosePCMModel,close_evidence=True)
        self.assertEqual(3,retired['recording']['cycle']);self.assertEqual(5,closed['recording']['cycle'])
        self.assertFalse(model.memory);self.assertEqual(1,model.count('feature-recorded-audio-observe'))
        self.assertEqual(1,self.guarded_count(model));self.assertIsNone(lease.state['pending'])
        self.assertFalse(any(model.native_root.iterdir()))
    def test_normal_close_uses_original_start_and_fresh_independent_absence_with_no_allocation(self):
        b,model=self.domain();self.assertTrue(self.close(b)['performed'])
        actions=deepcopy(b.m.actions);commands=deepcopy(model.commands)
        self.assertFalse(model.memory);self.assertEqual(0,model.count('feature-recorded-audio-observe'))
        self.assertEqual(1,self.guarded_count(model));self.assertGreaterEqual(model.count('feature-recorded-audio-files'),2)
        archive=IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,b.parent.run,b.lock,b.parent.fixture_url)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Pure close archive attempted write')):
            owner=IOSAudioPCMLease.archive(PrivateFeatureState(b.root/'ios-audio-close-lease.json'),archive)
            self.assertTrue(owner.retired()['retired']);self.assertFalse(owner.retired()['captured'])
            self.assertIsNone(owner.state['allocation']);self.assertEqual(1,owner.recording['cycle'])
        self.assertEqual(commands,model.commands);self.assertEqual(actions,b.m.actions)
    def test_lost_guarded_release_return_keeps_durable_close_and_retry_only_reads_absence(self):
        b,model=self.domain();model.lose_close=True
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertFalse(model.memory);self.assertEqual('close',b.parent.state['operations'][-1]['verb'])
        self.assertIsNone(b.parent.state['pending']);actions=deepcopy((b.m.actions,b.m.page_model.actions))
        issued=PrivateFeatureState(b.root/'ios-audio-close-lease.json').read();self.assertIsNotNone(issued)
        model.lose_close=False;self.assertTrue(self.close(b)['performed'])
        self.assertEqual(1,self.guarded_count(model));self.assertEqual(0,model.count('feature-recorded-audio-observe'))
        self.assertEqual(actions,(b.m.actions,b.m.page_model.actions))
    def test_preexisting_real_tap_file_refuses_before_release_and_preserves_original_inode(self):
        b,model=self.domain();path=model.native_root/INPUT;path.write_bytes(b'foreign PCM responsibility');path.chmod(0o600)
        before=(path.read_bytes(),path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertEqual(0,self.guarded_count(model));self.assertTrue(model.memory)
        self.assertEqual(before,(path.read_bytes(),path.stat().st_ino))
    def test_new_cycle_between_original_native_check_and_guarded_release_is_not_cleared(self):
        b,model=self.domain();model.race='cycle'
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertTrue(model.memory);self.assertEqual(1,self.guarded_count(model));self.assertEqual(2,b.m.cycle)
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertEqual(1,self.guarded_count(model))
    def test_foreign_process_source_instance_at_guarded_release_preserves_buffer(self):
        b,model=self.domain();model.race='instance'
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertTrue(model.memory);self.assertEqual(1,self.guarded_count(model))
    def test_release_ack_cannot_replace_real_fresh_memory_absence_or_be_resent(self):
        b,model=self.domain();model.keep_close_memory=True
        with self.assertRaises(NativeUIError):self.close(b)
        with self.assertRaises(NativeUIError):self.close(b)
        self.assertTrue(model.memory);self.assertEqual(1,self.guarded_count(model))
    def test_close_without_owned_start_preserves_preexisting_native_buffer_without_release(self):
        b,model=self.domain(owned=False);self.assertTrue(self.close(b)['performed'])
        self.assertTrue(model.memory);self.assertEqual([],model.commands)
        self.assertFalse((b.root/'ios-audio-close-lease.json').exists())


if __name__=='__main__':unittest.main()
