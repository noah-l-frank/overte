"""Actual Node page -> original Root4 -> existing historical image context.

No PNG, physical native authority or full26 result is fabricated here. The
existing actual page fixture keeps its explicit native/clock producers.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters import tablet_web_child_rotation as rotation,tablet_web_rotation_fence as fence
from ios.self_tests import test_ios_tablet_web_page_flow as page


class TabletAggregateImageContextTests(unittest.TestCase):
    def setUp(self):
        fixture=page.TabletPageFlowTests();self.addCleanup(fixture.doCleanups)
        self.b=fixture.opened();self.runtime=self.b.runtime
        self.runtime.observe();source=self.runtime.observer.source
        expected=fence.scope(source.binding,source.run,source.role,source.fixture,source.pid)
        value=rotation.make(source);source.store.write(value,source.saved)
        def guard():rotation.decode(source.store.read(),expected);return True
        def intent(kind,value):
            previous=source.store.read();current=rotation.with_copy_intent(previous,kind,value,expected)
            source.store.write(current,previous)
        copies=OriginalFrameStore(source.root,source.binding,source.run,source.role,guard,intent,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=source.monotonic)
        copies.write(1,rotation.copy_body(value,expected))
        current=aggregate.open_owned(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,source.guard,
            epoch_ms=source.epoch_ms,monotonic=source.monotonic,admission=source.admission)
        self.runtime.observer.source=self.b.source=current
        self.original=self.runtime.observe();self.runtime.proof_cache=None
        self.tail=dict(tabletWebTailSourceVersion=1,bootstrap=deepcopy(self.original['bootstrap']),
            primaryBootstrap=deepcopy(self.original['primaryBootstrap']),observation=deepcopy(self.original['observation']))

    def test_actual_page_original_routes_owned_root_and_existing_image_context_keeps_copies_and_expires(self):
        before=len(self.b.commands)
        with self.runtime.image_observation_context(self.original,self.b.root) as (observed,tail):
            value=tail(self.tail)
            self.assertEqual(self.original['observation']['reference']['index'],value['row']['index'])
            self.assertEqual('reference',observed['public']['state']['page'])
            value['frame']['state']['iosTabletWebStateVersion']=0
            self.assertEqual(2,tail(self.tail)['frame']['state']['iosTabletWebStateVersion'])
        with self.assertRaises(NativeUIError):tail(self.tail)
        self.assertEqual(before,len(self.b.commands))

    def test_same_bytes_owned_child_inode_change_during_actual_tail_read_invalidates_context(self):
        before=len(self.b.commands);actual=OriginalFrameStore.read;changed=[]
        path=self.runtime.observer.source.children['trace'].store.path;inode=path.stat().st_ino
        def read(store,value):
            result=actual(store,value)
            if not changed:
                state=self.runtime.observer.source.children['trace'].store
                body=state.read();state.write(body,body);changed.append(path.stat().st_ino)
            return result
        with self.assertRaises(NativeUIError):
            with self.runtime.image_observation_context(self.original,self.b.root) as (_observed,tail):
                with patch.object(OriginalFrameStore,'read',read):tail(self.tail)
        self.assertEqual(1,len(changed));self.assertNotEqual(inode,changed[0]);self.assertEqual(before,len(self.b.commands))


if __name__=='__main__':unittest.main()
