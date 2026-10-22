"""No-build inspection of actual held-buffer/capture ownership source."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]


class TabletDeferredNativeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.source=(ROOT/'ios/web/IOSTabletWebDeferred.h').read_text()

    def test_timeout_never_drops_or_replays_an_actual_held_callback(self):
        sweep=self.source.split('inline void sweep()',1)[1].split('inline bool parityEnvelope(',1)[0]
        self.assertIn('>=30000',sweep);self.assertIn('fail("hold-deadline-exceeded")',sweep)
        self.assertNotIn('callback={}',sweep);self.assertNotIn('callback()',sweep);self.assertNotIn('std::move',sweep)
        intercept=self.source.split('inline bool intercept(',1)[1].split('inline QVariantMap observe(',1)[0]
        self.assertLess(intercept.index('>=30000'),intercept.index('row->callback='))
        self.assertIn('row->callback=[original=std::move(original),lifetime,lease] { original(); };return true;',intercept)

    def test_native_nonce_claim_precedes_mutation_and_repeating_never_executes_again(self):
        command=self.source.split('inline QVariantMap command(',1)[1].split('inline bool intercept(',1)[0]
        self.assertLess(command.index('actual.commands.emplace'),command.index('operation=="arm"'))
        self.assertLess(command.index('return found->second.second'),command.index('original();returned=true'))
        self.assertIn('old.value("issued")',self.source);self.assertIn('old.value("sequence")',self.source)
        self.assertIn('if (!actual.complete || occupied()',command)
        self.assertIn('row->id!=input.value("recordId").toString()',command)
        self.assertEqual(1,command.count('original();returned=true'))

    def test_real_body_return_and_actual_weak_capture_death_remain_distinct(self):
        self.assertIn('std::weak_ptr<void> lifetime',self.source)
        self.assertIn('row->lifetime.expired() && row->expired.isEmpty()',self.source)
        self.assertIn('row->returned=clock();',self.source);self.assertIn('row->unwound=clock();',self.source)
        self.assertIn('{"bufferPending",static_cast<bool>(row->callback)}',self.source)
        self.assertIn('{"callbackAlive",!row->lifetime.expired()}',self.source)
        self.assertIn('feature_closures::retain(originalContext,feature_closures::Kind::JavaScript)',self.source)
        self.assertNotIn('std::shared_ptr<WKWebView',self.source)

    def test_hold_matches_only_actual_controlled_parity_and_unchanged_source_arguments(self):
        self.assertIn('bytes.size()>4096',self.source)
        self.assertIn('QSet<QString>{"contract","action","sequence"}',self.source)
        self.assertIn('row->identity!=actualIdentity',self.source)
        self.assertIn('actualGeneration!=actualIdentity.value("grant").toULongLong()',self.source)
        self.assertIn('actualIdentity.value("nonce")!=nonce',self.source)
        self.assertIn('actualIdentity.value("url")!=frame.toString(QUrl::FullyEncoded)',self.source)
        self.assertIn('source.value("carrier").isNull() || source.value("binding").isNull()',self.source)
        self.assertNotIn('emitScriptEvent(',self.source)


if __name__=='__main__':unittest.main()
