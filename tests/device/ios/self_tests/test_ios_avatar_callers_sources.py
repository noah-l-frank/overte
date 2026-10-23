"""Versioned native children retain their originals in the existing Source2."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.self_tests import avatar_callers2_fixture as current
from ios.self_tests.test_ios_avatar_sources import AvatarSourcesTests


class AvatarCallersSourcesTests(AvatarSourcesTests):
    def test_callers2_actual_source_archive_preserves_native_tables_and_private_reconstruction(self):
        self.fixture.prototypes['scripts']=current.scripts2();current.timer2(self.fixture.prototypes['scripts'])
        self.fixture.prototypes['http']=current.http2()
        # The unchanged native Entities1 getter can genuinely be empty before
        # any entity API call. It supplies no invented returned UUID or caller.
        self.fixture.prototypes['entities']=dict(iosAvatarEntitiesVersion=1,requestId='ios-'+'c'*32,runId=self.fixture.run,
            instance='d'*32,sequence=1,processId=42,clockDomain='native-main-avatar-entities',
            clockBefore=dict(epochMs=current.EPOCH+100,monotonicMs=100),clockAfter=dict(epochMs=current.EPOCH+110,monotonicMs=110),
            source=dict(avatarEntitiesLedgerVersion=1,instance='e'*32,complete=True,events=[]))
        with self.lock.held():
            owner=self.owner();frame=owner.read();before=deepcopy(self.fixture.sources)
            self.assertEqual(2,frame['originals']['scripts']['iosAvatarScriptsVersion']);self.assertEqual(2,frame['originals']['http']['iosAvatarSocialHttpVersion'])
            self.assertEqual(self.fixture.prototypes['scripts']['source'],frame['originals']['scripts']['source'])
            archived=self.owner(historical=True);self.assertEqual(frame,archived.frames[0]);self.assertEqual(before,self.fixture.sources)
            self.assertEqual(2,owner.previous['iosAvatarSourcesVersion'])


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarCallersSourcesTests(name) for name in loader.getTestCaseNames(AvatarCallersSourcesTests)
        if name.startswith('test_callers2_'))


if __name__=='__main__':unittest.main()
