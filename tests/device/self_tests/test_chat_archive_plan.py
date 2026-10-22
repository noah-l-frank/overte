"""Typed original warm catalog acquisition; no synthetic history-method reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_archive import PicoChatArchivePlan


class ChatArchivePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.peer=self.root/'peer';self.peer.mkdir(mode=0o700)
        self.plan=PicoChatArchivePlan.__new__(PicoChatArchivePlan);self.plan.catalog=ChatArchiveCatalog();self.addCleanup(self.plan.catalog.close_host)
        self.plan.state=self.root/'normal-script-state.json';self.plan.peer_directory=self.peer
        self.store=PrivateFeatureState(self.root/'original-child.json');self.store.write(dict(phase='reading',chunks=[]),None)
    def do_not_call(self,*args):raise AssertionError('A decoding method is not a fresh source or immutable file owner')

    def test_actual_immutable_dispatcher_chunks_are_catalogued_despite_callable_history_method(self):
        chunks=ChatSourceChunks(self.store,dict(scope='original-dispatcher'))
        manifest=chunks.append(dict(original=dict(command='already-consumed')),[])
        value=dict(phase='ready',chunks=manifest);self.store.write(value,self.store.read())
        owner=SimpleNamespace(store=self.store,previous=value,history=self.do_not_call,chunks=chunks)
        self.plan.add_owner(owner);self.plan.catalog.verify_all()
        self.assertEqual({'primary/'+self.store.path.name,'primary/'+chunks.store(0).path.name},set(self.plan.catalog.rows))
        self.assertEqual(value,self.store.read())

    def test_original_pre_stop_inventory_refuses_rootless_chunks_without_adoption_or_deletion(self):
        key='a'*32;self.plan.key=key;self.plan.state=self.root/('normal-script-state-'+key+'.json')
        self.plan.ui=self.root/('normal-script-ui-'+key+'.json')
        ledger=PrivateFeatureState(self.root/('chat-archive-retirement-'+key+'.json'))
        self.plan.adapter=SimpleNamespace(_chat_archive_retirement_store=lambda target:ledger);self.plan.target='synthetic-target'
        lock=self.peer/'script-sources.lock';lock.touch(mode=0o600)
        owned=PrivateFeatureState(self.root/('chat-original-'+key+'.json'));owned.write(dict(original=True),None)
        self.plan.inventory({owned.path})
        orphan=PrivateFeatureState(self.root/('chat-unknown-'+key+'.json.frame-000.json'))
        orphan.write(dict(original='unresolved'),None);before=orphan.path.read_bytes()
        with self.assertRaises(NativeUIError):self.plan.inventory({owned.path})
        self.assertEqual(before,orphan.path.read_bytes());self.assertEqual(dict(original=True),owned.read())
        self.assertIsNone(ledger.read())

    def test_pre_stop_inventory_keeps_only_exact_known_consumed_mutable_peer_reader_root(self):
        key='a'*32;self.plan.key=key;self.plan.state=self.root/('normal-script-state-'+key+'.json')
        self.plan.ui=self.root/('normal-script-ui-'+key+'.json')
        ledger=PrivateFeatureState(self.root/('chat-archive-retirement-'+key+'.json'))
        self.plan.adapter=SimpleNamespace(_chat_archive_retirement_store=lambda target:ledger);self.plan.target='synthetic-target'
        reader=PrivateFeatureState(self.peer/'actor-files.json')
        original=dict(pending=None,closing=False,removed=False,request=dict(operation='inspect',commandId='b'*32),
            result=dict(commandId='b'*32,retired=True))
        reader.write(original,None);bound_original=object()
        files=SimpleNamespace(store=reader,original=bound_original,_owned=reader.read)
        self.plan.parent=SimpleNamespace(cache_release=SimpleNamespace(files=files),peer=SimpleNamespace(files=bound_original,files_store=reader))
        self.plan.pre_stop_inventory();self.assertEqual({},self.plan.catalog.rows);self.assertEqual(original,reader.read())
        current=reader.read();reader.write({**current,'pending':dict(operation='retire')},current)
        with self.assertRaises(NativeUIError):self.plan.pre_stop_inventory()
        self.assertIsNone(ledger.read());self.assertTrue(reader.path.exists())

    def test_embedded_background_history_does_not_invoke_method_or_hide_an_unknown_file_owner(self):
        value=self.store.read();owner=SimpleNamespace(store=self.store,previous=value,history=self.do_not_call)
        self.plan.add_owner(owner);self.plan.catalog.verify_all();self.assertEqual(1,len(self.plan.catalog.rows))
        owner.chunks='unknown-file-owner'
        with self.assertRaises(NativeUIError):self.plan.add_owner(owner)
        self.assertEqual(value,self.store.read())


if __name__=='__main__':unittest.main()
