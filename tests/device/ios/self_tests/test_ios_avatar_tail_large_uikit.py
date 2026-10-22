"""The actual near-limit UIKit2 raw reply crosses real bounded tail files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from ios.adapters import uikit_input
from ios.self_tests.avatar_uikit_fixture import UIKit2Boundary
from ios.self_tests.test_ios_avatar_postlogout_tail import AvatarPostLogoutTailTests


class AvatarTailLargeUIKitTests(AvatarPostLogoutTailTests):
    def test_large_uikit2_raw_is_typed_unchanged_before_and_after_real_tail_retention(self):
        f=self.f.f;owner=self.owner()
        query=dict(schemaVersion=1,action=uikit_input.ACTION,commandId='ios-'+'9'*32,runId=f.run,fixtureUrl=owner.uikit_fixture_url())
        low,high,last=0,2048,None
        while low<=high:
            count=(low+high)//2;candidate=UIKit2Boundary(f.now,lambda:round(f.clock*1000),pid=42)
            for _ in range(count):candidate.touch(lambda:None)
            raw=json.dumps(candidate.packet(query)).encode()
            if len(raw)<=uikit_input.LIMIT-128:last=candidate;low=count+1
            else:high=count-1
        self.assertIsNotNone(last);self.uikit=last
        row=owner.capture();record=owner.record(row['reference']);parent=record['uikit'];raw=owner.segments.read(parent)
        self.assertGreater(len(raw),uikit_input.LIMIT-8192);self.assertEqual(4,len(parent['chunks']))
        packet=json.loads(raw);uikit_input.original(packet);self.assertEqual(packet,owner.uikit(record))
        self.assertEqual(3,owner.proof(row)['iosAvatarPostLogoutTailProofVersion'])
        self.assertLess(self.store.path.stat().st_size,65536);self.assertLess(owner.file(row['index']).path.stat().st_size,65536)
        for chunk in parent['chunks']:self.assertLess(owner.segments.store.path(chunk).stat().st_size,1024*1024)
        archived=self.archive(owner);self.assertEqual(raw,archived.segments.read(parent));self.assertEqual(owner.proof(row),archived.proof(row))


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarTailLargeUIKitTests(name) for name in loader.getTestCaseNames(AvatarTailLargeUIKitTests) if name.startswith('test_large_uikit2_'))


if __name__=='__main__':unittest.main()
