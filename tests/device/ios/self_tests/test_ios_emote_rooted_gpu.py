"""Actual file/journal joins with explicitly modeled native GPU replies."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios.adapters.emote_rooted_gpu import validate
from self_tests.test_owned_vulkan_world_frame import owner,World,BINDING,RUN,REQUEST,TICKET

class CurrentGPUTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.store=PrivateFeatureState(self.root/('graphics-world-frame-primary-0-'+REQUEST[4:]+'.json'))
        self.native=World();self.owner=owner(self.native,self.store,self.root)
        self.owner.capture(TICKET);self.captured=deepcopy(self.store.read());self.owner.release();self.original=deepcopy(self.store.read())
        self.flow=SimpleNamespace(root=self.root,role='primary',run=RUN,state=dict(binding=BINDING),lock=self.owner.lock,
            primary_lock=self.owner.lock,store=PrivateFeatureState(self.root/'ios-emote-primary-feature.json'))
    def parts_for(self,original):
        samples=SimpleNamespace(state=dict(phase='ready',rows=[{}]),record=lambda _:dict(requestId=REQUEST,owner=pack([original])))
        frames=SimpleNamespace(state=dict(records=[],pending=None))
        return dict(samples=samples,restoration=frames)
    def check(self,original=None):
        with self.owner.lock.held():return validate(self.flow,self.parts_for(self.original if original is None else original))
    def test_current_original_and_completed_absent_inspection_keep_identity_and_send_nothing(self):
        self.owner.release();before=deepcopy(self.store.read());commands=deepcopy(self.native.commands)
        self.assertEqual({self.store.path:before},self.check())
        self.assertEqual(before,self.store.read());self.assertEqual(commands,self.native.commands)
    def test_captured_current_owner_cannot_borrow_released_parent(self):
        self.store.write(self.captured,self.store.read());commands=deepcopy(self.native.commands)
        with self.assertRaises(NativeUIError):self.check()
        self.assertEqual(self.captured,self.store.read());self.assertEqual(commands,self.native.commands)
    def test_unknown_later_inspection_stays_unresolved_without_requery_or_release(self):
        send=self.native.send
        def lost(query):
            send(query)
            if query['operation']=='inspect':raise OSError('Actual modeled inspection return lost')
        self.native.send=lost
        with self.assertRaises(NativeUIError):self.owner.release()
        self.native.send=send;before=self.store.read();commands=deepcopy(self.native.commands)
        with self.assertRaises(NativeUIError):self.check()
        self.assertEqual(before,self.store.read());self.assertEqual(commands,self.native.commands)
    def test_missing_parent_owner_never_adopts_present_current_metadata(self):
        commands=deepcopy(self.native.commands)
        with self.owner.lock.held(),self.assertRaises(NativeUIError):validate(self.flow,self.parts_for(None))
        self.assertEqual(commands,self.native.commands)
    def test_absent_parent_metadata_is_retained_explicitly_and_later_presence_is_rejected(self):
        request='ios-'+'b'*32;parts=self.parts_for(None)
        parts['samples'].record=lambda _:dict(requestId=request,owner=pack([None]))
        path=self.flow.store.path.with_name('graphics-world-frame-primary-0-'+request[4:]+'.json')
        commands=deepcopy(self.native.commands)
        with self.owner.lock.held():self.assertEqual({path:None},validate(self.flow,parts))
        store=PrivateFeatureState(path);store.write(dict(unresolved=True),None)
        with self.owner.lock.held(),self.assertRaises(NativeUIError):validate(self.flow,parts)
        self.assertEqual(dict(unresolved=True),store.read());self.assertEqual(commands,self.native.commands)

if __name__=='__main__':unittest.main()
