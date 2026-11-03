"""Current/stale/foreign pre-import UI originals and interrupted PNG custody."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_ui_source import AssetsUiSource
from ios.adapters.assets_ui_samples import AssetsUiSamples
from adapters.normal_ui import NativeUIError
from feature_journeys.evidence import MarkerNotReady
from ios.self_tests.assets_ui_screen_fixture import UiFixture,RUN,TICKET


class AssetsUiSampleTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);self.root=Path(temp.name);self.root.chmod(0o700)
        self.f=UiFixture(self,self.root)
    def test_actual_normal_upload_browser_original_screen_qualifies_before_any_Model_import(self):
        self.assertFalse(self.f.b.entities);self.assertFalse(self.f.b.models)
        owner=self.f.samples();reference=owner.capture(TICKET);value=owner.read(reference)
        self.assertEqual('browse',value['measured']['checkpoint']);self.assertEqual(self.f.subject,value['measured']['subjectControl'])
        self.assertEqual(self.f.last_png,value['raw']);self.assertEqual(1,len(self.f.gets))
        self.assertFalse(self.f.b.entities);self.assertFalse(self.f.b.models)
        owner.cleanup_files();owner.files_absent();self.assertEqual(value['raw'],owner.read(reference)['raw'])
    def test_original_UI_and_PNG_replay_with_all_live_sends_and_writes_forbidden(self):
        owner=self.f.samples();reference=owner.capture(TICKET);original=owner.read(reference);owner.cleanup_files()
        files={str(path):(path.stat().st_ino,path.read_bytes()) for path in self.root.rglob('*') if path.is_file()}
        def forbidden(*_args,**_kwargs):raise AssertionError('Historical source may not send, acquire or write')
        with (patch.object(self.f.b,'exchange',side_effect=forbidden),patch.object(self.f.b.native_clock,'send',side_effect=forbidden),
              patch.object(PrivateFeatureState,'write',side_effect=forbidden)):
            source=AssetsUiSource.from_archive(self.f.source.store.read(),self.f.source.store,self.f.upload,self.f.marker,self.f.f.lock,
                subject=self.f.subject,checkpoint='browse')
            replay=AssetsUiSamples(source,self.f.artifacts,self.f.policy,SimpleNamespace(call=forbidden),forbidden,historical=True)
            self.assertEqual(original['raw'],replay.read(reference)['raw']);self.assertTrue(replay.files_absent())
            with self.assertRaises(NativeUIError):replay.capture(TICKET)
        self.assertEqual(files,{str(path):(path.stat().st_ino,path.read_bytes()) for path in self.root.rglob('*') if path.is_file()})
    def test_fresh_WDA_ACK_with_actual_stale_marker_PNG_cannot_qualify(self):
        self.f.display_ticket='c'*32;owner=self.f.samples()
        with self.assertRaises(MarkerNotReady):owner.capture(TICKET)
        self.assertEqual(1,len(self.f.gets));self.assertEqual(1,len(owner.record_references()))
        with self.assertRaises(MarkerNotReady):owner.read(owner.record_references()[0])
        self.assertFalse(self.f.b.models)
    def test_current_ticket_from_foreign_run_cannot_qualify(self):
        self.f.display_run='f'*32;owner=self.f.samples()
        with self.assertRaises(MarkerNotReady):owner.capture(TICKET)
        self.assertEqual(1,len(self.f.gets));self.assertFalse(self.f.b.models)
    def test_actual_blank_UI_pixels_with_current_marker_cannot_qualify(self):
        self.f.blank=True;owner=self.f.samples()
        with self.assertRaises(AssertionError):owner.capture(TICKET)
        self.assertEqual(1,len(self.f.gets));self.assertFalse(self.f.b.models)
    def test_actual_normal_page_close_rejects_UI_source_before_any_screenshot_GET(self):
        owner=self.f.samples();self.f.b.exchange(dict(op='input',id='assets.home',action='activate'))
        with self.assertRaises(NativeUIError):owner.capture(TICKET)
        self.assertEqual([],self.f.gets);self.assertFalse(self.f.b.models)
    def test_actual_PNG_return_survives_lost_later_native_clock_and_unknown_GET_is_not_replayed(self):
        count=0
        def clock():
            nonlocal count
            count+=1
            if count==2:raise OSError('Modeled native clock return lost after actual WDA PNG')
            return self.f.native_clock()
        owner=self.f.samples(clock)
        with self.assertRaises((OSError,NativeUIError)):owner.capture(TICKET)
        self.assertEqual(1,len(self.f.gets));pending=owner.state['pending'];self.assertEqual('failed',pending['status'])
        self.assertIsNone(pending['png']);self.assertEqual(self.f.last_png,owner.raw.read(pending['archive']))
        with self.assertRaises(NativeUIError):self.f.samples().capture(TICKET)
        self.assertEqual(1,len(self.f.gets));owner.cleanup_files();owner.files_absent()
        self.assertEqual(self.f.last_png,owner.raw.read(pending['archive']))


if __name__=='__main__':unittest.main()
