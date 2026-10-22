"""Private per-source postlogout ownership beyond the old nested journal limit."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import unittest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutPartsTests(AvatarPostLogoutReadsTests):
    def test_parts2_repeated_native_histories_stay_private_and_small_without_rewriting_old_originals(self):
        owner=self.owner();first=owner.capture();path=owner.originals.path(first['original']);original=path.read_bytes();rows=[first]
        for _ in range(11):rows.append(owner.capture())
        self.assertEqual(12,len(rows));self.assertTrue(all('partsCarrier' in row and 'parts' not in row for row in rows))
        self.assertLess(self.store.path.stat().st_size,65536);self.assertEqual(original,path.read_bytes())
        proof=owner.proof(first);calls=deepcopy(self.calls);archived=self.archive(owner)
        self.assertEqual(proof,archived.proof(first));self.assertEqual(owner.proof(rows[-1]),archived.proof(rows[-1]));self.assertEqual(calls,self.calls)

    def test_parts2_actual_empty_opened_source_part_stays_owned_and_cannot_change_after_abandonment(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def callback(parent):
            intent(parent)
            if parent['label']=='parts' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Lost actual account boundary carrier open return')
        owner.segments.intent=callback
        with self.assertRaises(OSError):owner.capture()
        parent=deepcopy(owner.state['pending']['parts']['before']);calls=deepcopy(self.calls)
        again=self.owner();abandoned=again.recover();self.assertEqual('abandoned',abandoned['status']);self.assertEqual(calls,self.calls)
        self.assertEqual([dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest(),complete=False)],again.segments.inspect(parent))
        row=again.capture();again.proof(row);self.archive(again).proof(row)
        path=again.segments.store.path(parent['chunks'][0]);inode=path.stat().st_ino
        with path.open('ab') as stream:stream.write(b'{')
        self.assertEqual(inode,path.stat().st_ino)
        with self.assertRaises(NativeUIError):self.archive(again)

    def test_parts2_interrupted_partial_file_adopts_native_original_without_a_query(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def callback(parent):
            intent(parent)
            if parent['label']=='partial' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Lost actual partial file opened return')
        owner.segments.intent=callback
        with self.assertRaises(OSError):owner.capture()
        pending=deepcopy(owner.state['pending']);calls=deepcopy(self.calls)
        again=self.owner();row=again.recover();self.assertEqual('observed',row['status']);again.proof(row)
        self.assertEqual(calls,self.calls);partial=again.row_partial(row)
        self.assertEqual(pending['partialOriginal'],partial['orphanPartials'][0]['parent'])
        self.assertEqual([dict(bytes=0,sha256=hashlib.sha256(b'').hexdigest(),complete=False)],partial['orphanPartials'][0]['snapshots'])
        self.archive(again).proof(row)

    def test_parts2_rehashed_source_part_is_not_an_interrupted_partial_carrier(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def callback(parent):
            intent(parent)
            if parent['label']=='parts' and parent['chunks'] and parent['chunks'][-1]['phase']=='opened' and not lost:
                lost.append(True);raise OSError('Retained original account-boundary prefix')
        owner.segments.intent=callback
        with self.assertRaises(OSError):owner.capture()
        raw=deepcopy(owner.previous);state=unpack(raw['payload'])[0];parent=state['pending']['parts']['before']
        state['pending']['orphanPartials']=[dict(parent=deepcopy(parent),snapshots=owner.segments.inspect(parent))];raw['payload']=pack([state])
        with self.assertRaises(NativeUIError):owner.parse(raw)

    def test_parts2_exhausted_capacity_precedes_the_next_native_request(self):
        owner=self.owner();owner.state['nextSegment']=1024;calls=deepcopy(self.calls)
        # Existing bytes are checked by the normal owner; the capacity guard
        # itself must precede factory construction or a native/model request.
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(calls,self.calls);self.assertIsNone(owner.state['pending'])


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarPostLogoutPartsTests(name) for name in loader.getTestCaseNames(AvatarPostLogoutPartsTests) if name.startswith('test_parts2_'))


if __name__=='__main__':unittest.main()
