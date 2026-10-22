"""Real editable-byte hashes, modeled import/Qt clocks; native uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
import uuid

from adapters.native_clock_join import digest
from adapters.native_scene_loads import resource_hash
from adapters.normal_ui import NativeUIError
from ios.adapters import scene_inventory as inventory
from ios.self_tests.test_ios_scene_inventory import Boundary as Inventory,IDS
from ios.self_tests.test_ios_navigation_state import RUN,URL


class Boundary(Inventory):
    def __init__(self):
        super().__init__();self.commits=0;self.generation=0;self.loads=[];self.anchor=None;self.origin_complete=True
        self.body=(Path(__file__).resolve().parents[2]/'fixture'/'scene.json').read_bytes();self.commit()
    def commit(self):
        self.clock+=.001;before=self.clocks()
        # This is the SDK model's actual import event, independently captured
        # BEFORE any query. Later reads cannot select a new baseline map.
        rows=[dict(id=id_,hostType='domain',ready=True,createdEpochUs=self.created,lastEditedEpochUs=self.edited,
            lastEditedAfterEpochUs=self.edited,semanticBytes=len(raw),semanticSha256=hashlib.sha256(raw).hexdigest())
            for id_,raw in sorted(self.raw.items())]
        original_tree=dict(entityInventoryVersion=1,profile=inventory.PROFILE,treeInstance='e'*32,
            revisionBefore=self.revision,revisionAfter=self.after_revision,totalEntities=len(rows),complete=True,entities=rows)
        self.clock+=.001;self.commits+=1;self.generation+=1
        self.anchor=dict(generation=self.generation,resourceSha256=resource_hash(self.url),bodyBytes=len(self.body),
            bodySha256=hashlib.sha256(self.body).hexdigest(),clockBefore=before,clockAfter=self.clocks(),tree=original_tree)
        self.loads.append(dict(id=uuid.uuid4().hex,kind='request',generation=self.generation,resourceSha256=resource_hash(self.url),
            startedEpochMs=before['epochMs']-1,updatedEpochMs=self.epoch(),releasedEpochMs=self.epoch(),
            phase='committed',pending=False,result=0,bytes=len(self.body)))
    def original(self):
        mutate=self.mutate;self.mutate=None
        try:value=json.loads(super().original())
        finally:self.mutate=mutate
        value['iosSceneInventoryVersion']=2
        value['source']['commitOrigin']=dict(iosSceneCommitOriginVersion=1,instance='b'*32,processId=42,
            currentGeneration=self.generation,commits=self.commits,complete=self.origin_complete,latest=deepcopy(self.anchor))
        value['source']['sceneLoads'].update(currentGeneration=self.generation,requests=deepcopy(self.loads))
        if mutate:mutate(value)
        self.last=deepcopy(value);return json.dumps(value)


class SceneCommitOriginTests(unittest.TestCase):
    def setUp(self):self.source=Boundary()
    def read(self):return self.source.reader().read(RUN)

    def test_original_import_map_body_and_native_clocks_precede_the_current_observation(self):
        value=self.read();before=deepcopy(value);anchor=inventory.unchanged_since_commit(value,URL)
        self.assertEqual(self.source.anchor,anchor);self.assertEqual(before,value)
        self.assertEqual(hashlib.sha256(self.source.body).hexdigest(),anchor['bodySha256'])
        self.assertLess(anchor['clockAfter']['epochMs'],value['clockBefore']['epochMs'])
        self.assertNotIn('passed',anchor);anchor['tree']['entities'].clear()
        self.assertEqual(before,value)

    def test_unsaved_edit_addition_removal_and_same_count_replacement_are_detected_before_leaving(self):
        for fault in ('edit','add','remove','replace'):
            source=Boundary();original=deepcopy(source.anchor)
            if fault=='edit':source.raw[IDS[1]]=b'actual unsaved edit'
            elif fault=='add':source.raw['00000000-0000-4000-8000-000000000003']=b'new unowned entity'
            elif fault=='remove':del source.raw[IDS[1]]
            else:del source.raw[IDS[1]];source.raw['00000000-0000-4000-8000-000000000003']=b'faraway unowned entity properties'
            source.revision=source.after_revision=3;value=source.reader().read(RUN)
            self.assertEqual(original,value['source']['commitOrigin']['latest'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):inventory.unchanged_since_commit(value,URL)

    def test_notification_and_creation_edit_times_do_not_replace_declared_editable_semantics(self):
        original=deepcopy(self.source.anchor);self.source.revision=self.source.after_revision=10
        self.source.edited='1700000099999000';self.source.created='18446744073709551615'
        value=self.read();self.assertEqual(original,inventory.unchanged_since_commit(value,URL))
        self.assertEqual('18446744073709551615',value['source']['tree']['entities'][0]['createdEpochUs'])

    def test_current_legacy_inventory_cannot_claim_a_commit_anchor_or_unsaved_edit_safety(self):
        source=Inventory();value=source.reader().read(RUN)
        self.assertEqual(1,value['iosSceneInventoryVersion'])
        with self.assertRaises(NativeUIError):inventory.unchanged_since_commit(value,URL)

    def test_missing_partial_or_failed_commit_context_cannot_establish_an_unchanged_world(self):
        for fault in ('missing','partial','failed','body','generation','resource','release','foreign-url'):
            value=self.read();origin=value['source']['commitOrigin'];latest=origin['latest']
            if fault=='missing':origin.update(commits=0,latest=None)
            elif fault=='partial':latest['tree']['complete']=False;origin['complete']=False
            elif fault=='failed':origin['complete']=False
            elif fault=='body':latest['bodyBytes']+=1
            elif fault=='generation':origin['currentGeneration']=value['source']['sceneLoads']['currentGeneration']=2
            elif fault=='resource':latest['resourceSha256']='f'*64
            elif fault=='release':latest['clockAfter']['epochMs']+=1;latest['clockAfter']['monotonicMs']+=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):
                inventory.unchanged_since_commit(value,URL if fault!='foreign-url' else 'http://foreign.invalid/scene.json')

    def test_forged_clock_process_tree_birth_digest_or_native_version_is_rejected(self):
        for fault in ('pid','tree','bodySha','future','clockDrift','version','commits','unknown'):
            source=Boundary()
            def change(value):
                origin=value['source']['commitOrigin'];latest=origin['latest']
                if fault=='pid':origin['processId']=43
                elif fault=='tree':latest['tree']['treeInstance']='f'*32
                elif fault=='bodySha':latest['bodySha256']='a'*63
                elif fault=='future':latest['clockAfter']['epochMs']=value['clockAfter']['epochMs']+1
                elif fault=='clockDrift':latest['clockAfter']['monotonicMs']+=500
                elif fault=='version':origin['iosSceneCommitOriginVersion']=True
                elif fault=='commits':origin['commits']=129
                else:latest['expectedUnchanged']=True
            source.mutate=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_same_import_cannot_rewrite_its_old_body_map_clock_or_source_birth(self):
        for fault in ('body','map','clock','birth','counter','resurrect'):
            source=Boundary();reader=source.reader();old=reader.read(RUN)
            if fault=='resurrect':
                source.origin_complete=False;old=reader.read(RUN);source.origin_complete=True
            def change(value):
                origin=value['source']['commitOrigin'];latest=origin['latest']
                if fault=='body':latest['bodySha256']='f'*64
                elif fault=='map':latest['tree']['entities'][0]['semanticSha256']='f'*64
                elif fault=='clock':latest['clockBefore']['epochMs']+=1;latest['clockBefore']['monotonicMs']+=1
                elif fault=='birth':origin['instance']='f'*32
                elif fault=='counter':origin['commits']=0
            source.mutate=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(old,reader.last)

    def test_historical_original_is_not_refreshed_or_rebased_when_product_changes(self):
        original=self.read();hash_before=digest(original);self.source.raw[IDS[1]]=b'changed later';self.source.clock+=100
        self.assertEqual(self.source.anchor,inventory.unchanged_since_commit(original,URL))
        self.assertEqual(hash_before,digest(original))
        with self.assertRaises(NativeUIError):inventory.unchanged_since_commit(self.read(),URL)

    def test_a_real_later_import_advances_origin_and_preserves_the_original_native_request_history(self):
        reader=self.source.reader();before=reader.read(RUN);original=deepcopy(before)
        self.source.raw[IDS[1]]=b'actual next imported editable state';self.source.revision=self.source.after_revision=3
        self.source.body=b'actual next source bytes';self.source.commit();after=reader.read(RUN)
        latest=inventory.unchanged_since_commit(after,URL)
        self.assertEqual(2,latest['generation']);self.assertEqual(hashlib.sha256(self.source.body).hexdigest(),latest['bodySha256'])
        self.assertEqual(before['source']['sceneLoads']['requests'],after['source']['sceneLoads']['requests'][:-1])
        self.assertEqual(original,before);self.assertNotEqual(before['source']['commitOrigin']['latest'],latest)

    def test_later_import_cannot_retire_old_clocks_or_invent_more_commits_than_request_generations(self):
        for fault in ('utc','monotonic','count'):
            source=Boundary();reader=source.reader();old=reader.read(RUN);source.commit()
            def change(value):
                origin=value['source']['commitOrigin'];latest=origin['latest'];previous=old['source']['commitOrigin']['latest']
                if fault=='count':
                    origin['commits']=3;latest['generation']=origin['currentGeneration']=3
                    value['source']['sceneLoads']['currentGeneration']=3;value['source']['sceneLoads']['requests'][-1]['generation']=3
                else:
                    field='epochMs' if fault=='utc' else 'monotonicMs'
                    shift=latest['clockBefore'][field]-previous['clockAfter'][field]+1
                    for key in ('clockBefore','clockAfter'):latest[key][field]-=shift
            source.mutate=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)

