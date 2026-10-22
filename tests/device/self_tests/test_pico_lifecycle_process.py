"""Original source/OS birth boundaries; no client, process, device or network run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement,PicoLifecycleDomain,run_lifecycle_restart
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
from adapters.script_journey.history import unpack
from self_tests import test_pico_lifecycle_world as world_seams
from self_tests.test_pico_lifecycle_join import XTransport
from self_tests.test_pico_lifecycle_world import Native,BINDING,RUN
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_chat_observation import Boundary as ChatBoundary

NEW_BINDING=BINDING|dict(processIdentity='124:500',sessionId='new-original-bridge',generation=2)


class LifecycleProcessTests(unittest.TestCase):
    def setUp(self):
        self.fixture=world_seams.LifecycleWorldTests();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.root,self.native,self.session=self.fixture.root,self.fixture.native,self.fixture.session
        self.fixture.path=self.root/'lifecycle-world-owner.json'
        self.transport=XTransport(self.native,self.fixture.path);self.transport.back_path=self.root/'lifecycle-x-back-owner.json'
        self.fixture.transport=self.transport;self.session.transport=self.transport
        self.world=self.fixture.owner();self.world.prepare();self.new_native=None;self.installed=True
        self.process=PicoLifecycleProcessRetirement(self.root/'lifecycle-process-owner.json',RUN,self.session.profile,lambda:self.installed,
            self.world.lock,monotonic=lambda:self.native.clock,sleep=self.sleep)
        self.feature,self.source=self.features(self.native,123,'a'*32,1)
        self.domain_boundary,self.domain=self.domains(self.native,123,'9'*32,'1'*32,'2'*32,19000)
        self.process.begin(self.world,self.source,self.domain)
    def sleep(self,seconds):
        self.native.clock+=seconds
        if self.new_native is not None:self.new_native.clock=self.native.clock
    def features(self,native,pid,instance,launches):
        boundary=FeatureBoundary()
        def mutate(value):
            epoch=native.epoch();value.update(processId=pid,instance=instance,capturedEpochMs=epoch,requestedEpochMs=epoch)
            value['animationFence']['requestedEpochMs']=epoch;value['animation']['capturedEpochMs']=epoch
            value['animation']['clip']['evaluatedEpochMs']=epoch
            value['lifecycle'].update(launches=launches,activations=launches)
        boundary.mutate=mutate;reader=boundary.reader();reader.pid=pid;reader.clock_ms=native.epoch
        reader.monotonic=lambda:self.native.clock;reader.sleep=self.sleep;reader.guard=lambda:native.alive
        return boundary,reader
    def domains(self,native,pid,instance,handler,birth,epoch):
        boundary=ChatBoundary()
        def mutate(value):
            value.update(chatVersion=2,processId=pid,instance=instance,capturedEpochMs=native.epoch())
            value['source']['session']=dict(domainSessionVersion=1,instance=handler,revision=2,connected=True,
                domainSha256='4'*64,connectionBirth=birth,connectedEpochMs=epoch,mixerActive=True)
        boundary.mutate=mutate;reader=boundary.reader();reader.pid=pid;reader.clock_ms=native.epoch
        reader.monotonic=lambda:self.native.clock;reader.sleep=self.sleep;reader.guard=lambda:native.alive
        return boundary,PicoLifecycleDomain(reader,self.process.lock)
    def shutdown(self,restore=True):
        self.native.create();self.world.world_input();self.world.release()
        back=PicoLifecycleBack(self.native.sources()[0],self.session,self.transport.back_path,RUN,BINDING,lambda:self.native.alive,
            source_lock=self.world.lock,monotonic=lambda:self.native.clock,sleep=self.sleep)
        joined=PicoLifecycleXJoin(self.world,back,self.root/'lifecycle-x-join.json');joined.back_once()
        self.native.ui.shown=False;self.world.world_input();self.world.release()
        # Explicit normal navigation/physics source boundary. No restore ACK.
        self.joined=joined
        if restore:
            self.native.drive.source['feetPosition']=[1,2,3];self.native.drive.source['bodyPosition']=[1,3,3]
        self.process.prepare(joined,self.source,self.domain);self.process.prepare_inputs(self.source)
        self.joined=joined
    def new_process(self,inputs=True):
        if inputs:
            self.process.inputs.stop(lambda:dict(stopped=True))
            self.process.inputs.launch(lambda:dict(running=False,identity=None),lambda:dict(launched=True))
        self.sleep(.01);self.native.alive=False;self.new_native=Native();self.new_native.clock=self.native.clock
        epoch=self.new_native.epoch();axes=self.new_native.axes.source
        axes.update(createdEpochMs=epoch,frameEpochMs=epoch);axes['events'][0].update(occurredEpochMs=epoch)
        self.new_native.ui.mutate=lambda value:(value.update(processId=124,instance='5'*32),value['source']['keyboard'].update(instance='7'*32))
        self.new_native.axes.mutate=lambda value:value.update(processId=124,instance='6'*32)
        self.new_native.drive.mutate=lambda value:value.update(processId=124,instance='8'*32)
        readers=self.new_native.sources()
        for reader in readers:reader.pid=124;reader.source_lock=self.process.lock;reader.monotonic=lambda:self.native.clock;reader.sleep=self.sleep
        self.new_ui,self.new_axes,self.new_avatar=readers
        self.new_feature,self.new_source=self.features(self.new_native,124,'d'*32,2)
        self.presence_boundary=PresenceBoundary(pid=124,epoch_ms=self.new_native.epoch);self.presence_boundary.presence='absent'
        self.presence_boundary.edit=lambda value:value.update(instance='d'*32)
        self.presence=self.presence_boundary.reader();self.presence.monotonic=lambda:self.native.clock;self.presence.sleep=self.sleep
        self.new_domain_boundary,self.new_domain=self.domains(self.new_native,124,'e'*32,'f'*32,'c'*32,epoch)
    def observe(self,binding=NEW_BINDING):
        return self.process.observe(binding,self.new_source,self.presence,self.new_domain,self.new_ui,self.new_axes,self.new_avatar)
    def test_original_process_death_new_birth_domain_and_restored_baseline_retire_only_process_scopes(self):
        self.shutdown();self.new_process();started=self.native.clock;result=self.observe()
        self.assertTrue(result['processOwnedScopesRetired']);self.assertEqual(2,result['worldAttempts'])
        self.assertEqual((123,124),(result['originalProcessId'],result['currentProcessId']))
        self.assertTrue(self.joined.back.state['frames']);self.assertTrue(self.joined.back.state['phase']=='retained')
        self.assertTrue(all(owner.read() is not None for owner in self.process.owners));self.assertTrue(result['journalsRetained'])
        self.assertEqual('process-retired',self.process.state['phase'])
        self.assertGreaterEqual(self.native.clock-started,3)
        restored=PicoLifecycleProcessRetirement(self.process.store.path,RUN,self.session.profile,lambda:self.installed,
            self.process.lock,monotonic=lambda:self.native.clock,sleep=self.sleep)
        self.assertEqual(self.process.state,restored.state);self.assertFalse(self.native.alive)
    def test_stop_and_launch_acknowledgments_without_original_esrch_do_not_retire_scopes(self):
        self.shutdown();self.new_process();self.presence_boundary.presence='present'
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase']);self.assertTrue(all(owner.read() for owner in self.process.owners))
    def test_permission_unknown_reused_pid_and_unadvanced_original_birth_fail_closed(self):
        self.shutdown();self.new_process();self.presence_boundary.presence='unknown'
        with self.assertRaises(NativeUIError):self.observe()
        self.presence_boundary.presence='absent'
        for wrong in (NEW_BINDING|dict(processIdentity='123:500'),NEW_BINDING|dict(processIdentity='124:300'),NEW_BINDING|dict(sessionId=BINDING['sessionId'])):
            with self.subTest(wrong=wrong),self.assertRaises(NativeUIError):self.observe(wrong)
        self.assertEqual('prepared',self.process.state['phase'])
    def test_native_actual_settings_pose_and_new_source_lifetimes_cannot_be_requested_into_restore(self):
        self.shutdown();self.new_process();self.new_native.drive.source['feetPosition'][0]+=.1
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase'])
    def test_actual_domain_change_or_unobserved_reconnect_does_not_restore_original_domain(self):
        self.shutdown();self.new_process();original=self.new_domain_boundary.mutate
        def foreign(value):original(value);value['source']['session']['domainSha256']='0'*64
        self.new_domain_boundary.mutate=foreign
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase'])
    def test_shutdown_requires_actual_original_position_and_three_second_restored_quiet(self):
        with self.assertRaises(NativeUIError):self.shutdown(restore=False)
        self.assertEqual('begun',self.process.state['phase']);self.assertIsNone(self.process.inputs.store.read())
        self.assertEqual(3,len(self.transport.envelopes));self.assertTrue(all(owner.read() for owner in self.process.owners))
    def test_fresh_stop_guard_rejects_frozen_device_clock_and_delayed_stop(self):
        self.shutdown();self.source.clock_ms=lambda:self.process.state['shutdown']['native']['capturedEpochMs']
        self.sleep(2)
        with self.process.lock.held(),self.assertRaises(NativeUIError):self.process.require_stop_ready(self.source)
        self.assertEqual('prepared',self.process.inputs.read()['phase'])
    def test_final_device_clock_jump_during_guard_with_frozen_host_clock_prevents_stop(self):
        self.shutdown();epoch=[self.source.clock_ms()];self.source.clock_ms=lambda:epoch[0]
        original=self.source.guard
        def jump():
            okay=original();epoch[0]+=2000;return okay
        self.source.guard=jump;host=self.native.clock
        with self.process.lock.held(),self.assertRaises(NativeUIError):self.process.require_stop_ready(self.source)
        self.assertEqual(host,self.native.clock);self.assertEqual('prepared',self.process.inputs.read()['phase'])
    def test_same_original_source_and_changed_settings_cannot_be_new_process_baseline(self):
        self.shutdown();self.new_process();original=self.new_feature.mutate
        def changed(value):original(value);value['audio']['muted']=not self.process.state['originalNative']['audio']['muted']
        self.new_feature.mutate=changed
        with self.assertRaises(NativeUIError):self.observe()
        self.new_feature.mutate=original;original_ui=self.new_native.ui.mutate
        def reused(value):original_ui(value);value['instance']=self.native.ui.value['instance']
        self.new_native.ui.mutate=reused
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase'])
    def test_original_journal_change_is_not_retired_after_actual_new_process_absence(self):
        self.shutdown();self.new_process();owner=self.process.owners[2];value=owner.read();owner.write(value|dict(unexpected=True),value)
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase']);self.assertTrue(owner.read()['unexpected'])
    def test_final_source_guard_processing_delay_is_unavailable(self):
        self.shutdown();self.new_process();original=self.presence.guard;triggered=[]
        def delayed():
            result=original()
            if not triggered:triggered.append(True);self.sleep(2)
            return result
        self.presence.guard=delayed
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase'])
    def test_new_domain_connection_history_cannot_change_during_baseline_quiet(self):
        self.shutdown();self.new_process();original=self.new_domain_boundary.mutate;count=[]
        def reconnect(value):
            original(value);count.append(True)
            if len(count)>1:value['source']['session']['revision']+=2
        self.new_domain_boundary.mutate=reconnect
        with self.assertRaises(NativeUIError):self.observe()
        self.assertEqual('prepared',self.process.state['phase'])
    def run_restart(self,stop,launch):
        return run_lifecycle_restart(self.process,lambda:self.process.prepare(self.joined,self.source,self.domain),
            lambda:self.source,stop,lambda:dict(running=False,identity=None),launch,
            lambda:self.assertEqual('launch-issued',self.process.inputs.read()['phase']),self.observe)
    def test_uncertain_stop_is_not_resent_and_existing_inputs_own_recovery(self):
        self.shutdown();calls=[]
        def stop():calls.append('stop');raise RuntimeError('Explicit lost stop receipt')
        def launch():calls.append('launch');self.new_process(inputs=False);return dict(launched=True)
        with self.assertRaises(NativeUIError):self.run_restart(stop,launch)
        self.assertEqual('stop-issued',self.process.inputs.read()['phase'])
        result=self.run_restart(stop,launch);self.assertTrue(result['processOwnedScopesRetired'])
        self.assertEqual(['stop','launch'],calls)
    def test_uncertain_launch_is_not_resent_and_only_original_readers_reconcile(self):
        self.shutdown();calls=[]
        def stop():calls.append('stop');return dict(stopped=True)
        def launch():calls.append('launch');self.new_process(inputs=False);raise RuntimeError('Explicit lost launch receipt')
        with self.assertRaises(NativeUIError):self.run_restart(stop,launch)
        self.assertEqual('launch-issued',self.process.inputs.read()['phase'])
        result=self.run_restart(stop,launch);self.assertTrue(result['processOwnedScopesRetired'])
        self.assertEqual(['stop','launch'],calls)
        self.assertTrue(self.run_restart(stop,launch)['processOwnedScopesRetired'])
        self.assertEqual(['stop','launch'],calls)


if __name__=='__main__':unittest.main()
