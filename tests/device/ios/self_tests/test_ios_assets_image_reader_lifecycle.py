"""Closed History2 + full observed lifecycle counterexamples; declared SDK model.

These tests execute host codecs and real Python weak lifetimes. No C++/Qt/GPU
execution or automatic product cleanup/whole Resource retirement is claimed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import assets_image_reader_queue as queue,assets_image_reader_lifecycle as lifecycle
from ios.self_tests.assets_image_reader_lifecycle_boundary_fixture import Boundary
from ios.self_tests.assets_image_reader_queue_fixture import Boundary as LiteralBoundary,Holder,RUN


class AssetsImageReaderLifecycleTests(unittest.TestCase):
    def closed(self):
        b=Boundary();b.close_owned();return b,b.read()
    def join(self,packets):return lifecycle.linked_closed(*packets,'1'*32)

    def test_actual_native_sharing_ids_close_observed_edges_without_storage_or_gpu_completion(self):
        b,packets=self.closed();facts=self.join(packets)
        self.assertEqual(['9'*32],facts['sourceIds']);self.assertEqual([1],facts['queuedEventIds'])
        self.assertTrue(facts['observedDerivedMarkersAndQtArgumentCopiesGone'])
        self.assertTrue(facts['allObservedGpuSharingOwnersGone'])
        for key in ('decoderCompletionAvailable','destructorCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable'):
            self.assertIs(False,facts[key])

    def test_independent_gpu_holder_survives_source_and_marker_and_blocks_until_actual_release(self):
        b=Boundary();b.close_owned(keep_gpu=True);packets=b.read()
        self.assertFalse(packets[1]['source']['tasks'][0]['sourceOwnersAlive'])
        self.assertFalse(packets[1]['source']['tasks'][0]['derivedMarkerAlive'])
        with self.assertRaises(NativeUIError):self.join(packets)
        b.gpu=None;gc.collect();self.join(b.read())

    def test_slot_return_does_not_destroy_held_event_argument_values(self):
        b=Boundary();task=b.images.create();gpu=Holder();b.images.invoke(task,gpu);b.images.finish(task)
        event=b.images.parent.queue.pop();event.deliver(destroy=False)
        del gpu;del task;b.close_owned()
        held=b.read();self.assertIsNotNone(held[0]['source']['entries'][-1]['receiverReturned'])
        with self.assertRaises(NativeUIError):self.join(held)
        event.destroy_arguments();del event;gc.collect();self.join(b.read())

    def test_selected_undispatched_task_cannot_disappear_behind_dispatch_only_table(self):
        b=Boundary();pending=b.add_task(selected=True);b.close_owned()
        packets=b.read();self.assertEqual(2,len(packets[0]['source']['taskTextureSources']))
        self.assertEqual(1,len(packets[0]['source']['entries']))
        with self.assertRaises(NativeUIError):self.join(packets)
        b.images.parent.phase(pending,'runEntered');b.images.parent.phase(pending,'readEntered')
        b.images.finish(pending);del pending;gc.collect();self.join(b.read())

    def test_positive_nonempty_unmatched_foreign_task_is_excluded_even_while_it_is_alive(self):
        b=Boundary();foreign=b.add_task();b.close_owned();packets=b.read()
        row=packets[0]['source']['taskTextureSources'][-1]
        self.assertEqual(('unmatched',''),(row['textureSourceState'],row['textureSourceId']))
        self.assertTrue(packets[1]['source']['tasks'][-1]['derivedMarkerAlive'])
        facts=self.join(packets);self.assertNotIn(foreign.id,facts['taskIds'])

    def test_empty_weak_owner_metadata_is_not_unmatched_or_expired_selected_source(self):
        b=Boundary();foreign=b.add_task(unknown=True);b.close_owned();packets=b.read()
        self.assertEqual('empty',packets[0]['source']['taskTextureSources'][-1]['textureSourceState'])
        with self.assertRaises(NativeUIError):self.join(packets)
        del foreign

    def test_h5_revision_change_after_native_unmatched_lookup_requires_new_actual_original(self):
        b=Boundary();foreign=b.add_task();b.close_owned();packet,parent,origin=b.read()
        origin['source']['history']['textureOwnership']['revision']+=1
        with self.assertRaises(NativeUIError):queue.texture_links(packet,parent,origin,'1'*32)
        del foreign

    def test_receiver_of_other_producer_on_selected_resource_is_not_hidden_by_queue_entries(self):
        b=Boundary();b.images.parent.receive(b.gpu);b.close_owned();packets=b.read()
        self.assertEqual(2,len(packets[0]['source']['receiverTextureSources']))
        self.assertEqual(1,len(packets[0]['source']['entries']))
        with self.assertRaises(NativeUIError):self.join(packets)

    def test_later_source1_task_or_receiver_prefix_cannot_be_silently_omitted(self):
        for fault in ('task','receiver'):
            b=Boundary();packet=b.reader.read(RUN,source1=b.parent)
            if fault=='task':later=b.add_task()
            else:b.images.parent.receive(b.gpu)
            parent=b.parent.read(RUN);b.model.time=b.elapsed;origin=b.origin.read(RUN)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.join((packet,parent,origin))

    def test_exact_identity_not_url_payload_or_expected_model_hash_selects_source_groups(self):
        for fault in ('task-source','receiver-source','h5-instance','source1-instance','reader','resource'):
            b,packets=self.closed();packet,parent,origin=deepcopy(packets);reader='1'*32
            if fault=='task-source':packet['source']['taskTextureSources'][0]['textureSourceId']='7'*32
            elif fault=='receiver-source':packet['source']['receiverTextureSources'][0]['textureSourceId']='7'*32
            elif fault=='h5-instance':packet['source']['originTextureReference']['instance']='7'*32
            elif fault=='source1-instance':packet['source']['source1Instance']='7'*32
            elif fault=='reader':reader='7'*32
            else:packet['source']['taskTextureSources'][0]['resourceId']='7'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):queue.texture_links(packet,parent,origin,reader)

    def test_closed_history2_shapes_states_and_foreign_fields_are_strict(self):
        for fault in ('bool-version','unknown','empty-matched','named-unmatched','null-unmatched','state','duplicate-task',
                'duplicate-receiver','receiver-not-observed','source1-ref','h5-ref','revision-bool','lookup-before-queue','receiver-cap'):
            b,packets=self.closed();packet=deepcopy(packets[0]);h=packet['source'];task=h['taskTextureSources'][0]
            if fault=='bool-version':h['assetImageReaderQueueHistoryVersion']=True
            elif fault=='unknown':task['wantedResourceHash']='f'*64
            elif fault=='empty-matched':task['textureSourceId']=''
            elif fault=='named-unmatched':task['textureSourceState']='unmatched'
            elif fault=='null-unmatched':task.update(textureSourceState='unmatched',textureSourceId=None)
            elif fault=='state':task['textureSourceState']='expired-means-unrelated'
            elif fault=='duplicate-task':h['taskTextureSources'].append(deepcopy(task))
            elif fault=='duplicate-receiver':h['receiverTextureSources']*=2
            elif fault=='receiver-not-observed':h['entries'][0]['receiverTextureSourceState']='not-observed'
            elif fault=='source1-ref':h['source1TextureReference']['instance']='7'*32
            elif fault=='h5-ref':h['originTextureReference']['clockDomain']='native-assets-image-reader-observer'
            elif fault=='revision-bool':h['originTextureReference']['revision']=True
            elif fault=='lookup-before-queue':h['source1TextureReference']['clock']['epochMs']=h['clock']['epochMs']-1
            else:h['receiverTextureSources']*=257
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):queue.original(packet)

    def test_literal_history1_is_readable_and_cannot_be_in_place_upgraded_into_identity_authority(self):
        b=LiteralBoundary();task=b.create();gpu=Holder();b.invoke(task,gpu);b.finish(task);b.parent.deliver()
        r=b.reader();literal=r.read(RUN,source1=b.parent.reader());queue.original(literal)
        _,packets=self.closed()
        with self.assertRaises(NativeUIError):queue.successor(literal['source'],packets[0]['source'])
        with self.assertRaises(NativeUIError):queue.texture_links(literal,r.parent_original,packets[2],'1'*32)

    def test_unmatched_attachment_needs_higher_revision_and_matched_owner_cannot_rebind(self):
        b,packets=self.closed();history=packets[0]['source']
        for fault in ('same-revision','rebind','erase','empty-heal'):
            old=deepcopy(history);new=deepcopy(history)
            if fault=='same-revision':old['taskTextureSources'][0].update(textureSourceState='unmatched',textureSourceId='')
            elif fault=='rebind':new['taskTextureSources'][0]['textureSourceId']='7'*32
            elif fault=='erase':new['taskTextureSources'][0].update(textureSourceState='unmatched',textureSourceId='')
            else:old['taskTextureSources'][0].update(textureSourceState='empty',textureSourceId='')
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):queue.successor(old,new)
        old=deepcopy(history);old['taskTextureSources'][0].update(textureSourceState='unmatched',textureSourceId='')
        new=deepcopy(history);new['originTextureReference']['revision']+=1
        queue.successor(old,new)

    def test_pure_original_join_performs_no_query_input_write_process_or_socket_effect(self):
        b,packets=self.closed();saved=deepcopy(packets)
        with (patch.object(b.reader,'read',side_effect=AssertionError('query')),
                patch.object(b.parent,'read',side_effect=AssertionError('parent query')),
                patch('subprocess.Popen',side_effect=AssertionError('process')),
                patch('socket.socket',side_effect=AssertionError('socket'))):
            self.join(packets)
        self.assertEqual(saved,packets)

    def test_native_weak_bridge_source_keeps_material_atomic_health_and_non_nested_locks(self):
        # Source shape only. This cannot establish C++ build or runtime behavior.
        from pathlib import Path
        root=Path(__file__).resolve().parents[4]
        origin=(root/'tests/device/native/IOSAssetsModelOrigin.h').read_text()
        source1=(root/'tests/device/native/IOSAssetsImageReaderObservation.h').read_text()
        bridge=(root/'libraries/material-networking/src/material-networking/IOSAssetsImageReaderQueueObservation.cpp').read_text()
        lookup=origin.split('QVariantMap textureSources(',1)[1].split('void textureIncomplete()',1)[0]
        self.assertIn('source.owner_before(empty) || empty.owner_before(source)',lookup)
        self.assertIn('graphics::Material::featureAssetsTextureObservationComplete()',lookup)
        self.assertIn('QString selected=QStringLiteral("");',lookup)
        self.assertIn('QString selected=QStringLiteral(""),state=QStringLiteral("not-observed");',bridge)
        self.assertNotIn('.lock()',lookup);self.assertNotIn('getTexture',lookup);self.assertNotIn('requestedUrl',lookup)
        self.assertIn('for (const auto& task:owner.tasks)',source1)
        self.assertIn('for (const auto& receiver:owner.receivers)',source1)
        self.assertLess(bridge.index('// Release Bridge BEFORE Source1'),bridge.index('textureSourceContexts()'))
        self.assertLess(bridge.index('textureSourceContexts()'),bridge.index('shared().textureSources(sources)'))
        self.assertIn('actual.source.owner_before(receiverSources[index])',bridge)
        self.assertIn('receiverSources[index].owner_before(actual.source)',bridge)

    def test_positive_unmatched_foreign_receiver_is_not_a_selected_resource_consumer(self):
        b=Boundary();foreign=b.add_task();b.images.parent.receive(b.gpu);b.close_owned();packets=b.read()
        row=packets[0]['source']['receiverTextureSources'][-1]
        self.assertEqual('unmatched',row['textureSourceState'])
        facts=self.join(packets);self.assertNotIn(row['receiverId'],facts['receiverIds'])
        self.assertNotIn(foreign.id,facts['taskIds'])

    def test_late_actual_sharing_group_attachment_expands_selection_and_preserves_pending_task(self):
        import weakref
        b=Boundary();foreign=b.add_task();actual=b.resources[-1].source;token=actual._sharing_owner_token
        source_weak=weakref.ref(actual);del actual
        first=b.read();self.assertNotIn(foreign.id,queue.texture_links(*first,'1'*32)['taskIds'])
        inventory=b.model.state['history']['textureOwnership'];birth=b.texture_stamp()
        inventory['revision']=b.texture_revision=3
        inventory['nodes'].append(dict(id='7'*32,kind='source',born=deepcopy(birth),strongOwnersAlive=True,ownershipExpiryObserved=None))
        inventory['links'].append(dict(deepcopy(inventory['links'][0]),id='6'*32,channel=1,sourceId='7'*32,
            born=deepcopy(birth),lastObserved=deepcopy(birth),revision=3))
        b.source_owner_ids[token]='7'*32;original=b.model.mutate;death=[]
        def observe(packet):
            original(packet);row=packet['source']['history']['textureOwnership']['nodes'][-1]
            row['strongOwnersAlive']=source_weak() is not None
            if not row['strongOwnersAlive']:
                if not death:death.append(deepcopy(packet['source']['history']['clock']))
                row['ownershipExpiryObserved']=deepcopy(death[0])
        b.model.mutate=observe;b.close_owned();later=b.read()
        self.assertIn(foreign.id,queue.texture_links(*later,'1'*32)['taskIds'])
        self.assertEqual('unmatched',first[0]['source']['taskTextureSources'][-1]['textureSourceState'])
        self.assertEqual('matched',later[0]['source']['taskTextureSources'][-1]['textureSourceState'])
        self.assertIsNone(later[1]['source']['tasks'][-1]['runEntered'])
        with self.assertRaises(NativeUIError):self.join(later)
