"""One original normal TOOLS/stroke/restore/Delete with native CPU originals.

Domain authority, SDK pose, host tree and scene retirement are explicit seams;
this does not qualify the whole Create parent or a device renderer allocation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import hashlib
import unittest
import test_create_polyvox_controls_native as native_controls


class CreateVoxelSourceNativeTests(unittest.TestCase):
    run_original=native_controls.CreatePolyvoxControlsNativeTests.run_original

    def test_normal_tools_original_volume_mesh_timers_restore_delete_and_retained_owner(self):
        from adapters.pico4 import create_entities,create_polyvox_resources
        outputs=self.run_original('create-voxel-source-controls.cpp',('normal','retained-renderer','ignored-controller'))
        for mode,capture in outputs.items():
            raw=capture['raw'];packet=json.loads(raw);history=packet['nativeJoin'];receipts=capture['hostReceipts']
            self.assertEqual(history,[json.loads(line) for line in capture['traceLines']])
            self.assertEqual(len(history),len(receipts))
            for row,receipt,line in zip(history,receipts,capture['traceLines']):
                self.assertEqual(row['sequence'],receipt['sequence'])
                self.assertEqual(hashlib.sha256(line).hexdigest(),receipt['sourceSha256'])
                self.assertGreaterEqual(receipt['capturedHostEpochMs'],row['capturedEpochMs'])
                self.assertLessEqual(receipt['capturedHostEpochMs']-row['capturedEpochMs'],500)
            self.assertGreater(len(history),30);self.assertLessEqual(len(history),512)
            self.assertLessEqual(len(raw.encode()),16*1024*1024)
            self.assertEqual(packet['before'],packet['restored'])
            self.assertEqual(1,len(packet['deleteCommands']));self.assertEqual(1,len(packet['deleteLists']))
            self.assertEqual(list(range(1,len(history)+1)),[row['sequence'] for row in history])
            previous=None;previous_entity=None
            for row in history:
                frame=row['entityFrame']
                create_entities.validate(frame,frame['requestId'],frame['processId'],row['capturedEpochMs'],'a'*32)
                create_entities.continuity(previous_entity,frame);previous_entity=frame
                self.assertEqual(6,frame['source']['createEntitySourceVersion'])
                self.assertEqual(frame['sequence'],row['sequence'])
                self.assertEqual(frame['source'],row['retirementSource'])
                self.assertEqual(frame['source']['polyvoxResources'],row['polyvoxResources'])
                create_polyvox_resources.validate(row['polyvoxResources'],row['capturedEpochMs'])
                if previous:create_polyvox_resources.continuity(previous,row['polyvoxResources'])
                previous=row['polyvoxResources']
                if row['volume'] is not None:create_entities.voxel_source(row['volume'])
            initial=next(row for row in history if row['phase']=='before-local-insert')
            self.assertEqual([],initial['entityFrame']['source']['entities'])
            self.assertEqual([],initial['entityFrame']['source']['localCreations']['events'])
            self.assertTrue(create_entities.retired(initial['entityFrame']['source']))
            before=next(row for row in history if row['phase']=='baseline')
            source=before['entityFrame']['source'];self.assertEqual(1,len(source['entities']))
            self.assertEqual(1,len(source['localCreations']['events']))
            event=source['localCreations']['events'][0];entity=source['entities'][0]
            self.assertEqual(before['entityId'],event['id']);self.assertEqual(event['id'],entity['id'])
            self.assertEqual('PolyVox',event['type']);self.assertEqual('domain',event['hostType'])
            self.assertEqual(source['sessionId'],event['sessionId']);self.assertEqual(source['sessionId'],entity['lastEditedBy'])
            self.assertEqual(event['createdEpochUs'],entity['createdEpochUs'])
            self.assertGreaterEqual(event['observedEpochMs'],initial['entityFrame']['capturedEpochMs'])
            self.assertGreaterEqual(entity['createdEpochUs'],initial['entityFrame']['capturedEpochMs']*1000)
            self.assertEqual(64,before['volume']['nonzero']);self.assertTrue(before['volume']['ready'])
            self.assertGreater(before['volume']['vertices'],0);self.assertGreater(before['volume']['indices'],0)
            self.assertTrue(create_polyvox_resources.joined(before['polyvoxResources'],before['entityId']))
            after=next(row for row in history if row['phase']=='after-original-stroke')
            self.assertEqual(64 if mode=='ignored-controller' else 16,after['volume']['nonzero'])
            self.assertEqual(0 if mode=='ignored-controller' else 1,after['mutationCalls'])
            self.assertTrue(after['volume']['ready'])
            old_values=create_entities.voxel_source(before['volume']);new_values=create_entities.voxel_source(after['volume'])
            if mode=='ignored-controller':
                self.assertEqual(old_values,new_values)
                self.assertEqual(before['volume']['dataBase64'],after['volume']['dataBase64'])
            else:
                self.assertNotEqual(old_values,new_values)
                self.assertTrue(all(new==old or old==255 and new==0 for old,new in zip(old_values,new_values)))
                self.assertGreaterEqual(len(after['polyvoxResources']['meshes']),2)
                self.assertTrue(create_polyvox_resources.joined(after['polyvoxResources'],after['entityId']))
                self.assertEqual(before['polyvoxResources']['bindings'][0]['renderer'],after['polyvoxResources']['bindings'][0]['renderer'])
                self.assertNotEqual(before['polyvoxResources']['bindings'][0]['entityMesh'],after['polyvoxResources']['bindings'][0]['entityMesh'])
                self.assertTrue(any(row['phase']=='volume-ready-before-render' and row['polyvoxResources']['bindings'][0]['renderObservations']>0
                    and not create_polyvox_resources.joined(row['polyvoxResources'],row['entityId']) for row in history))
                self.assertNotEqual(before['volume']['dataBase64'],after['volume']['dataBase64'])
                self.assertTrue(any(timer['invocations']>0 for timer in after['timers']))
                self.assertTrue(all(not timer['alive'] for timer in after['timers']))
            quiet=[row for row in history if row['phase']=='delete-quiet']
            self.assertGreaterEqual(quiet[-1]['capturedEpochMs']-quiet[0]['capturedEpochMs'],3000)
            self.assertGreaterEqual(quiet[-1]['capturedElapsedMs']-quiet[0]['capturedElapsedMs'],3000)
            quiet_sequences={row['sequence'] for row in quiet};host_quiet=[row for row in receipts if row['sequence'] in quiet_sequences]
            self.assertGreaterEqual(host_quiet[-1]['capturedHostMonotonicNs']-host_quiet[0]['capturedHostMonotonicNs'],3_000_000_000)
            self.assertGreaterEqual(host_quiet[-1]['capturedHostEpochMs']-host_quiet[0]['capturedHostEpochMs'],3000)
            self.assertLessEqual(max(b['capturedHostMonotonicNs']-a['capturedHostMonotonicNs'] for a,b in zip(host_quiet,host_quiet[1:])),500_000_000)
            self.assertLessEqual(max(b['capturedElapsedMs']-a['capturedElapsedMs'] for a,b in zip(quiet,quiet[1:])),500)
            self.assertLessEqual(max(b['capturedEpochMs']-a['capturedEpochMs'] for a,b in zip(quiet,quiet[1:])),500)
            self.assertTrue(all(not row['inTree'] and row['deleteCalls']==1 for row in quiet))
            retired=[create_entities.retired(row['retirementSource']) for row in quiet]
            if mode=='retained-renderer':
                self.assertTrue(all(not value for value in retired));self.assertTrue(quiet[-1]['entityAlive'])
            else:
                self.assertTrue(all(retired));self.assertFalse(quiet[-1]['entityAlive'])
                self.assertEqual(0,quiet[-1]['cpuBuffers'])


if __name__=='__main__':unittest.main()
