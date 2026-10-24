"""Keep original capture pixels separate from a later Save/Share phase.

The marker endpoint is an explicit native producer seam. Original VM/native
readers, host capture inodes/bytes, role reducer and common evidence rule run.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import test_snapshots_role as source
from feature_journeys.engine import Journey


class SnapshotsMarkerPhaseTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='snapshot-marker-phase-');self.addCleanup(temp.cleanup)
        self.b=source.SnapshotRolesBoundary(temp.name)
        self.ticket='d'*32
        self.marker=dict(source=dict(phoneCreateFixtureVersion=2,originalInput=dict(ticket=source.TICKET)))
        self.b.feature.state['marker']=dict(operation='prepare')
        self.restore=Mock()
        self.b._create_fixture_observer=lambda *_args,**_kwargs:SimpleNamespace(read=lambda *_:deepcopy(self.marker),restore=self.restore)
        self.render=Mock(side_effect=AssertionError('An older marker cannot authorize a current render acquisition'))
        self.b._world_render_capture=self.render
    def phase(self,verb):
        self.b.phase=lambda:dict(active=True,activations=[dict(ticket=self.ticket,stimulus=dict(verb=verb))])
        self.b.provider['ticket']=self.ticket
        self.b.provider['activations'].append(dict(ticket=self.ticket,verb=verb,capturedEpochMs=self.b.epoch))
    def test_later_save_keeps_actual_original_file_without_claiming_a_retimed_world_png(self):
        self.phase('save')
        with patch('overte_phone_snapshots_role.marker_ready',side_effect=AssertionError('No current marker image requested')):
            with self.b.role() as role:
                measured=role.read(0);frame=deepcopy(role.frames[-1])
        self.render.assert_not_called();self.assertEqual(self.marker,frame['marker'])
        self.assertFalse(frame['imageReady']);self.assertIsNone(frame['image']);self.assertIsNone(frame['capture'])
        self.assertEqual(self.ticket,frame['ticket']);self.assertEqual(source.TICKET,self.b.feature.state['captureTicket'])
        self.assertEqual(1,measured['state']['files'])
        # A private capture alone is not evidence of the later Save result.
        self.assertFalse(any(row['kind']=='file' for row in measured['artifacts']))
        self.assertFalse(any(row['kind']=='image' for row in measured['artifacts']))
        binary=frame['binaries'][0]
        self.assertEqual(self.b.raw,source.SnapshotsBinary.archive(self.b.root,binary))
        self.assertEqual(19000,binary['acquisition']['nativeClosedEpochMs'])
        with self.b.role() as role:self.assertEqual(self.marker,role.frames[-1]['marker'])
        self.restore.assert_called_once_with([self.marker])
    def test_missing_current_marker_image_still_fails_the_common_image_requirement(self):
        self.phase('background-resume')
        with self.b.role() as role:measured=role.read(0)
        engine=Journey('snapshots',source.RUN,self.b.feature.fixture_url,invoke=lambda *_:None,witness=lambda:None,
            activate=lambda *_:None,read_artifact=lambda *_:None,image_policy=dict(screen=source.POLICY,file=source.POLICY),
            continuity=lambda *_:None,monotonic=lambda:self.b.clock,epoch_ms=lambda:self.b.epoch,sleep=lambda _:None,report=lambda _:None)
        with self.assertRaisesRegex(AssertionError,'Required original image evidence is missing'):
            engine.artifacts(measured,self.ticket,['image'])
        self.render.assert_not_called();self.assertEqual(source.TICKET,self.marker['source']['originalInput']['ticket'])

    def test_refreshed_marker_uses_latest_input_instead_of_immutable_creation_ticket(self):
        self.phase('save')
        # Version 3 preserves creation ownership while its latest refresh names
        # the actual visible challenge. Neither an older challenge nor a matching
        # creation ticket can authorize a new image for this Save phase.
        self.marker['source'].update(phoneCreateFixtureVersion=3,
            originalInput=dict(ticket=self.ticket),lastRefreshInput=dict(ticket=source.TICKET))
        with patch('overte_phone_snapshots_role.marker_ready',side_effect=AssertionError('Creation ticket is not the latest challenge')):
            with self.b.role() as role:
                measured=role.read(0);frame=deepcopy(role.frames[-1])
        self.render.assert_not_called()
        self.assertEqual(self.marker,frame['marker'])
        self.assertEqual(self.ticket,frame['ticket'])
        self.assertFalse(frame['imageReady']);self.assertIsNone(frame['image'])
        self.assertFalse(any(row['kind']=='image' for row in measured['artifacts']))


if __name__=='__main__':unittest.main()
