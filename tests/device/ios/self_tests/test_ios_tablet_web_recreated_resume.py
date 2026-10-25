"""Actual host page recreation follows the unchanged native lifecycle branch.

IOSWebView.mm applicationStateChanged tears down then scheduleOpen()s the same
policy URL. This producer model does the actual host page destruction/reload;
native code and physical lifecycle execution remain unqualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from ios.self_tests import test_ios_tablet_web_page_flow as pages
from ios.self_tests.tablet_web_lifecycle_fixture import TabletLifecycleModel


class TabletRecreatedResumeTests(unittest.TestCase):
    def test_actual_new_host_document_and_physical_view_keep_original_sourceStamp_and_script_membership(self):
        fixture=pages.TabletPageFlowTests('test_actual_source_button_handler_fetches_server_page_and_independent_Source9_derives_it')
        fixture.setUp();self.addCleanup(fixture.doCleanups);b=fixture.opened();model=TabletLifecycleModel(b)
        before=b.runtime.validate_original(b.runtime.observe())['public']['state'];old=deepcopy(b.page_identity)
        source=deepcopy(b.template['sources']);manager=deepcopy(b.manager);view=b.wk_view;owner=deepcopy(b.template['state']['owners'][-1])
        original_host_document=b.host_app.call('page-read',requestId='ios-'+'f'*32,epoch=b.epoch())['dom']['document']
        model.execute('mobile: backgroundApp',dict(seconds=-1))
        self.assertFalse(b.template['state']['presentations']);self.assertEqual('web',b.ui.qt.page);self.assertFalse(model.foreground)
        self.assertTrue(all(not row['windowAttached'] for row in b.template['state']['targets'] if row['kind']=='wk'))
        model.execute('mobile: activateApp',dict(bundleId=b.target['appId']))
        after=b.runtime.validate_original(b.runtime.observe())['public']['state']
        self.assertEqual(before['documentLoads']+1,after['documentLoads']);self.assertTrue(after['open'])
        self.assertEqual(source,b.template['sources']);self.assertEqual(manager,b.manager)
        self.assertEqual(old['source'],b.page_identity['source']);self.assertEqual(old['sourceIdentity'],b.page_identity['sourceIdentity'])
        self.assertEqual(old['sourceUrl'],b.page_identity['sourceUrl']);self.assertGreater(b.page_identity['creation'],old['creation'])
        self.assertNotEqual(old['nonce'],b.page_identity['nonce']);self.assertNotEqual(view,b.wk_view)
        self.assertEqual(owner['id'],b.template['state']['owners'][-1]['id']);self.assertEqual(1,len(b.template['state']['owners']))
        current=b.host_app.call('page-read',requestId='ios-'+'e'*32,epoch=b.epoch())['dom']['document']
        self.assertNotEqual(original_host_document,current);self.assertEqual(2,len(b.browser.snapshot(b.source.run)['responses']))


if __name__=='__main__':unittest.main()
