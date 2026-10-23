"""Canonical public acquisition time stays separate from native originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack
from ios.adapters.navigation_restoration import NavigationRestoration
from ios.self_tests import test_ios_navigation_restoration as fixture


class NavigationRestorationClockTests(unittest.TestCase):
    setUp=fixture.NavigationRestorationTests.setUp
    acquire=fixture.NavigationRestorationTests.acquire
    action=fixture.NavigationRestorationTests.action
    ready=fixture.NavigationRestorationTests.ready
    restart_call=fixture.NavigationRestorationTests.restart_call
    install=fixture.NavigationRestorationTests.install
    inputs=fixture.NavigationRestorationTests.inputs
    configure=fixture.NavigationRestorationTests.configure

    def test_actual_original_host_window_qualifies_canonical_publication_without_retiming_native(self):
        owner=self.configure();public=owner.advance();h=self.h
        with h.flow.held():
            owner.load();reference=owner.reference();image=owner.image(reference['requestId'],historical=True)
            before=deepcopy(image.originals());commands=deepcopy(self.new.gpu.commands)
            def forbidden(*_args,**_kwargs):self.fail('Historical clock qualification attempted transport')
            with patch.object(h.flow.runtime,'_sources',side_effect=forbidden),patch.object(h.flow.client,'request',side_effect=forbidden):
                derived=owner.validate_original(reference)
                probe=object.__new__(PhaseWitnessPublisher)
                probe.run=h.run;probe.area='world-navigation';probe.validate_original=owner.validate_original
                actual,body=probe.original(reference)
            self.assertEqual(derived,actual);self.assertEqual(public,derived['public'])
            self.assertEqual(derived['acquisition']['hostBeforeEpochMs'],body['capturedEpochMs'])
            self.assertEqual(before,image.originals());self.assertEqual(commands,self.new.gpu.commands)
            for invalid in (derived['acquisition']['hostBeforeEpochMs']-1,derived['acquisition']['hostAfterEpochMs']+1):
                changed=deepcopy(derived);changed['public']['capturedEpochMs']=invalid
                probe.validate_original=lambda _reference:deepcopy(changed)
                with self.subTest(captured=invalid),self.assertRaises(NativeUIError):probe.original(reference)
            self.assertEqual(before,image.originals());self.assertEqual(commands,self.new.gpu.commands)


class NavigationRestorationClockFormatTests(unittest.TestCase):
    def test_literal_v1_envelope_keeps_its_version_and_new_envelopes_write_two(self):
        owner=object.__new__(NavigationRestoration)
        owner.flow=SimpleNamespace(run='owned-run',role='actor',root=Path('/owned'))
        owner.context={};state=dict(rows=[],pending=None)
        owner.version=1;legacy=owner.envelope(state)
        self.assertEqual(1,legacy['iosNavigationRestorationVersion']);self.assertEqual(state,owner.decode(legacy))
        original=deepcopy(legacy);owner.version=2;current=owner.envelope(state)
        self.assertEqual(2,current['iosNavigationRestorationVersion']);self.assertEqual(state,owner.decode(current))
        self.assertEqual(original,legacy)
        for invalid in (True,0,3):
            owner.version=invalid;value=dict(current,iosNavigationRestorationVersion=invalid,payload=pack([state]))
            with self.subTest(version=invalid),self.assertRaises(NativeUIError):owner.decode(value)


if __name__=='__main__':unittest.main()
