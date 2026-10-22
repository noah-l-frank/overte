"""Independent process/target and actual entity/renderer Create counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import hashlib
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters.create_peer import project_actor,replicated,domains
from ios.self_tests.test_ios_create_state import packet,version2,add_model,add_editor,remap,RUN,ID
from ios.self_tests.test_ios_create_files import BINDING
from ios.self_tests.test_ios_emote_world import packet as domain_packet

PEER_BINDING=BINDING|dict(targetFingerprint='a'*64,sessionId='peer-session',processIdentity='43')


def pair():
    primary=version2(packet());add_model(primary);version2(primary);add_editor(primary,selected=[ID])
    peer=deepcopy(primary);peer.update(instance='e'*32,processId=43);peer['source']['localSessionId']='55555555-5555-4555-8555-555555555555';peer['source']['roots']=[]
    return primary,peer


def domain_pair(primary,peer):
    result=[]
    for state in (primary,peer):
        value=domain_packet(state['processId']);offset=state['clockAfter']['epochMs']-20000
        def shift(item):
            if type(item) is dict:
                for key,child in item.items():
                    if (key.endswith('EpochMs') or key=='epochMs') and type(child) is int and child>0:item[key]+=offset
                    else:shift(child)
            elif type(item) is list:
                for child in item:shift(child)
        shift(value);value['runId']=state['runId'];value['source']['markers']=[]
        value['source']['tree']=deepcopy(state['source']['tree'])
        value['source']['domain'].update(domainId=state['source']['domainId'],selfSha256=hashlib.sha256(uuid.UUID(state['source']['localSessionId']).bytes).hexdigest())
        result.append(value)
    return result


class CreatePeerTests(unittest.TestCase):
    def test_actor_reads_primary_ui_independently_and_world_results_from_distinct_peer(self):
        primary,peer=pair();state=project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))
        self.assertEqual(['model'],state['objects']);self.assertTrue(state['editor']);self.assertEqual(['model'],state['selection'])
        self.assertEqual([],peer['source']['roots']);self.assertFalse(any('performed' in row for row in replicated(primary,peer,[ID],BINDING,PEER_BINDING)))

    def test_target_alias_source_alias_local_only_entity_and_creator_mismatch_are_not_replication(self):
        for fault in ('target','instance','self','domain','missing','host','creator','position','name','loaded','permission'):
            primary,peer=pair();binding=deepcopy(PEER_BINDING);row=peer['source']['entities'][0]
            if fault=='target':binding['targetFingerprint']=BINDING['targetFingerprint']
            elif fault=='instance':peer['instance']=primary['instance']
            elif fault=='self':peer['source']['localSessionId']=primary['source']['localSessionId']
            elif fault=='domain':peer['source']['domainId']='99999999-9999-4999-8999-999999999999'
            elif fault=='missing':peer['source']['entities']=[];peer['source']['tree'].update(entities=[],totalEntities=0)
            elif fault=='host':row['hostType']='local';peer['source']['tree']['entities'][0]['hostType']='local'
            elif fault=='creator':row['lastEditedBy']=peer['source']['localSessionId']
            elif fault=='position':row['position'][0]+=1
            elif fault=='name':row['name']='unrelated-object'
            elif fault=='loaded':row['model']['loaded']=False
            else:peer['source']['canRez']=peer['source']['canRezTmp']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):project_actor(primary,peer,RUN,[ID],BINDING,binding,domain_originals=domain_pair(primary,peer))

    def test_local_remap_or_requested_texture_without_original_peer_consumption_is_not_remote_effect(self):
        primary,peer=pair();remap(primary['source']['entities'][0])
        with self.assertRaises(NativeUIError):project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))
        remap(peer['source']['entities'][0]);self.assertTrue(project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))['textured'])
        peer['source']['entities'][0]['model']['textures'][0]['original']['consumptions']=[]
        with self.assertRaises(NativeUIError):project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))

    def test_stale_serverless_disconnected_or_foreign_mixer_original_cannot_prove_domain_peer(self):
        for fault in ('stale','serverless','disconnected','mixer','self','tree'):
            primary,peer=pair();originals=domain_pair(primary,peer)
            if fault=='stale': originals[1]['clockAfter']['epochMs']-=2000
            elif fault=='serverless':originals[1]['source']['domain']['serverless']=True
            elif fault=='disconnected':originals[1]['source']['domain']['connected']=False
            elif fault=='mixer':originals[1]['source']['domain']['avatarMixerSha256']='c'*64
            elif fault=='self':originals[1]['source']['domain']['selfSha256']=originals[0]['source']['domain']['selfSha256']
            else:originals[1]['source']['tree']['entities'][0]['semanticSha256']='d'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=originals)

    def test_deletion_requires_actual_absence_in_both_processes(self):
        primary,peer=pair();primary['source']['entities']=[];primary['source']['tree'].update(entities=[],totalEntities=0)
        primary['source']['roots'][0]['page']['selectedIds']=[]
        with self.assertRaises(NativeUIError):project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))
        peer['source']['entities']=[];peer['source']['tree'].update(entities=[],totalEntities=0)
        self.assertEqual([],project_actor(primary,peer,RUN,[ID],BINDING,PEER_BINDING,domain_originals=domain_pair(primary,peer))['objects'])


if __name__=='__main__':unittest.main()
