"""Actual sealed Python source graph; native/Parent provenance remain seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.chat_journey.evidence_archive import stamp
from adapters.chat_journey.remote_actor_graph import ChatRemoteActorGraph
from adapters.normal_ui import NativeUIError
from self_tests import test_pico_chat_cursor_actor as fixture


class ChatRemoteActorGraphTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.PicoChatCursorActorTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.actor=self.h.actor;self.actor.stop_once();actor=self.actor
        self.stores=dict(actor=actor.store,stop=actor.stop_store,seal=actor.seal.store,
            flow=actor.publisher.observation.flow_store,cleanup=actor.publisher.observation.cleanup_store,
            publisher=actor.publisher.store,cursor=actor.publisher.cursor.store,
            code=actor.publisher.observation.samples.script_source.store)
        for owner in actor.publisher.cursor.owners:
            self.stores[owner.stage+'-observation']=owner.store;self.stores[owner.stage+'-samples']=owner.samples.store
        self.expected={key:deepcopy(actor.previous[key]) for key in ('runId','fixtureUrl','binding','peerBinding','hostProcessIdentity','instance','stopCommand')}

    def acquire(self):
        return ChatRemoteActorGraph(self.actor.store.path.read_bytes(),stamp(self.actor.store.path.lstat()),self.stores,self.expected)

    def test_original_graph_is_historical_pending_without_any_reconstructed_live_actor(self):
        before=self.h.h.queries();posts=len(self.h.h.posts);reader=self.acquire()
        self.assertTrue(reader.pending);self.assertFalse(reader.failed);self.assertEqual(9,len(reader.histories))
        self.assertEqual(3,len(reader.frames['publisher']));reader.verify()
        self.assertEqual(before,self.h.h.queries());self.assertEqual(posts,len(self.h.h.posts))
        self.assertIsNot(reader,self.actor);self.assertIsInstance(reader.frames['cleanup-observation'],list)
        # Original physical identities remain pinned after full historical load.
        child=reader.histories['cursor'].store(0);value=child.read();child.write(value,value)
        with self.assertRaises(NativeUIError):reader.verify()
        self.assertTrue(child.path.exists());self.assertTrue(reader.pending)


    def test_wrong_scope_native_bytes_and_mutable_cache_types_cannot_qualify_pending_graph(self):
        wrong={**self.expected,'instance':'f'*32}
        with self.assertRaises(NativeUIError):
            ChatRemoteActorGraph(self.actor.store.path.read_bytes(),stamp(self.actor.store.path.lstat()),self.stores,wrong)
        reader=self.acquire();reader.frames['active-samples']=tuple(reader.frames['active-samples'])
        with self.assertRaises(NativeUIError):reader.verify()
        self.assertTrue(reader.failed)
        reader=self.acquire();reader.histories['cursor'].identities=[list(row) for row in reader.histories['cursor'].identities]
        with self.assertRaises(NativeUIError):reader.verify()
        self.assertTrue(reader.failed)
        reader=self.acquire();reader.frames['active-samples'][0]['peer']['processId']+=1
        with self.assertRaises(NativeUIError):reader.validate()
        with self.assertRaises(NativeUIError):reader.verify()
        self.assertTrue(reader.failed)
        self.assertTrue(all(store.path.exists() for store in self.stores.values()))


if __name__=='__main__':unittest.main()
