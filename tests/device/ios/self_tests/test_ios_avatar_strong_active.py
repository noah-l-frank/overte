"""Selected full active recipes use original AvatarApp/People/request sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.self_tests import test_ios_avatar_whole_active as active
from ios.self_tests.avatar_strong_app_domain import StrongAvatarAppDomain


class AvatarStrongActiveTests(active.AvatarWholeActiveTests):
    domain_type=StrongAvatarAppDomain


if __name__=='__main__':unittest.main()
