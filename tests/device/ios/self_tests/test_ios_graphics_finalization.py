"""Paired Graphics teardown on original host files and synthetic native/OS SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from contextlib import ExitStack

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.graphics_finalization import IOSGraphicsFinalization
from ios.self_tests.test_ios_graphics_feature import FeatureHarness
from ios.self_tests.test_ios_retired_process import Boundary,SOURCE
from ios.self_tests.test_ios_graphics_scene import RUN
from ios.self_tests import test_ios_graphics_restart_barrier as barriers
from ios.adapters.graphics_fixture import GraphicsPhasePending
from self_tests.test_completed_frame_lease import BINDING
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION


class FinalizationHarness(FeatureHarness):
    planned=barriers.RestartBarrierTests.planned
    primary_join=barriers.RestartBarrierTests.primary_join
    restarting=barriers.RestartBarrierTests.restarting
    def setUp(self):
        super().setUp();self.os=Boundary();self.base._operation=None;self.bound_pid=self.sdk.pid
        scope={k:v for k,v in BINDING.items() if k!='processIdentity'}
        session=dict(sessionId=BINDING['sessionId'],generation=BINDING['generation'],targetFingerprint=BINDING['targetFingerprint'])
        self.base.read_session=lambda _:deepcopy(session);self.base._scope=lambda *_:deepcopy(scope)
        case=self
        class Gate:
            def record(self):
                return dict(phase=case.binding_phase,scope=deepcopy(scope),source=deepcopy(SOURCE),
                    process=dict(pid=case.sdk.pid if case.binding_phase=='bound' else case.bound_pid))
            def process_source(self):return deepcopy(SOURCE)
            def verify(self):
                need(case.binding_phase=='bound' and case.sdk.running and case.sdk.foreground)
                case.bound_pid=case.sdk.pid;case.os.pid=case.sdk.pid;case.os.anchor['pid']=case.sdk.pid
                case.os.anchor['bundlePids']=[case.sdk.pid]*2
                return dict(installedCandidateVerified=True)
            def continuity(self):need(case.binding_phase=='bound');return case.sdk.process()
            def finish_retirement(self):need(not case.sdk.running and case.binding_phase=='retiring');case.binding_phase='retired'
            def retired_absence(self):need(not case.sdk.running and case.binding_phase=='retired')
        self.base._binding=lambda *_:Gate()
        def execute(_session,operation,query):
            need(operation=='mobile: overteRetiredProcessInfo')
            case.os.clock=case.sdk.clock
            case.os.states=[4 if case.sdk.foreground else 3 if case.sdk.running else 1]*2
            case.os.pids=[case.sdk.pid if case.sdk.running else 0]*2
            case.os.running=[case.sdk.running and case.sdk.pid==case.os.pid]*2
            value=case.os.send(query);case.sdk.clock=case.os.clock;return value
        self.bridge._existing=lambda _:(SimpleNamespace(execute=execute),session['sessionId'],deepcopy(session),self.sdk.target,deepcopy(scope))
        original_reader=self.bridge._retired_process_observer
        def os_reader(*args):
            value=original_reader(*args);value.epoch_ms=self.sdk.host_epoch;value.monotonic=lambda:self.sdk.clock;return value
        self.bridge._retired_process_observer=os_reader
        for name in ('_graphics_final_source','_graphics_final_stop','_graphics_final_stopped','_graphics_process_retirement'):
            setattr(self.adapter,name,getattr(self.bridge,name))
        self.adapter._retired_process_observer=self.bridge._retired_process_observer
        source=self.gpu.source
        def world(packet):
            source(packet)
            if 'renderTrace' in packet.get('source',{}):
                current=self.sdk.subject_reader().read(RUN,require_avatar=True,require_camera=True)['source']['view']
                packet['source']['renderTrace']['recordedView'].update({k:deepcopy(current[k]) for k in ('position','rotation','fieldOfViewDegrees','aspectRatio')})
        self.gpu.source=world

    def finalizer(self,role='primary'):return IOSGraphicsFinalization(self.feature(role))

    def restored_roles(self,*,held=None):
        self.baseline()
        if held is not None:self.webs[self.sdk.pid].held=held
        self.client.close()
        self.assertFalse(self.finalizer().step());self.assertTrue(self.sdk.running)
        self.assertFalse(self.finalizer('actor').step());self.assertTrue(self.sdk.running)

    def finish_roles(self):
        for _ in range(8):
            self.sdk.clock+=1.1;self.finalizer('actor').step()
            if self.finalizer().step():return self.finalizer()
        self.fail('Original paired process quiet windows did not complete')

    def no_live_sources(self):
        stack=ExitStack()
        for name in ('normal_feature_runtime','_native_feature_observer','_graphics_subject_observer','_scene_load_observer',
                     '_web_closure_observer','_graphics_ui_source','_script_file_io','_vulkan_world_frame_owner'):
            stack.enter_context(patch.object(self.adapter,name,side_effect=AssertionError('No foreground/native source after process exit')))
        return stack


class GraphicsFinalizationTests(FinalizationHarness,unittest.TestCase):
    def test_both_roles_restore_original_world_and_images_before_one_normal_stop_and_os_queries(self):
        self.restored_roles();primary=self.finalizer()
        with primary.lock.held():
            state=primary.read();self.assertEqual('restored',state['phase'])
            frames=[primary.validate_role(role) for role in ('primary','actor')]
            self.assertNotEqual(frames[0]['capture']['requestId'],frames[1]['capture']['requestId'])
            self.assertEqual([4.,0.,2.],frames[1]['subjectAfter']['source']['avatarPose']['feetPosition'])
            self.assertEqual([],self.inputs);self.assertEqual([],self.os.queries)
        self.assertFalse(self.finalizer().step());self.assertEqual(['app.stop'],self.inputs);self.assertFalse(self.sdk.running)
        self.assertEqual(1,len(self.os.queries));self.assertIsNotNone(primary.store.read())
        # Foreground/native factories must never be used once the process died.
        with patch.object(self.adapter,'normal_feature_runtime',side_effect=AssertionError('No native runtime after stop')):
            finished=False
            for _ in range(6):
                self.sdk.clock+=1.1;self.finalizer('actor').step();finished=self.finalizer().step()
                if finished:break
            self.assertTrue(finished)
        receipt=primary.receipt_store().read();self.assertIsNotNone(receipt)
        with primary.lock.held():
            plan=primary.validate_receipt(receipt);copies=primary.manifest(plan['items'])
        for role in ('primary','actor'):
            value=copies['ios-graphics-'+role+'-0-process-retirement.json'];state=unpack(value['payload'])[0]
            self.assertTrue(state['windows'][-1]['complete']);self.assertGreaterEqual(state['windows'][-1]['elapsedMs'],3000)
        self.assertFalse(list(self.root.glob('ios-graphics-*.json')))
        self.assertFalse(list(self.root.glob('graphics-world-frame-*.json')))
        self.assertTrue(self.finalizer('actor').step());self.assertTrue(self.finalizer().step())
        self.assertEqual(['app.stop'],self.inputs)

    def test_cached_software_image_keeps_its_nonzero_pre_exit_count_in_the_final_archive(self):
        self.restored_roles(held='offscreen-image');self.finalizer().step()
        with self.no_live_sources():owner=self.finish_roles()
        with owner.lock.held():
            plan=owner.validate_receipt(owner.receipt_store().read());copies=owner.manifest(plan['items'])
        for role in ('primary','actor'):
            value=copies['ios-graphics-'+role+'-0-lifetime.json'];state=unpack(value['payload'])[0]
            ref=state['records'][-1];row=unpack(copies['ios-graphics-'+role+'-0-lifetime-'+str(ref['ordinal'])+'.json']['payload'])[0]
            self.assertEqual('held',row['mode']);self.assertEqual(42,row['web']['processId'])
            self.assertEqual(1,row['web']['contexts'][0]['resources']['offscreen-image']['pending'])
            self.assertFalse(state['windows'][-1]['complete'])

    def test_lost_stop_return_recovers_actual_os_absence_without_any_second_stop_or_native_query(self):
        self.restored_roles();self.fault='lost-stop'
        with self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertFalse(self.sdk.running);self.assertEqual('retiring',self.binding_phase);self.fault=''
        with self.no_live_sources(),patch.object(self.base,'invoke',side_effect=AssertionError('No stop/launch replay')):self.finish_roles()
        self.assertEqual(['app.stop'],self.inputs);self.assertEqual('retired',self.binding_phase)

    def test_ignored_stop_remains_owned_without_another_terminate_or_a_green_cleanup(self):
        self.restored_roles();self.fault='ignored-stop'
        with self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertTrue(self.sdk.running)
        with self.no_live_sources():
            for _ in range(4):
                self.sdk.clock+=1.1;self.assertFalse(self.finalizer('actor').step());self.assertFalse(self.finalizer().step())
        self.assertEqual(['app.stop'],self.inputs);self.assertIsNone(self.finalizer().receipt_store().read())
        self.assertTrue(list(self.root.glob('ios-graphics-*.json')))

    def test_stop_ack_with_a_still_present_numeric_pid_cannot_replace_original_os_absence(self):
        self.restored_roles()
        def ack(_selector,*,source_lock):
            source_lock.assert_held();self.inputs.append('app.stop');self.binding_phase='retiring';return dict(stopped=True)
        with patch.object(self.adapter,'_graphics_final_stop',side_effect=ack):self.assertFalse(self.finalizer().step())
        self.assertTrue(self.sdk.running)
        with self.no_live_sources():
            for _ in range(4):
                self.sdk.clock+=1.1;self.assertFalse(self.finalizer('actor').step());self.assertFalse(self.finalizer().step())
        self.assertEqual(['app.stop'],self.inputs);self.assertIsNone(self.finalizer().receipt_store().read())

    def test_foreign_actor_original_with_a_valid_recomputed_hash_still_prevents_stop(self):
        self.restored_roles();owner=self.finalizer()
        with owner.lock.held():
            state=owner.read();ref=state['roles']['actor']['frame'];changed=owner.load(ref);changed['role']='primary'
            state['roles']['actor']['frame']=owner.retain('actor-restored-frame',changed);owner.save()
        with self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertEqual([],self.inputs);self.assertTrue(self.sdk.running)

    def test_replaced_original_png_prevents_stop_even_with_unmodified_native_flags(self):
        self.restored_roles();owner=self.finalizer()
        with owner.lock.held():owner.read();frame=owner.validate_role('actor')
        (owner.root/frame['owner']['name']).write_bytes(b'Changed original PNG')
        with self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertEqual([],self.inputs);self.assertEqual([],self.os.queries)

    def test_unindexed_runtime_responsibility_is_rejected_before_stop(self):
        self.restored_roles();store=PrivateFeatureState(self.root/'ios-graphics-unindexed.json');store.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertEqual([],self.inputs);self.assertEqual(dict(unknown=True),store.read())

    def test_partial_metadata_removal_adopts_original_archives_without_replaying_stop(self):
        self.restored_roles();self.finalizer().step();discard=PrivateFeatureState.discard;failed=[False]
        def lost(store,value):
            discard(store,value)
            if store.path.name=='ios-graphics-primary-0-samples.json' and not failed[0]:
                failed[0]=True;raise OSError('Synthetic lost committed metadata-removal return')
        with self.no_live_sources(),patch.object(PrivateFeatureState,'discard',new=lost),self.assertRaises(NativeUIError):self.finish_roles()
        self.assertTrue(failed[0]);self.assertFalse((self.root/'ios-graphics-primary-0-samples.json').exists())
        owner=self.finalizer()
        with owner.lock.held():self.assertEqual('retiring',owner.read()['phase'])
        with self.no_live_sources(),patch.object(self.base,'invoke',side_effect=AssertionError('No stop replay')):
            self.assertTrue(self.finalizer().step())
        self.assertEqual(['app.stop'],self.inputs);self.assertIsNotNone(owner.receipt_store().read())

    def test_changed_candidate_scope_prevents_final_source_admission_and_stop(self):
        self.baseline();self.client.close();existing=self.bridge._existing
        def foreign(selector):
            parts=list(existing(selector));parts[4]=dict(parts[4],artifactSha256='f'*64);return tuple(parts)
        with patch.object(self.bridge,'_existing',side_effect=foreign),self.assertRaises(NativeUIError):self.finalizer().step()
        self.assertEqual([],self.inputs);self.assertEqual([],self.os.queries)

    def test_manifest_pages_keep_originals_external_to_the_bounded_parent_payload(self):
        from adapters.script_feature.history import pack
        owner=self.finalizer();copies={'ios-graphics-page-'+str(n)+'.json':dict(sequence=n,data='x'*1024) for n in range(130)}
        with owner.lock.held():
            pages=owner.freeze(copies);self.assertEqual(3,len(pages));self.assertEqual(copies,owner.manifest(pages))
            self.assertLess(len(pack([dict(items=pages)])),4096)

    def test_archive_serialization_cannot_turn_an_aged_process_pair_into_permission_to_remove_metadata(self):
        self.restored_roles();self.finalizer().step();freeze=IOSGraphicsFinalization.freeze;aged=[False]
        def slow(owner,copies):
            result=freeze(owner,copies)
            if not aged[0] and any('-process-retirement.json' in name for name in copies):
                self.sdk.clock+=2;aged[0]=True
            return result
        with self.no_live_sources(),patch.object(IOSGraphicsFinalization,'freeze',new=slow):
            for _ in range(8):
                self.sdk.clock+=1.1;self.finalizer('actor').step();self.assertFalse(self.finalizer().step())
                if aged[0]:break
        self.assertTrue(aged[0]);owner=self.finalizer()
        self.assertTrue((self.root/'ios-graphics-primary-0-samples.json').exists())
        self.assertIsNone(owner.receipt_store().read())
        with owner.lock.held():self.assertEqual('stopped',owner.read()['phase'])
        queries=len(self.os.queries)
        with self.no_live_sources():self.finish_roles()
        self.assertGreater(len(self.os.queries),queries);self.assertEqual(['app.stop'],self.inputs)

    def test_failed_owner_intent_before_any_capture_is_preserved_as_unallocated_failure_through_finalization(self):
        self.baseline();call=self.activate('open');self.feature().act(call);write=PrivateFeatureState.write
        count=sum(q['operation']=='read' for q in self.gpu.commands)
        def failed(store,value,previous):
            if store.path.name.startswith('graphics-world-frame-primary-') and value.get('phase')=='planned':
                raise OSError('Synthetic owner intent rejected before any native capture')
            return write(store,value,previous)
        with patch.object(PrivateFeatureState,'write',new=failed),self.assertRaises(NativeUIError):self.feature().observe(
            dict(contractVersion=CONTRACT_VERSION,runId=RUN,afterSequence=0))
        self.assertEqual(count,sum(q['operation']=='read' for q in self.gpu.commands));self.client.close()
        self.finalizer().step();self.finalizer('actor').step();self.finalizer().step()
        with self.no_live_sources():owner=self.finish_roles()
        with owner.lock.held():plan=owner.validate_receipt(owner.receipt_store().read());copies=owner.manifest(plan['items'])
        index=unpack(copies['ios-graphics-primary-0-samples.json']['payload'])[0]
        row=index['owners'][-1];self.assertEqual('abandoned',row['phase'])
        value=copies['ios-graphics-primary-0-'+row['requestId'][4:]+'-sample.json'];original=unpack(value['payload'])[0]
        self.assertIsNone(original['capture']);self.assertIsNone(original['retirement'])
        self.assertFalse(original['provider']['active']);self.assertEqual(['app.stop'],self.inputs)

    def test_stage_one_finalization_keeps_old_world_and_native_lifetimes_under_their_original_pids(self):
        call,primary=self.restarting()
        with primary.lock.held():self.assertFalse(primary.progress_rejoined(primary.control()))
        with self.assertRaises(GraphicsPhasePending):self.feature('actor').publish()
        self.feature().act(call);self.assertEqual(43,self.sdk.pid);self.client.close()
        self.finalizer().step();self.finalizer('actor').step();self.finalizer().step()
        with self.no_live_sources():owner=self.finish_roles()
        with owner.lock.held():plan=owner.validate_receipt(owner.receipt_store().read());copies=owner.manifest(plan['items'])
        self.assertEqual(1,plan['stage']);self.assertEqual('43',plan['binding']['processIdentity'])
        for role in ('primary','actor'):
            old=unpack(copies['ios-graphics-'+role+'-0-lifetime.json']['payload'])[0]
            new=unpack(copies['ios-graphics-'+role+'-1-lifetime.json']['payload'])[0]
            self.assertEqual('42',old['binding']['processIdentity']);self.assertEqual('43',new['binding']['processIdentity'])
            self.assertEqual(42,new['original']['subject']['processId'])
            process=unpack(copies['ios-graphics-'+role+'-1-process-retirement.json']['payload'])[0]
            self.assertTrue(process['windows'][-1]['complete'])
        self.assertEqual(['app.stop','app.launch','app.stop'],self.inputs)

    def test_missing_actor_role_never_authorizes_stop_or_os_absence_queries(self):
        self.baseline();self.client.close()
        self.finalizer().step();self.finalizer().step()
        self.assertEqual([],self.inputs);self.assertEqual([],self.os.queries);self.assertTrue(self.sdk.running)

    def test_retirement_intent_prevents_public_input_from_racing_final_world_restoration(self):
        self.baseline();call=self.activate('open');self.client.close();self.finalizer().step();before=list(self.sdk.model.actions)
        with self.assertRaises(NativeUIError):self.feature().act(call)
        self.assertEqual(before,self.sdk.model.actions);self.assertEqual([],self.inputs)


if __name__=='__main__':unittest.main()
