"""Actual next VM, inline source bytes and normal trusted inline Send.

Prior file selection is explicit setup. Actual generated JS, normal WDA
callbacks, files and independent native DTO readers execute on host models;
this cannot qualify native/device behavior or the complete paired journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator,NativeUIError
from ios.adapters.tablet_web_actions import ordinary_toolbar
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.adapters.tablet_web_inputs import TabletWebInputs
from ios.self_tests import test_ios_tablet_web_page_flow as page_tests


class TabletInlineFlowTests(unittest.TestCase):
    def test_actual_second_generation_inline_is_not_HTTP_and_original_reference_script_echoes(self):
        fixture=page_tests.TabletPageFlowTests('test_actual_source_button_handler_fetches_server_page_and_independent_Source9_derives_it')
        fixture.setUp();self.addCleanup(fixture.doCleanups);b=fixture.opened();runtime=b.runtime
        initial=runtime.validate_original(runtime.observe())['public']['state'];self.assertEqual('http',initial['documentKind'])
        before_http=len(b.browser.snapshot(b.source.run)['responses']);original_manager=b.manager['instance']
        ordinary_toolbar(runtime,'Close',lambda method,path,body,ownership:b.ui.call(method,'/session/'+b.binding['sessionId']+path,body))
        ui=NativeUI(b.ui,b.binding['sessionId'],lambda:True,monotonic=b.mono,sleep=b.sleep)
        for name in ('scripts.entry','scripts.stop.0','tablet.home'):
            row=next(item for item in b.ui.controls() if item['id']==name)
            ui.click_with_token(Locator('accessibility id','OverteNavigation.'+name),row['token'])
        files=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/'explicit-inline-files.json'),b.binding)
        owned=files.reserve_app(b.source.run,b.source.fixture,'c'*32)
        runtime.read_auxiliary('files',ownership=owned,operation='stage',files=originals(b.source.run,b.source.fixture,'c'*32,owned['nonce']))
        b.load(b.directories[owned['runId']].as_uri()+'/script.js');runtime.remember_app(owned)
        self.assertNotEqual(original_manager,b.manager['instance'])
        scripts=runtime.read_auxiliary('scripts');self.assertEqual(3,scripts['source']['membership']['revision'])
        row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.inline')
        ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.inline'),row['token'])
        value=runtime.validate_original(runtime.observe())['public']['state']
        self.assertEqual(('inline','inline',0,1,2),(value['page'],value['documentKind'],value['httpStatus'],value['inlineLeases'],value['documentLoads']))
        self.assertEqual(before_http,len(b.browser.snapshot(b.source.run)['responses']))
        navigation=b.template['sources']['navigations'][-1];self.assertTrue(navigation['sourceUrl'].startswith('data:text/html;charset=utf-8;base64,'))
        self.assertEqual(navigation['sourceUrl'],b.host_app.call('read')['navigations'][-1]['source'])
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],runtime.observer.readers['dom'],b.lock,runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        inputs.perform('c'*32,'actual-inline-send','tap','bridge')
        echoed=runtime.validate_original(runtime.observe())['public']['state']
        self.assertEqual((1,1,1),(echoed['attemptedMessages'],echoed['bridgeMessages'],echoed['bridgeEchoes']))
        arm=runtime.defer('arm');self.assertEqual('armed',arm['status'])
        inputs.perform('c'*32,'actual-held-inline-send','tap','bridge')
        held_value=runtime.validate_original(runtime.observe())['public']['state']
        self.assertEqual((2,1,1,1),(held_value['attemptedMessages'],held_value['bridgeMessages'],held_value['bridgeEchoes'],held_value['deferredMessages']))
        from ios.adapters import tablet_web_deferred as deferred
        captured=deepcopy(b.source.children['deferred'].history()[-1])
        held=deepcopy(deferred.held(captured));self.assertTrue(held['callbackAlive']);self.assertTrue(held['bufferPending'])
        old_source=b.template['sources']['carriers'][-1]['id']
        ordinary_toolbar(runtime,'Close',lambda method,path,body,ownership:b.ui.call(method,'/session/'+b.binding['sessionId']+path,body))
        row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.return')
        ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.return'),row['token'])
        returned=runtime.validate_original(runtime.observe())['public']['state']
        self.assertEqual(('http','primary',200,0,3),(returned['documentKind'],returned['origin'],returned['httpStatus'],returned['inlineLeases'],returned['documentLoads']))
        self.assertEqual(before_http+1,len(b.browser.snapshot(b.source.run)['responses']))
        carrier=next(row for row in b.template['sources']['carriers'] if row['id']==old_source)
        self.assertTrue(carrier['alive']);self.assertIn('retired',carrier);self.assertTrue(all(not row['current'] and 'revoked' in row for row in carrier['bindings']))
        self.assertEqual(['http','inline','http'],[row['kind'] for row in b.template['sources']['navigations']])
        retained=b.deferred_model.callback  # Actual extra reference, not an expected liveness flag.
        result=runtime.defer('deliver',held['id']);self.assertEqual('delivered',result['status'])
        runtime.observe();returned_capture=b.source.children['deferred'].history()[-1]
        self.assertIsNotNone(returned_capture['records'][-1]['returned']);self.assertTrue(returned_capture['records'][-1]['callbackAlive'])
        with self.assertRaises(NativeUIError):deferred.drained(captured,returned_capture)
        del retained
        final=runtime.validate_original(runtime.observe())['public']['state']
        self.assertEqual((2,1,1,0),(final['attemptedMessages'],final['bridgeMessages'],final['bridgeEchoes'],final['deferredMessages']))
        actual=b.template['deferred']['records'][-1]
        self.assertEqual(held['original'],actual['original']);self.assertFalse(actual['callbackAlive'])
        self.assertIsNotNone(actual['returned']);self.assertIsNotNone(actual['finally']);self.assertIsNotNone(actual['expired'])
        self.assertLess(actual['finally']['epochMs'],actual['expired']['epochMs'])
        deferred.drained(captured,b.source.children['deferred'].history()[-1])


if __name__=='__main__':unittest.main()
