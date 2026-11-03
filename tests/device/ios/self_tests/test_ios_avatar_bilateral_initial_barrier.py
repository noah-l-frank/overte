"""Actual paired initial archives/CAS and own-lock resume, native producers modeled.

No archive, decoder or returned frame is patched. Explicit stage-stop sentries
end the composed preparation before marker inputs; the changed normal gate
must still qualify real preparation/observation under the original API budget.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import threading,time,unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import VERSION
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.adapters.avatar_initial_barrier import publish_peer,original
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_whole_snapshots import AvatarWholeSnapshots
from ios.self_tests.avatar_installed_full15_fixture import NativeInstalledFrontdoor
from ios.self_tests import test_ios_avatar_prepare_composed as preparation
from ios.self_tests.avatar_prepare_fixture import RUN


class InitialStageStopped(RuntimeError):pass


class AvatarBilateralInitialBarrierTests(unittest.TestCase):
    retain_originals=True
    @classmethod
    def setUpClass(cls):preparation.AvatarPrepareComposedTests.setUpClass()
    @classmethod
    def tearDownClass(cls):preparation.AvatarPrepareComposedTests.tearDownClass()
    def initial_pair(self,*,fault=None):
        frontdoor=NativeInstalledFrontdoor(self);d=frontdoor.domain;runtime=IOSAvatarRuntime(frontdoor.adapter)
        owners={}
        for role in ('primary','actor'):
            old=d.owners[role];settings=dict(artifactRoot=str(old.root),imagePolicy=deepcopy(old.policy))
            settings['actorTarget' if role=='primary' else 'primaryTarget']='actor' if role=='primary' else 'primary'
            if role=='actor':settings['authorityRead']=dict(mode='adapter',token=d.adapter)
            owners[role]=IOSAvatarFeature(runtime,role,d.client,RUN,role,settings)
        primary,actor=owners['primary'],owners['actor']
        # Native source validity requires the independently real normal login
        # first. This is fixture setup, not injected account/session state.
        with actor.held(paired=True):actor.initialize()
        with actor.held():actor.login();actor.close_preparation_tablet()
        stop=InitialStageStopped('Declared counter boundary after actual initial, before any marker input')
        with patch.object(primary,'wait_peer_initial',side_effect=stop),self.assertRaises(InitialStageStopped):primary.prepare()
        with primary.held():primary.load();before=deepcopy(primary.previous);self.assertIsNone(primary.state['initialBarrier'])
        context=patch.object(actor,'prepare_marker',side_effect=stop)
        if fault is None:
            with context,self.assertRaises(InitialStageStopped):actor.prepare()
        else:
            with context,fault,self.assertRaises(OSError):actor.prepare()
        return frontdoor,d,runtime,primary,actor,before
    def commands(self,d):return {role:deepcopy(native.commands) for role,native in d.natives.items()}
    def test_real_typed_bilateral_cas_preserves_peer_prefix_and_public_resume_ignores_busy_peer_sdk(self):
        f,d,runtime,primary,actor,before=self.initial_pair()
        with primary.held(paired=True):
            primary.load();peer=IOSAvatarFeature.archive(runtime,actor.store.read(),d.client,primary.locks);old=unpack(before['payload'])[0]
            self.assertEqual(old['snapshots'],primary.state['snapshots'][:len(old['snapshots'])])
            self.assertTrue(all(same(primary.state[key],value) for key,value in old.items() if key not in ('snapshots','initialBarrier')))
            archived=IOSAvatarFeature.archive(runtime,primary.previous,d.client,primary.locks)
            self.assertEqual(peer.initial_original(),original(archived));self.assertIsNotNone(archived.state['initialBarrier'])
        commands=self.commands(d);inputs={role:list(native.input_log) for role,native in d.natives.items()}
        entered=threading.Event();release=threading.Event();errors=[]
        def own_marker_lock():
            try:
                with ScriptSourceLock(actor.lock.path).held():entered.set();release.wait(6)
            except BaseException as error:errors.append(error);entered.set()
        worker=threading.Thread(target=own_marker_lock,name='avatar-declared-independent-own-marker-lock');worker.start()
        self.assertTrue(entered.wait(2));sentry=InitialStageStopped('Actual public call reached own-marker resume before peer SDK acquisition')
        started=time.monotonic()
        try:
            with patch.object(runtime,'_sources',side_effect=AssertionError('Initial metadata resume performed SDK source work')):
                with patch.object(primary,'prepare_marker',side_effect=sentry),self.assertRaises(InitialStageStopped) as caught:
                    primary.observe(dict(contractVersion=VERSION,runId=RUN,afterSequence=0))
            self.assertIs(sentry,caught.exception);self.assertLess(time.monotonic()-started,5)
        finally:release.set();worker.join(timeout=3)
        self.assertFalse(worker.is_alive());self.assertEqual([],errors);self.assertEqual(commands,self.commands(d))
        self.assertEqual(inputs,{role:list(native.input_log) for role,native in d.natives.items()})
    def test_lost_saved_peer_snapshot_recovers_exact_birth_without_source_input_or_barrier_rebase(self):
        retained=[];actual=AvatarWholeSnapshots.retain
        def lost(ledger,value):
            reference=actual(ledger,value)
            if ledger.originals.role=='primary' and value.get('role')=='actor' and not retained:
                entry=deepcopy(ledger.entries()[reference['index']-1]);path=ledger.originals.path(entry)
                retained.append(dict(reference=deepcopy(reference),entry=entry,path=path,inode=path.stat().st_ino,body=path.read_bytes()))
                raise OSError('Declared lost return after actual peer snapshot birth, before initial barrier CAS')
            return reference
        f,d,runtime,primary,actor,before=self.initial_pair(fault=patch.object(AvatarWholeSnapshots,'retain',lost))
        self.assertEqual(1,len(retained));saved=retained[0];commands=self.commands(d)
        with primary.held(paired=True):
            primary.load();sender=IOSAvatarFeature.archive(runtime,actor.store.read(),d.client,primary.locks);self.assertIsNone(primary.state['initialBarrier'])
            entries=deepcopy(primary.state['snapshots']);actor_barrier=deepcopy(sender.state['initialBarrier'])
            peer=IOSAvatarFeature.archive(runtime,primary.previous,d.client,primary.locks)
            publish_peer(sender,peer);primary.load()
            sender=IOSAvatarFeature.archive(runtime,actor.store.read(),d.client,primary.locks)
            self.assertEqual(saved['reference'],primary.state['initialBarrier']['owner']);self.assertEqual(entries,primary.state['snapshots'])
            self.assertEqual(actor_barrier,sender.state['initialBarrier']);self.assertEqual(sender.initial_original(),original(primary))
        self.assertEqual(commands,self.commands(d));self.assertEqual(saved['inode'],saved['path'].stat().st_ino);self.assertEqual(saved['body'],saved['path'].read_bytes())
        with primary.held(),patch.object(runtime,'_sources',side_effect=AssertionError('Archive queried SDK')):self.assertTrue(primary.initial_admitted())
    def test_foreign_current_peer_initial_metadata_and_abort_refuse_before_transport(self):
        f,d,runtime,primary,actor,before=self.initial_pair();commands=self.commands(d)
        with actor.held():
            actor.load();old=deepcopy(actor.previous)
            # Preserve the original mutable header as a separate counter artifact.
            backup=PrivateFeatureState(f.root/'counter-original-peer-feature-before.json');backup.write(old,None)
            state=unpack(old['payload'])[0];state['initial']['reference']['sha256']='0'*64
            changed=deepcopy(old);changed['payload']=pack([state]);actor.store.write(changed,old)
        with patch.object(runtime,'_sources',side_effect=AssertionError('Foreign metadata queried SDK')):
            with self.assertRaises(NativeUIError):primary.initial_admitted()
            with actor.held():
                foreign=actor.store.read();self.assertEqual(changed,foreign)
                preserved=PrivateFeatureState(f.root/'counter-original-peer-feature-foreign.json');preserved.write(foreign,None)
                actor.store.write(old,foreign);self.assertEqual(old,actor.store.read())
            self.assertTrue(primary.initial_admitted())
            self.assertEqual(changed,preserved.read())
            abort=PrivateFeatureState(primary.store.path.with_name('ios-avatar-primary-'+RUN+'-abort.json'))
            abort.write(dict(declaredExistingAbortFence=True),None)
            with self.assertRaises(NativeUIError):primary.initial_admitted()
        self.assertEqual(commands,self.commands(d));self.assertEqual(old,backup.read())


if __name__=='__main__':unittest.main()
