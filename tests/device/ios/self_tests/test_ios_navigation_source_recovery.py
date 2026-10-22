"""Interrupted original sources, real private PNGs and modeled SDK ports."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import unittest

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import unpack
from ios.self_tests import test_ios_navigation_observation_owner as fixture


class NavigationSourceRecoveryTests(unittest.TestCase):
    setUp=fixture.NavigationObservationOwnerTests.setUp
    child=fixture.NavigationObservationOwnerTests.child
    index=fixture.NavigationObservationOwnerTests.index
    activate=fixture.NavigationObservationOwnerTests.activate
    owner=fixture.NavigationObservationOwnerTests.owner
    take=fixture.NavigationObservationOwnerTests.take

    @contextmanager
    def held(self):
        error=None
        with self.lock.held():
            try:yield
            except BaseException as caught:error=caught
        if error is not None:raise error

    def failed(self,*,previous=None):
        self.ui.fail=True;owner=self.owner(previous=previous)
        with self.assertRaises(OSError):self.take(owner)
        self.ui.fail=False;return owner

    def test_explicit_abandonment_preserves_all_originals_and_new_read_has_distinct_identity(self):
        with self.held():
            first=self.failed();old=deepcopy(first.state);commands=deepcopy(self.gpu.commands);reads=self.ui.reads
            recovered=self.owner(first.request);self.assertIsNone(recovered.abandon_sources())
            self.assertEqual(old,recovered.state|dict(phase=old['phase']))
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            self.assertIsNone(recovered.archive());self.assertEqual('failed',recovered.state['phase'])
            second=self.owner(previous=recovered);result=self.take(second)
            self.assertEqual('A',result['state']['location']);self.assertNotEqual(first.request,second.request)
            self.assertEqual(2,self.gpu.frames);self.assertGreater(second.state['originals']['model']['sequence'],old['originals']['model']['sequence'])
            self.assertEqual(recovered.store.read(),first.envelope(recovered.state))

    def test_abandoned_originals_reconstruct_without_live_sdk_and_changed_png_still_fails(self):
        with self.held():
            first=self.failed();first.abandon_sources();self.sdk.okay=False
            commands=deepcopy(self.gpu.commands);reads=self.ui.reads
            historical=self.owner(first.request,historical=True);self.assertIsNone(historical.archive())
            self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)
            child=historical.images.frozen_child(historical.state['imageRow'],unpack(historical.state['imageArchive']['payload'])[0])
            path=self.root/child.state['frameOwner']['name'];path.write_bytes(path.read_bytes()+b'changed')
            with self.assertRaises(NativeUIError):historical.archive()

    def test_new_reader_cannot_reset_any_actually_accepted_partial_source(self):
        with self.held():
            first=self.failed();first.abandon_sources()
            self.model_source.sequence=0;self.sources['model']=self.model_source.reader()
            second=self.owner(previous=first)
            with self.assertRaises(NativeUIError):self.take(second)
            self.assertEqual('reading',second.state['phase']);self.assertEqual(2,self.gpu.frames)
            with self.assertRaises(NativeUIError):second.abandon_sources()

    def test_missing_channel_in_partial_owner_cannot_hide_earlier_complete_channel_floor(self):
        with self.held():
            first=self.owner();self.take(first)
            second=self.failed(previous=first);second.abandon_sources()
            self.assertNotIn('ui',second.state['originals']);self.ui.sequence=0
            third=self.owner(previous=second)
            with self.assertRaises(NativeUIError):self.take(third)
            with self.assertRaises(NativeUIError):third.abandon_sources()
            self.assertEqual(3,self.gpu.frames)

    def test_actual_phase_crossing_can_be_retained_but_never_published_as_old_success(self):
        with self.held():
            original=self.ui.capture
            def crossing():
                value=original();self.client.activate('c'*32,'open',{});return value
            self.ui.capture=crossing;first=self.owner()
            with self.assertRaises(NativeUIError):self.take(first)
            sources=deepcopy(first.state['originals']);first.abandon_sources()
            self.assertIsNone(first.archive());self.assertEqual(sources,first.state['originals'])
            self.ui.capture=original;self.activate('d'*32)
            second=self.owner(previous=first);self.assertEqual('A',self.take(second)['state']['location'])

    def test_overlong_window_stays_original_and_only_a_distinct_read_can_be_fresh(self):
        with self.held():
            original=self.ui.capture
            def delayed():
                value=original();self.sdk.gpu.sleep(2.);return value
            self.ui.capture=delayed;first=self.owner()
            with self.assertRaises(NativeUIError):self.take(first)
            window=deepcopy(first.state['clockJoin']);first.abandon_sources()
            self.assertIsNone(first.archive());self.assertEqual(window,first.state['clockJoin'])
            self.ui.capture=original;second=self.owner(previous=first)
            self.assertEqual('A',self.take(second)['state']['location'])
            self.assertGreaterEqual(second.state['clockJoin']['hostBeforeEpochMs'],window['hostAfterEpochMs'])
            self.assertGreater(second.state['nativeStart']['nativeBefore']['sequence'],window['nativeAfter']['sequence'])

    def test_lost_abandonment_return_never_resends_a_source_or_image(self):
        with self.held():
            first=self.failed();write=first.store.write
            def lost(value,previous):
                if unpack(value['payload'])[0]['phase']=='failed':raise OSError('Synthetic lost metadata return')
                write(value,previous)
            first.store.write=lost
            with self.assertRaises(OSError):first.abandon_sources()
            commands=deepcopy(self.gpu.commands);reads=self.ui.reads;first.store.write=write
            recovered=self.owner(first.request);recovered.abandon_sources()
            self.assertIsNone(recovered.archive());self.assertEqual(commands,self.gpu.commands);self.assertEqual(reads,self.ui.reads)

    def test_unresolved_image_cannot_be_abandoned_as_a_source_only_attempt(self):
        with self.held():
            images=self.index(factory=lambda _request:(_ for _ in ()).throw(OSError('Synthetic factory failure')))
            first=self.owner(images=images)
            with self.assertRaises(OSError):self.take(first)
            original=deepcopy(first.store.read())
            with self.assertRaises(NativeUIError):first.abandon_sources()
            self.assertEqual(original,first.store.read());self.assertEqual([],self.gpu.commands)


if __name__=='__main__':unittest.main()
