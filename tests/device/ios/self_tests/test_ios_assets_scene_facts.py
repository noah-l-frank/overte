"""Independent world/parser aliases and honest unqualified rendered pixels."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_scene_facts import scene,peer_model
from ios.self_tests.assets_scene_facts_fixture import pair,reseal


class AssetsSceneFactsTests(unittest.TestCase):
    def test_independent_actual_peer_and_each_original_parser_body_keep_pixels_and_retirement_unavailable(self):
        primary,peer,lineage=pair();before=deepcopy((primary,peer,lineage));proof=peer_model(primary,peer,lineage)
        self.assertEqual(lineage['entityId'],proof['entityId']);self.assertEqual(lineage['sha256'],proof['sha256'])
        self.assertNotEqual(proof['primaryReaderId'],proof['peerReaderId']);self.assertFalse(proof['renderedPixelsAvailable']);self.assertFalse(proof['resourceRetirementAvailable'])
        self.assertEqual(before,(primary,peer,lineage))

    def test_target_process_native_instance_session_or_mixer_alias_is_not_independent_actor(self):
        for fault in ('target','pid','instance','session','mixer'):
            primary,peer,lineage=pair()
            if fault=='target':peer['binding']['targetFingerprint']=primary['binding']['targetFingerprint']
            elif fault=='pid':peer['binding']['processIdentity']='42'
            elif fault=='instance':peer['originals']['createAfter']['instance']=primary['originals']['createAfter']['instance']
            elif fault=='session':peer['originals']['createAfter']['source']['localSessionId']=primary['originals']['createAfter']['source']['localSessionId']
            else:peer['originals']['domain']['source']['domain']['avatarMixerSha256']='e'*64
            reseal(peer)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):peer_model(primary,peer,lineage)

    def test_peer_requested_url_or_loaded_wrapper_without_matching_original_consumed_bytes_is_not_qualified(self):
        for fault in ('body','delivery','reader','history','loaded','model-url'):
            primary,peer,lineage=pair();origin=peer['originals']['origin'];row=origin['source']['history']['downloads'][0]
            if fault=='body':
                raw=b'actual independent foreign parser body';row.update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
            elif fault=='delivery':row['deliveryReturned']=None
            elif fault=='reader':row['id']=primary['originals']['origin']['source']['history']['downloads'][0]['id'];origin['source']['models'][0]['origin']['geometry']['readerId']=row['id']
            elif fault=='history':origin['source']['history']['instance']=primary['originals']['origin']['source']['history']['instance']
            elif fault=='loaded':origin['source']['models'][0]['loaded']=False
            else:origin['source']['models'][0]['origin']['modelUrl']='atp:/foreign/model.fbx'
            reseal(peer)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):peer_model(primary,peer,lineage)

    def test_clock_relabel_incomplete_tree_or_foreign_owner_cannot_become_original_actor_fact(self):
        for fault in ('clock','digest','tree','owner','role'):
            primary,peer,lineage=pair()
            if fault=='clock':peer['clockJoin']['hostAfterEpochMs']+=1000
            elif fault=='digest':peer['originals']['origin']['source']['models'][0]['loaded']=False
            elif fault=='tree':peer['originals']['createAfter']['source']['tree']['complete']=False;reseal(peer)
            elif fault=='owner':peer['originals']['createAfter']['source']['entities'][0]['lastEditedBy']=peer['originals']['createAfter']['source']['localSessionId'];reseal(peer)
            else:peer['role']='actor-primary'
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):peer_model(primary,peer,lineage)
