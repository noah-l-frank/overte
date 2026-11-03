"""Original Source3 child writes under the same canonical normal owner graph.

The first six normal inputs and Background prepare/attachment execute. These
storage counters add no source observation, HOME, resume or whole-flow verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey import source_bundles
from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
from adapters.script_journey.history import canonical
import test_lifecycle_actor_storage3 as raw_fixture


class LifecycleSourceWriteGateTests(unittest.TestCase):
    setUp=raw_fixture.LifecycleActorStorage3Tests.setUp
    baseline=raw_fixture.LifecycleActorStorage3Tests.baseline
    fields=raw_fixture.LifecycleActorStorage3Tests.fields
    act=raw_fixture.LifecycleActorStorage3Tests.act

    def ready(self):
        self.baseline()
        for index in range(6):self.act(index)
        with self.graph.operations.lock.held():
            owner=self.graph.operations.child('background')
            self.writer=self.graph.source;self.raw=owner.originals
            self.gate=self.writer.storage_gate
            self.assertIs(self.gate,self.raw.write_gates['source'])
            self.assertEqual('prepared',owner.state['phase'])
            self.assertEqual([],self.stage.editor.background.inputs)
            # The exact existing original is retained again for storage-only
            # qualification. It is never published as another fresh sample.
            record,_=source_bundles.original(self.writer.history,self.writer.disk['chunks'],
                self.writer.disk['bundles'],self.writer.disk['records'][0])
            self.value,_=source_bundles.original(self.writer.history,self.writer.disk['chunks'],
                self.writer.disk['bundles'],record['worldBundle'])
        self.queries=len(self.stage.native_calls());self.background_queries=len(self.stage.editor.background.history.commands)

    def unchanged_queries(self):
        self.assertEqual(self.queries,len(self.stage.native_calls()))
        self.assertEqual(self.background_queries,len(self.stage.editor.background.history.commands))
        self.assertEqual([],self.stage.editor.background.inputs)
        self.stage.command('exit');self.stage.worker.wait(timeout=10)
        self.assertEqual(0,self.stage.worker.returncode)
        absent=self.stage.process.require_absent();self.stage.process.final_absence(absent)

    def test_actual_created_ofd_roundtrip_matches_unchanged_default_chunk_bytes(self):
        self.ready();writer=self.writer;before_records=deepcopy(writer.disk['records'])
        old_chunks=deepcopy(writer.disk['chunks']);old_refs=deepcopy(writer.disk['bundles'])
        copy_dir=Path(tempfile.mkdtemp(prefix='lifecycle-source-default-codec-'));copy_dir.chmod(0o700)
        copied=PrivateFeatureState(copy_dir/writer.store.path.name)
        copied.write(deepcopy(writer.disk),None)
        for index in range(len(old_chunks)):
            child=copy_dir/writer.history.store(index).path.name
            child.write_bytes(writer.history.store(index).path.read_bytes());child.chmod(0o600)
        default=ChatSourceChunks(copied,writer.scope);default.load(old_chunks)
        reference,parts=source_bundles.prepare(self.value,len(old_refs),old_refs)
        manifest=old_chunks
        for part in parts:
            manifest=default.append(part,manifest)
            updated=copied.read();updated['chunks']=manifest;copied.write(updated,copied.read())
        made=[];close=OriginalDescriptor.close
        def observed_close(owner):
            if self.gate.child is not None and any(row['owner'] is owner
                    for row in self.gate.child.prepared.values()):
                owner.require(owner.fd);made.append((owner,owner.node,os.fstat(owner.fd).st_mode&0o777))
            return close(owner)
        with writer.lock.held(),patch.object(OriginalDescriptor,'close',observed_close):
            bundle=writer.append_original(self.value)
            self.raw.namespace.guard_lease();bill=self.raw.namespace()
        self.assertEqual(len(old_refs),bundle);self.assertEqual(reference,writer.disk['bundles'][bundle])
        self.assertEqual(before_records,writer.disk['records']);self.assertEqual(manifest,writer.disk['chunks'])
        actual,_=source_bundles.original(writer.history,writer.disk['chunks'],writer.disk['bundles'],bundle)
        self.assertEqual(self.value,actual);self.assertEqual(len(parts),len(made))
        self.assertTrue(all(owner.closed and not owner.lost and mode==0o600 for owner,_node,mode in made))
        for index in range(len(old_chunks),len(manifest)):
            self.assertEqual(default.store(index).path.read_bytes(),writer.history.store(index).path.read_bytes())
        self.assertIsNone(self.raw.namespace._write);self.assertEqual([],self.gate.held)
        self.assertLessEqual(bill['parts']+self.raw.archive.bill()['parts'],512)
        self.unchanged_queries()

    def test_capacity_refusal_precedes_prepare_and_child_creation_and_holds_exact_value(self):
        self.ready();writer=self.writer;incoming=dict(raw='\x00'*(1024*1024))
        before={path.name:(path.read_bytes(),signature(path.lstat())) for path in self.stage.root.iterdir()}
        with writer.lock.held(),patch('adapters.pico4.lifecycle_observation.source_bundles.prepare') as prepare,\
                patch.object(self.raw.namespace,'begin_write',wraps=self.raw.namespace.begin_write) as admission,\
                self.assertRaises(NativeUIError):writer.append_original(incoming)
        prepare.assert_not_called();self.assertEqual(1,admission.call_count)
        self.assertEqual(before,{path.name:(path.read_bytes(),signature(path.lstat())) for path in self.stage.root.iterdir()})
        self.assertIs(incoming,self.gate.held[-1].value)
        self.assertTrue(any(owner is self.gate for _path,owner in UNRESOLVED))
        self.unchanged_queries()

    def test_equal_byte_exchanged_child_is_not_accepted_from_posthoc_path_identity(self):
        self.ready();writer=self.writer;write=os.pwrite;swapped=[]
        def exchange(descriptor,data,offset):
            count=write(descriptor,data,offset)
            if not swapped:
                owner=next(row['owner'] for row in self.gate.child.prepared.values() if row['owner'].fd==descriptor)
                path=writer.history.store(len(writer.history.identities)).path
                replacement=path.with_name(path.name+'.foreign')
                replacement.write_bytes(os.pread(descriptor,65537,0));replacement.chmod(0o600)
                os.replace(replacement,path);swapped.append((path,path.read_bytes(),signature(path.lstat()),owner))
            return count
        with writer.lock.held(),patch('adapters.pico4.lifecycle_write_gate.os.pwrite',exchange),\
                self.assertRaises(NativeUIError):writer.append_original(self.value)
        self.assertEqual(1,len(swapped));path,raw,stamp,owner=swapped[0]
        self.assertEqual((raw,stamp),(path.read_bytes(),signature(path.lstat())))
        self.assertFalse(owner.closed);self.assertFalse(self.gate.close_host())
        self.assertEqual((raw,stamp),(path.read_bytes(),signature(path.lstat())))
        self.assertTrue(self.gate.poisoned);self.assertIs(self.value,self.gate.child.value)
        self.unchanged_queries()

    def test_actual_recycled_child_ofd_refuses_and_never_closes_foreign_descriptor(self):
        self.ready();writer=self.writer;write=os.pwrite;recycled=[]
        def recycle(descriptor,data,offset):
            count=write(descriptor,data,offset)
            if not recycled:
                owner=next(row['owner'] for row in self.gate.child.prepared.values() if row['owner'].fd==descriptor)
                path=writer.history.store(len(writer.history.identities)).path
                os.close(descriptor);foreign=os.open(path,os.O_RDWR|os.O_CLOEXEC)
                if foreign!=descriptor:os.dup2(foreign,descriptor);os.close(foreign)
                recycled.append((owner,descriptor,signature(os.fstat(descriptor))))
            return count
        with writer.lock.held(),patch('adapters.pico4.lifecycle_write_gate.os.pwrite',recycle),\
                self.assertRaises(NativeUIError):writer.append_original(self.value)
        self.assertEqual(1,len(recycled));owner,descriptor,stamp=recycled[0]
        self.assertTrue(owner.lost);self.assertFalse(self.gate.close_host())
        self.assertEqual(stamp,signature(os.fstat(descriptor)))
        self.assertTrue(any(held is self.gate for _path,held in UNRESOLVED))
        # The uncertain/recycled descriptor is intentionally retained until the
        # owning test-host exits; a logical cleanup may not close it.
        self.unchanged_queries()

    def test_unknown_source_root_cas_retains_real_child_and_original_old_root_ofd(self):
        self.ready();writer=self.writer;write=writer.store.write;before=deepcopy(writer.disk)
        def unknown(value,previous):write(value,previous);raise OSError('Actual Source3 CAS, unknown return')
        with writer.lock.held(),patch.object(writer.store,'write',side_effect=unknown),\
                self.assertRaises(OSError):writer.append_original(self.value)
        self.assertEqual(before,writer.disk);self.assertNotEqual(before,writer.store.read())
        self.assertTrue(self.gate.poisoned);self.assertIs(self.value,self.gate.child.value)
        self.assertTrue(self.gate.child.prepared)
        self.assertTrue(all(row['owner'].closed and not row['owner'].lost for row in self.gate.child.prepared.values()))
        root=next(permit for permit in self.gate.held if permit.kind=='root')
        root.old.require(root.old.fd);self.assertEqual(0,os.fstat(root.old.fd).st_nlink)
        with writer.lock.held(),self.assertRaises(NativeUIError):self.raw.namespace()
        self.assertFalse(self.gate.close_host());self.unchanged_queries()


if __name__=='__main__':unittest.main()
