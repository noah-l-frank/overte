"""Original screen owner over actual SDK/DOM/marker HTTP, host renderer only.

Prior file selection is an explicit setup boundary; ordinary selection and
loaded disposal are separate qualified cases. These PNGs model WDA, not UIKit
pixels, and cannot qualify native or device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator
from feature_journeys.evidence import image_observation,MarkerNotReady
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.adapters.tablet_web_samples import TabletWebSamples
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletLiveScreenTests(unittest.TestCase):
    def test_actual_marker_script_refresh_and_original_WDA_PNG_bracket_never_use_expected_pixels(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary
        fixture.primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0))
        ticket='b'*32;fixture.fixture.journal.activate(RUN,ticket,'open',{})
        with fixture.primary.parts() as runtime:
            owned=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/'component-prepared-files.json'),b.binding).reserve_app(RUN,b.source.fixture,ticket)
            runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
            b.load(b.directories[owned['runId']].as_uri()+'/script.js');b.ui.qt.opened=True
            runtime.remember_app(owned)
            ui=NativeUI(runtime.client,b.binding['sessionId'],lambda:runtime.process() is not None,monotonic=b.mono,sleep=b.sleep)
            row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.open')
            ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
            samples=TabletWebSamples(runtime,b.root,fixture.settings['imagePolicy']);first=samples.capture(ticket)
            before=samples.read(first);image_observation(before['raw'],RUN,ticket,fixture.settings['imagePolicy'])
            next_ticket='d'*32;fixture.fixture.journal.activate(RUN,next_ticket,'reload',{})
            second=samples.capture(next_ticket);after=samples.read(second)
            image_observation(after['raw'],RUN,next_ticket,fixture.settings['imagePolicy'])
            with self.assertRaises(MarkerNotReady):image_observation(before['raw'],RUN,next_ticket,fixture.settings['imagePolicy'])
            self.assertNotEqual(before['raw'],after['raw'])
            self.assertEqual(2,sum(path.endswith('/screenshot') for method,path in fixture.sdk.calls if method=='GET'))
            samples.cleanup_files();samples.files_absent()
            self.assertEqual(after['raw'],samples.read(second)['raw'])
            self.assertEqual([],fixture.sdk.errors)


if __name__=='__main__':unittest.main()
