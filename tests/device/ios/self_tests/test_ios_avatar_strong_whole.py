"""Whole strict source admission with current native producer generations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from ios.self_tests import test_ios_avatar_whole_cleanup as whole
from ios.self_tests.avatar_strong_domain import StrongDomain


class AvatarStrongWholeCleanupTests(whole.AvatarWholeCleanupTests):
    domain_type=StrongDomain


if __name__=='__main__':unittest.main()
