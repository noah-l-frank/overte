"""81 real canonical source groups: storage capacity, not16-step effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from pathlib import Path
import sys
import unittest
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_actor_originals import ActorOriginals
from adapters.pico4.lifecycle_actor_storage import STAGE,checked_file
from adapters.native_feature_observation import decode
from adapters.script_journey.history import canonical,MAX_FRAMES,MAX_RAW
from feature_journeys.fixtures import context
import test_lifecycle_actor_composition as composition_fixture


class LifecycleActorStorageCapacityTests(unittest.TestCase):
    def test_81_fresh_six_source_groups_keep_all_originals_under_unchanged_caps(self):
        stage=composition_fixture.LifecycleActorCompositionTests();stage.setUp();self.addCleanup(stage.doCleanups)
        stage.start();actor_queries=[]
        for index in range(81):
            if index==27:
                stage.client.activate(uuid.uuid4().hex,'open-editor',dict(editor='create'))
                stage.editor.owner.tablet();stage.editor.owner.open_create();stage.editor.owner.focus_create()
            if index==54:
                stage.client.activate(uuid.uuid4().hex,'type',dict(text=context(stage.run)['unicode']))
                stage.editor.owner.type_create()
            before=len(stage.native_calls());sample=stage.sample()
            actual=stage.native_calls()[before:];self.assertEqual(['gesture','drive','ui','pending','feature','subject'],actual)
            actor_queries.extend(actual);expected='none' if index<27 else 'create'
            self.assertEqual(expected,sample['facts']['editor'])
            self.assertEqual('' if index<54 else context(stage.run)['unicode'],sample['facts']['text'])
            stage.native.sleep(.02)
            if (index+1)%9==0:print('Actual canonical fresh source groups: '+str(index+1)+'/81',flush=True)
        original=ActorOriginals(PrivateFeatureState(stage.root/'lifecycle-actor-originals.json'))
        self.assertEqual(2,original.version);self.assertEqual(81,len(original.root['records']))
        self.assertEqual(243,len(original.root['chunks']));self.assertIsNone(original.root['pending'])
        self.assertEqual('delivered',original.root['publication']['phase']);self.assertFalse((stage.root/STAGE).exists())
        self.assertEqual(['gesture','drive','ui','pending','feature','subject']*81,actor_queries)
        primary_queries=len(stage.native_calls())-len(actor_queries)
        self.assertGreater(primary_queries,0) # Constructor and normal input UI queries remain in the log.
        cursors={key:[] for key in ('gesture','drive','ui','pending','native','subject')}
        commands={key:[] for key in cursors};oldest=[];reconstructed=0;retired=0
        for index,row in enumerate(original.root['records']):
            group=original.group(index);entries=group['entries'];self.assertEqual(15,len(entries))
            self.assertEqual(['phase-before','gesture','gesture','drive','drive','ui','ui','world',
                'pending','pending','native','native','subject','subject','phase-after'],[entry['key'] for entry in entries])
            packets=[]
            for key in cursors:
                value=original.last(key,record=index);frame=value['original'] if key in ('gesture','drive','ui') else value[key]
                self.assertEqual(hashlib.sha256(frame['raw'].encode()).hexdigest(),frame['sha256'])
                packet=decode(frame['raw']);packets.append(packet);reconstructed+=len(frame['raw'].encode())
                cursors[key].append(packet['sequence']);commands[key].append(packet.get('requestId',packet.get('commandId')))
            before=entries[0]['value'];after=entries[-1]['value']
            self.assertEqual(before['activations'],after['activations'])
            self.assertEqual(stage.editor.binding,original.root['binding'])
            phase=original.original(row['phase']);ledger=checked_file(phase['stagingTransfer'])
            self.assertEqual(list(range(15)),ledger['retired']);self.assertEqual(15,len(ledger['retirementReceipts']))
            self.assertTrue(all(r['phase']=='observed' and r['removed'] and r['originalFileDescriptionClosed']
                for r in ledger['retirementReceipts']));retired+=15
            reply=original.original(row['reply']);self.assertTrue(reply['stagingRetirement']['receipt']['originalFileDescriptionClosed'])
            captured=[packet['capturedEpochMs'] for packet in packets]
            captured.extend(packet['requestedEpochMs'] for packet in packets if 'requestedEpochMs' in packet)
            gesture=packets[0]['source']
            if gesture['known']:captured.append(gesture['frameEpochMs'])
            self.assertEqual(min(captured),group['record']['publication']['capturedEpochMs']);oldest.append(min(captured))
        self.assertTrue(all(len(set(values))==81 and values==sorted(values) for values in cursors.values()))
        self.assertTrue(all(len(set(values))==81 for values in commands.values()))
        self.assertEqual(81,len(set(oldest)));bill=stage.last_worker['sourceStorage']
        self.assertLessEqual(bill['parts'],MAX_FRAMES);self.assertGreater(bill['parts'],243)
        for key in ('containerRawBytes','decodedLogicalBytes','storedBytes','reservedStoredBytes'):self.assertLessEqual(bill[key],MAX_RAW)
        self.assertLessEqual(bill['largestFileBytes'],65536)
        paths=[original.store.path,*[original.history._path(i) for i in range(243)]]
        actual_stored=sum(path.stat().st_size for path in paths)
        self.assertEqual(244,len(paths));self.assertLessEqual(actual_stored,MAX_RAW)
        namespace_files=[path for path in stage.root.rglob('*') if path.is_file()]
        namespace_stored=sum(path.stat().st_size for path in namespace_files)
        self.assertLessEqual(namespace_stored,MAX_RAW)
        stage.command('exit');stage.worker.wait(timeout=10);self.assertEqual(0,stage.worker.returncode)
        absence=stage.process.require_absent();stage.process.final_absence(absence)
        report=dict(lifecycleActorStorageCapacityVersion=2,actualSourceGroups=81,actualActorSixSourceQueries=len(actor_queries),
            actualSharedSourceQueries=len(stage.native_calls()),actualPrimarySourceQueries=primary_queries,
            actualDecodedSourceBytes=reconstructed,actualStagePartsRetired=retired,actualStageRootsRetired=81,
            mainParts=243,mainFiles=244,mainStoredBytes=actual_stored,mainRootBytes=len(original.raw),
            privateNamespaceFiles=len(namespace_files),privateNamespaceStoredBytes=namespace_stored,
            minimum16StepFreshSourceGroups=51,full16StepEffectsProved=False,
            actualAdmittedInputPhases=3,nativeQtSdkPhysics='declared existing fixture model',
            highwater=bill,actualWorkerReturnCode=stage.worker.returncode)
        PrivateFeatureState(stage.root/'lifecycle-actor-storage-capacity-diagnostics.json').write(report,None)
        print('Lifecycle V2 actual capacity bill: '+canonical(report).decode(),flush=True)


if __name__=='__main__':unittest.main()
