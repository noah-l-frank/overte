"""Warm decode reuse preserves every original physical read and admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.decoded_chunks import ChatDecodedPrefix
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack


class DecodedChunkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=PrivateFeatureState(Path(self.temp.name)/'original.json');self.scope={'run':'original'}
        self.history=ChatSourceChunks(self.store,self.scope);self.root=None;self.manifest=[]
        self.append({'actual':[1,'Grüße',{'nested':True}]})
        self.cache=ChatDecodedPrefix(self.history)

    def append(self,value):
        reading={**self.scope,'phase':'reading','chunks':self.manifest};self.store.write(reading,self.root)
        self.manifest=self.history.append(value,self.manifest)
        self.root={**reading,'phase':'ready','chunks':self.manifest};self.store.write(self.root,reading)

    def load(self):
        history=ChatSourceChunks(self.store,self.scope);candidate=self.cache.begin(history,self.manifest)
        return history.load(self.manifest,decoder=candidate),candidate

    def admit(self):
        rows,candidate=self.load();self.cache.commit(candidate);return rows

    def test_warm_prefix_reads_every_original_file_but_only_new_transcripts_are_unpacked(self):
        rows,candidate=self.load();self.assertFalse(self.cache.records)
        self.cache.commit(candidate);self.append({'new':[2,3]})
        reads=[];read=PrivateFeatureState.read
        def measured(store):
            reads.append(store.path);return read(store)
        with patch.object(PrivateFeatureState,'read',measured),patch('adapters.chat_journey.decoded_chunks.unpack',wraps=unpack) as decoder:
            current,pending=self.load()
        self.assertEqual(1,decoder.call_count)
        self.assertEqual(rows+[{'new':[2,3]}],current)
        self.assertTrue(all(self.history.store(i).path in reads for i in range(2)))
        self.assertEqual(1,len(self.cache.records));self.cache.commit(pending)
        current[0]['actual'].append('inspection mutation')
        with patch('adapters.chat_journey.decoded_chunks.unpack',side_effect=AssertionError('Old transcript was decoded again')):
            original,pending=self.load()
        self.assertEqual(rows+[{'new':[2,3]}],original);self.cache.commit(pending)

    def test_same_value_replaced_child_cannot_be_adopted_by_decoder(self):
        self.admit();child=self.history.store(0);value=child.read();child.write(value,value)
        with self.assertRaises(NativeUIError):self.load()
        self.assertEqual(1,len(self.cache.records))

    def test_scope_path_and_foreign_candidate_are_refused(self):
        self.admit()
        for history in (ChatSourceChunks(self.store,{'run':'foreign'}),
                ChatSourceChunks(PrivateFeatureState(self.store.path.with_name('foreign.json')),self.scope)):
            with self.assertRaises(NativeUIError):self.cache.begin(history,self.manifest)
        _,candidate=self.load();other=copy(candidate)
        with self.assertRaises(NativeUIError):self.cache.commit(other)

    def test_complete_inventory_and_permission_guards_still_run_on_warm_load(self):
        self.admit();extra=self.store.path.with_name(self.store.path.name+'.frame-foreign')
        extra.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):self.load()
        extra.rmdir();self.history.store(0).path.chmod(0o644)
        with self.assertRaises(NativeUIError):self.load()

    def test_internal_decoded_bytes_changed_with_same_metadata_are_refused_before_return(self):
        self.admit();record=self.cache.records[0]
        self.cache.records=self.cache._records=((*record[:2],record[2]+b' ',*record[3:]),)
        # Even a coherently changed identity pin cannot bypass the per-use SHA.
        self.cache.seal=self.cache._seal=(self.cache.records,self.cache.identity,self.cache.sha)
        with self.assertRaises(NativeUIError):self.load()

    def test_candidate_cannot_replace_finished_records_or_commit_before_complete_load(self):
        history=ChatSourceChunks(self.store,self.scope);candidate=self.cache.begin(history,self.manifest)
        with self.assertRaises(NativeUIError):self.cache.commit(candidate)
        history.load(self.manifest,decoder=candidate)
        candidate.records=candidate._records=candidate.finished_records=tuple(list(candidate.records))
        with self.assertRaises(NativeUIError):self.cache.commit(candidate)

    def test_coherent_byte_and_hash_replacement_cannot_rebind_original_prefix(self):
        self.admit();record=self.cache.records[0];raw=b'[{"foreign":true}]'
        self.cache.records=self.cache._records=((*record[:2],raw,hashlib.sha256(raw).hexdigest(),record[4]),)
        self.cache.seal=self.cache._seal=(self.cache.records,self.cache.identity,self.cache.sha)
        with self.assertRaises(NativeUIError):self.load()


if __name__=='__main__':unittest.main()
