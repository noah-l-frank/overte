"""No-build exact current registry/weak-target selection and callsite checks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]


class TabletWebStateNativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'ios/web/IOSWebView.mm').read_text()
        cls.body=cls.source.split('QVariantMap IOSWebView::featureTabletWebStateObservation(',1)[1].split('QVariantMap IOSWebView::featureTabletWebDOMObservation(',1)[0]

    def test_actual_registry_and_private_current_flags_are_read_without_product_mutation(self):
        for original in ('featureRegistry.values()','owner->featureBrowserIdentity(true)','auto& data=*owner->_private',
                'data.generation','data.view!=nil','data.presentation.isViewLoaded','!data.image.isNull()',
                'data.openTimer.isActive()','data.deadline.isActive()','data.resumeOnForeground'):
            self.assertIn(original,self.body)
        for mutation in ('tearDown(', 'stopLoading]', 'removeFromSuperview]', 'dismissViewController', 'setVisible(', 'reset(', 'clear()', 'new IOSWebView'):
            self.assertNotIn(mutation,self.body)
        self.assertIn('featureEnabled() || !NSThread.isMainThread',self.body)

    def test_genuine_weak_UIKit_targets_and_descendants_are_inspected_after_private_clear(self):
        for actual in ('for (const auto& target:inputs.targets)','UIView* view=qt?(UIView*)target.button:(UIView*)target.view',
                'view.window!=nil','view.superview!=nil','item.isFirstResponder','item.subviews','visited>=2048 || depth>=64',
                'uikit_input::targetOriginal(target)','@autoreleasepool'):
            self.assertIn(actual,self.body)
        self.assertNotIn('uikit_input::birth(',self.body);self.assertNotIn('uikit_input::install(',self.body)
        self.assertNotIn('Object alive means retired',self.body)

    def test_teardown_entry_is_not_terminal_and_unknown_hook_or_cleanup_failure_stays_incomplete(self):
        teardown=self.source.split('void IOSWebView::tearDown()',1)[1].split('void IOSWebView::stop()',1)[0]
        self.assertLess(teardown.index('"view-teardown"'),teardown.index('[_private->view removeFromSuperview]'))
        self.assertIn('if (data.cleanupFailed) {actual.complete=false;}',self.body)
        self.assertIn('!inputs.complete || !inputs.installed || !uikit_input::methodUnchanged()',self.body)
        self.assertIn('++otherLiveTablets',self.body);self.assertIn('data.policy.surface()==web::Surface::Tablet',self.body)
        self.assertNotIn('actual.complete=true',self.body)

    def test_first_observed_source_is_never_retimed_or_reassigned_on_same_QObject(self):
        header=(ROOT/'ios/web/IOSTabletWebState.h').read_text()
        self.assertIn('QPointer<QObject> object',header)
        observed=header.split('inline void observed(',1)[1]
        self.assertLess(observed.index('row->object==object && row->fixture==fixture'),observed.index('row->source=source'))
        self.assertIn('if (!owner->object && owner->expired.isEmpty())',self.body)
        self.assertIn('current.isEmpty()?QVariant():QVariant(current)',self.body)
        self.assertIn('"source",owner->source',self.body)


if __name__=='__main__':unittest.main()
