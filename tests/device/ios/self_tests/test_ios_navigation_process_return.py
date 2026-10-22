"""Real new-process return journals/HTTP/normal inputs; app and SDK modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import time
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters import normal_input
from ios.adapters.navigation_process_return import NavigationProcessReturn
from ios.self_tests.test_ios_navigation_process_scope import NavigationProcessScopeTests
from ios.self_tests.test_ios_navigation_world_measurements import global_packet
from navigation_observation import viewpoint_urls


class NavigationProcessReturnTests(unittest.TestCase):
    def setUp(self):
        self.h=NavigationProcessScopeTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.h.proof.fixture.provider.clock_ms=lambda:int(self.h.h.epoch())
        self.h.h.fixture.epoch_ms=lambda:int(self.h.h.epoch())
        with self.h.held():
            self.scope=self.h.scope();self.b,self.native=self.h.sdk(self.scope)
            basis=self.scope.archive();floor=basis['originals']['ui'];epoch=floor['sampleEpochMs']
            self.b.scene=basis['providerInputs']['sceneUrl'];self.b.current=basis['originals']['navigation']['source']['sceneUrl']
            self.scope.sources['ui']=self.native
            # The modeled SDK retains original scene import/tree history and
            # emits fresh read packets. No production validator rewrites it.
            for ordinal,name in enumerate(('inventory','navigation')):
                packet=deepcopy(basis['originals'][name]);start=epoch+11+ordinal*2
                delta=start-packet['clockBefore']['epochMs'];packet['sequence']+=1;packet['requestId']='ios-'+uuid.uuid4().hex
                for key in ('epochMs','monotonicMs'):
                    packet['clockBefore'][key]+=delta;packet['clockAfter'][key]+=delta
                load=packet['source']['sceneLoads'];load['sequence']+=2;load['commandId']=packet['requestId']
                load['capturedEpochMs']=packet['clockAfter']['epochMs']
                def read(_run,packet=packet):
                    self.h.h.advance(packet['clockAfter']['epochMs']);return deepcopy(packet)
                self.scope.sources[name].read=read
            prior=self.scope.archive()['clockJoin']['nativeAfter'];packets=[]
            for sequence,stamp in ((prior['sequence']+1,epoch+10),(prior['sequence']+2,epoch+101)):
                value=global_packet(stamp,sequence);value.update(processId=43,instance=prior['instance'],lifecycle=deepcopy(prior['lifecycle']))
                packets.append(value)
            self.scope.native.values=packets
        self.http=patch.object(normal_input,'urlopen',self.b.post);self.http.start();self.addCleanup(self.http.stop)
        # Advance an independent modeled host if setup was expensive. Never
        # regress the same provider clock after its earlier real HTTP reply.
        # Original native DTOs and their epochs remain unchanged.
        self.h.h.host=max(self.h.h.host,time.time()*1000-self.h.h.ms)
    def owner(self):
        return NavigationProcessReturn(PrivateFeatureState(self.scope.store.path.with_name('ios-navigation-process-return-43.json')),
            self.scope,self.b.ui,self.native,epoch_ms=self.h.h.epoch,monotonic=self.h.h.mono)

    def test_new_process_ordinary_return_uses_unchanged_old_static_baseline_and_its_own_root(self):
        with self.h.held():
            initial=self.scope.original_admission();context=deepcopy(self.scope.owner.store.read())
            owner=self.owner();self.assertEqual({'performed':True},owner.return_to_original())
            self.assertEqual(viewpoint_urls(initial['base']['url'])['A'],self.b.current)
            self.assertEqual('delivered',owner.state['phase']);self.assertNotIn('restored',owner.state)
            self.assertEqual('43',owner.binding['processIdentity']);self.assertEqual('42',initial['binding']['processIdentity'])
            self.assertFalse(unpack(owner.state['addressOwner']['payload'])[0]['rows'][-1]['closed']['drained'])
            calls=list(self.b.calls);self.assertEqual({'performed':True},self.owner().return_to_original());self.assertEqual(calls,self.b.calls)
            self.assertEqual(initial,self.scope.original_admission());self.assertEqual(context,self.scope.owner.store.read())

    def test_foreign_or_reused_scene_sources_refuse_before_any_normal_input(self):
        with self.h.held():
            reader=self.scope.sources['navigation'];original=reader.read
            def foreign(run):
                value=original(run);value['source']['sceneUrl']='hifi://foreign-world';return value
            reader.read=foreign;owner=self.owner()
            with self.assertRaises((NativeUIError,ValueError)):owner.return_to_original()
            self.assertEqual([],self.b.inputs);self.assertEqual('checking',self.owner().state['phase'])
            before=list(self.h.h.reads)
            with self.assertRaises(NativeUIError):self.owner().return_to_original()
            self.assertEqual(before,self.h.h.reads)

    def test_changed_unowned_camera_mode_refuses_before_replacing_the_owned_world(self):
        with self.h.held():
            reader=self.scope.sources['navigation'];original=reader.read
            def changed(run):
                value=original(run);value['source']['view']['mode']='third person';return value
            reader.read=changed
            with self.assertRaises(NativeUIError):self.owner().return_to_original()
            self.assertEqual([],self.b.inputs)

    def test_lost_middle_source_keeps_exact_prefix_and_never_reacquires_or_sends(self):
        with self.h.held():
            self.scope.sources['navigation'].read=lambda _run:(_ for _ in ()).throw(OSError('Synthetic source loss'))
            owner=self.owner()
            with self.assertRaises(OSError):owner.return_to_original()
            rebuilt=self.owner();self.assertEqual({'inventory'},set(rebuilt.state['gate']['originals']))
            before=deepcopy(rebuilt.store.read());reads=list(self.h.h.reads)
            with self.assertRaises(NativeUIError):rebuilt.return_to_original()
            with self.assertRaises(NativeUIError):rebuilt.recover_return()
            self.assertEqual(before,rebuilt.store.read());self.assertEqual(reads,self.h.h.reads);self.assertEqual([],self.b.inputs)

    def test_slow_issued_journal_cannot_deliver_an_expired_scene_gate(self):
        with self.h.held():
            owner=self.owner();write=owner.store.write
            def slow(value,previous):
                result=write(value,previous)
                if unpack(value['payload'])[0]['phase']=='issued':self.h.h.ms+=2000
                return result
            owner.store.write=slow
            with self.assertRaises(NativeUIError):owner.return_to_original()
            self.assertEqual([],self.b.inputs);self.assertEqual('issued',self.owner().state['phase'])
            self.assertIsNone(owner.address().read())

    def test_ignored_return_delivery_does_not_supply_restoration_or_cleanup(self):
        with self.h.held():
            before=self.b.current;self.b.mutation='goto-ignored';owner=self.owner()
            self.assertEqual({'performed':True},owner.return_to_original());self.assertEqual(before,self.b.current)
            self.assertNotIn('restored',owner.state);self.assertNotIn('cleaned',owner.state)
            self.assertFalse(unpack(owner.state['addressOwner']['payload'])[0]['rows'][-1]['closed']['drained'])

    def test_lost_final_parent_return_adopts_actual_child_original_without_read_or_replay(self):
        with self.h.held():
            owner=self.owner();write=owner.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='delivered':raise OSError('Synthetic parent result loss')
                return write(value,previous)
            owner.store.write=lost
            with self.assertRaises(OSError):owner.return_to_original()
            rebuilt=self.owner();self.assertEqual('issued',rebuilt.state['phase']);before=list(self.b.calls)
            self.b.call=lambda *_args,**_kwargs:self.fail('Historical recovery called SDK')
            self.assertEqual({'performed':True},rebuilt.recover_return());self.assertEqual(before,self.b.calls)
            self.assertEqual('delivered',self.owner().state['phase'])

    def test_lost_native_input_return_stays_issued_without_adopting_an_incomplete_child(self):
        with self.h.held():
            native=self.native.deliver
            def lost(command):native(command);raise OSError('Synthetic original native return loss')
            self.native.deliver=lost;owner=self.owner()
            with self.assertRaises(OSError):owner.return_to_original()
            rebuilt=self.owner();calls=list(self.b.calls)
            with self.assertRaises(NativeUIError):rebuilt.recover_return()
            with self.assertRaises(NativeUIError):rebuilt.return_to_original()
            self.assertEqual(calls,self.b.calls);self.assertNotIn('PhoneAddressGoButton',self.b.inputs)


if __name__=='__main__':unittest.main()
