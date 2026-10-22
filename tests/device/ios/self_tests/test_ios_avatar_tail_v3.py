"""Current UIKit originals, bounded private journals and no-resend recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_avatar_postlogout_tail import AvatarPostLogoutTailTests


class AvatarTail3Tests(AvatarPostLogoutTailTests):
    def test_tail3_real_pending_callback_prevents_cleanup_until_actual_return(self):
        owner=self.owner();first=owner.capture();original=owner.record(first['reference'])
        def callback():
            with self.assertRaises(NativeUIError):owner.capture()
            row=deepcopy(owner.state['rows'][-1]);packet=owner.uikit(owner.record(row['reference']))
            self.assertTrue(packet['pendingDispatches']);self.assertIsNone(packet['dispatches'][-1]['returned'])
            with self.assertRaises(NativeUIError):self.archive(owner).proof(row)
            return row
        pending=self.uikit.touch(callback);before=deepcopy(self.channel_calls)
        again=self.owner();closed=again.capture();proof=again.proof(closed)
        self.assertEqual(3,proof['iosAvatarPostLogoutTailProofVersion']);self.assertEqual(2,proof['uikit']['dispatchSequence'])
        with self.assertRaises(NativeUIError):again.proof(pending)
        self.assertEqual(original,again.record(first['reference']));self.assertEqual(before,self.channel_calls[:len(before)])

    def test_tail3_lost_empty_opened_raw_is_owned_and_cannot_change_after_abandonment(self):
        owner=self.owner();original=owner.segments.intent;lost=[]
        def intent(parent):
            original(parent)
            if parent['label']=='scripts' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Lost original opened passive source carrier')
        owner.segments.intent=intent
        with self.assertRaises(NativeUIError):owner.capture()
        before=deepcopy(self.channel_calls);again=self.owner();row=again.recover();self.assertEqual(before,self.channel_calls)
        partial=again.row_partial(row);parent=partial['raws']['scripts'][0]
        self.assertEqual([dict(bytes=0,sha256=__import__('hashlib').sha256(b'').hexdigest(),complete=False)],again.segments.inspect(parent))
        archived=self.archive(again);self.assertEqual(partial,archived.row_partial(row))
        path=again.segments.store.path(parent['chunks'][0]);inode=path.stat().st_ino
        with path.open('ab') as stream:stream.write(b'{')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.archive(again)
        self.assertEqual(before,self.channel_calls)

    def test_tail3_rehashed_query_raw_cannot_be_reclassified_as_partial_orphan(self):
        from adapters.script_feature.history import pack,unpack
        owner=self.owner();first=owner.capture();original=owner.segments.intent;lost=[]
        def intent(parent):
            original(parent)
            if parent['label']=='scripts' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Retain a genuine opened query raw')
        owner.segments.intent=intent
        with self.assertRaises(NativeUIError):owner.capture()
        actual=unpack(owner.previous['payload'])[0]
        parents=dict(wrongLabel=actual['pending']['raws']['scripts'][0],wrongIndexTag=actual['rows'][0]['partialCarrier'])
        for kind,parent in parents.items():
            metadata=deepcopy(owner.previous);state=unpack(metadata['payload'])[0]
            state['pending']['orphanCarriers']=[dict(parent=deepcopy(parent),snapshots=owner.segments.inspect(parent))]
            metadata['payload']=pack([state])
            # A valid recomputed outer history hash cannot turn actual query
            # bytes or an earlier row into this interrupted carrier admission.
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):owner.parse(metadata)

    def test_tail3_actual_interrupted_partial_carrier_is_retained_before_distinct_local_adoption(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def callback(parent):
            intent(parent)
            if parent['label']=='partial' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Lost actual row carrier opened return')
        owner.segments.intent=callback
        with self.assertRaises(OSError):owner.capture()
        pending=deepcopy(owner.state['pending']);orphan=pending['rowCarrier'];calls=deepcopy(self.channel_calls)
        again=self.owner();row=again.recover();again.proof(row);self.assertEqual(calls,self.channel_calls)
        partial=again.row_partial(row);self.assertEqual(orphan,partial['orphanCarriers'][0]['parent'])
        self.assertEqual([dict(bytes=0,sha256=__import__('hashlib').sha256(b'').hexdigest(),complete=False)],partial['orphanCarriers'][0]['snapshots'])
        self.archive(again).proof(row)
        path=again.segments.store.path(orphan['chunks'][0]);inode=path.stat().st_ino
        with path.open('ab') as stream:stream.write(b'{')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.archive(again)
        self.assertEqual(calls,self.channel_calls)

    def test_tail3_distinct_reads_keep_small_metadata_and_untouched_prior_originals(self):
        owner=self.owner();first=owner.capture();bytes_before=owner.file(first['index']).path.read_bytes();seen=[]
        for _ in range(7):
            row=owner.capture();seen.append(row);self.assertEqual(3,owner.proof(row)['iosAvatarPostLogoutTailProofVersion'])
        self.assertLess(self.store.path.stat().st_size,65536)
        self.assertEqual(bytes_before,owner.file(first['index']).path.read_bytes())
        archived=self.archive(owner)
        self.assertEqual(owner.proof(first),archived.proof(first))
        self.assertEqual(len(seen),len({owner.record(row['reference'])['queries']['uikit']['commandId'] for row in seen}))


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarTail3Tests(name) for name in loader.getTestCaseNames(AvatarTail3Tests) if name.startswith('test_tail3_'))


if __name__=='__main__':unittest.main()
