"""Actual same-SDK reentry cannot hide earlier native query ownership.

Real HTTP/AFC/private files execute over explicit native boundary models.
No query is repeated to reconstruct an existing original reference.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_native_reads import TabletNativeReads
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletAuxiliaryReentryTests(unittest.TestCase):
    def test_public_observe_after_new_runtime_keeps_actual_earlier_Script_original_reference(self):
        fixture=PairedTabletFixture(self);feature=fixture.primary
        feature.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        with feature.parts() as runtime:
            runtime.read_auxiliary('scripts');reference=deepcopy(runtime.auxiliary('scripts').state['records'][-1])
        with feature.parts() as rebuilt:
            calls=len(fixture.sdk.calls);files=set(fixture.boundary.root.glob('tabletweb-aux-*.json'))
            before={path:path.read_bytes() for path in files}
            refs=rebuilt.auxiliary_references()
            self.assertEqual(reference,refs['scripts']);self.assertEqual(calls,len(fixture.sdk.calls))
            self.assertEqual(files,set(fixture.boundary.root.glob('tabletweb-aux-*.json')))
            self.assertEqual(before,{path:path.read_bytes() for path in files})
        actual=feature.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));self.assertEqual([],actual['resources'])
    def test_unknown_own_query_and_foreign_existing_header_never_become_missing_history_or_new_send(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary
        with fixture.primary.parts() as runtime:
            runtime.read_auxiliary('scripts');owner=runtime.auxiliary('scripts')
            store=owner.store;original=store.read();foreign=deepcopy(original);foreign['binding']['sessionId']='foreign-existing-sdk'
            store.write(foreign,original)
        with fixture.primary.parts() as rebuilt:
            calls=len(fixture.sdk.calls)
            with self.assertRaises((NativeUIError,ValueError)):rebuilt.auxiliary_references()
            self.assertEqual(calls,len(fixture.sdk.calls));self.assertEqual(foreign,store.read())
        store.write(original,foreign)
        with fixture.primary.parts() as runtime:
            b.lost='feature-script-observe'
            with self.assertRaises((NativeUIError,OSError)):runtime.read_auxiliary('scripts')
        with fixture.primary.parts() as rebuilt:
            calls=len(fixture.sdk.calls)
            with self.assertRaises((NativeUIError,ValueError)):rebuilt.auxiliary_references()
            self.assertEqual(calls,len(fixture.sdk.calls))
            history=TabletNativeReads(b.root,b.binding,RUN,'primary','scripts',rebuilt.observer.source.lock,lambda:True,
                epoch_ms=b.host,monotonic=b.mono,historical=True)
            self.assertTrue(history.blocked);self.assertEqual('failed',history.state['pending']['status'])


if __name__=='__main__':unittest.main()
