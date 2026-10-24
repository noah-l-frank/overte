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
        from test_assets_read_native import ROOT
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
            self.assertEqual(['canonical-file-directory','file-directory-with-slash','qrc-directory-spellings','foreign-file-context','foreign-qrc-context','foreign-voxel-file-context','foreign-voxel-qrc-context'],packet['sourceUrlCounterexamples'])
            self.assertEqual(1,len(packet['addCommands']));self.assertEqual(1,len(packet['addCuboids']))
            self.assertEqual(['push','pop'],[item['event'] for item in packet['dialogEvents']])
            self.assertTrue(all(item['url'].endswith('/qml/NewPolyVoxDialog.qml') for item in packet['dialogEvents']))
            initial_cuboid=packet['addCuboids'][0]
            self.assertEqual({'x':2,'y':2,'z':2},initial_cuboid['low'])
            self.assertEqual({'x':4,'y':4,'z':4},initial_cuboid['size']);self.assertEqual(255,initial_cuboid['value'])
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
            insertion=next(row for row in history if row['phase']=='normal-add-local-insert')
            properties=insertion['normalAddProperties'];self.assertEqual('terrain',properties['name'])
            self.assertEqual({'x':8,'y':8,'z':8},properties['voxelVolumeSize'])
            self.assertEqual({'x':8,'y':8,'z':8},properties['dimensions'])
            paths=('serverless/Textures/ground_5-2K/2K-ground_5-diffuse.jpg','serverless/Textures/ground_grass_gen_05.png')
            expected={'qrc:///'+path:hashlib.sha256((ROOT/'interface/resources'/path).read_bytes()).hexdigest() for path in paths}
            self.assertEqual('qrc:///'+paths[0],properties['xTextureURL'])
            self.assertEqual('qrc:///'+paths[1],properties['yTextureURL'])
            self.assertEqual(properties['xTextureURL'],properties['zTextureURL'])
            before=next(row for row in history if row['phase']=='baseline')
            textures=before['textureOriginals'];self.assertEqual(set(expected),{row['url'] for row in textures})
            bindings=before['polyvoxResources']['bindings'][0]['textures']
            self.assertEqual(3,len(bindings));self.assertTrue(all(bindings));self.assertEqual(bindings[0],bindings[2]);self.assertNotEqual(bindings[0],bindings[1])
            self.assertEqual(2,len(before['polyvoxResources']['textures']))
            for texture in textures:
                self.assertTrue(texture['alive']);self.assertTrue(texture['loaded']);self.assertFalse(texture['failed'])
                self.assertTrue(texture['pixelsObserved']);self.assertTrue(texture['pixelsAlive'])
                self.assertGreater(texture['width'],0);self.assertGreater(texture['height'],0)
                self.assertGreater(texture['originalWidth'],0);self.assertGreater(texture['originalHeight'],0)
                self.assertGreater(texture['storedBytes'],0);self.assertRegex(texture['sourceHash'],r'^[0-9a-f]{32}$')
                self.assertEqual(1,len(texture['requests']))
                request=texture['requests'][0];self.assertTrue(request['factoryOwnerAlive']);self.assertFalse(request['qObjectParentAlive']);self.assertTrue(request['finished']['success'])
                self.assertEqual({'factoryOnGui':False,'factoryOwnerAffinityOnGui':True,'requestAffinityOnGui':False,'originalRenderCaller':True,'hasQObjectParent':False,'qObjectParentIsFactoryOwner':False,'qObjectParentAffinityOnGui':None},request['provenance'])
                self.assertTrue(request['finished']['onRequestThread'])
                self.assertEqual(expected[texture['url']],request['finished']['sha256']);self.assertGreater(request['finished']['bytes'],0)
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
            for frame in quiet:
                self.assertEqual(2,len(frame['textureOriginals']))
                for texture in frame['textureOriginals']:
                    self.assertTrue(texture['pixelsObserved'])
                    self.assertEqual(mode=='retained-renderer',texture['alive'])
                    self.assertEqual(mode=='retained-renderer',texture['pixelsAlive'])
                    self.assertTrue(all(request['factoryOwnerAlive']==(mode=='retained-renderer') and not request['qObjectParentAlive'] for request in texture['requests']))
                    self.assertTrue(all(not request['alive'] for request in texture['requests']))
            retired=[create_entities.retired(row['retirementSource']) for row in quiet]
            if mode=='retained-renderer':
                self.assertTrue(all(not value for value in retired));self.assertTrue(quiet[-1]['entityAlive'])
            else:
                self.assertTrue(all(retired));self.assertFalse(quiet[-1]['entityAlive'])
                self.assertEqual(0,quiet[-1]['cpuBuffers'])


if __name__=='__main__':unittest.main()
