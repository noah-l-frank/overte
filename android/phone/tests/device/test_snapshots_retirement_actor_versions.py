"""Actual closed archives retain exact legacy/v2/v3 actor ownership and originals.

Native/SDK sources are explicit producers. TLS inputs, files, process exit,
quiet windows and public repeated finalization execute the production paths.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_phase_transition as transitions
import test_snapshots_full_retirement_audit as full
import test_snapshots_feature as partial
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import pack,unpack
from overte_phone_snapshots_retirement import PhoneSnapshotsRetirement,completed_archive,NAMES
from overte_phone_snapshots_evidence import SnapshotsOriginals


class SnapshotRetirementActorVersionsTests(unittest.TestCase):
    setUpClass=classmethod(transitions.SnapshotPhaseTransitionTests.setUpClass.__func__)
    tearDownClass=classmethod(transitions.SnapshotPhaseTransitionTests.tearDownClass.__func__)
    setUp=transitions.SnapshotPhaseTransitionTests.setUp
    start=transitions.SnapshotPhaseTransitionTests.start
    activate=transitions.SnapshotPhaseTransitionTests.activate
    receive=transitions.SnapshotPhaseTransitionTests.receive
    send=transitions.SnapshotPhaseTransitionTests.send
    observe_primary=transitions.SnapshotPhaseTransitionTests.observe_primary
    observe_primary_with_actor=transitions.SnapshotPhaseTransitionTests.observe_primary_with_actor
    assert_transition=transitions.SnapshotPhaseTransitionTests.assert_transition

    def cleanup(self):
        h=transitions.harness
        return self.rig.invoke('feature.snapshots.cleanup',dict(contractVersion=h.VERSION,runId=h.RUN))

    def archive(self):
        h=transitions.harness
        # Inspection of actual private originals is fixture setup only. Public
        # cleanup below must independently establish fresh native authority.
        return completed_archive(self.rig.root,self.rig.model.model_binding,h.RUN,lambda:True)

    def finish_transition(self):
        r=self.rig;r.act('open');r.act('capture',dict(mode='still',format='png'));r.act('save');r.act('upload')
        r.invoke('feature.snapshots.observe',dict(contractVersion=transitions.harness.VERSION,
            runId=transitions.harness.RUN,afterSequence=0))
        self.start(baseline=True);self.assert_transition(self.activate('cleanup'))
        self.assertEqual({'performed':True},self.cleanup())
        # The scheduling prerequisite now records actual nonempty Primary
        # observations. Retirement must see a new real cleaned observation,
        # rather than accidentally reusing the earlier empty baseline frame.
        self.observe_primary_with_actor('acknowledged')
        self.assertEqual('fresh',self.receive()['stage'])
        r.client.close();self.send('close');self.assertEqual('retired',self.receive()['stage'])
        self.child.wait(timeout=5);self.assertEqual(0,self.child.returncode)
        self.assertEqual({'performed':True},self.cleanup())
        paths=list(r.root.glob('emote-frame-snapshots-retirement-*.json'));self.assertEqual(1,len(paths))
        return paths[0]

    def validate_candidate(self,candidate):
        h=transitions.harness;r=self.rig
        feature=r.adapter._snapshots_feature('test-only-appium',h.RUN,retirement=True)
        with feature.lock.held(),r.adapter.existing_input_session('test-only-appium'):
            feature.load();return PhoneSnapshotsRetirement(feature).validate_archive(candidate)

    def test_v3_actual_transition_survives_closed_exit_and_double_finalize_with_no_active_controls(self):
        path=self.finish_transition();before=(path.stat().st_ino,path.read_bytes());archive=self.archive()
        header=archive['controls']['phone-snapshots-actor-lifecycle.json'];state=unpack(header['payload'])[0]
        self.assertEqual(3,header['snapshotsActorVersion']);self.assertEqual(1,len(state['transitions']))
        self.assertIn('primaryCue',state)
        self.assertEqual('before-sources',state['transitions'][0]['kind'])
        self.assertTrue(all(PrivateFeatureState(self.rig.root/name).read() is None for name in NAMES))
        self.assertEqual({'performed':True},self.cleanup());self.assertEqual({'performed':True},self.cleanup())
        self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))
        self.assertEqual(archive,self.validate_candidate(archive))

    def test_actual_completed_v3_archive_rejects_versions_shape_scope_floor_and_missing_original(self):
        path=self.finish_transition();archive=self.archive();unchanged=(path.stat().st_ino,path.read_bytes())
        name='phone-snapshots-actor-lifecycle.json'
        for fault in ('bool-version','unknown-version','legacy-with-transitions','v2-with-primary-cue',
                'missing-primary-cue','bool-cue-version','unknown-state','scope','role-floor',
                'mode-null','mode-version','mode-bool-version','mode-process','mode-missing','mode-extra',
                'actor-process-vs-mode','actor-cue-missing-for-mode'):
            with self.subTest(fault=fault):
                candidate=deepcopy(archive);header=candidate['controls'][name];state=unpack(header['payload'])[0]
                if fault=='bool-version':header['snapshotsActorVersion']=True
                elif fault=='unknown-version':header['snapshotsActorVersion']=4
                elif fault=='legacy-with-transitions':header['snapshotsActorVersion']=1
                elif fault=='v2-with-primary-cue':header['snapshotsActorVersion']=2
                elif fault=='missing-primary-cue':state.pop('primaryCue');header['payload']=pack([state])
                elif fault=='bool-cue-version':
                    state['primaryCue']=dict(snapshotPrimaryCueVersion=True,header=candidate['controls']['phone-snapshots-primary-originals.json'])
                    header['payload']=pack([state])
                elif fault=='unknown-state':state['unowned']=True;header['payload']=pack([state])
                elif fault=='scope':state['transitions'][0]['scope']=dict(kind='foreground',handoffId=None);header['payload']=pack([state])
                elif fault.startswith('mode-'):
                    owner=candidate['owner'];owned=unpack(owner['payload'])[0]
                    mode=owned['cleanupStages']['readReadyMode'];self.assertEqual(1,mode['snapshotCleanupReadReadyVersion'])
                    if fault=='mode-null':owned['cleanupStages']['readReadyMode']=None
                    elif fault=='mode-version':mode['snapshotCleanupReadReadyVersion']=2
                    elif fault=='mode-bool-version':mode['snapshotCleanupReadReadyVersion']=True
                    elif fault=='mode-process':mode['actorProcess']['start']='0'
                    elif fault=='mode-missing':owned['cleanupStages'].pop('readReadyMode')
                    else:mode['unknownSchedulingField']=True
                    owner['payload']=pack([owned])
                    # Keep both archived Feature copies mutually consistent.
                    # Rejection must inspect their mode against real originals,
                    # not merely notice unequal duplicate owner envelopes.
                    candidate['controls']['phone-snapshots-feature.json']=deepcopy(owner)
                elif fault=='actor-process-vs-mode':
                    state['process']['start']='0';header['payload']=pack([state])
                elif fault=='actor-cue-missing-for-mode':
                    state['primaryCue']=None;header['payload']=pack([state])
                else:
                    role=candidate['controls']['phone-snapshots-actor-originals.json'];body=unpack(role['payload'])[0]
                    body.update(sequence=0,manifests=[]);role['payload']=pack([body])
                with self.assertRaises(NativeUIError):self.validate_candidate(candidate)
                self.assertEqual(unchanged,(path.stat().st_ino,path.read_bytes()))
        native=self.rig.setup.f.native;identity=native.identity;changed=[];refused=[]
        restore=SnapshotsOriginals.restore;bound=PhoneSnapshotsRetirement.bound
        def late_target(engine,*args,**kwargs):
            value=restore(engine,*args,**kwargs)
            if engine.kind=='snapshots' and engine.role=='actor' and not changed:
                changed.append(True);native.identity='32:foreign-retirement-start'
            return value
        def current_guard(retirement):
            try:return bound(retirement)
            except Exception as error:
                if changed:refused.append(type(error).__name__)
                raise
        try:
            with patch.object(SnapshotsOriginals,'restore',late_target),patch.object(PhoneSnapshotsRetirement,'bound',current_guard):
                with self.assertRaises(NativeUIError):self.validate_candidate(archive)
            self.assertEqual([True],changed);self.assertTrue(refused)
        finally:native.identity=identity
        self.assertEqual(unchanged,(path.stat().st_ino,path.read_bytes()))
        state=unpack(archive['controls'][name]['payload'])[0];reference=state['transitions'][0]
        host=SnapshotsOriginals(self.rig.root,archive['owner']['binding'],transitions.harness.RUN,'actor',lambda:True,lambda *_:None,kind='snapshots')
        entries=host.manifest(reference['manifest']);original=host.path(host.expand(entries[-1]));saved=original.read_bytes()
        original.unlink()
        with self.assertRaises(NativeUIError):self.cleanup()
        self.assertEqual(unchanged,(path.stat().st_ino,path.read_bytes()))
        self.assertTrue(all(PrivateFeatureState(self.rig.root/name).read() is None for name in NAMES))
        # Do not repair with replacement bytes/inode: the failed owner remains
        # red and this fixture is retired by its own ordinary teardown.
        self.assertTrue(saved)

    def legacy_full_archive(self,version):
        r=self.rig;r.cleanup_public=self.cleanup
        r.act('open');r.act('capture',dict(mode='still',format='png'));r.act('save');r.act('upload')
        r.client.activate('d'*32,'cleanup',{});self.assertEqual({'performed':True},self.cleanup())
        full.FullRetirementAuditTests.close_with_original_actor(r)
        store=PrivateFeatureState(r.root/'phone-snapshots-actor-lifecycle.json');header=store.read();state=unpack(header['payload'])[0]
        self.assertEqual([],state['transitions'])
        from overte_phone_snapshots_actor import validate_primary_cue
        cue=state['primaryCue'];self.assertIsNotNone(cue)
        feature=r.adapter._snapshots_feature('test-only-appium',transitions.harness.RUN)
        primary=PrivateFeatureState(r.root/'phone-snapshots-primary-originals.json')
        with feature.lock.held(),feature.adapter.existing_input_session(feature.selector):
            feature.load();primary_header=primary.read()
            def actual_owners():
                feature.header_authority()
                self.assertEqual(header,store.read());self.assertEqual(primary_header,primary.read());return True
            validate_primary_cue(feature,cue,primary_header,history_guard=actual_owners)
        state.pop('primaryCue')
        if version==1:state.pop('transitions')
        # Format conversion only: the verified current scheduling cue has no
        # field in v1/v2. Preserve the same real quiet/exit/closure evidence;
        # no target observation or result is added by this schema fixture.
        legacy=dict(header,snapshotsActorVersion=version,payload=pack([state]));store.write(legacy,header)
        self.assertEqual({'performed':True},self.cleanup());archive=self.archive()
        self.assertEqual(legacy,archive['controls']['phone-snapshots-actor-lifecycle.json'])
        path=next(r.root.glob('emote-frame-snapshots-retirement-*.json'));before=(path.stat().st_ino,path.read_bytes())
        self.assertEqual({'performed':True},self.cleanup());self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))
        body=unpack(self.archive()['controls']['phone-snapshots-actor-lifecycle.json']['payload'])[0]
        self.assertNotIn('primaryCue',body)
        if version==1:self.assertNotIn('transitions',body)
        else:self.assertEqual([],body['transitions'])

    def test_legacy_encoding_of_actual_full_closed_actor_is_not_rewritten_in_completed_archive(self):self.legacy_full_archive(1)
    def test_v2_encoding_of_actual_full_closed_actor_is_not_rewritten_in_completed_archive(self):self.legacy_full_archive(2)

    def partial_archive(self,version):
        rig=partial.SnapshotsFeatureTests('test_partial_finalize_requires_real_actor_exit_and_retires_exact_journals_idempotently')
        rig.setUp()
        try:
            write=PrivateFeatureState.write
            def encoded(store,value,previous):
                if version in (2,3) and store.path.name=='phone-snapshots-actor-lifecycle.json':
                    body=unpack(value['payload'])[0];body['transitions']=[]
                    if version==3:body['primaryCue']=None
                    value=dict(value,snapshotsActorVersion=version,payload=pack([body]))
                return write(store,value,previous)
            with patch.object(PrivateFeatureState,'write',encoded):
                rig.test_partial_finalize_requires_real_actor_exit_and_retires_exact_journals_idempotently()
            archive=completed_archive(rig.root,rig.adapter.binding,rig.client.run,lambda:True)
            self.assertEqual(version,archive['controls']['phone-snapshots-actor-lifecycle.json']['snapshotsActorVersion'])
        finally:rig.doCleanups()

    def test_actual_partial_legacy_closed_archive_repeats_without_rewriting(self):self.partial_archive(1)
    def test_actual_partial_v2_closed_archive_repeats_without_creating_role_controls(self):self.partial_archive(2)
    def test_actual_partial_v3_closed_archive_repeats_without_creating_role_controls(self):self.partial_archive(3)


if __name__=='__main__':unittest.main()
