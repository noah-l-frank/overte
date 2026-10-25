"""A current original page frame can be the actual screenshot's left fence.

Real local SDK/HTTP/PNG/JS/original files execute. Prior file selection and
native presentation/clock producers are explicit models, not device evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.adapters.tablet_web_samples import TabletWebSamples
from ios.self_tests.tablet_web_paired_fixture import PairedTabletFixture
from ios.self_tests.test_ios_tablet_web_sources import RUN


class TabletImageBeforeTests(unittest.TestCase):
    def test_exact_current_original_saves_one_query_but_old_foreign_unjoined_and_aged_frames_never_GET(self):
        fixture=PairedTabletFixture(self);b=fixture.boundary;primary=fixture.primary
        primary.observe(dict(contractVersion=16,runId=RUN,afterSequence=0));ticket='b'*32
        fixture.fixture.journal.activate(RUN,ticket,'open',{})
        with primary.parts() as runtime:
            files=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/'explicit-screen-setup.json'),b.binding)
            owned=files.reserve_app(RUN,b.source.fixture,ticket)
            runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(RUN,owned['fixtureUrl'],ticket,owned['nonce']))
            b.load(b.directories[owned['runId']].as_uri()+'/script.js');b.ui.qt.opened=True;runtime.remember_app(owned)
            ui=NativeUI(runtime.client,b.binding['sessionId'],lambda:runtime.process() is not None,monotonic=b.mono,sleep=b.sleep)
            row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.open')
            ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
            source=runtime.observer.source;samples=TabletWebSamples(runtime,b.root,fixture.settings['imagePolicy'])
            first=runtime.tail_source();current=runtime.tail_source()
            def no_GET(original):
                before=sum(method=='GET' and path.endswith('/screenshot') for method,path in fixture.sdk.calls)
                with self.assertRaises(NativeUIError):samples.capture(ticket,before=original)
                self.assertEqual(before,sum(method=='GET' and path.endswith('/screenshot') for method,path in fixture.sdk.calls))
                self.assertIsNone(samples.state['pending']);self.assertIsNone(samples.state['original'])
            no_GET(first)
            foreign=deepcopy(current);foreign['observation']['binding']['processIdentity']='43';no_GET(foreign)
            child=source.children['trace'];child.capture(runtime.observer.readers['trace']);no_GET(current)
            current=runtime.tail_source();b.sleep(1.5);no_GET(current)
            current=runtime.tail_source();count=len(source.state['records']);reference=samples.capture(ticket,before=current)
            self.assertEqual(count+1,len(source.state['records']))
            actual=samples.read(reference);self.assertEqual(current,actual['row']['before'])
            self.assertEqual(source.state['records'][-1],actual['row']['after']['observation']['reference'])
            self.assertEqual(1,sum(method=='GET' and path.endswith('/screenshot') for method,path in fixture.sdk.calls))
            self.assertEqual([],fixture.sdk.errors)


if __name__=='__main__':unittest.main()
