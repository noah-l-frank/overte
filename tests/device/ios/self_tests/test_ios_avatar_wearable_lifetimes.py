"""Ordinary Avatar recipes plus genuine host weak-retention counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.adapters.avatar_cleanup_sources import wearable_lifetimes
from ios.self_tests import test_ios_avatar_observation as appearance_fixture
from ios.self_tests import test_ios_avatar_entities as entity_fixture
from ios.self_tests import test_ios_create_entities as tree_fixture


class AvatarWearableLifetimesTests(unittest.TestCase):
    def setUp(self):
        self.appearance=appearance_fixture.AvatarObservationTests();self.appearance.setUp();self.addCleanup(self.appearance.doCleanups)
        a=self.appearance;f=a.fixture.fixture;self.native=tree_fixture.NativeBoundary();native=self.native
        native.tree_instance=a.fixture.source.frames[0]['originals']['renderers']['source']['tree']['treeInstance']
        def epoch():native.now=f.now();return native.now
        native.tick=epoch;send=native.send
        def sending(query):send(query);native.packet['runId']=query['runId']
        native.send=sending;self.reader=native.reader();self.before=self.reader.read(f.run)
        post=f.widget.post
        def transported(request,timeout):
            previous=f.widget.wearable_id;result=post(request,timeout);current=f.widget.wearable_id
            if current is not None and current!=previous:
                actual=f.prototypes['entities']['source']['events'][-1]
                native.manager=deepcopy(actual['caller']['manager']);native.code=deepcopy(actual['caller']['code'])
                native.call_sequence=actual['caller']['sequence']-1;self.assertEqual(current,native.add(id_=current))
                self.held=native.items[current]
            elif previous is not None and current is None:
                # Bookmark application clears the actual entity through a
                # native setter: no script deleteEntity return is fabricated.
                item=native.items.pop(previous)
                for weak,row in native.rows:
                    if weak() is item:native.tree_event('removed',row)
            return result
        seam=patch.object(normal_input,'urlopen',transported);seam.start();self.addCleanup(seam.stop)
        name='e2e-'+f.run
        for index,(verb,inputs) in enumerate((('avatar-url',dict(resource='avatar-a.fst')),
                ('avatar-bookmark-save',dict(name=name)),('wearable-add',dict(resource='gltf-bundle/main.gltf')),
                ('avatar-bookmark-choose',dict(name=name)),('avatar-restore',{}),('avatar-bookmark-delete',dict(name=name))),1):
            a.act(verb,inputs,index)
    def measure(self,packet):
        a=self.appearance;sources=a.history()
        return wearable_lifetimes(sources,a.baseline,len(sources.frames),self.before,packet,
            fixture_url=a.fixture.fixture.phase.fixture_url,expected_code=entity_fixture.EXPECTED)
    def test_original_return_tree_removal_and_actual_weak_expiry_are_all_required(self):
        f=self.appearance.fixture.fixture;retained=self.reader.read(f.run)
        self.assertFalse(retained['source']['tree']['entities'][0]['destroyed'])
        with self.assertRaises(NativeUIError):self.measure(retained)
        del self.held;gc.collect();gone=self.reader.read(f.run);proof=self.measure(gone)
        self.assertEqual(1,len(proof['owned']));self.assertGreater(proof['endpointEpochMs'],0)
        self.assertTrue(next(iter(proof['owned'].values()))['lifetime']['destroyed'])
        self.assertEqual(['add-returned'],[row['kind'] for row in gone['source']['calls']['events']])
    def test_matching_tree_absence_cannot_replace_original_API_UUID_or_birth_or_exact_caller(self):
        f=self.appearance.fixture.fixture;del self.held;gc.collect();gone=self.reader.read(f.run);self.measure(gone)
        for fault in ('returned-id','caller-sequence','tree-birth','weak-live','incomplete'):
            changed=deepcopy(gone)
            if fault=='returned-id':changed['source']['calls']['events'][0]['entityId']='00000000-0000-4000-8000-000000000001'
            elif fault=='caller-sequence':changed['source']['calls']['events'][0]['caller']['sequence']+=1
            elif fault=='tree-birth':changed['source']['tree']['entities'][0]['bornEpochMs']-=1
            elif fault=='weak-live':changed['source']['tree']['entities'][0].update(destroyed=False,destructionObservedEpochMs=0,destructionObservedMonotonicMs=0)
            else:changed['source']['tree']['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.measure(changed)


if __name__=='__main__':unittest.main()
