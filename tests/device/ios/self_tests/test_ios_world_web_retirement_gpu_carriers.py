"""Real private GPU carrier writes/recovery, without native/GPU effect claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import uuid
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_retirement import WorldWebRetirement


def binding():
    return dict(sourceRevision='1'*40,artifactSha256='2'*64,processIdentity='host-carrier-model',
        sessionId='host-carrier-session',generation=1,targetFingerprint='3'*64)


class WorldWebRetirementGpuCarriersTests(unittest.TestCase):
    def test_interrupted_record_index_never_reuses_carrier_namespace_or_discards_unknown_file_birth(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);lock=ScriptSourceLock(root/'script-feature-sources.lock')
            with lock.held():
                owner=object.__new__(WorldWebRetirement);owner.version=2;owner.binding=binding();owner.run='a'*32;owner.lock=lock
                owner.scope=SimpleNamespace(root=root);owner.source=SimpleNamespace(binding=owner.binding,run=owner.run,historical=False,bound=lambda:True,monotonic=lambda:0)
                owner.store=PrivateFeatureState(root/'ios-world-web-primary-retirement.json');owner.previous=None;owner.state=dict(pending=None)
                def save():
                    value=deepcopy(owner.state);owner.store.write(value,owner.previous);owner.previous=value
                owner.save=save
                def row():return dict(index=1,gpu=[],gpuOriginals={},gpuAcquisition=uuid.uuid4().hex)
                first=row();owner.state['pending']=first;save();store=owner.gpu_store(first)
                body=dict(requestId='ios-'+'b'*32,owner={'actual':'retained-packet'},clocksBefore={'actual':'before'},clocksAfter={'actual':'after'})
                reference=store.write(1,body);first['gpu'].append(dict(requestId=body['requestId'],original=reference));save()
                self.assertEqual([body],owner.gpu_rows(first))
                second=row();owner.state['pending']=second;save();other=owner.gpu_store(second)
                self.assertNotEqual(store.namespace,other.namespace)
                second_reference=other.write(1,body);second['gpu'].append(dict(requestId=body['requestId'],original=second_reference));save()
                self.assertEqual([body],owner.gpu_rows(second));self.assertEqual([body],owner.gpu_rows(first))
                unknown=row();owner.state['pending']=unknown;save()
                def lost(kind,value):
                    unknown['gpuOriginals']['1']=value;save();raise RuntimeError('Lost after actual durable planned intent')
                unknown_store=owner.gpu_store(unknown);unknown_store.intent=lost
                with self.assertRaises(RuntimeError):unknown_store.write(1,body)
                owner.pending_gpu(unknown)
                with self.assertRaises(NativeUIError):owner.pending_gpu(unknown,readable=True)
                self.assertFalse(unknown_store.path(unknown['gpuOriginals']['1']).exists())
                self.assertEqual('planned',unknown['gpuOriginals']['1']['phase'])

    def test_replaced_same_bytes_original_inode_and_changed_saved_projection_fail_closed(self):
        # The frame store itself owns the actual byte/inode boundary; exercise
        # this production retirement projection without making a GPU verdict.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);lock=ScriptSourceLock(root/'script-feature-sources.lock')
            with lock.held():
                owner=object.__new__(WorldWebRetirement);owner.version=2;owner.binding=binding();owner.run='a'*32;owner.lock=lock
                owner.scope=SimpleNamespace(root=root);owner.source=SimpleNamespace(binding=owner.binding,run=owner.run,historical=False,bound=lambda:True,monotonic=lambda:0)
                owner.store=PrivateFeatureState(root/'ios-world-web-primary-retirement.json');owner.previous=None
                row=dict(index=1,gpu=[],gpuOriginals={},gpuAcquisition=uuid.uuid4().hex);owner.state=dict(pending=row)
                def save():
                    value=deepcopy(owner.state);owner.store.write(value,owner.previous);owner.previous=value
                owner.save=save;save();store=owner.gpu_store(row)
                body=dict(requestId='ios-'+'b'*32,owner={},clocksBefore={},clocksAfter={});reference=store.write(1,body)
                row['gpu'].append(dict(requestId=body['requestId'],original=reference));save();self.assertEqual([body],owner.gpu_rows(row))
                row['gpu'][0]['requestId']='ios-'+'c'*32
                with self.assertRaises(NativeUIError):owner.gpu_rows(row)
                row['gpu'][0]['requestId']=body['requestId']
                path=store.path(store.expand(reference));raw=path.read_bytes();replacement=path.with_suffix('.replacement')
                replacement.write_bytes(raw);replacement.chmod(0o600);replacement.replace(path)
                with self.assertRaises(NativeUIError):owner.gpu_rows(row)


if __name__=='__main__':unittest.main()
