"""Warm global original catalog join; direct-wait evidence cannot finalize."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_archive import PicoChatArchivePlan
from adapters.pico4.chat_composition import PicoChatComposition
from self_tests import test_chat_cursor_cleanup_consumption as seams


class ChatCursorArchiveTests(unittest.TestCase):
    def test_every_global_graph_original_is_catalogued_but_direct_wait_cannot_restart_or_archive(self):
        h=seams.ChatCursorCleanupConsumptionTests();h.setUp();self.addCleanup(h.doCleanups)
        h.wait();h.journey.consumed_cleanup(h.ticket,h.barrier,0)
        consumed=h.consumer;before=h.h.queries();posts=len(h.h.posts);restarts=[]
        parent=PicoChatComposition.__new__(PicoChatComposition)
        parent.failed=False;parent.target='projected-pico';parent.source=consumed.primary.source
        parent.previous=dict(phase='caches-retired',completedSteps=26)
        parent.binding=deepcopy(consumed.scope['binding']);parent.peer=SimpleNamespace(binding=deepcopy(consumed.scope['peerBinding']))
        parent.cache_release=SimpleNamespace(roles=(consumed.primary.samples,),defer_ipc=True)
        parent.guard=lambda:True
        parent.adapter=SimpleNamespace(_chat_cursor_cleanup_consumption_store=lambda _target:h.store,
            _chat_cursor_source_seal_store=lambda _target,*,witness:h.seals[int(witness)].store,
            _chat_restart_io=lambda *_args:restarts.append('forbidden'))
        def plan():
            result=PicoChatArchivePlan.__new__(PicoChatArchivePlan)
            result.parent=parent;result.adapter=parent.adapter;result.target=parent.target
            result.state=h.h.root/'projected-state.json';result.peer_directory=h.h.root/'peer'
            result.catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(result.catalog.close_host);return result
        original=plan();metadata=original.add_cursor_cleanup_consumption(consumed);original.catalog.verify_all()
        self.assertFalse(metadata['chatCursorSequenceSucceeded'])
        self.assertEqual(1,metadata['chatCursorCleanupConsumptionVersion'])
        self.assertNotIn('chatCleanupBaselineSha256',metadata)
        expected={consumed.store.path}
        expected.update(consumed.history.store(i).path for i in range(len(consumed.history.identities)))
        for seal in consumed.seals:
            expected.add(seal.store.path)
            for owner in seal.owners:
                expected.add(owner.store.path)
                expected.update(owner.history.store(i).path for i in range(len(owner.history.identities)))
        self.assertEqual(expected,{row['store'].path for row in original.catalog.rows.values()})
        self.assertGreater(len(expected),80)
        # Neither an actual returned source receipt nor caller metadata may
        # relabel this direct wait as the full shared execute() recipe.
        with self.assertRaises(NativeUIError):parent.require_consumed_cleanup(consumed)
        h.journey._cleanup_sequence_succeeded=True # Explicit caller-state corruption countercase.
        try:
            with self.assertRaises(NativeUIError):parent.require_consumed_cleanup(consumed)
        finally:h.journey._cleanup_sequence_succeeded=False
        with self.assertRaises(NativeUIError):parent.restart_and_close_application(h.barrier,cleanup_consumption=consumed)
        self.assertTrue(parent.failed);self.assertFalse(hasattr(parent,'archive_plan'))
        self.assertFalse(hasattr(parent,'cursor_cleanup_consumption'));self.assertEqual([],restarts)
        self.assertEqual(before,h.h.queries());self.assertEqual(posts,len(h.h.posts))
        self.assertTrue(all(path.exists() for path in expected))
        # Same bytes at a replacement inode cannot become an original graph
        # by being acquired during a subsequent catalog window.
        replaced=consumed.seals[1].owners[-1]
        replaced.store.write(replaced.previous,replaced.previous)
        with self.assertRaises(NativeUIError):plan().add_cursor_cleanup_consumption(consumed)
        with self.assertRaises(NativeUIError):original.catalog.verify_all()
        self.assertTrue(all(path.exists() for path in expected))
        self.assertEqual(before,h.h.queries());self.assertEqual(posts,len(h.h.posts))


if __name__=='__main__':unittest.main()
