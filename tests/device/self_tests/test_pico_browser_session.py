"""Actual Journey/export/configuration; operation coordinator is a declared model.

These ordering cases do not qualify the canonical operation owner or native VR.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapter_operation_host import PinnedFile
from adapters.pico4.browser_session import PicoBrowserSession, UNRESOLVED
from feature_journeys.engine import Journey
from self_tests.test_feature_journeys import Boundary, POLICY, RUN


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pico-browser-session-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.root.chmod(0o700)
        self.events = []; self.failure = None; self.exits = []
        self.url = 'http://controlled.test/feature-fixture/v1/runs/' + RUN + '/'
        self.config = PrivateFeatureState(self.root/'config.json')
        self.config.write(dict(picoBrowserRunConfigVersion=1,
            foreignFixtureUrl='http://foreign.test/feature-fixture/v1', actorToken='a'*64), None)
        fixture = self
        class Owner:
            manifest = fixture.root/'adapter.json'
            target = 'declared-model'
            def guard(self): pass
            def browser_component(self, run, url, operation, arguments=None, *, whole_budget):
                fixture.events.append(operation)
                fixture.assertEqual((RUN, fixture.url), (run, url))
                fixture.assertEqual(fixture.whole, whole_budget)
                if fixture.failure == operation: raise RuntimeError('Declared uncertain model result')
                if operation == 'consume':
                    return dict(journeyConsumptionReceivedVersion=2,
                        **{key:arguments[key] for key in ('nonce', 'recordSha256', 'commonSha256')})
                if operation == 'finalize':
                    return dict(runId=RUN, sequenceCompleted=True, hostReleased=True, deviceAcceptance=False)
                return dict(protocolOnly=True)
            @contextmanager
            def browser_input_context(self,run,url,operation,arguments,*,whole_budget):
                self.browser_component(run,url,'input.begin',dict(operation=operation,arguments=arguments),whole_budget=whole_budget)
                try:yield
                finally:self.browser_component(run,url,'input.end',whole_budget=whole_budget)
        self.owner = Owner()
        class Context:
            def __enter__(self): fixture.events.append('enter'); return fixture.owner
            def __exit__(self, kind, value, traceback): fixture.exits.append(kind); return False
        self.archive_paths=[]
        self.session = SimpleNamespace(operation_host=lambda artifacts:(self.archive_paths.append(artifacts) or Context()))
        self.client = SimpleNamespace(run=RUN, url=self.url.rsplit('/runs/', 1)[0],
            close=lambda:self.events.append('fixture.close'))
        now = time.monotonic()
        self.whole = dict(id='b'*32, startedMonotonic=now, deadlineMonotonic=now+120)

    def scope(self):
        return PicoBrowserSession(self.session, self.root, RUN, self.url, self.config.path, self.whole)

    def execute(self, scope):
        boundary = Boundary('tablet-web')
        journey = Journey('tablet-web', RUN, self.url, invoke=boundary.invoke, witness=boundary.witness,
            activate=boundary.activate, read_artifact=boundary.files.__getitem__, image_policy=deepcopy(POLICY),
            continuity=boundary.continuity, monotonic=lambda:boundary.clock, epoch_ms=boundary.epoch,
            sleep=boundary.sleep, report=boundary.reports.append, after_cleanup_baseline=scope.export.callback)
        scope.export.attach(journey); journey.execute()
        self.assertTrue(boundary.reports[-1]['sequenceCompleted'])
        return journey

    def test_actual_journey_exports_before_fixture_retirement_then_model_actor_return_and_close(self):
        scope = self.scope()
        with scope:
            prefix = ['python', 'adapter.py', '--kind', 'pico', '--native-binding', '--apk', 'owned.apk']
            with patch('adapters.pico4.browser_session.pico_command', return_value=prefix): scope.start_actor()
            journey = self.execute(scope)
            self.assertEqual(28, len(journey.phases))
            self.assertEqual(['enter', 'begin', 'actor.start', 'consume'], self.events)
            self.assertTrue(scope.finalize(self.client)['hostReleased'])
        self.assertEqual(['enter', 'begin', 'actor.start', 'consume', 'fixture.close', 'actor.return', 'finalize'], self.events)
        self.assertEqual([None], self.exits)
        self.assertTrue(scope.config_pin.owner.closed)
        self.assertTrue(scope.export.file.parent.closed)

    def test_uncertain_fixture_delete_is_attempted_once_and_never_returns_actor(self):
        scope = self.scope()
        def failed(): self.events.append('fixture.close'); raise OSError('Declared lost DELETE reply')
        self.client.close = failed
        with self.assertRaises(OSError):
            with scope:
                self.execute(scope); scope.finalize(self.client)
        self.assertEqual(1, self.events.count('fixture.close'))
        self.assertNotIn('actor.return', self.events)
        with self.assertRaises(NativeUIError): scope.close_fixture(self.client)
        self.assertTrue(scope.config_pin.owner.closed)

    def test_missing_finalization_exits_original_context_as_failure_and_keeps_export(self):
        scope = self.scope()
        with self.assertRaises(NativeUIError):
            with scope: self.execute(scope)
        self.assertEqual([NativeUIError], self.exits)
        self.assertTrue(scope.export.store.path.exists())
        self.assertTrue(scope.export.file.parent.closed)
        self.assertNotIn('actor.return', self.events)

    def test_uncertain_begin_unwinds_context_without_an_export_or_second_delivery(self):
        scope = self.scope(); self.failure = 'begin'
        with self.assertRaises(RuntimeError):
            with scope: self.fail('An uncertain begin cannot enter its body')
        self.assertEqual(['enter', 'begin'], self.events)
        self.assertEqual([RuntimeError], self.exits)
        self.assertIsNone(scope.export); self.assertTrue(scope.config_pin.owner.closed)

    def test_same_byte_configuration_replacement_refuses_before_private_send(self):
        scope = self.scope()
        try:
            replacement = self.root/'replacement.json'
            replacement.write_bytes(self.config.path.read_bytes()); replacement.chmod(0o600)
            self.config.path.rename(self.root/'retained-config.json'); replacement.rename(self.config.path)
            with self.assertRaises(ValueError): scope.call('actor.return')
            self.assertEqual([], self.events)
        finally:
            # The name changed; close only the original descriptor pair.
            self.assertTrue(scope.config_pin.owner.close())

    def test_common_files_coexist_with_the_strict_original_stdio_archive(self):
        from adapters.pico4.operation_archive import OperationArchive
        scope=self.scope()
        with self.assertRaisesRegex(RuntimeError,'Declared prefix stop'):
            with scope:
                self.assertEqual([self.root/'pico-browser-operation-archive'],self.archive_paths)
                self.assertEqual(0o700,scope.archive_path.stat().st_mode & 0o777)
                archive=OperationArchive(scope.archive_path,dict(declaredPrefix=True))
                try:
                    (self.root/'scene-ready.json').write_bytes(b'actual Common artifact')
                    archive.guard();scope.call('actor.return')
                    (scope.archive_path/'orphan.bin').write_bytes(b'unadmitted original')
                    with self.assertRaises(ValueError):archive.guard()
                    (scope.archive_path/'orphan.bin').unlink()
                finally:archive.close()
                raise RuntimeError('Declared prefix stop')
        self.assertEqual(['enter','begin','actor.return'],self.events)
        self.assertTrue(scope.artifact_parent.closed and scope.archive_directory.closed)

    def test_preexisting_archive_directory_file_or_symlink_is_never_adopted(self):
        for kind in ('directory','file','symlink'):
            with self.subTest(kind=kind):
                scope=self.scope();path=scope.archive_path
                if kind=='directory':path.mkdir(mode=0o700)
                elif kind=='file':path.write_bytes(b'original orphan')
                else:path.symlink_to(self.root,target_is_directory=True)
                try:
                    with self.assertRaises(FileExistsError):scope.__enter__()
                    self.assertEqual([],self.events);self.assertEqual([],self.archive_paths)
                    self.assertTrue(scope.artifact_parent.closed and scope.config_pin.owner.closed)
                finally:
                    if kind=='directory':path.rmdir()
                    else:path.unlink()

    def test_replaced_archive_or_parent_is_refused_before_another_dispatch(self):
        for kind in ('archive','parent'):
            with self.subTest(kind=kind):
                artifacts=self.root/('common-artifacts-'+kind);artifacts.mkdir(mode=0o700)
                scope=PicoBrowserSession(self.session,artifacts,RUN,self.url,self.config.path,self.whole)
                scope.__enter__();before=list(self.events)
                path=scope.archive_path if kind=='archive' else artifacts
                retained=path.with_name(path.name+'-retained')
                path.rename(retained);path.mkdir(mode=0o700)
                try:
                    with self.assertRaises(NativeUIError):scope.call('actor.return')
                    self.assertEqual(before,self.events)
                    self.assertFalse(scope.close_local())
                    self.assertFalse(scope.archive_directory.closed)
                finally:
                    path.rmdir();retained.rename(path)
                    self.assertTrue(scope.export.close_host())
                    for owner in (scope.config_pin.owner,scope.archive_directory,scope.artifact_parent):
                        if not owner.closed:self.assertTrue(owner.close())
                    UNRESOLVED[:]=[owner for owner in UNRESOLVED if owner is not scope]
                    scope.archive_path.rmdir()
                    self.events.clear();self.archive_paths.clear()

    def test_expired_budget_opens_no_configuration_or_cli_handles(self):
        now = time.monotonic(); self.whole.update(startedMonotonic=now-2, deadlineMonotonic=now-1)
        with patch('adapters.pico4.browser_session.PinnedFile', side_effect=AssertionError('No late open')):
            with self.assertRaises(NativeUIError): self.scope()
        self.assertEqual([], self.events)

    def test_mutable_configuration_cannot_replace_original_actor_authority_or_recover_by_reset(self):
        scope = self.scope(); original = deepcopy(scope.config)
        try:
            scope.config['actorToken'] = 'd'*64
            with self.assertRaises(NativeUIError): scope.call('actor.return')
            scope.config = original
            with self.assertRaises(NativeUIError): scope.call('actor.return')
            self.assertEqual([], self.events)
        finally:
            self.assertTrue(scope.close_local())

    def test_foreign_configuration_holder_is_neither_adopted_nor_closed(self):
        scope = self.scope(); original = scope.config_pin
        foreign_path = self.root/'foreign-private-config.json'
        foreign_path.write_bytes(self.config.path.read_bytes()); foreign_path.chmod(0o600)
        foreign = PinnedFile(foreign_path, 65536)
        try:
            scope.config_pin = foreign
            with self.assertRaises(NativeUIError): scope.call('actor.return')
            self.assertFalse(scope.close_local()); self.assertIn(scope, UNRESOLVED)
            self.assertFalse(original.owner.closed); self.assertFalse(foreign.owner.closed)
            self.assertEqual([], self.events)
        finally:
            self.assertTrue(original.owner.close()); self.assertTrue(foreign.owner.close())
            UNRESOLVED[:] = [owner for owner in UNRESOLVED if owner is not scope]


if __name__ == '__main__':
    unittest.main()
