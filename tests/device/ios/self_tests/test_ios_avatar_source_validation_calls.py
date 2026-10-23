"""One full typed channel validation per frame, with full previous checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from ios.adapters import avatar_social_http
from ios.self_tests import test_ios_avatar_sources as fixture


class AvatarSourceValidationCallTests(unittest.TestCase):
    def test_current_http_packet_is_not_fully_validated_twice_for_one_frame_join(self):
        f=fixture.AvatarSourcesTests();f.setUp();self.addCleanup(f.doCleanups)
        with f.lock.held():
            owner=f.owner();before=owner.read();after=owner.read();calls=[];validate=avatar_social_http.validate
            def counted(value,*args,**kwargs):
                calls.append(value['requestId']);return validate(value,*args,**kwargs)
            with patch.object(avatar_social_http,'validate',counted):owner.validate_frame(after,before)
        self.assertEqual(1,calls.count(after['originals']['http']['requestId']))
        self.assertEqual(1,calls.count(before['originals']['http']['requestId']))


if __name__=='__main__':unittest.main()
