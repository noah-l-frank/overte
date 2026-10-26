"""Exact child/parent original join, never a generic lifecycle allowance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.audio_recorded_owner import IOSAudioRecordedOwner
from ios.self_tests.audio_background_domain import AudioBackgroundDomain,TICKET
from ios.self_tests.test_ios_audio_recorded_owner import RUN


class AudioBackgroundBridgeTests(unittest.TestCase):
    def setUp(self):self.b=AudioBackgroundDomain(self,pages=self._testMethodName in (
        'test_canonical_resume_composes_original_os_child_then_normal_page_close',
        'test_retired_pcm_keeps_original_cycle_through_later_mute_background_and_page_return'))

    def parent(self):
        b=self.b;m=b.m
        owner=IOSAudioRecordedOwner(b.store,b.root,b.binding,RUN,b.lock,m.guard,native=m.reader(),io=m.io(),
            phase=PhaseFixtureReader(m.client(),RUN,'audio',epoch_ms=m.epoch,monotonic=lambda:m.clock),
            epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        m.owner=owner;return owner

    def test_exact_child_allows_fresh_parent_cut_and_later_normal_cycles_and_pure_replay(self):
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();result=owner.adopt_background(child)
        self.assertEqual('cancelled',result['state']['phase']);self.assertEqual('backgrounded',result['state']['error'])
        self.assertEqual(2,len(b.inputs));self.assertEqual(1,b.m.actions.count('audio.record'))
        b.m.add_phase('record-start','8'*32);owner.act(b.m.ticket,'record-start')
        b.m.add_phase('record-cancel','9'*32);owner.act(b.m.ticket,'record-cancel')
        current=deepcopy(owner.state);reads=b.reads;inputs=deepcopy(b.inputs);b.native_blocked=True
        sdk=(len(b.f.commands),len(b.fixture.calls))
        archive=IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,RUN,b.lock,owner.fixture_url)
        self.assertEqual(current,archive.state);self.assertEqual(reads,b.reads);self.assertEqual(inputs,b.inputs)
        self.assertEqual(sdk,(len(b.f.commands),len(b.fixture.calls)))

    def test_parent_cannot_cross_lifecycle_without_exact_completed_child(self):
        b=self.b;b.owner.act(TICKET);owner=self.parent();b.m.add_phase('record-start','8'*32)
        before=deepcopy(b.m.actions)
        with self.assertRaises(NativeUIError):owner.act(b.m.ticket,'record-start')
        self.assertEqual(before,b.m.actions)

    def test_incomplete_child_cannot_authorize_parent_transition(self):
        b=self.b;owner=self.parent();saved=b.store.path.read_bytes()
        with self.assertRaises(NativeUIError):owner.adopt_background(b.owner)
        self.assertEqual(saved,b.store.path.read_bytes());self.assertEqual([],b.inputs)

    def test_saved_bridge_original_recovers_without_os_resend_or_new_native_cut(self):
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();write=OriginalFrameStore.write;saved={}
        def lost(store,index,value):
            reference=write(store,index,value)
            if store.namespace=='ios-audio-recorded' and value['verb']=='background-resume':
                path=store.path(store.expand(reference));saved.update(path=path,body=path.read_bytes(),inode=path.stat().st_ino)
                raise OSError('Declared loss after parent bridge original saved')
            return reference
        with patch.object(OriginalFrameStore,'write',lost):
            with self.assertRaises(OSError):owner.adopt_background(child)
        reads=b.reads;b.native_blocked=True;result=self.parent().adopt_background()
        self.assertEqual('cancelled',result['state']['phase']);self.assertEqual(reads,b.reads);self.assertEqual(2,len(b.inputs))
        self.assertEqual(saved['body'],saved['path'].read_bytes());self.assertEqual(saved['inode'],saved['path'].stat().st_ino)

    def test_retained_bridge_repeats_historical_result_without_source_or_os_input(self):
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();result=owner.adopt_background(child)
        reads=b.reads;b.native_blocked=True;self.assertEqual(result,self.parent().adopt_background())
        self.assertEqual(reads,b.reads);self.assertEqual(2,len(b.inputs))

    def test_failed_bridge_cas_retains_child_and_sends_no_recording_input(self):
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();before=b.store.path.read_bytes()
        with patch.object(owner.store,'write',side_effect=OSError('Declared failed bridge CAS')):
            with self.assertRaises(OSError):owner.adopt_background(child)
        self.assertEqual(before,b.store.path.read_bytes());self.assertEqual(2,len(b.inputs));self.assertEqual(1,b.m.actions.count('audio.record'))

    def test_replaced_child_source_cannot_be_hidden_by_parent_archive(self):
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();owner.adopt_background(child)
        source=child.frames.path(child.frames.expand(child.state['records'][-1]));source.unlink();b.native_blocked=True
        with self.assertRaises((NativeUIError,FileNotFoundError)):
            IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,RUN,b.lock,owner.fixture_url)

    def test_changed_prefix_or_unrelated_bridge_owner_is_rejected(self):
        from ios.adapters.audio_background_bridge import proof
        from adapters.script_feature.history import unpack,pack
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();owner.adopt_background(child)
        original=owner.state['background']['proof']
        for fault in ('reference','prefix'):
            bad=deepcopy(original)
            if fault=='reference':bad['before']['sha256']='f'*64
            else:
                state=unpack(bad['child']['payload'])[0];parent=unpack(state['parent']['payload'])[0]
                parent['operations']=[];state['parent']['payload']=pack([parent]);bad['child']['payload']=pack([state])
            with self.assertRaises(NativeUIError):proof(owner,bad,owner.state)

    def test_canonical_resume_composes_original_os_child_then_normal_page_close(self):
        b=self.b;m=b.m;owner=self.parent()
        result=b.runtime.resume_recording('test-only',owner,TICKET,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        self.assertEqual('backgrounded',result['state']['error']);self.assertEqual('audio',m.page_model.route)
        m.add_phase('close','a'*32);self.assertFalse(owner.act(m.ticket,'close')['state']['open'])
        self.assertEqual('closed',m.page_model.route);self.assertEqual(2,len(b.inputs));self.assertEqual(1,m.actions.count('audio.record'))
        archived=IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,RUN,b.lock,owner.fixture_url)
        self.assertEqual(owner.state,archived.state)

    def test_retired_pcm_keeps_original_cycle_through_later_mute_background_and_page_return(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters.audio_pcm_lease import IOSAudioPCMLease
        from ios.self_tests.test_ios_audio_pcm_lease import PCMModel
        b=self.b;m=b.m;owner=self.parent();m.automatic=True
        m.add_phase('await-completion','a'*32);owner.act(m.ticket,'await-completion')
        pcm=PCMModel(m);native,preview=pcm.reader();store=PrivateFeatureState(b.root/'ios-audio-pcm-lease.json')
        lease=IOSAudioPCMLease(store,owner,native=native,preview=preview);lease.capture();retired=lease.retire()
        original=(store.path.stat().st_ino,store.path.read_bytes());m.automatic=False
        activate=m.activate
        def active_cycle(identifier,*,token):
            cycle=m.cycle;result=activate(identifier,token=token)
            if m.cycle!=cycle:pcm.memory=True # Actual begin allocates evidence again.
            return result
        m.activate=active_cycle
        m.add_phase('record-start','b'*32);owner.act(m.ticket,'record-start')
        m.add_phase('mute','c'*32,enabled=True);owner.act(m.ticket,'mute',enabled=True)
        m.add_phase('mute','d'*32,enabled=False);owner.act(m.ticket,'mute',enabled=False)
        m.add_phase('record-start','e'*32);owner.act(m.ticket,'record-start')
        ticket='f'*32;m.add_phase('background-resume',ticket)
        result=b.runtime.resume_recording('test-only',owner,ticket,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        self.assertEqual('backgrounded',result['state']['error'])
        m.add_phase('close','9'*32);self.assertFalse(owner.act(m.ticket,'close')['state']['open'])
        commands=deepcopy(pcm.commands);reads=b.reads;b.native_blocked=True
        archive=IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,RUN,b.lock,owner.fixture_url)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Pure PCM archive must not write')):
            self.assertEqual(retired,IOSAudioPCMLease.archive(store,archive).retired())
        self.assertEqual(original,(store.path.stat().st_ino,store.path.read_bytes()))
        self.assertEqual(commands,pcm.commands);self.assertEqual(reads,b.reads)
        self.assertEqual(1,retired['recording']['cycle']);self.assertEqual(3,m.cycle)
        self.assertTrue(pcm.memory) # Old retirement is not absence for later cycles.
        self.assertEqual(1,pcm.count('feature-recorded-audio-release'));self.assertEqual(2,len(b.inputs))

    def test_bridge_cannot_be_detached_from_the_parent_state_ledger(self):
        from adapters.script_feature.history import unpack,pack
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();owner.adopt_background(child)
        value=deepcopy(owner.previous);state=unpack(value['payload'])[0];state['background']=None
        with self.assertRaises(NativeUIError):owner.decode(dict(value,payload=pack([state])))

    def test_prefix_view_keeps_full_current_inventory_and_refuses_orphan_original(self):
        from adapters.normal_feature_state import PrivateFeatureState
        b=self.b;child=b.owner;child.act(TICKET);owner=self.parent();owner.adopt_background(child)
        PrivateFeatureState(b.root/'ios-audio-recorded-orphan.json').write(dict(retained='unowned original'),None)
        with self.assertRaises(NativeUIError):
            IOSAudioRecordedOwner.archive(b.store,b.root,b.binding,RUN,b.lock,owner.fixture_url)

    def test_canonical_resume_recovers_lost_home_before_adopting_parent(self):
        b=self.b;m=b.m;owner=self.parent();b.fault='lost-home'
        def resume():return b.runtime.resume_recording('test-only',owner,TICKET,m.client(),epoch_ms=m.epoch,monotonic=lambda:m.clock,sleep=m.sleep)
        with self.assertRaises(OSError):resume()
        self.assertFalse(b.f.process['foreground']);self.assertIsNone(owner.state['background'])
        b.fault=None;self.assertEqual('backgrounded',resume()['state']['error']);self.assertEqual(2,len(b.inputs))


class AudioBackgroundLegacyTests(unittest.TestCase):
    def test_literal_three_page_owner_keeps_exact_read_grammar_and_refuses_bridge(self):
        from ios.self_tests import test_ios_audio_recorded_owner as recording
        from ios.self_tests.audio_page_cycle_domain import AudioPageCycleDomain
        f=recording.AudioRecordedOwnerTests();f.setUp();self.addCleanup(f.doCleanups)
        m=f.model=AudioPageCycleDomain(f.root);m.add_phase('open','3'*32)
        with patch('ios.adapters.audio_recorded_owner.VERSION',3),f.owner() as owner:
            owner.act(m.ticket,'open');m.add_phase('close','a'*32);owner.act(m.ticket,'close')
            self.assertNotIn('background',owner.state);self.assertNotIn('background',owner.original(owner.state['records'][-1]))
            expected=deepcopy(owner.state);url=owner.fixture_url
            with self.assertRaises(NativeUIError):owner.adopt_background()
        with f.lock.held():
            archive=IOSAudioRecordedOwner.archive(f.store,f.root,recording.BINDING,RUN,f.lock,url)
            self.assertEqual(3,archive.version);self.assertEqual(expected,archive.state)
