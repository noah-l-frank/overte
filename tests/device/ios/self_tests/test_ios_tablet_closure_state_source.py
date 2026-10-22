"""No-build provenance checks of actual neutral native source routing.

These inspect C++/Objective-C++ source; they do not execute native lifetimes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[4]


class TabletClosureStateSourceTests(unittest.TestCase):
    def test_every_neutral_lease_image_failure_and_native_bag_uses_original_context_state(self):
        header=(ROOT/'ios/web/IOSWebClosureTrace.h').read_text();native=(ROOT/'ios/web/IOSWebView.mm').read_text()
        self.assertIn('State* source { nullptr };',header)
        self.assertIn('return context && context->source ? *context->source : state();',header)
        body=header.split('class Lease final {',1)[1].split('inline QVariantMap observe(',1)[0]
        self.assertEqual(2,body.count('auto& data = contextState(_context);'))
        self.assertNotIn('auto& data = state();',body)
        self.assertIn('const auto id = contextState(context).instance',body)
        self.assertIn('}, [context] { auto& data = contextState(context);',body)
        object_=native.split('void nativeObject(void* object,',1)[1].split('namespace overte::ios',1)[0]
        self.assertIn('contextState(context).instance + ":" + QString::number(context->id)',object_)
        self.assertNotIn('auto& data = state();',object_)
        # Equal numeric IDs in independent actual sources cannot alias a bag.
        bag={'original-http:1:8':'http lease','original-tablet:1:8':'tablet lease'}
        self.assertEqual(2,len(bag))

    def test_default_http_factory_and_serializer_keep_old_grammar_and_filter(self):
        header=(ROOT/'ios/web/IOSWebClosureTrace.h').read_text()
        factory=header.split('inline ContextPointer context(',1)[1].split('class Lease final {',1)[0]
        self.assertIn('auto& data = state();',factory);self.assertIn('Context { found->second }',factory)
        self.assertNotIn('tablet',factory.split('QVariantMap descriptor',1)[1])
        observer=header.split('inline QVariantMap observe(',1)[1]
        self.assertIn('{"iosWebClosureVersion", 5}',observer);self.assertIn('value("sourceUrl").toString().startsWith(prefix)',observer)
        self.assertNotIn('iosTabletWebClosuresVersion',observer)
        own=(ROOT/'ios/web/IOSTabletWebClosures.h').read_text()
        self.assertIn('{"iosTabletWebClosuresVersion",1}',own);self.assertIn('new feature_closures::State',own)
        self.assertIn('feature_closures::Context{found->second,&data}',own)
        self.assertNotIn('{"iosWebClosureVersion",',own)


if __name__=='__main__':unittest.main()
