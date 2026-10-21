"""Exact original sample copies remain historical after metadata retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_samples import IOSGraphicsSamples,GraphicsMarkerPending
from ios.self_tests.test_ios_graphics_samples import SamplesHarness,POLICY
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET

class OriginalArchiveTests(SamplesHarness,unittest.TestCase):
    def prepare(self):
        self.scene().prepare();s=self.samples();s.read(TICKET,self.sdk.host_epoch());return s
    def originals(self,s):
        return {r['requestId']:dict(sample=s.sample_store(r).read(),owner=s.owner(r).store.read()) for r in s.state['owners']}
    def archive(self,s,originals,**changes):
        values=dict(path=s.store.path,run=RUN,role=s.role,stage=s.stage,lock=self.lock,binding=s.binding,
            fixture_url=self.client.url,provider_instance=s.instance,artifact_root=self.root/'pixels',image_policy=POLICY,originals=originals)
        return IOSGraphicsSamples.archive_owned(s.previous,**(values|changes))
    def remove_metadata(self,s):
        s.store.discard(s.previous)
        for row in s.state['owners']:
            store=s.sample_store(row);store.discard(store.read());store=s.owner(row).store;store.discard(store.read())
    def test_actual_originals_survive_metadata_removal_without_sdk_or_new_clocks(self):
        with self.lock.held():
            s=self.prepare();data=self.originals(s);expected=deepcopy(s.state);self.remove_metadata(s);self.sdk.clock+=100
            with patch.object(self.adapter,'normal_feature_runtime',side_effect=AssertionError('No live SDK')):
                self.assertEqual(expected,self.archive(s,data))
            self.assertIsNone(s.store.read())
            with self.assertRaises(NativeUIError):self.archive_index(s)
    def test_missing_extra_foreign_role_and_new_pid_cannot_fill_original_scope(self):
        with self.lock.held():
            s=self.prepare();data=self.originals(s)
            for altered in ({},dict(data,unexpected={})):
                with self.assertRaises(NativeUIError):self.archive(s,altered)
            changed=deepcopy(data);changed[next(iter(changed))]['sample']['role']='actor'
            with self.assertRaises(NativeUIError):self.archive(s,changed)
            with self.assertRaises(NativeUIError):self.archive(s,data,binding=dict(s.binding,processIdentity='43'))
    def test_changed_original_png_bytes_are_rejected_after_header_retirement(self):
        with self.lock.held():
            s=self.prepare();data=self.originals(s);path=self.root/'pixels'/s.owner(s.state['owners'][0]).name;self.remove_metadata(s)
            path.write_bytes(b'Changed original pixels')
            with self.assertRaises(NativeUIError):self.archive(s,data)
    def test_marker_pending_original_does_not_turn_into_an_observed_image_in_archive(self):
        with self.lock.held():
            self.scene().prepare();self.gpu.marker='f'*32;s=self.samples()
            with self.assertRaises(GraphicsMarkerPending):s.read(TICKET,self.sdk.host_epoch())
            state=self.archive(s,self.originals(s));self.assertEqual(0,state['sequence'])
            self.assertEqual('marker-pending',state['owners'][0]['phase'])
    def test_unresolved_capture_is_not_an_empty_ready_archive_after_app_death(self):
        with self.lock.held():
            self.scene().prepare();self.gpu.lost=True;s=self.samples()
            with self.assertRaises(NativeUIError):s.read(TICKET,self.sdk.host_epoch())
            commands=len(self.gpu.commands);self.sdk.running=False
            with self.assertRaises(NativeUIError):self.archive(s,{})
            self.assertEqual(commands,len(self.gpu.commands));self.assertEqual('reading',s.state['phase'])
if __name__=='__main__':unittest.main()
