"""Actual app-button WDA callback precedes independent original page facts.

The preceding file-load authority is explicit test setup; the complete normal
file picker is qualified separately. Native producers/clocks are host models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import unittest
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,Locator
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles,originals
from ios.self_tests.tablet_web_page_fixture import TabletPageBoundary


class TabletPageFlowTests(unittest.TestCase):
    def observed(self,b):
        try:return b.runtime.observe()
        except Exception as error:
            blocked=[name for name,child in b.source.children.items() if child.state.get('pending') is not None]
            if blocked:raise AssertionError('Actual pending Source9 component: '+','.join(blocked)) from error
            raise
    def native_codecs(self,b):
        from ios.adapters.tablet_web_history import TYPED
        for name,module in TYPED.items():
            packet=json.loads(b.raw[module.ACTION+'.json'])
            try:module.original(packet)
            except Exception as error:raise AssertionError('Explicit native model codec: '+name) from error
    def opened(self):
        b=TabletPageBoundary(self);files=OwnedTabletWebAppFiles(None,PrivateFeatureState(b.root/'prepared-files.json'),b.binding)
        owned=files.reserve_app(b.source.run,b.source.fixture,'b'*32)
        b.produce(dict(schemaVersion=1,action='feature-script-files',commandId='ios-'+'e'*32,operation='stage',runId=owned['runId'],ownerToken=owned['ownerToken'],
            files={name:base64.b64encode(raw).decode() for name,raw in originals(owned['featureRun'],owned['fixtureUrl'],owned['ticket'],owned['nonce']).items()}))
        b.load(b.directories[owned['runId']].as_uri()+'/script.js');b.ui.qt.opened=True
        admission=b.runtime.remember_app(owned);self.assertEqual(admission,b.source.state['apps'][-1])
        ui=NativeUI(b.ui,b.binding['sessionId'],lambda:True,monotonic=b.mono,sleep=b.sleep)
        row=next(item for item in b.ui.controls() if item['id']=='tablet-web-app.open')
        ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.open'),row['token'])
        return b

    def test_actual_source_button_handler_fetches_server_page_and_independent_Source9_derives_it(self):
        b=self.opened()
        self.assertEqual(1,len(b.host_app.call('read')['navigations']));self.assertEqual(1,len(b.browser.snapshot(b.source.run)['responses']))
        original=self.observed(b);self.native_codecs(b);measured=b.runtime.validate_original(original)
        self.assertTrue(measured['public']['state']['open']);self.assertEqual('reference',measured['public']['state']['page'])
        self.assertEqual(1,measured['public']['state']['documentLoads']);self.assertEqual(0,measured['public']['state']['bridgeEchoes'])
        self.assertNotEqual(b.template['state']['presentations'][0]['target'],b.template['document']['source']['presentationAfter']['view'])
        self.assertFalse(any(row['alive'] for row in b.button_source.snapshot()['controls']))
    def test_actual_W3C_touch_and_native_active_field_unicode_are_observed_independently(self):
        b=self.opened()
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,
            monotonic=b.mono,epoch_ms=b.host)
        from feature_journeys.fixtures import context
        message=context(b.source.run)['unicode']
        touch=inputs.perform('b'*32,'focus-text','tap','text')
        text=inputs.perform('b'*32,'replace-text','replace','text',text=message)
        self.assertNotEqual(touch,text)
        original=self.observed(b);self.native_codecs(b);value=b.runtime.validate_original(original)['public']['state']
        self.assertEqual(message,value['text']);self.assertTrue(value['focused']);self.assertEqual(0,value['bridgeEchoes'])
        self.assertEqual(2,len(inputs.state['records']));self.assertIsNone(inputs.state['pending'])
    def test_actual_normal_W3C_Send_derives_native_VM_call_stack_and_DOM_echo_without_ACK_facts(self):
        b=self.opened()
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        inputs.perform('b'*32,'send-message','tap','bridge')
        original=self.observed(b);self.native_codecs(b);value=b.runtime.validate_original(original)['public']['state']
        self.assertEqual((1,1,1),tuple(value[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        calls=[row for row in b.template['emitter']['calls'] if row['caller']['manager']['instance']==b.manager['instance']]
        self.assertEqual(1,len(calls));self.assertEqual(2,len([row for row in b.template['emitter']['sinks'] if row['call']==calls[0]['id']]))
        self.assertEqual(3,len(calls[0]['caller']['emitStack']['frames']))
    def test_ordinary_native_Close_returns_real_Home_and_retains_old_WK_weak_lifetime(self):
        b=self.opened();before=self.observed(b);self.assertTrue(b.runtime.validate_original(before)['public']['state']['open'])
        from ios.adapters.tablet_web_actions import ordinary_toolbar
        sent=[]
        def normal_send(method,path,body,ownership):
            sent.append((method,path,ownership));return b.ui.call(method,'/session/'+b.binding['sessionId']+path,body)
        ordinary_toolbar(b.runtime,'Close',normal_send)
        actual=b.runtime.validate_original(b.runtime.observe())['public']
        self.assertFalse(actual['state']['open']);self.assertEqual(1,actual['state']['documentLoads']);self.assertEqual(1,len(sent))
        self.assertTrue(b.ui.qt.opened);self.assertEqual('home',b.ui.qt.page)
        self.assertTrue(all(row['alive'] and not row['windowAttached'] for row in b.template['state']['targets'] if row['kind']=='wk'))
        self.assertTrue(actual['resources']);self.assertEqual(3,len(b.controls))
    def test_acknowledged_but_ignored_WDA_Send_has_no_native_or_DOM_effect(self):
        b=self.opened();b.ignore_wda=True
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        reference=inputs.perform('b'*32,'ignored-send','tap','bridge');inputs.decode();self.assertEqual('returned',inputs.records[-1]['phase'])
        value=b.runtime.validate_original(self.observed(b))['public']['state']
        self.assertEqual((0,0,0),tuple(value[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        self.assertEqual([],b.host_app.call('read')['emissions']);self.assertEqual(reference,inputs.state['records'][-1])
    def test_lost_WDA_return_keeps_failed_input_no_replay_and_observes_actual_independent_echo(self):
        b=self.opened();b.lose_wda_return=True
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        def owner():return TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        inputs=owner()
        with self.assertRaises(NativeUIError):inputs.perform('b'*32,'uncertain-send','tap','bridge')
        before=len(b.host_app.call('read')['emissions']);self.assertEqual(1,before)
        rebuilt=owner();self.assertTrue(rebuilt.blocked);self.assertEqual('failed',rebuilt.records[-1]['phase'])
        with self.assertRaises(NativeUIError):rebuilt.perform('b'*32,'uncertain-send','tap','bridge')
        self.assertEqual(before,len(b.host_app.call('read')['emissions']))
        value=b.runtime.validate_original(self.observed(b))['public']['state']
        self.assertEqual((1,1,1),tuple(value[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        self.assertEqual('failed',owner().records[-1]['phase'])

    def test_normal_anchor_back_reload_preserve_actual_native_prefix_and_new_document_originals(self):
        from copy import deepcopy
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        b=self.opened();self.observed(b)
        call=b.ui.call;errors=[]
        def actual_input(*args,**kwargs):
            try:return call(*args,**kwargs)
            except Exception as error:errors.append(error);raise
        b.ui.call=actual_input
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        initial=deepcopy(b.template['ledger']['events']);original_target=deepcopy(b.template['touches']['targets'])
        for ordinal,(control,page) in enumerate((('same-origin','B'),('back','reference'),('reload','reference')),2):
            try:inputs.perform('b'*32,'normal-'+control,'tap',control)
            except Exception:
                if errors:raise AssertionError('Actual ordinary boundary: '+str(errors[-1])) from errors[-1]
                raise
            actual=b.runtime.validate_original(self.observed(b))['public']['state'];self.native_codecs(b)
            self.assertEqual(page,actual['page']);self.assertEqual(ordinal,actual['documentLoads'])
            self.assertEqual(initial,b.template['ledger']['events'][:len(initial)])
            self.assertEqual(original_target,b.template['touches']['targets'][:len(original_target)])
            self.assertEqual(1,len(b.template['sources']['navigations']))
        self.assertEqual(['navigate','back','reload'],[row['kind'] for row in b.host_app.call('read')['pageRequests']])
        self.assertEqual(4,len(b.browser.snapshot(b.source.run)['responses']))

    def test_actual_404_document_then_fixture_restore_and_normal_reload_have_distinct_original_receipts(self):
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        b=self.opened();self.observed(b)
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        inputs.perform('b'*32,'ordinary-recovery-link','tap','recovery')
        failed=b.runtime.validate_original(self.observed(b))['public']['state']
        self.assertEqual(('recovery',404,2),(failed['page'],failed['httpStatus'],failed['documentLoads']))
        actual_404=b.browser.snapshot(b.source.run)['responses'][-1]
        b.browser.control(b.source.run,dict(operation='restore-resource'))
        # Restoring the fixture does not change the already loaded document.
        self.assertEqual(404,b.runtime.validate_original(self.observed(b))['public']['state']['httpStatus'])
        inputs.perform('b'*32,'ordinary-recovery-reload','tap','reload')
        recovered=b.runtime.validate_original(self.observed(b))['public']['state']
        self.assertEqual(('recovery',200,3),(recovered['page'],recovered['httpStatus'],recovered['documentLoads']))
        actual_200=b.browser.snapshot(b.source.run)['responses'][-1]
        self.assertNotEqual(actual_404['responseId'],actual_200['responseId'])
        self.assertEqual(actual_404,b.browser.snapshot(b.source.run)['responses'][-2])

    def test_actual_foreign_URL_editor_navigation_and_Send_leave_attempt_without_VM_delivery_or_echo(self):
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        from urllib.parse import urlsplit,urlunsplit
        b=self.opened();self.observed(b)
        inputs=TabletWebInputs(b.ui,b.source.children['dom'],b.runtime.observer.readers['dom'],b.lock,b.runtime.native_clock,monotonic=b.mono,epoch_ms=b.host)
        own=urlsplit(b.page_identity['url']);foreign=urlsplit(b.runtime.observer.origins['foreign'])
        address=urlunsplit((foreign.scheme,foreign.netloc,own.path,'',''))
        inputs.perform('b'*32,'focus-foreign','tap','foreign');inputs.perform('b'*32,'type-foreign','replace','foreign',text=address)
        inputs.perform('b'*32,'ordinary-foreign-navigate','tap','navigate')
        current=b.runtime.validate_original(self.observed(b))['public']['state']
        self.assertEqual(('foreign','foreign',200,2),(current['page'],current['origin'],current['httpStatus'],current['documentLoads']))
        inputs.perform('b'*32,'ordinary-foreign-send','tap','bridge')
        actual=b.runtime.validate_original(self.observed(b))['public']['state'];self.native_codecs(b)
        self.assertEqual((1,0,0),tuple(actual[key] for key in ('attemptedMessages','bridgeMessages','bridgeEchoes')))
        self.assertEqual([],b.host_app.call('read')['emissions'])
        self.assertEqual(['native-envelope','native-envelope-return'],[row['kind'] for row in b.host_app.call('read')['pageEvents']])

    def test_normal_Script_Stop_executes_actual_Ending_and_real_host_VM_exit_before_terminal_model(self):
        from adapters.native_script_terminal import terminal
        from ios.adapters.tablet_web_actions import ordinary_toolbar
        b=self.opened();before=b.runtime.read_auxiliary('terminal')
        ordinary_toolbar(b.runtime,'Close',lambda method,path,body,ownership:b.ui.call(method,'/session/'+b.binding['sessionId']+path,body))
        ui=NativeUI(b.ui,b.binding['sessionId'],lambda:True,monotonic=b.mono,sleep=b.sleep)
        for name in ('scripts.entry','scripts.stop.0'):
            row=next(item for item in b.ui.controls() if item['id']==name)
            ui.click_with_token(Locator('accessibility id','OverteNavigation.'+name),row['token'])
        after=b.runtime.read_auxiliary('terminal');scripts=b.runtime.read_auxiliary('scripts')
        rows=terminal(after,b.manager,b.code,after_sequence=before['source']['eventSequence'],after_epoch=before['capturedEpochMs'])
        self.assertEqual(['thread-bound','shutdown-drained','thread-finished'],[row['kind'] for row in rows])
        self.assertTrue(b.ending_original['stopped']);self.assertEqual(0,b.ending_original['connections'])
        self.assertIsNotNone(b.host_app.process.poll());self.assertEqual([],scripts['source']['engines'])
        self.assertEqual([],scripts['source']['membership']['managers']);self.assertEqual(1,b.ui.qt.inputs.count('scripts.stop.0'))
        self.assertTrue(all(row['removed'] is not None for row in b.button_source.snapshot()['buttons']))


if __name__=='__main__':unittest.main()
