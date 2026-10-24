"""Real private file/CAS recovery; paired evidence decoder is an explicit model.

These tests establish persistence behavior only. The actual paired original
decoder is qualified separately by the rooted window scenario.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,same,unpack
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import projection
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.emote_retirement import Frozen
from ios.self_tests.test_ios_emote_sources import BINDING,RUN
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.adapters.emote_terminal_replay import IOSEmoteTerminalReplay


class TerminalJournalTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.roles={};self.qualifications=0
        for role in terminal.ROLES:
            directory=self.root/role;directory.mkdir(mode=0o700)
            binding=deepcopy(BINDING)
            if role=='actor':binding.update(targetFingerprint='9'*64,sessionId='actor-sdk',processIdentity='42')
            lock=ScriptSourceLock(directory/'script-feature-sources.lock')
            self.roles[role]=SimpleNamespace(root=self.artifacts,binding=binding,run=RUN,lock=lock,
                store=PrivateFeatureState(directory/('ios-emote-'+role+'-'+RUN+'-terminal-live.json')))
        for role in ('actor','primary'):
            held=self.roles[role].lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.window=object.__new__(IOSEmoteTerminalWindow);self.window.roles=self.roles
        self.window.guard=lambda:all(owner.lock.assert_held() is None for owner in self.roles.values())
        for role,owner in self.roles.items():
            owner.originals=OriginalFrameStore(self.artifacts,owner.binding,RUN,role,self.window.guard,lambda *_:None,
                namespace='emote-rooted-live',schema_prefix='iosEmoteRootedLive',kind='inputs')
        self.refs={role:dict(index=1,sha256=('a' if role=='primary' else 'b')*64,bytes=2,device=0,inode=1) for role in terminal.ROLES}
        self.description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='emotes',runId=RUN,ticket='2'*32,
            roles={role:dict(binding=binding_from_context(owner.binding),heldResources=[],
                originalSha256=('3' if role=='primary' else '4')*64) for role,owner in self.roles.items()})
        self.samples=[]
        for index in range(3):
            state=deepcopy(SCENARIOS['emotes']['baseline']);epoch=100000+index*1600
            primary=dict(schemaVersion=1,contractVersion=16,runId=RUN,sequence=index+1,capturedEpochMs=epoch,
                state=state,artifacts=[],resources=[],lifecycle=dict(backgrounds=0,activations=1,launches=1))
            actor=dict(ticket=self.description['ticket'],actor='owned-observer',actorSequence=index+1,
                capturedEpochMs=epoch,facts=projection('emotes',state),sequence=index+1,receivedEpochMs=epoch+1)
            self.samples.append(dict(primary=primary,actor=actor))
        original=dict(iosEmoteTerminalWindowVersion=1,description=deepcopy(self.description),references=deepcopy(self.refs),
            samples=deepcopy(self.samples),journals={},primary=[],actor=[],publisher={})
        self.proof=dict(original=original,seal=dict(featureTerminalSealVersion=1,description=deepcopy(self.description),
            windowSha256=digest(self.samples),liveOriginalSha256=digest(original)))
        terminal.sealed(self.proof['seal'],self.description,self.samples)
        def describe(refs):need(same(refs,self.refs));return deepcopy(self.description)
        def qualify(description,samples,references,*,publisher_store):
            need(same(description,self.description) and same(samples,self.samples) and same(references,self.refs))
            self.qualifications+=1;return deepcopy(self.proof)
        self.window.describe,self.window.qualify=describe,qualify
        self.publisher=PrivateFeatureState(self.root/'publisher.json')

    def owner(self):return IOSEmoteTerminalJournal(self.window)
    def inspect(self,owner):return owner.inspect(self.refs)
    def seal(self,owner):return owner.seal(self.description,self.samples,publisher_store=self.publisher)
    def identity(self,owner):
        path=owner.originals.path(owner.originals.expand(owner.state['record']))
        info=path.stat();return path,info.st_dev,info.st_ino,path.read_bytes()

    def test_inspect_seal_and_replay_keep_one_actual_original_and_requalify(self):
        owner=self.owner();self.assertEqual('inspect',self.inspect(owner)['stage']);self.inspect(owner)
        result=self.seal(owner);identity=self.identity(owner);self.assertEqual('seal',result['stage'])
        resumed=self.owner();self.assertEqual(result,self.seal(resumed));self.assertEqual(identity,self.identity(resumed))
        self.assertEqual(2,self.qualifications)
        wrong=deepcopy(self.samples);wrong[0]['actor']['receivedEpochMs']+=1
        with self.assertRaises(NativeUIError):resumed.seal(self.description,wrong,publisher_store=self.publisher)
        self.assertEqual(identity,self.identity(resumed))

    def test_saved_file_return_loss_recovers_same_inode_without_new_qualification(self):
        owner=self.owner();self.inspect(owner);intent=owner.intent
        def lost(kind,value):
            intent(kind,value)
            if value['phase']=='saved':raise OSError('Actual saved original return lost')
        owner.originals.intent=lost
        with self.assertRaises(OSError):self.seal(owner)
        pending=deepcopy(owner.state['pending']);self.assertEqual('saved',pending['phase'])
        path=owner.originals.path(pending);identity=(path.stat().st_ino,path.read_bytes())
        resumed=self.owner();resumed.recover();self.assertEqual(1,self.qualifications)
        self.assertEqual(identity,(path.stat().st_ino,path.read_bytes()));self.assertEqual('sealed',resumed.state['phase'])
        self.seal(resumed);self.assertEqual(2,self.qualifications)

    def test_lost_completed_metadata_return_poison_requires_reconstruction(self):
        owner=self.owner();self.inspect(owner);write=PrivateFeatureState.write
        def lost(store,value,previous):
            write(store,value,previous)
            if store.path==owner.store.path and unpack(value['payload'])[0]['phase']=='sealed':
                raise OSError('Actual metadata commit return lost')
        with patch.object(PrivateFeatureState,'write',lost),self.assertRaises(OSError):self.seal(owner)
        with self.assertRaises(NativeUIError):owner.bound()
        resumed=self.owner();identity=self.identity(resumed);self.seal(resumed)
        self.assertEqual(identity,self.identity(resumed))

    def test_planned_unknown_birth_never_guesses_saved_original_or_recreates_it(self):
        owner=self.owner();self.inspect(owner);intent=owner.intent
        def lost(kind,value):
            intent(kind,value)
            if value['phase']=='saved':raise OSError('Saved return lost')
        owner.originals.intent=lost
        with self.assertRaises(OSError):self.seal(owner)
        path=owner.originals.path(owner.state['pending']);before=(path.stat().st_ino,path.read_bytes())
        state=deepcopy(owner.state);state['pending'].update(phase='planned',file=None)
        value=owner.envelope(state);owner.store.write(value,owner.previous)
        resumed=self.owner()
        with self.assertRaises(NativeUIError):resumed.recover()
        self.assertEqual(value,resumed.store.read());self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))

    def test_opened_incomplete_file_remains_owned_and_is_not_rewritten(self):
        owner=self.owner();self.inspect(owner);intent=owner.intent
        def lost(kind,value):
            intent(kind,value)
            if value['phase']=='opened':raise OSError('Interrupted before file bytes')
        owner.originals.intent=lost
        with self.assertRaises(OSError):self.seal(owner)
        path=owner.originals.path(owner.state['pending']);identity=(path.stat().st_ino,path.read_bytes())
        resumed=self.owner()
        with self.assertRaises(NativeUIError):resumed.recover()
        self.assertEqual(identity,(path.stat().st_ino,path.read_bytes()));self.assertEqual('sealing',resumed.state['phase'])

    def test_staged_before_file_intent_can_resume_exact_proof_without_regeneration(self):
        owner=self.owner();self.inspect(owner)
        with patch.object(owner.originals,'write',side_effect=OSError('Before file intent')),self.assertRaises(OSError):self.seal(owner)
        self.assertIsNone(owner.state['pending']);self.assertEqual('sealing',owner.state['phase'])
        resumed=self.owner();resumed.recover();self.assertEqual(1,self.qualifications)
        self.assertEqual(self.proof,resumed.originals.read(resumed.originals.expand(resumed.state['record'])))

    def test_orphan_and_foreign_journal_are_refused(self):
        owner=self.owner();self.inspect(owner)
        for fault in ('boolean-version','foreign-run','foreign-binding','phase'):
            value=deepcopy(owner.previous)
            if fault=='boolean-version':value['iosEmoteTerminalJournalVersion']=True
            elif fault=='foreign-run':value['runId']='f'*32
            elif fault=='foreign-binding':value['bindings']['actor']['processIdentity']='99'
            else:
                state=deepcopy(owner.state);state['phase']='sealed';value=owner.envelope(state)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError,TypeError)):owner.decode(value)
        path=self.artifacts/('emote-terminal-frame-inputs-'+RUN+'-primary-0001-'+'f'*64+'.json')
        path.write_bytes(b'{}');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.owner()

    def test_replay_bootstrap_checks_original_inode_and_metadata_before_graph_decode(self):
        owner=self.owner();self.inspect(owner);self.seal(owner);identity=self.identity(owner)
        locks=(self.roles['primary'].lock,self.roles['actor'].lock)
        IOSEmoteTerminalReplay(owner.store,*locks).guard()
        for fault in ('boolean-version','foreign-lock','unsealed','foreign-index','wrong-original-inode'):
            value=deepcopy(owner.previous);state=unpack(value['payload'])[0]
            if fault=='boolean-version':value['iosEmoteTerminalJournalVersion']=True
            elif fault=='foreign-lock':value['locks']['actor']=value['locks']['primary']
            elif fault=='unsealed':state['phase']='sealing'
            elif fault=='foreign-index':state['record']['index']=2
            else:state['record']['inode']+=1
            if fault not in ('boolean-version','foreign-lock'):
                value['payload']=pack([state])
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                changed=IOSEmoteTerminalReplay(Frozen(owner.store.path,value),*locks);changed.read()
        self.assertEqual(identity,self.identity(owner))


if __name__=='__main__':unittest.main()
