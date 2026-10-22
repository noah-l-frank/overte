"""Actual normal restore, unchanged source journals and new-process PNG owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_restored_image import NavigationRestoredImage
from ios.self_tests import test_ios_navigation_restored_state as sources


class NavigationRestoredImageTests(unittest.TestCase):
    setUp=sources.NavigationRestoredStateTests.setUp
    action=sources.NavigationRestoredStateTests.action
    ready=sources.NavigationRestoredStateTests.ready
    restart_call=sources.NavigationRestoredStateTests.restart_call
    install=sources.NavigationRestoredStateTests.install
    acquire=sources.NavigationRestoredStateTests.acquire

    def owner(self,call,request,*,historical=False):
        h=self.h
        return NavigationRestoredImage(PrivateFeatureState(h.root/('ios-navigation-restored-primary-'+request[4:]+'.json')),
            h.root,call['process_context']['restart']['input']['newBinding'],h.run,'primary',request,h.flow.lock,lambda:h.sdk.okay,
            native=None if historical else self.new.native,sources=None if historical else self.new.sources,
            fixture=None if historical else h.fixture,frame_factory=None if historical else self.new.gpu.factory,
            historical=historical,epoch_ms=h.now,monotonic=h.mono,sleep=h.sdk.gpu.sleep,
            process_context=call['process_context'],owner_files=call['owner_files'],directory=call['directory'],previous=self.prior_owner)

    def test_current_static_render_replays_without_sdk_and_keeps_all_root_lifetimes_explicit(self):
        call=self.acquire();h=self.h;request='ios-'+uuid.uuid4().hex
        with h.flow.held():
            owner=self.owner(call,request);result,proof,raw=owner.acquire(h.now())
            self.assertEqual('43',proof['binding']['processIdentity']);self.assertTrue(proof['lifetimeEndRequired'])
            self.assertEqual(b'\x89PNG\r\n\x1a\n',raw[:8]);self.assertEqual('A',result['rendered']['location'])
            self.assertEqual(43,owner.originals()['capture']['processId'])
            self.assertEqual('retained',proof['addressRoot']['root']['status'])
            commands=deepcopy(self.new.gpu.commands);h.sdk.okay=False
            frozen=self.owner(call,request,historical=True)
            self.assertEqual((result,proof,raw),frozen.archive());self.assertEqual(commands,self.new.gpu.commands)
            with self.assertRaises(NativeUIError):owner.bound()


if __name__=='__main__':unittest.main()
