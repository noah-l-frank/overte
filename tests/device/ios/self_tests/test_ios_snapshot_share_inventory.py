"""Six source originals after real Share quiet; native/OS production modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_inventory_owner import SnapshotShareSourceInventoryOwner,ShareSourceInventoryAction
from ios.adapters.snapshot_share_seal_owner import ShareAdmissionSealAction
from ios.adapters import snapshot_share_inventory as source
from ios.self_tests.snapshot_share_inventory_domain import SourceInventoryFlow
from ios.self_tests.snapshot_share_domain import RUN,SYSTEM_UI


class SnapshotShareInventoryTests(unittest.TestCase):
    def prepared(self):
        domain=SourceInventoryFlow(self)
        with domain.owner() as owner,self.assertRaises(NativeUIError):owner.source_inventory_owner()
        domain.activate('share-open','1'*32)
        with domain.owner() as owner:owner.open('1'*32)
        domain.activate('share-select-owned','2'*32)
        with domain.owner() as owner:
            owner.select('2'*32);owner.cleanup()
            with self.assertRaises(NativeUIError):owner.source_inventory_owner()
            owner.admission_seal_owner().seal()
        return domain
    def history(self,domain):
        share=IOSSnapshotShareOwner.history(PrivateFeatureState(domain.main.ctx.root/'snapshot-share-owner.json'),domain.main.ctx.lock,
            domain.archive.source_lock,domain.main.ctx.binding,domain.archive.binding,RUN,domain.archive.fixture_url,SYSTEM_UI,
            domain.primary.target['appId'],domain.archive.ipa,domain.archive.admission_store)
        return SnapshotShareSourceInventoryOwner.history(PrivateFeatureState(domain.archive.root/'share-source-inventory-owner.json'),share,
            domain.archive.ipa,domain.archive.admission_store)

    def test_normal_six_output_inventory_preserves_first_files_and_replays_without_live_sources(self):
        domain=self.prepared();files={name:(domain.archive.documents/name).read_bytes() for name in source.NAMES}
        with domain.owner() as share:
            owner=share.source_inventory_owner();proof=owner.inspect();packet,raw=owner.original()
            self.assertTrue(proof['sourceOriginalsRetained']);self.assertTrue(proof['sourceFilesRetirementRequired']);self.assertEqual(6,len(proof['outputs']))
            for key,value in (('snapshotShareSourceInventoryVersion',True),('processId',True),('sourceInstance','0'*32),
                    ('admissionSealSha256','0'*64),('parentIdentity','0'*64),('requestId','ios-'+'0'*32)):
                changed=deepcopy(packet);changed[key]=value
                with self.subTest(key=key),self.assertRaises(NativeUIError):source.original(changed,owner.state['nonce'],owner.share,owner.sealed)
            for fault in ('name','hash','count','retire-intent','retire-result','clock','current','frozen','readers'):
                changed=deepcopy(packet)
                if fault=='name':changed['outputs'][2]['name']='foreign.bytes'
                elif fault=='hash':changed['outputs'][2]['sha256']='0'*64
                elif fault=='count':changed['outputs'][2]['byteCount']=True
                elif fault in ('retire-intent','retire-result'):
                    at=3 if fault=='retire-intent' else 4;value=json.loads(base64.b64decode(changed['outputs'][at]['data']));value['complete']=not value['complete']
                    changed['outputs'][at]['data']=base64.b64encode(json.dumps(value).encode()).decode()
                elif fault=='clock':changed['clockBefore']['monotonicMs']+=251
                else:changed[dict(current='current',frozen='frozen',readers='readersClosed')[fault]]=False
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.qualified(source.original(changed,owner.state['nonce'],owner.share,owner.sealed))
            self.assertEqual(raw,owner.original()[1]);plan=owner.action(True).plan
            with self.assertRaises(NativeUIError):ShareAdmissionSealAction(owner.root,owner.lock,owner.binding,owner.run,1,plan,lambda:True,historical=True)
            changed=deepcopy(plan);changed['control']='snapshot.share.archive.admission-seal'
            with self.assertRaises(NativeUIError):ShareSourceInventoryAction(owner.root,owner.lock,owner.binding,owner.run,1,changed,lambda:True,historical=True)
        self.assertEqual(1,domain.archive.inventory_calls);self.assertEqual(files,{name:(domain.archive.documents/name).read_bytes() for name in source.NAMES})
        counts=(domain.archive.import_count,domain.archive.chunk_count,domain.archive.retire_count)
        for producer in (domain.archive.import_original,domain.archive.chunk,domain.archive.retire,domain.archive.inspect_retirement):
            with self.subTest(producer=producer),self.assertRaises(NativeUIError):producer(domain.archive.ui)
        self.assertEqual(counts,(domain.archive.import_count,domain.archive.chunk_count,domain.archive.retire_count))
        self.assertEqual(files,{name:(domain.archive.documents/name).read_bytes() for name in source.NAMES})
        with (domain.main.ctx.lock.held(),domain.archive.source_lock.held(),patch.object(domain.archive,'execute',side_effect=AssertionError('Live SDK used')),
                patch.object(domain.primary,'probe',side_effect=AssertionError('Live primary used')),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('History wrote'))):
            reader=self.history(domain);self.assertEqual(proof,reader.proof());self.assertEqual(raw,reader.original()[1])
            with self.assertRaises(NativeUIError):reader.inspect()

    def test_lost_inventory_button_return_reads_first_native_original_without_another_query(self):
        domain=self.prepared();domain.lost_buttons.add('snapshot.share.archive.source-inventory')
        with domain.owner() as share,self.assertRaises(NativeUIError):share.source_inventory_owner().inspect()
        raw=domain.archive.inventory_text.encode()
        with domain.owner() as share:
            owner=share.source_inventory_owner();self.assertTrue(owner.inspect()['sourceOriginalsRetained']);self.assertEqual(raw,owner.original()[1])
        self.assertEqual(1,domain.archive.inventory_calls)

    def test_lost_readonly_inventory_value_keeps_native_original_without_another_query(self):
        domain=self.prepared();domain.archive.lost_inventory_value=True
        with domain.owner() as share,self.assertRaises((NativeUIError,OSError)):share.source_inventory_owner().inspect()
        with domain.owner() as share:self.assertTrue(share.source_inventory_owner().inspect()['sourceOriginalsRetained'])
        self.assertEqual(1,domain.archive.inventory_calls)

    def test_same_bytes_in_a_replaced_global_file_remain_unqualified_and_are_not_adopted(self):
        domain=self.prepared();path=domain.archive.documents/source.NAMES[3];replacement=path.with_name('replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path);identity=path.stat().st_ino;raw=path.read_bytes()
        for _ in range(2):
            with domain.owner() as share,self.assertRaises(NativeUIError):share.source_inventory_owner().inspect()
        self.assertEqual(1,domain.archive.inventory_calls);self.assertEqual((identity,raw),(path.stat().st_ino,path.read_bytes()))
        with domain.main.ctx.lock.held(),domain.archive.source_lock.held():
            reader=self.history(domain);self.assertFalse(reader.original()[0]['current']);self.assertIsNone(reader.state['result'])

    def test_unexpected_reserved_source_name_remains_owned_and_blocks_complete_inventory(self):
        domain=self.prepared();path=domain.archive.documents/'.record-unowned';path.write_bytes(b'Owned or unknown source temporary');path.chmod(0o600)
        for _ in range(2):
            with domain.owner() as share,self.assertRaises(NativeUIError):share.source_inventory_owner().inspect()
        self.assertEqual(1,domain.archive.inventory_calls);self.assertEqual(b'Owned or unknown source temporary',path.read_bytes())
        self.assertTrue(all((domain.archive.documents/name).exists() for name in source.NAMES))


if __name__=='__main__':unittest.main()
