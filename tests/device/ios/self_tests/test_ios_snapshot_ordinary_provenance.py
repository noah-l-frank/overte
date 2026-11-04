"""Prospective original custody/provenance counters; native producers are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation, snapshot_provenance as source
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_provenance_packet import SnapshotProvenancePacket
from ios.self_tests.snapshot_provenance_domain import ProvenanceCaptureDomain
from ios.self_tests.test_ios_snapshot_capture_rendered_review import RUN, TICKET


class SnapshotOrdinaryProvenanceTests(unittest.TestCase):
    def prepared(self):
        d = ProvenanceCaptureDomain(self)
        d.prepare()
        return d

    def capture(self, d, page):
        return d.runtime.capture_child(page)

    def test_actual_model_callback_png_and_capture_join_then_genuine_original_history_without_queries(self):
        d = self.prepared()
        with d.owner() as page:
            capture = self.capture(d, page)
            result = capture.provenance()
            child = capture.history('provenance', 1)
            original = child.historical()
            self.assertTrue(original['raw'].endswith('\n'))
            self.assertEqual(original['raw'], d.capture.raws[source.FILE])
            self.assertTrue(result['sameOrdinaryCallbackPixelsEstablished'])
            self.assertTrue(result['sceneFidelityRequired'] and result['independentActorRequired'] and result['wholeFeatureRequired'])
            scope = dict(store=capture.store, lock=capture.lock, binding=capture.binding, run=RUN,
                fixture_url=capture.phase.fixture_url, combined=True)
            packet_scope = (child.store, child.lock, child.binding, child.run, child.role, child.index)
            calls = (len(d.provenance_queries), d.capture.capture_count)
            pins = {p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in d.ctx.root.iterdir() if p.is_file()}
            def forbidden(*_a, **_k):
                raise AssertionError('Original archive attempted an acquisition/write')
            with patch.object(feature_observation, 'post_request', forbidden), patch.object(PrivateFeatureState, 'write', side_effect=forbidden):
                archived = IOSSnapshotCaptureOwner.archive(**scope)
                packet = SnapshotProvenancePacket.history(*packet_scope)
                self.assertEqual(result, packet.join_capture(archived))
                self.assertEqual(original, packet.historical())
            self.assertEqual(pins, {p.name:(p.stat().st_dev,p.stat().st_ino,p.read_bytes()) for p in d.ctx.root.iterdir() if p.is_file()})
            self.assertEqual(calls, (len(d.provenance_queries), d.capture.capture_count))

    def test_wrong_capture_request_cannot_join_or_reissue_original_provenance_query(self):
        d = self.prepared()
        d.provenance_fault = lambda value: value['source']['captures'][0].update(requestId='snap_1700000000000_999')
        with d.owner() as page:
            capture = self.capture(d, page)
            for _attempt in range(2):
                with self.assertRaises(NativeUIError):
                    capture.provenance()
        self.assertEqual(1, len(d.provenance_queries))
        self.assertEqual(1, d.capture.capture_count)

    def test_foreign_frame_source_process_refuses_before_native_original_admission(self):
        d = self.prepared()
        d.provenance_fault = lambda value: value['source']['captures'][0]['frame'].update(processId=43)
        with d.owner() as page:
            capture = self.capture(d, page)
            with self.assertRaises(NativeUIError):
                capture.provenance()
            slot = next(v for v in capture.state['slots'] if v['kind']=='provenance')
            self.assertIsNone(slot['sha256'])
            self.assertEqual('issued', capture.child(slot).state['phase'])
        self.assertEqual(1, len(d.provenance_queries))

    def test_same_capture_frame_index_change_between_original_reads_refuses(self):
        d = self.prepared()
        with d.owner() as page:
            capture = self.capture(d, page)
            capture.provenance()
            before = capture.history('provenance', 1).historical()['packet']
            after = deepcopy(before)
            after.update(requestId='ios-'+'e'*32, sequence=before['sequence']+1)
            after['source']['captures'][0]['frame']['frameIndex'] += 1
            with self.assertRaises(NativeUIError):
                source.validate(after, dict(schemaVersion=1, action=source.ACTION,
                    commandId=after['requestId'], runId=RUN), 42, previous=before)

    def test_same_capture_projection_change_between_original_reads_refuses(self):
        d = self.prepared()
        with d.owner() as page:
            capture = self.capture(d, page)
            capture.provenance()
            before = capture.history('provenance', 1).historical()['packet']
            after = deepcopy(before)
            after.update(requestId='ios-'+'e'*32, sequence=before['sequence']+1)
            after['source']['captures'][0]['frame']['camera']['projection'][0] += .125
            with self.assertRaises(NativeUIError):
                source.validate(after, dict(schemaVersion=1, action=source.ACTION,
                    commandId=after['requestId'], runId=RUN), 42, previous=before)

    def test_separate_worldframe_backend_cannot_relabel_ordinary_opengl_callback(self):
        d = self.prepared()
        d.provenance_fault = lambda value: value['source']['captures'][0]['frame'].update(backend='vulkan')
        with d.owner() as page, self.assertRaises(NativeUIError):
            self.capture(d, page).provenance()
        self.assertEqual(1, len(d.provenance_queries))

    def test_missing_model_callback_has_no_provenance_even_when_other_capture_facts_complete(self):
        d = ProvenanceCaptureDomain(self)
        d.deliver_callback = False
        d.prepare()
        with d.owner() as page:
            capture = self.capture(d, page)
            self.assertTrue(capture.result()['image'])
            with self.assertRaises(NativeUIError):
                capture.provenance()
        self.assertEqual(1, d.capture.capture_count)
        self.assertEqual(1, len(d.provenance_queries))

    def test_valid_capture_with_wrong_callback_rgba_hash_cannot_discharge_image_association(self):
        d = self.prepared()
        d.provenance_fault = lambda value: value['source']['captures'][0]['frame']['readback'].update(pixelSha256='0'*64)
        with d.owner() as page, self.assertRaises(NativeUIError):
            self.capture(d, page).provenance()
        self.assertEqual(1, d.capture.capture_count)
        self.assertEqual(1, len(d.provenance_queries))

    def test_same_byte_replacement_provenance_frame_inode_refuses_historical_original(self):
        d = self.prepared()
        with d.owner() as page:
            capture = self.capture(d, page)
            capture.provenance()
            child = capture.history('provenance', 1)
            saved = child.state['storage']
            path = child.files().path(saved)
            raw, identity = path.read_bytes(), path.stat().st_ino
            path.rename(path.with_name('retained-'+path.name))
            path.write_bytes(raw)
            path.chmod(0o600)
            self.assertNotEqual(identity, path.stat().st_ino)
            with self.assertRaises(NativeUIError):
                SnapshotProvenancePacket.history(child.store,child.lock,child.binding,child.run,child.role,child.index)
        self.assertEqual(1, len(d.provenance_queries))


if __name__ == '__main__':
    unittest.main()
