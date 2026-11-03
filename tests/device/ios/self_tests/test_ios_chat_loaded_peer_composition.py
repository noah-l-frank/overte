"""Paired real Chat Scripts/IPA/WAL with declared native Qt/SDK producers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.adapters.chat_draft_owner import IOSChatDraftOwner,_ARCHIVE_FRONTIERS
from ios.adapters.chat_send_operation import IOSChatSendOperation
from ios.adapters.chat_receive_sources import IOSChatReceiveSources
from ios.self_tests.chat_loaded_peer_fixture import LoadedPairedFixture

class ChatLoadedPeerCompositionTests(unittest.TestCase):
    def make(self):
        self.loaded=LoadedPairedFixture(self);self.f=self.loaded.f;return self.loaded
    def send(self,role,token):
        self.f.type(role,token=token)
        return IOSChatSendOperation(self.f.receive,self.f.drafts[role].owner,sender_role=role).send(self.f.models[role].ticket)
    def receive(self,role,fact):
        link=self.loaded.contexts[role].link(fact)
        with self.f.drafts[role].owner() as owner:return owner.receive_peer(fact['ticket'],link)
    def query_census(self):
        return {role:deepcopy((m.widgets.calls,m.root_queries,m.code_queries,m.qml_queries)) for role,m in self.f.models.items()}
    def test_real_both_direction_send_incoming_history_and_pure_loaded_original_archives(self):
        loaded=self.make();self.f.open();outgoing=self.send('primary','unicode');peer=self.receive('peer',outgoing)
        reply=self.send('peer','reply');primary=self.receive('primary',reply)
        self.assertEqual(3,outgoing['iosChatSendReceiveDerivedVersion']);self.assertEqual(3,reply['iosChatPeerSendReceiveDerivedVersion'])
        self.assertEqual((),_ARCHIVE_FRONTIERS.get());self.assertEqual(1,len(self.f.models['primary'].source['chatSends']))
        self.assertEqual(1,len(self.f.models['peer'].source['chatSends']))
        source=self.f.receive;files=self.f.pair.census();queries=self.query_census();commands=self.f.pair.commands()
        archive=IOSChatReceiveSources.archive(source.store,source.primary_binding,source.binding,source.run,
            self.f.pair.artifacts['primary'],self.f.pair.artifacts['peer'],self.f.parts['binding'],
            self.f.pair.locks['primary'],self.f.pair.locks['peer'])
        contexts=self.f.pair.runtime._chat_receipt_contexts('primary','peer',source.run,
            self.f.models['primary'].client(),archive,qml_artifacts=loaded.artifacts)
        with patch.object(PrivateFeatureState,'write',side_effect=AssertionError('Historical loaded peer proof wrote state')):
            for role,fact,result,version in (('primary',reply,primary,9),('peer',outgoing,peer,11)):
                draft=self.f.drafts[role]
                owner=IOSChatDraftOwner.archive(draft.f.store,draft.f.root,draft.binding,draft.run,draft.f.lock,
                    draft.m.owner.fixture_url,source_bound=True,peer_actor=role=='peer',peer_receipts=contexts[role],
                    qml_bound=True,qml_artifact=loaded.artifacts[role])
                self.assertEqual(version,owner.version);self.assertEqual(result,owner.receive_peer(fact['ticket'],contexts[role].link(fact)))
                raws=[owner.original(ref)['originals'] for ref in owner.state['records']]
                self.assertTrue(any(raw['qmlSources'] is not None for raw in raws))
                for raw in raws:
                    self.assertEqual(4,raw['view']['chatViewVersion'])
                    for entry in raw['qmlEntryBindings']:
                        self.assertTrue(entry['imageBytesBound']);self.assertFalse(entry['qtSdkSourceAvailable'])
                        self.assertFalse(entry['importGraphAvailable']);self.assertFalse(entry['aotGraphAvailable'])
        self.assertEqual(files,self.f.pair.census());self.assertEqual(queries,self.query_census());self.assertEqual(commands,self.f.pair.commands())
    def test_literal_seven_and_eight_cannot_adopt_loaded_symmetric_journals(self):
        self.make();self.f.open();files=self.f.pair.census();queries=self.query_census()
        for role in ('primary','peer'):
            draft=self.f.drafts[role]
            with self.subTest(role=role),self.assertRaises(NativeUIError):
                IOSChatDraftOwner.archive(draft.f.store,draft.f.root,draft.binding,draft.run,draft.f.lock,
                    draft.m.owner.fixture_url,source_bound=True,peer_actor=role=='peer',peer_receipts=self.loaded.contexts[role])
        primary=self.f.drafts['primary']
        with self.assertRaises(NativeUIError):
            IOSChatDraftOwner.archive(primary.f.store,primary.f.root,primary.binding,primary.run,primary.f.lock,
                primary.m.owner.fixture_url,source_bound=True,qml_bound=True,qml_artifact=self.loaded.artifacts['primary'])
        self.assertEqual(files,self.f.pair.census());self.assertEqual(queries,self.query_census())
    def test_foreign_loaded_entry_bytes_refuse_before_normal_primary_send(self):
        self.make();self.f.open();self.f.type('primary',token='unicode');model=self.f.models['primary'];inputs=deepcopy(model.widgets.calls)
        def foreign(value):value['qtDependencyEntryImage']['symbolFileOffset']='400'
        model.qml_fault=foreign
        with self.assertRaises((ValueError,NativeUIError)):
            IOSChatSendOperation(self.f.receive,self.f.drafts['primary'].owner).send(model.ticket)
        self.assertEqual(inputs,model.widgets.calls);self.assertEqual(0,len(model.source['chatSends']))
    def test_lost_saved_loaded_incoming_frame_recovers_exact_original_without_query_or_send_replay(self):
        self.make();self.f.open();fact=self.send('peer','reply');draft=self.f.drafts['primary'];store=draft.f.store;write=store.write
        def lost(value,previous):
            result=write(value,previous);observation=unpack(value['payload'])[0]['observation']
            if observation is not None and observation['wire'] is not None and observation['wire']['phase']=='saved':
                raise OSError('Declared lost saved QML-bound incoming frame return')
            return result
        with patch.object(store,'write',side_effect=lost),self.assertRaises(OSError):self.receive('primary',fact)
        wire=unpack(store.read()['payload'])[0]['observation']['wire'];path=draft.m.owner.frames.path(wire)
        before=(path.stat().st_dev,path.stat().st_ino,path.read_bytes());queries=self.query_census();result=self.receive('primary',fact)
        self.assertEqual(wire['index'],result['original']['index']);self.assertEqual(queries,self.query_census())
        self.assertEqual(before,(path.stat().st_dev,path.stat().st_ino,path.read_bytes()));self.assertEqual(1,len(self.f.models['peer'].source['chatSends']))

class ChatLoadedPeerProfileTests(unittest.TestCase):
    def test_explicit_combination_versions_and_literal_profiles_remain_closed(self):
        profiles={3:(False,False,False,False),4:(True,False,False,False),5:(True,True,False,False),
            6:(True,False,True,False),7:(True,True,True,False),8:(True,False,False,True),
            9:(True,False,True,True),10:(True,True,False,True),11:(True,True,True,True)}
        for version,flags in profiles.items():
            options=dict(zip(('source_bound','peer_actor','peer_receipts','qml_bound'),flags))
            self.assertEqual(version,IOSChatDraftOwner.read_version(None,**options))
            self.assertEqual(version,IOSChatDraftOwner.read_version(dict(iosChatDraftOwnerVersion=version),**options))
            for other in profiles:
                if other==version:continue
                with self.subTest(version=version,other=other),self.assertRaises(NativeUIError):
                    IOSChatDraftOwner.read_version(dict(iosChatDraftOwnerVersion=other),**options)
        for version in (1,2):self.assertEqual(version,IOSChatDraftOwner.read_version(dict(iosChatDraftOwnerVersion=version)))
        for flags in ((False,True,False,False),(False,False,True,False),(False,False,False,True)):
            with self.assertRaises(NativeUIError):IOSChatDraftOwner.read_version(None,**dict(zip(('source_bound','peer_actor','peer_receipts','qml_bound'),flags)))
