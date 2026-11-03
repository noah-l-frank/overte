"""SAME normal Parent + explicit independent Source4 native/GUI clock model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from copy import deepcopy
import gc
import weakref
from adapters.normal_ui import NativeUIError
from adapters.pico4.avatar_remote_state import source_store
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4 import remote_joint_pose
from self_tests.pico_emote_stream_fixture import StreamCycleModel,RUN

RETAINED=[]


class StreamCycleTests(unittest.TestCase):
    def setUp(self):
        self.model=StreamCycleModel();self.addCleanup(self.finalize)
        print('Retained actual modeled Source4/Parent roots:',*[str(path) for path in self.model.roots],flush=True)

    def finalize(self):
        def inventory():return {str(path):dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),physical=signature(path.stat()))
            for root in self.model.roots for path in root.rglob('*') if path.is_file()}
        before=inventory();self.model.close();after=inventory();self.assertEqual(before,after)
        self.assertTrue(all(root.is_dir() for root in self.model.roots))
        RETAINED.append(dict(roots=[str(path) for path in self.model.roots],files=after,originalModelCloseCalled=True))

    def test_original_normal_play_cancel_close_quiet_and_two_role_arm_stop_drain_share_one_parent(self):
        m=self.model
        with m.m.s.lock.held():cycle=m.create()
        with cycle.held():
            baseline=cycle.baseline();self.assertEqual('baseline',baseline['phase'])
            original=(cycle.parent.state['started'],cycle.parent.state['epochMs'],cycle.parent.state['hostEpochMs'])
            cycle.act(m.m.input.call('open'))
            first=cycle.sample_pair()
            value=cycle.act(m.m.input.call('play',{'name':'Waving'}));self.assertEqual('playback',value['kind'])
        # No source lock is held while the real modeled GUI clock advances.
        before=[producer.published for producer in m.streams.values()];m.m.tick(500)
        self.assertTrue(all(producer.published>previous for producer,previous in zip(m.streams.values(),before)))
        with cycle.held():
            second=cycle.sample_pair()
            changed=remote_joint_pose.changed(first['actor']['source']['subject']['remoteJointPose'],
                second['actor']['source']['subject']['remoteJointPose'])
            self.assertTrue(changed['copiedPoseChanged'])
            cycle.act(m.m.input.call('cancel'));cycle.act(m.m.input.call('close'))
            m.m.s.journal.activate(RUN,'f'*32,'cleanup');quiet=cycle.cleanup(sleep=m.m.sleep)
            self.assertTrue(quiet['sourceStopped']);self.assertFalse(quiet['sourceDrained'])
            self.assertGreaterEqual(quiet['originalParentNativeQuiet']['nativeQuiet']['window']['elapsedMs'],3000)
            self.assertEqual(original,(cycle.parent.state['started'],cycle.parent.state['epochMs'],cycle.parent.state['hostEpochMs']))
        for producer in m.streams.values():producer.event_loop_turn()
        with cycle.held():
            result=cycle.drain();self.assertTrue(result['sourceDrained'])
            self.assertFalse(result['wholeFeatureComplete']);self.assertFalse(result['stereoQualified'])
            self.assertFalse(result['independentActorQualified'])
            for role,producer in m.streams.items():
                self.assertEqual(['arm','stop','drain'],[request['operation'] for request in producer.controls])
                self.assertFalse(producer.timer or producer.deadline_timer);self.assertEqual(0,producer.pending_timers)
            self.assertEqual(['tablet.open','tablet.close'],m.m.input.controllers)
            self.assertEqual(2,len(m.m.input.transport.envelopes))
            self.assertLessEqual(cycle.originals.other_bill()['parts']+cycle.originals.archive.bill()['parts'],512)
            self.assertLessEqual(cycle.originals.other_bill()['storedBytes']+cycle.originals.archive.bill()['storedBytes'],16*1024*1024)


class StreamFenceTests(unittest.TestCase):
    setUp=StreamCycleTests.setUp
    finalize=StreamCycleTests.finalize

    def create(self):
        with self.model.m.s.lock.held():return self.model.create()

    def test_prior_actor_source3_journal_blocks_both_arms_before_normal_input(self):
        m=self.model;cycle=self.create();config=cycle.roles[1][1]
        old=source_store(config['adapter'],config['target'],RUN,area='emotes')
        old.write(dict(picoRemoteAvatarSourceVersion=3,historicalOnly=True),None)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual([[],[]],[producer.controls for producer in m.streams.values()])
        self.assertEqual([],m.m.input.inputs);self.assertEqual([],m.m.input.controllers)
        self.assertEqual('baseline-issued',cycle.parent.store.read()['state']['phase'])
        self.assertEqual('arming',cycle.store.read()['phase']);self.assertTrue(old.path.exists())

    def test_lost_original_arm_return_keeps_both_reservations_and_never_rearms_or_inputs(self):
        m=self.model;m.streams['primary'].fault='lost-arm';cycle=self.create()
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual(1,len(m.streams['primary'].controls));self.assertEqual(0,m.streams['primary'].getters)
        self.assertEqual(2,len(cycle.originals.archive.state['pending']))
        self.assertEqual([],m.m.input.inputs);self.assertEqual([],m.m.input.controllers)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual(1,len(m.streams['primary'].controls));self.assertTrue(m.streams['primary'].sample.exists())

    def test_same_bytes_replaced_budget_refuses_next_actual_sample_getter(self):
        m=self.model;cycle=self.create()
        with cycle.held():cycle.baseline()
        path=cycle.policy.path;replacement=path.with_name('owned-budget-counter-replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        before=[producer.getters for producer in m.streams.values()]
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(before,[producer.getters for producer in m.streams.values()])
        self.assertEqual([],m.m.input.inputs);self.assertEqual([],m.m.input.controllers)

    def test_expired_last_original_native_control_fence_sends_zero_and_retains_intent(self):
        m=self.model;producer=m.streams['primary'];original=producer.native.send
        def delayed(request):m.m.tick(1500);return original(request)
        producer.native.send=delayed;cycle=self.create()
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual([],producer.controls);self.assertEqual(0,producer.getters)
        self.assertEqual(2,len(cycle.originals.archive.state['pending']))
        self.assertEqual([],m.m.input.controllers);self.assertEqual('reading',cycle.streams['primary'].store.read()['phase'])

    def test_actual_accepted_control_unknown_role_cas_keeps_raw_and_sticky_reading(self):
        m=self.model;cycle=self.create();write=LifecycleProcessFile.write;lost=[]
        def unknown(owner,value,previous):
            write(owner,value,previous)
            if 'emote-remote-owner-' in owner.path.name and len(value.get('chunks',[]))==1 and not lost:
                lost.append(True);raise OSError('Actual published role CAS response lost')
        with patch.object(LifecycleProcessFile,'write',unknown),self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual([True],lost);role=cycle.streams['primary'];actual=role.store.read()
        self.assertEqual('reading',actual['phase']);self.assertEqual('arm',actual['state']['pending']['command']['operation'])
        self.assertEqual(1,len(actual['chunks']));self.assertEqual(1,len(m.streams['primary'].controls))
        self.assertTrue(cycle.originals.archive.literal(role.wire.last_reference))
        self.assertEqual([],m.m.input.controllers)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual(1,len(m.streams['primary'].controls))

    def test_identical_first_sample_replacement_cannot_be_adopted_after_actual_arm(self):
        m=self.model;cycle=self.create()
        with cycle.held():cycle.baseline()
        producer=m.streams['primary'];path=producer.sample;replacement=path.with_name('owned-first-sample-replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(0,cycle.streams['primary'].state['lastSampleSequence'])
        self.assertTrue(cycle.originals.archive.literal(cycle.streams['primary'].wire.last_reference))
        self.assertEqual([],m.m.input.controllers)

    def test_same_node_same_id_timestamp_mutation_refuses_initial_original(self):
        m=self.model;cycle=self.create()
        with cycle.held():cycle.baseline()
        path=m.streams['primary'].sample;info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1))
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(0,cycle.streams['primary'].state['lastSampleSequence'])
        self.assertEqual([],m.m.input.controllers)

    def test_real_budget_loss_after_ack_getter_retains_wire_before_business_refusal(self):
        m=self.model;binary=m.streams['primary'].execute_bytes;returned=[]
        def original_then_lost(*args,**options):
            wire=binary(*args,**options);returned.append(wire)
            path=m.cycle.policy.path;replacement=path.with_name('owned-late-budget-replacement')
            replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path);return wire
        # Fault boundary is installed BEFORE the original callback is sealed.
        m.streams['primary'].execute_bytes=original_then_lost;cycle=self.create()
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual(1,len(returned));role=cycle.streams['primary']
        self.assertEqual(returned[0],cycle.originals.archive.literal(role.wire.last_reference))
        self.assertEqual('reading',role.store.read()['phase']);self.assertFalse(role.state['chunks'])
        self.assertEqual(1,len(m.streams['primary'].controls));self.assertEqual([],m.m.input.controllers)

    def test_same_sample_inode_under_replaced_native_root_refuses_original_authority(self):
        m=self.model;cycle=self.create()
        with cycle.held():cycle.baseline()
        path=m.streams['primary'].sample;old=path.parent.with_name('owned-old-native-root')
        path.parent.rename(old);path.parent.mkdir(mode=0o700)
        for child in old.iterdir():child.rename(path.parent/child.name)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(0,cycle.streams['primary'].state['lastSampleSequence'])
        self.assertTrue(cycle.originals.archive.literal(cycle.streams['primary'].wire.last_reference))
        self.assertEqual([],m.m.input.controllers)

    def test_equal_memory_sample_graph_replacement_refuses_before_next_native_getter(self):
        m=self.model;cycle=self.create()
        with cycle.held():cycle.baseline();cycle.sample_pair()
        role=cycle.streams['primary'];role.last_sample=deepcopy(role.last_sample)
        before=[producer.getters for producer in m.streams.values()]
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.sample_pair()
        self.assertEqual(before,[producer.getters for producer in m.streams.values()])
        self.assertEqual([],m.m.input.controllers)

    def test_aggregate_real_actor_files_prevent_both_native_sends_before_any_new_budget(self):
        m=self.model;cycle=self.create();(m.actor_root/'owned-actor-capacity-counter.bin').write_bytes(b'\0'*(16*1024*1024))
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual([[],[]],[producer.controls for producer in m.streams.values()])
        self.assertEqual([],m.m.input.controllers);self.assertEqual([],m.m.input.inputs)
        self.assertEqual('baseline-issued',cycle.parent.store.read()['state']['phase'])


class StreamCoordinatorIdentityTests(unittest.TestCase):
    setUp=StreamCycleTests.setUp
    finalize=StreamCycleTests.finalize

    def create(self):
        self.sdk=[]
        for role,producer in self.model.streams.items():
            clock=producer.native.clock_ms
            def observed(clock=clock,role=role):self.sdk.append(role);return clock()
            producer.native.clock_ms=observed
        with self.model.m.s.lock.held():return self.model.create()

    def refused(self,cycle):
        before=(list(self.sdk),list(self.model.m.s.calls),list(self.model.m.input.inputs),list(self.model.m.input.controllers))
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual(before,(self.sdk,self.model.m.s.calls,self.model.m.input.inputs,self.model.m.input.controllers))
        self.assertEqual([[],[]],[producer.controls for producer in self.model.streams.values()])
        self.assertEqual([0,0],[producer.getters for producer in self.model.streams.values()])
        self.assertIsNone(cycle.parent.store.read());self.assertFalse(cycle.path.exists())

    def test_phase_flip_cannot_skip_both_initial_arms_or_first_original_source_budget(self):
        cycle=self.create();cycle.phase='armed';self.refused(cycle)

    def test_equal_binding_config_graph_replacement_refuses_before_sdk_or_input(self):
        cycle=self.create();config=cycle.roles[1][1];config['binding']=deepcopy(config['binding']);self.refused(cycle)

    def test_actual_native_callback_replacement_refuses_before_sdk_or_input(self):
        cycle=self.create();native=cycle.roles[1][1]['native'];original=native.send
        native.send=lambda request:original(request);self.refused(cycle)

    def test_target_substitution_and_equal_empty_owner_graph_cannot_be_resealed_by_guard(self):
        cycle=self.create();cycle.roles[1][1]['target']='foreign-declared-model';cycle.streams={};self.refused(cycle)

    def test_foreign_actual_parent_descriptor_is_not_closed_after_graph_replacement(self):
        from adapters.normal_feature_state import PrivateFeatureState
        cycle=self.create();foreign=LifecycleProcessFile(PrivateFeatureState(self.model.actor_root/'owned-foreign-parent.json'))
        self.addCleanup(foreign.close_host);descriptor=foreign.parent.fd;cycle.file=foreign;self.refused(cycle)
        self.assertTrue(cycle.close_host());foreign.parent.require(descriptor)
        self.assertFalse(foreign.parent.closed);self.assertEqual(foreign.parent.node,(os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino))

    def lose_owner_cas(self,kind):
        from adapters.pico4.emote_stream_policy import PicoEmoteStreamPolicy
        from adapters.pico4.emote_stream_originals import PicoEmoteStreamOriginals
        cycle=self.create();selected=PicoEmoteStreamPolicy if kind=='policy' else PicoEmoteStreamOriginals
        construct=selected.__init__;write=LifecycleProcessFile.write;refs={};known={};lost=[]
        def actual_constructor(owner,*args,**options):
            construct(owner,*args,**options);refs['owner']=weakref.ref(owner)
            if kind=='originals':
                descriptor=owner.archive.directory;descriptor.require(descriptor.fd)
                known.update(fd=descriptor.fd,anchor=descriptor.anchor,node=descriptor.node)
            else:known.update(budget=owner.budget_pin,baseline=owner.baseline_pin)
        def actual_cas(owner,value,previous):
            write(owner,value,previous)
            target=(kind=='policy' and cycle._policy is None and value.get('budgetSha256') is not None
                or kind=='originals' and cycle._policy is not None and cycle._originals is None and 'owner' in refs)
            if owner.path==cycle.path and target and not lost:
                lost.append(True);raise OSError('Actual new original owner CAS reply lost')
        with patch.object(selected,'__init__',actual_constructor),patch.object(LifecycleProcessFile,'write',actual_cas),self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        self.assertEqual([True],lost)
        # No strong test reference or retained traceback may keep it alive.
        gc.collect();owner=refs['owner']();self.assertIsNotNone(owner)
        self.assertTrue(any(original is owner and complete for label,original,complete in cycle._pending_originals))
        self.assertIsNone(cycle._policy if kind=='policy' else cycle._originals)
        self.assertEqual([[],[]],[producer.controls for producer in self.model.streams.values()])
        self.assertEqual([0,0],[producer.getters for producer in self.model.streams.values()])
        self.assertEqual([],self.model.m.input.inputs);self.assertEqual([],self.model.m.input.controllers)
        with self.assertRaises(NativeUIError):
            with cycle.held():cycle.baseline()
        return cycle,owner,known

    def test_successful_policy_constructor_unknown_parent_cas_retains_exact_original_after_traceback_gc(self):
        cycle,owner,known=self.lose_owner_cas('policy');owner.identity();seen=[]
        def actual_window(raw):
            descriptor=owner.budget_file.active;descriptor.require(descriptor.fd)
            self.assertEqual(tuple(known['budget']),tuple(owner.budget_file.stamp))
            self.assertEqual(descriptor.node,(os.fstat(descriptor.fd).st_dev,os.fstat(descriptor.fd).st_ino))
            seen.append(True)
        raw,physical=owner.budget_file.read(validate=actual_window)
        self.assertEqual([True],seen);self.assertEqual(owner.raw,raw);self.assertEqual(known['budget'],physical)
        self.assertEqual(known['baseline'],owner.baseline_pin);self.assertTrue(cycle.close_host())

    def test_successful_raw_owner_constructor_unknown_parent_cas_retains_original_directory_ofd_after_gc(self):
        cycle,owner,known=self.lose_owner_cas('originals');descriptor=owner.archive.directory
        self.assertEqual((known['fd'],known['anchor'],known['node']),(descriptor.fd,descriptor.anchor,descriptor.node))
        descriptor.require(known['fd']);self.assertEqual(known['node'],(os.fstat(known['fd']).st_dev,os.fstat(known['fd']).st_ino))
        self.assertTrue(cycle.close_host());self.assertTrue(descriptor.closed)
        with self.assertRaises(OSError):os.fstat(known['fd'])


if __name__=='__main__':unittest.main()
