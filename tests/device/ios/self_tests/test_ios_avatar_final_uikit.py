"""Global original UIKit callback quiet, independent of Keys and Qt pointers."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_avatar_final import AvatarFinalTests


class AvatarFinalUIKitTests(AvatarFinalTests):
    def test_uikit_tail3_callback_between_quiet_samples_cannot_be_hidden_by_ended_contacts(self):
        owner=self.owner();first=self.capture(owner,1);original=owner.file(first['index']).path.read_bytes()
        self.clock[0]+=1.6
        self.cases['actor'].uikit.touch(lambda:None)
        second=self.capture(owner,2);self.clock[0]+=1.6;third=self.capture(owner,3)
        # The UIKit contacts have genuinely ended and the callbacks returned;
        # the earlier interval nevertheless contains new global dispatch work.
        actual=owner.group(owner.record(third))['actor']
        packet=actual['tail'].uikit(actual['ui']);self.assertEqual([],packet['pendingDispatches'])
        self.assertTrue(all(not row['active'] for row in packet['contacts']))
        with self.assertRaises(NativeUIError):owner.quiet([first,second,third],sequence=4)
        self.clock[0]+=1.6;fourth=self.capture(owner,4)
        proof=owner.quiet([second,third,fourth],sequence=5)
        self.assertEqual({'primary','actor'},set(proof['bilateralQuiet']))
        for group in (second,third,fourth):
            for parts in owner.group(owner.record(group)).values():self.assertEqual(3,parts['proof']['iosAvatarPostLogoutTailProofVersion'])
        counts={subject:deepcopy(case.channel_calls) for subject,case in self.cases.items()}
        archived=self.archive(owner);self.assertEqual(proof,archived.quiet([second,third,fourth],sequence=5))
        self.assertEqual(original,owner.file(first['index']).path.read_bytes())
        self.assertEqual(counts,{subject:case.channel_calls for subject,case in self.cases.items()})


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarFinalUIKitTests(name) for name in loader.getTestCaseNames(AvatarFinalUIKitTests) if name.startswith('test_uikit_'))


if __name__=='__main__':unittest.main()
