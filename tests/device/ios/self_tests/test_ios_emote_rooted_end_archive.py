"""Actual paired end archive/CAS/retirement with explicit authorization models.

Live/native seal, process death and SDK404 qualifications are modeled here. The
frozen archive transaction, immutable fence carriers, closed census, per-path
delete intent and interrupted metadata recovery use their actual host owners.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
from ios.self_tests.test_ios_process_retirement import BINDING,RUN


class RootedEndArchiveStorageTests(unittest.TestCase):
    @staticmethod
    def binding(role):
        return dict(BINDING,processIdentity='42' if role=='actor' else '43',
            sessionId='owned-actor' if role=='actor' else 'owned-primary',targetFingerprint=('d' if role=='actor' else 'e')*64)
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.root=Path(temporary.name);self.root.chmod(0o700)
        self.sdk={};self.artifacts={};self.locks={};self.paths=[];self.copies={};self.seal=dict(explicitPairedSealModel=True)
        for role in ('actor','primary'):
            sdk=self.root/(role+'-sdk');sdk.mkdir(mode=0o700);root=self.root/(role+'-originals');root.mkdir(mode=0o700)
            self.sdk[role],self.artifacts[role]=sdk,root;lock=ScriptSourceLock(sdk/'script-feature-sources.lock');self.locks[role]=lock
            held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
            for tail in ('marker','keys','pointers'):
                store=PrivateFeatureState(sdk/('ios-emote-'+role+'-'+tail+'.json'));store.write(dict(explicitOldWALModel=tail,role=role),None)
                self.paths.append(store);self.copies[str(store.path)]=store.read()
            feature=PrivateFeatureState(sdk/('ios-emote-'+role+'-feature.json'));feature.write(dict(explicitFeatureModel=role),None)
            self.paths.append(feature);self.copies[str(feature.path)]=feature.read()
        terminal_path=self.sdk['primary']/('ios-emote-primary-'+RUN+'-terminal.json')
        terminal=PrivateFeatureState(terminal_path);terminal.write(dict(explicitTerminalModel=True),None)
        self.paths.append(terminal);self.copies[str(terminal_path)]=terminal.read()
        self.proof=PrivateFeatureState(self.artifacts['primary']/'retained-proof-model.json');self.proof.write(dict(explicitProofModel=True),None)
        self.ownership=object.__new__(IOSEmoteRootedOwnership);self.ownership.path=terminal_path;self.ownership.terminal=terminal.read()
        self.ownership.roles=SimpleNamespace(run=RUN,locks=self.locks,copies={path:value for path,value in self.copies.items() if path!=str(terminal_path)})
        self.ownership.read=lambda:self.proof.read()
        self.enterContext(patch('ios.adapters.emote_rooted_fence._seal',side_effect=lambda proof,seal,**kwargs:need(same(proof,self.proof.read()) and same(seal,self.seal))))
        phase=dict(fixturePhaseVersion=1,instance='1'*32,sequence=2,requestId='2'*32,runId=RUN,area='emotes',capturedEpochMs=100000,
            active=False,createdEpochMs=90000,retiredEpochMs=99000,
            activations=[dict(sequence=1,ticket='8'*32,activatedEpochMs=95000,stimulus=dict(verb='cleanup',inputs={}))])
        self.archive=IOSEmoteRootedFinalArchive(PrivateFeatureState(self.sdk['primary']/('ios-emote-primary-'+RUN+'-rooted-final.json')),
            self.artifacts['primary'],self.binding('primary'),RUN,'primary',self.locks['primary'],self.locks['primary'],self.paths,lambda:True,
            lambda copies:need(same(copies,self.copies)))
        self.archive.begin(phase);self.archive.freeze();self.frozen=deepcopy(self.archive.previous)
        self.processes={};self.sessions={}
        for role in ('actor','primary'):
            process=object.__new__(IOSEmoteRootedProcessEnd);process.role,process.run,process.root=role,RUN,self.artifacts[role]
            process.lock=self.locks[role];process.archive=self.archive;process.ownership=self.ownership;process.seal=deepcopy(self.seal)
            process.binding=self.binding(role);process.retirement=None
            process.store=PrivateFeatureState(self.sdk[role]/('ios-emote-'+role+'-'+RUN+'-rooted-process-end.json'))
            process.previous=dict(explicitProcessEndModel=True,role=role);process.store.write(process.previous,None)
            frames=OriginalFrameStore(process.root,process.binding,RUN,role,lambda:True,lambda *args:None,
                namespace='emote-rooted-process',schema_prefix='emoteRootedProcess',monotonic=lambda:0)
            body={key:dict(explicitFinalWALModel=key,role=role) for key in ('scope','keys','pointers')}
            body['phaseAfter']=dict(capturedEpochMs=100000);ref=frames.write(1,body)
            process.frames,process.model_fence=frames,ref
            process.fence_original=lambda frames=frames,ref=ref:frames.read(frames.expand(ref))
            for key,tail in (('scope','marker'),('keys','keys'),('pointers','pointers')):
                store=PrivateFeatureState(process.lock.path.with_name('ios-emote-'+role+'-'+tail+'.json'));store.write(body[key],store.read())
            def completed(process=process):
                need(same(process.store.read(),process.previous));value=process.fence_original()
                for key,tail in (('scope','marker'),('keys','keys'),('pointers','pointers')):
                    path=process.lock.path.with_name('ios-emote-'+process.role+'-'+tail+'.json')
                    store=PrivateFeatureState(path) if process.retirement is None else process.retirement.store_for(path,value[key])
                    need(same(store.read(),value[key]))
                return deepcopy(process.previous)
            process.completed=completed;self.processes[role]=process
            session=object.__new__(IOSEmoteRootedSessionEnd);session.process=process
            session.store=PrivateFeatureState(self.sdk[role]/('ios-emote-'+role+'-'+RUN+'-rooted-sdk-end.json'))
            session.previous=dict(explicitSDKEndModel=True,role=role);session.store.write(session.previous,None)
            def sdk_completed(session=session):
                need(same(session.store.read(),session.previous));session.process.completed();return deepcopy(session.previous)
            session.completed=sdk_completed;self.sessions[role]=session
        self.processes['primary'].peer=self.processes['actor'];self.sessions['primary'].peer=self.sessions['actor']
        self.owner=self.reopen()
    def reopen(self):
        owner=IOSEmoteRootedEndArchive(self.archive,self.ownership,self.seal,lambda:True)
        owner.attach(self.processes,self.sessions);return owner
    def test_real_frozen_copy_and_final_fence_metadata_retire_then_replay_without_rewriting_originals(self):
        self.owner.prepare();self.assertTrue(self.owner.retire())
        self.assertEqual('complete',self.owner.state['phase']);self.assertTrue(all(path.read() is None for path in self.paths))
        self.assertEqual(self.frozen,self.archive.store.read());self.assertEqual(self.copies,self.archive.copies())
        self.assertTrue(self.reopen().retire())
    def test_lost_metadata_discard_reply_recovers_only_its_durable_pending_path(self):
        self.owner.prepare();target=self.paths[2].path;discard=PrivateFeatureState.discard;calls=[]
        def lost(store,value):
            calls.append(store.path);result=discard(store,value)
            if store.path==target:raise RuntimeError('Explicit lost metadata discard reply')
            return result
        with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(RuntimeError):self.owner.retire()
        self.assertEqual(2,self.owner.state['retired']);self.assertEqual(2,self.owner.state['pending']);self.assertIsNone(self.paths[2].read())
        self.assertTrue(self.reopen().retire());self.assertEqual(1,calls.count(target));self.assertTrue(all(path.read() is None for path in self.paths))
    def test_absence_without_exact_pending_delete_intent_cannot_retire_other_metadata(self):
        self.owner.prepare();self.paths[2].discard(self.paths[2].read())
        with self.assertRaises(NativeUIError):self.reopen().retire()
        self.assertIsNotNone(self.paths[0].read());self.assertEqual(0,self.owner.state['retired'])
    def test_unknown_initial_carrier_blocks_before_any_metadata_discard(self):
        rogue=PrivateFeatureState(self.artifacts['actor']/'emote-unowned-model.json');rogue.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertTrue(all(path.read() is not None for path in self.paths));self.assertIsNotNone(rogue.read())
    def test_changed_actual_process_journal_cannot_inherit_a_prepared_end_archive(self):
        self.owner.prepare();process=self.processes['actor'];process.store.write(dict(foreignProcessModel=True),process.previous)
        with self.assertRaises(NativeUIError):self.reopen().retire()
        self.assertTrue(all(path.read() is not None for path in self.paths))
    def test_original_mutation_during_verification_is_caught_by_the_earlier_file_lease(self):
        self.owner.prepare();old=self.proof.read()
        def changed():
            value=self.proof.read();self.proof.write(value,value);return value
        self.ownership.read=changed
        with self.assertRaises(NativeUIError):self.owner.retire()
        self.assertEqual(old,self.proof.read());self.assertTrue(all(path.read() is not None for path in self.paths))
    def test_retained_interpretation_rejects_arbitrary_paths_or_changed_fence_values(self):
        self.owner.prepare();process=self.processes['actor'];path=process.lock.path.with_name('ios-emote-actor-marker.json')
        with self.assertRaises(NativeUIError):self.owner.store_for(path,dict(foreign=True))
        with self.assertRaises(NativeUIError):self.owner.store_for(self.proof.path,self.proof.read())
    def test_missing_feature_bootstrap_requires_its_exact_committed_delete_intent_and_end_journals(self):
        self.owner.prepare();path=self.sdk['actor']/'ios-emote-actor-feature.json';index=[store.path for store in self.paths].index(path)
        discard=PrivateFeatureState.discard
        def lost(store,value):
            result=discard(store,value)
            if store.path==path:raise RuntimeError('Explicit lost feature discard reply')
            return result
        with patch.object(PrivateFeatureState,'discard',lost),self.assertRaises(RuntimeError):self.owner.retire()
        bootstrap=IOSEmoteRootedEndArchive(self.archive,self.ownership,self.seal,lambda:True)
        self.assertIsNone(bootstrap.processes);self.assertEqual(index,bootstrap.state['pending'])
        self.assertEqual(self.copies[str(path)],bootstrap.store_for(path,self.copies[str(path)]).read())
        process=self.processes['actor'];process.store.write(dict(foreign=True),process.previous)
        with self.assertRaises(NativeUIError):bootstrap.store_for(path,self.copies[str(path)])
    def test_unissued_missing_feature_cannot_borrow_prepared_paired_end_authority(self):
        self.owner.prepare();path=self.sdk['actor']/'ios-emote-actor-feature.json';store=PrivateFeatureState(path);store.discard(store.read())
        bootstrap=IOSEmoteRootedEndArchive(self.archive,self.ownership,self.seal,lambda:True)
        with self.assertRaises(NativeUIError):bootstrap.store_for(path,self.copies[str(path)])


if __name__=='__main__':unittest.main()
