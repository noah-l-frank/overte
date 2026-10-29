"""Actual33rd WDA/PNG/Node sample and same-original recovery/cleanup.

All native/UIKit/clock producers remain explicitly modeled. This is not the
public full26, independent Actor or physical/native/GPU qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import tablet_web_aggregate_root as aggregate
from ios.adapters import tablet_web_child_rotation as rotation,tablet_web_rotation_fence as fence
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.adapters.tablet_web_samples import TabletWebSamples
from ios.adapters.tablet_web_sample_root import TabletWebSampleRoot,samples_owner,canonical_name
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletOwnedSampleRootTests(unittest.TestCase):
    @staticmethod
    def source_root(runtime):
        source=runtime.observer.source;expected=fence.scope(source.binding,source.run,source.role,source.fixture,source.pid)
        value=rotation.make(source);source.store.write(value,source.saved)
        def guard():rotation.decode(source.store.read(),expected);return True
        def intent(kind,value):
            previous=source.store.read();current=rotation.with_copy_intent(previous,kind,value,expected)
            source.store.write(current,previous)
        copies=OriginalFrameStore(source.root,source.binding,source.run,source.role,guard,intent,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=source.monotonic)
        copies.write(1,rotation.copy_body(value,expected))
        result=aggregate.open_owned(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,source.guard,
            epoch_ms=source.epoch_ms,monotonic=source.monotonic,admission=source.admission)
        runtime.observer.source=result;return result

    @staticmethod
    def pin(path):
        row=path.stat();return row.st_dev,row.st_ino,row.st_size,row.st_mtime_ns,row.st_ctime_ns,path.read_bytes()

    def test_actual32_then33_pngs_lost34_original_return_recovers_without_get_replay_and_all_files_retire(self):
        fixture=PairedTabletFixture(self);boundary=fixture.boundary;primary=fixture.primary
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));ticket='b'*32
        fixture.fixture.journal.activate(RUN,ticket,'open',{})
        with primary.parts() as runtime:
            files=OwnedTabletWebAppFiles(None,PrivateFeatureState(boundary.root/'sample-root-normal-app-input.json'),boundary.binding)
            owned=files.reserve_app(RUN,runtime.observer.source.fixture,ticket)
            runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
            boundary.load(boundary.directories[owned['runId']].as_uri()+'/script.js');boundary.ui.qt.opened=True;runtime.remember_app(owned)
            ui=NativeUI(runtime.client,boundary.binding['sessionId'],lambda:runtime.process() is not None,monotonic=boundary.mono,sleep=boundary.sleep)
            row=next(item for item in boundary.ui.controls() if item['id']=='tablet-web-app.open')
            ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
            runtime.tail_source();source=self.source_root(runtime);boundary.source=source
            policy=fixture.settings['imagePolicy'];root=boundary.root
            def gets():return sum(method=='GET' and path.endswith('/screenshot') for method,path in fixture.sdk.calls)
            def observe_sample():
                # Match each ordinary Feature.observe operation separately;
                # never extend one operation across all32 screenshot inputs.
                with primary.operation():return runtime.observe_image(root,policy,ticket)
            began=gets();captured=[]
            for _index in range(32):captured.append(observe_sample())
            self.assertEqual(32,gets()-began)
            legacy=TabletWebSamples(runtime,root,policy);self.assertEqual(32,len(legacy.state['records']))
            parent=source.root/canonical_name(RUN,'primary');before=self.pin(parent)
            with self.assertRaises(NativeUIError):legacy.capture(ticket)
            self.assertEqual(32,gets()-began);self.assertEqual(before,self.pin(parent))
            captured.append(observe_sample());self.assertEqual(33,gets()-began)
            active=samples_owner(runtime,root,policy);self.assertIs(type(active),TabletWebSampleRoot)
            self.assertEqual(33,captured[-1]['sample']['index']);self.assertEqual(1,len(active.state['records']))
            self.assertEqual(before,self.pin(parent))
            first=active.read(captured[0]['sample']);first_bytes=first['raw'];first_png=first['row']['png']['name']
            last=active.read(captured[-1]['sample']);self.assertNotEqual(first['row']['png']['nonce'],last['row']['png']['nonce'])
            self.assertEqual(first_bytes,active.export(first_png))
            write=OriginalFrameStore.write;lost=[]
            def actual(store,index,frame):
                result=write(store,index,frame)
                if store.namespace=='tabletweb-screen-samples' and index==34 and not lost:
                    lost.append(deepcopy(result));raise OSError('Actual saved34th original local return lost')
                return result
            with patch.object(OriginalFrameStore,'write',actual),self.assertRaises(OSError):observe_sample()
            self.assertEqual(1,len(lost));self.assertEqual(34,gets()-began)
            current=samples_owner(runtime,root,policy);self.assertEqual('returned',current.state['pending']['status'])
            intent=deepcopy(current.state['original']);path=current.originals.path(intent);original=self.pin(path);calls=list(fixture.sdk.calls)
            with self.assertRaises(NativeUIError):current.capture(ticket)
            # This is the SAME cleanup_files path selected by ordinary
            # Feature cleanup, including saved-only return recovery first.
            current.cleanup_files();reference=current.state['records'][-1];self.assertEqual(34,reference['index'])
            self.assertEqual(original,self.pin(path));self.assertEqual(calls,fixture.sdk.calls)
            self.assertEqual(before,self.pin(parent));self.assertEqual(first_bytes,current.export(first_png))
            # Existing single Stage0 PNG owner really unlinks ALL34 owned
            # inodes; immutable raw fragments and both sample epochs remain.
            saved=samples_owner(runtime,root,policy,historical=True).files_absent()
            self.assertTrue(saved);self.assertEqual(34,gets()-began)
            for original in captured:self.assertFalse((root/current.read(original['sample'])['row']['png']['name']).exists())
            self.assertFalse((root/current.read(reference)['row']['png']['name']).exists())
            self.assertEqual(first_bytes,current.export(first_png));self.assertEqual(before,self.pin(parent))
            # A later35th real PNG without any original-file intent is NOT
            # the saved-return case. No cleanup/recovery may invent a receipt.
            def unsaved(store,index,frame):
                if store.namespace=='tabletweb-screen-samples' and index==35:
                    raise OSError('Actual35th original write unavailable before intent')
                return write(store,index,frame)
            with patch.object(OriginalFrameStore,'write',unsaved),self.assertRaises(OSError):observe_sample()
            self.assertEqual(35,gets()-began);held=samples_owner(runtime,root,policy)
            self.assertEqual('failed',held.state['pending']['status']);self.assertIsNone(held.state['original'])
            held_path=root/held.state['pending']['png']['name'];self.assertTrue(held_path.exists());calls=list(fixture.sdk.calls)
            for operation in (held.recover_original,held.cleanup_files,lambda:held.capture(ticket)):
                with self.assertRaises(NativeUIError):operation()
            historical=samples_owner(runtime,root,policy,historical=True)
            self.assertEqual('failed',historical.state['pending']['status'])
            with self.assertRaises(NativeUIError):historical.files_absent()
            self.assertTrue(held_path.exists());self.assertEqual(calls,fixture.sdk.calls)
            # Keep the authentic old parent inode OUTSIDE the actual scope;
            # no new unknown member can mask a samebytes/newinode failure.
            external=tempfile.TemporaryDirectory(prefix='tablet-sample-parent-original-');self.addCleanup(external.cleanup)
            previous=Path(external.name)/'sample32-parent.original.json';parent.rename(previous)
            parent.write_bytes(before[-1]);parent.chmod(0o600);self.assertEqual(before[1],previous.stat().st_ino)
            self.assertNotEqual(before[1],parent.stat().st_ino);calls=list(fixture.sdk.calls)
            with self.assertRaises(NativeUIError):samples_owner(runtime,root,policy,historical=True)
            self.assertEqual(calls,fixture.sdk.calls);self.assertEqual(before[-1],previous.read_bytes())
        self.assertEqual([],fixture.sdk.errors)


if __name__=='__main__':unittest.main()
