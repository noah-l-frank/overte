"""Real role SDK locks, original Node marker VMs and typed preparation cues.

Marker/native/SDK producers are explicit host models. No iOS/device/native
execution, acoustic evidence or complete Avatar qualification is established.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile,threading,unittest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_feature import IOSAvatarFeature,AvatarFeaturePending
from ios.adapters.emote_marker_files import originals
from ios.self_tests import emote_marker_domain_fixture as marker_native
from ios.self_tests.avatar_image_domain import role_marker_program
from ios.self_tests.test_ios_avatar_actor_input_cue import AvatarActorInputCueTests
from ios.self_tests.test_ios_avatar_feature import AvatarFeatureLocksTests
from feature_journeys.contract import VERSION


class MarkerPreparationBoundary:
    """Explicit once-issued preparation input model on actual owner files."""
    def __init__(self,owner,barrier=None):
        self.owner,self.barrier=owner,barrier;self.state=dict(webAdmission=None);self.inputs=0;self.admissions=0
        self.store=PrivateFeatureState(owner.store.path.parent/'declared-marker-intent.json')
    def prepare(self):
        self.owner.lock.assert_held();previous=self.store.read();need(previous is None)
        self.store.write(dict(declaredMarkerInputVersion=1,phase='issued'),None);self.inputs+=1
        if self.barrier is not None:self.barrier.wait(timeout=3)
    def admit_rendered(self):
        self.owner.lock.assert_held();self.admissions+=1;self.state['webAdmission']=1


class AvatarOwnMarkerPreparationTests(unittest.TestCase):
    def setUp(self):
        self.f=AvatarFeatureLocksTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.models=[]
    def owner(self,role,barrier=None):
        owner=self.f.owner(role);owner.state=dict(phase='preparing',initialBarrier=dict(original='declared-immutable-both-images'))
        store=PrivateFeatureState(owner.store.path.parent/'declared-preparation-state.json');store.write(deepcopy(owner.state),None)
        owner.load=lambda:setattr(owner,'state',store.read())
        def save():store.write(deepcopy(owner.state),store.read())
        owner.save=save;owner.initial_original=lambda:dict(declaredOriginal='unchanged')
        boundary=MarkerPreparationBoundary(owner,barrier);owner.marker_scope=lambda:boundary
        @contextmanager
        def existing(_selector):yield
        owner.runtime.existing_input_session=existing;self.models.append(boundary);return owner
    def test_actual_both_role_locks_allow_independent_marker_preparation_concurrently(self):
        barrier=threading.Barrier(2);owners=[self.owner(role,barrier) for role in ('primary','actor')];errors=[]
        def run(owner):
            try:owner.prepare_marker()
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=run,args=(owner,),name='avatar-own-marker-'+owner.role) for owner in owners]
        for worker in workers:worker.start()
        for worker in workers:worker.join(timeout=5)
        self.assertTrue(all(not worker.is_alive() for worker in workers));self.assertEqual([],errors)
        self.assertEqual(['ready','ready'],[owner.state['phase'] for owner in owners])
        self.assertEqual([1,1],[boundary.inputs for boundary in self.models]);self.assertEqual([1,1],[boundary.admissions for boundary in self.models])
    def test_saved_ready_role_never_repeats_marker_input_or_render_admission(self):
        owner=self.owner('actor');owner.prepare_marker();before=self.models[0].store.read();owner.prepare_marker()
        self.assertEqual(1,self.models[0].inputs);self.assertEqual(1,self.models[0].admissions);self.assertEqual(before,self.models[0].store.read())
    def test_missing_immutable_initial_barrier_refuses_before_marker_source_or_input(self):
        owner=self.owner('primary');owner.state['initialBarrier']=None;owner.save()
        with self.assertRaises(NativeUIError):owner.prepare_marker()
        self.assertEqual(0,self.models[0].inputs);self.assertIsNone(self.models[0].store.read())


class AvatarActorBaselineReadyTests(unittest.TestCase):
    def setUp(self):
        self.f=AvatarActorInputCueTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.current['verb']='baseline';self.f.current['inputs']={};self.f.primary_state['lastCall']=None
    def test_preparing_primary_baseline_releases_pair_without_current_queries_then_ready_admits(self):
        f=self.f;f.primary_state['phase']='preparing';f.save_primary();events=[]
        f.actor.prepare=lambda *,components=True:events.append('prepared-own-role')
        f.actor.source_parts=lambda:self.fail('Preparing Primary cannot admit current paired Source queries')
        with self.assertRaises(AvatarFeaturePending):f.actor.observe(dict(contractVersion=VERSION,runId=f.actor.run,afterSequence=0))
        self.assertEqual(['prepared-own-role'],events)
        # Fresh independent instances acquire both exact SDK lock inodes after
        # the public pending exception: no wait occurs under the paired scope.
        for role in ('primary','actor'):
            with self.f.f.owner(role).held(paired=True):pass
        f.primary_state['phase']='ready';f.save_primary();self.assertTrue(f.ready())
    def test_missing_primary_owner_cannot_admit_baseline_current_capture(self):
        self.f.primary.store.path.unlink();self.assertFalse(self.f.ready())
    def test_ready_foreign_binding_cannot_become_baseline_readiness(self):
        self.f.primary_state['phase']='ready';self.f.primary_state['bindings']['primary']['generation']+=1;self.f.save_primary()
        with self.assertRaises(NativeUIError):self.f.ready()


class AvatarParallelOriginalMarkerVMTests(unittest.TestCase):
    def test_two_actual_original_node_markers_keep_instance_program_positions_and_module_default(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);root=Path(directory.name);root.chmod(0o700)
        base=marker_native.PROGRAM;domains={};barrier=threading.Barrier(2);errors=[]
        for role,position in (('primary',[0,0,4]),('actor',[1.5,0,4])):
            child=root/role;child.mkdir(mode=0o700);(child/'script-bundle').mkdir(mode=0o700)
            files=originals('1'*32,'https://controlled.invalid/feature-fixture/v1/runs/'+('1'*32)+'/', '2'*32,'3'*32)
            for name in ('script-bundle/main.js','script-bundle/companion.js'):(child/name).write_bytes(files[name])
            domain=object.__new__(marker_native.RunningDomain);domain.files=SimpleNamespace(root=child);domain.time=1.
            domain.marker_program=role_marker_program(position);domains[role]=domain
        def start(domain):
            try:barrier.wait(timeout=3);domain.start()
            except BaseException as error:errors.append(error)
        workers=[threading.Thread(target=start,args=(domain,),name='avatar-original-marker-vm-'+role) for role,domain in domains.items()]
        for worker in workers:worker.start()
        for worker in workers:worker.join(timeout=8)
        self.assertTrue(all(not worker.is_alive() for worker in workers));self.assertEqual([],errors)
        self.assertEqual(base,marker_native.PROGRAM);self.assertNotEqual(domains['primary'].marker_program,domains['actor'].marker_program)
        for role,x in (('primary',0),('actor',1.5)):
            domain=domains[role];self.assertTrue(domain.running)
            self.assertEqual([x,1.6,1],domain.marker['position']);self.assertEqual(1,len(domain.vm['added']))
            self.assertEqual([domain.marker['id']],domain.vm['deleted']);self.assertEqual('local',domain.vm['added'][0]['host'])
            self.assertEqual((domain.files.root/'script-bundle/main.js').as_uri(),domain.worker['url'])


class AvatarOriginalMarkerDefaultCompatibilityTests(unittest.TestCase):
    def domain(self,kind,files):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup);root=Path(directory.name);root.chmod(0o700)
        (root/'script-bundle').mkdir(mode=0o700)
        for name in ('script-bundle/main.js','script-bundle/companion.js'):(root/name).write_bytes(files[name])
        domain=object.__new__(kind);domain.files=SimpleNamespace(root=root);domain.time=1.;domain.marker_program=None
        return domain
    def test_existing_create_start_looks_up_actual_camera_program_after_default_birth(self):
        from ios.self_tests.create_marker_domain_fixture import RunningDomain
        from ios.adapters.create_marker_files import originals as create_originals
        run='1'*32;files=create_originals(run,'https://controlled.invalid/feature-fixture/v1/runs/'+run+'/', '2'*32,'3'*32)
        domain=self.domain(RunningDomain,files);domain.world_template=dict(source=dict(view=dict(position=[9,2,7],rotation=[0,0,0,1])))
        domain.entity_call_sequence=0;domain.entity_items={};domain.entity_rows=[];domain.entity_events=[];domain.entity_calls=[]
        domain.entity_return_delay=0;domain.pending_entity_return=None;domain.ignore_entity_delete=False
        base=marker_native.PROGRAM;domain.start()
        self.assertIsNone(domain.marker_program);self.assertEqual(base,marker_native.PROGRAM)
        self.assertEqual([7.75,2.8,4],domain.marker['position']);self.assertEqual(1,len(domain.entity_items))
        self.assertEqual(domain.marker['id'],domain.entity_calls[0]['entityId'])
        self.assertEqual([domain.marker['id']],domain.vm['deleted'])
        domain.stop();self.assertFalse(domain.running);self.assertEqual({},domain.entity_items)
        self.assertEqual(['add-returned','delete-returned'],[row['kind'] for row in domain.entity_calls])
    def test_existing_world_web_start_looks_up_actual_camera_and_signal_program_after_default_birth(self):
        from ios.self_tests.world_web_scope_fixture import WorldWebDomain
        from ios.adapters.world_web_files import originals as web_originals
        run='1'*32;files=web_originals(run,'https://controlled.invalid/feature-fixture/v1/runs/'+run+'/', '2'*32,'3'*32)
        domain=self.domain(WorldWebDomain,files);base=marker_native.PROGRAM;domain.start()
        self.assertIsNone(domain.marker_program);self.assertEqual(base,marker_native.PROGRAM)
        self.assertEqual([0,1.6,5.5],domain.marker['position'])
        self.assertEqual('https://controlled.invalid/feature-fixture/v1/runs/'+run+'/tickets/'+('2'*32)+'/reference.html',domain.marker['sourceUrl'])
        self.assertEqual([domain.marker['id']],domain.vm['deleted']);self.assertTrue(domain.running)
        domain.stop();self.assertFalse(domain.running)
        self.assertEqual(['thread-bound','shutdown-drained','thread-finished'],[row['kind'] for row in domain.terminal_events])


if __name__=='__main__':unittest.main()
