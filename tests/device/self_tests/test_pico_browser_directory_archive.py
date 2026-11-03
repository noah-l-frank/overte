"""Private namespace strategy on the SAME Browser Parent/Actor/source graph.

Original product, GPU, Qt, controller and native clocks remain declared models.
Actual loopback servers, worker process, archive files and OFDs are exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from adapters.chat_journey.archive_file import signature
from adapters.pico4.tablet_web_binding import archive_sentry_prefix,retained
from adapters.script_journey.lock import ScriptSourceLock
from self_tests import test_pico_browser_independent_process as independent
from self_tests import test_pico_tablet_web_flow as flow
from self_tests import test_pico_tablet_web_stereo_flow as stereo
from self_tests.pico_browser_fixture import PicoTarget


class PicoBrowserDirectoryArchiveTests(unittest.TestCase):
    def make(self):
        class DirectoryFixture(flow.PicoTabletWebFlowTests):
            def make_target(self):
                state=self.path/archive_sentry_prefix('target').removesuffix('-archive-owner-')
                state.mkdir(mode=0o700)
                target=PicoTarget(self.clock,self.client,self.foreign,state,
                    source_lock=ScriptSourceLock(self.path/'script-sources.lock'))
                target.pico_configuration=('explicit-private-host-model',self.path)
                return target
        class DirectoryStereo(stereo.PicoTabletWebStereoFlowTests):fixture_type=DirectoryFixture
        class DirectoryCase(independent.PicoBrowserIndependentProcessTests):stereo_fixture_type=DirectoryStereo
        case=DirectoryCase('runTest');case.setUp();self.addCleanup(case.doCleanups)
        return case

    def test_existing_original_return_capture_archive_and_actual_host_close_use_the_same_graph(self):
        case=self.make();f=case.f;owner=case.original_return()
        f.primary.retire_returned_actor_captures(owner);capture=f.primary.remote_capture_retirement
        originals={row['store'].path.name:(row['raw'],signature(row['store'].path.lstat()))
            for row in capture.catalog.rows.values() if row['store'].path.parent==f.target.path}
        state=f.target.path;self.assertTrue(retained(f.target,'target'))
        result=f.primary.archive_retired_sources(directory_retirement=True);plan=f.primary.evidence_archive
        self.assertEqual(3,result['picoBrowserEvidenceArchiveVersion']);self.assertTrue(plan.completed)
        self.assertEqual(5,result['archive']['chatEvidenceArchiveVersion']);self.assertFalse(state.exists())
        self.assertTrue(plan.namespace_group.moved);self.assertTrue(plan.namespace_group.destination.exists())
        self.assertTrue(retained(f.target,'target'));self.assertEqual(result,plan.receipt())
        for name,(raw,physical) in originals.items():
            path=plan.namespace_group.destination/name
            self.assertEqual(raw,path.read_bytes());self.assertEqual(physical,signature(path.lstat()))
        closed=f.primary.close_archived_host();self.assertTrue(closed['hostReleased'])
        self.assertFalse(closed['commonSequenceSucceeded']);self.assertTrue(plan.namespace_group.source_parent.closed)
        self.assertFalse(retained(f.target,'target'));self.assertEqual(closed,f.primary.browser_host_close.receipt())
        self.assertEqual(result,plan.receipt());self.assertTrue(owner.close_host())

    def test_changed_whole_common_journey_then_original_archive_and_host_retirement(self):
        case=self.make();primary=case.f.primary;original=primary.archive_retired_sources
        # Select only the explicit production archive strategy. The original
        # common Journey, source readers, Actor and all deadlines are reused.
        primary.archive_retired_sources=lambda:original(directory_retirement=True)
        case.test_complete_shared_journey_then_original_independent_return_and_all_capture_retirement()

    def test_rootless_pending_file_directory_or_symlink_blocks_without_creating_a_state_namespace(self):
        for kind in ('file','directory','symlink'):
            with self.subTest(kind=kind):
                temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
                root=Path(temporary.name);root.chmod(0o700)
                adapter=SimpleNamespace(pico_configuration=('explicit-private-host-model',root))
                prefix=archive_sentry_prefix('target');path=root/(prefix+'a'*32+'.json.pending')
                if kind=='file':path.write_bytes(b'unknown-partial-owner')
                elif kind=='directory':path.mkdir(mode=0o700)
                else:path.symlink_to('missing-original')
                self.assertTrue(retained(adapter,'target'))
                self.assertFalse((root/prefix.removesuffix('-archive-owner-')).exists())


if __name__=='__main__':unittest.main()
