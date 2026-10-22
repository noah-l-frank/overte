"""No-build source-branch regression, not execution of native Qt/WK code."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import re
import unittest

ROOT=Path(__file__).resolve().parents[4]


class BrowserTraceSourceTests(unittest.TestCase):
    def test_actual_world_branch_uses_independent_original_getter_after_schedule_close(self):
        source=(ROOT/'ios/web/IOSWebView.mm').read_text()
        body=source.split('QVariantMap IOSWebView::featureBrowserIdentity(bool historical) const {',1)[1].split('QVariantMap IOSWebView::featureWorldIdentity(',1)[0]
        match=re.search(r'if \((actual\.policy\.surface\(\)==web::Surface::WorldEntity && [^\n]+)\) \{\s*const auto identity=featureWorldIdentity\(historical\);',body)
        self.assertIsNotNone(match)
        # Evaluate only the two actual source branch atoms and boolean grammar.
        # The previous `&& actual.generation` condition fails the zero-grant
        # historical rows, exposing independent getter/cache divergence.
        branch=match[1]
        for surface,generation,historical in (('world',3,False),('world',0,True),('world',0,False),('tablet',0,True)):
            expression=branch.replace('actual.policy.surface()==web::Surface::WorldEntity',str(surface=='world')).replace('actual.generation',str(bool(generation))).replace('historical',str(historical)).replace('&&',' and ').replace('||',' or ')
            self.assertRegex(expression,r'\A[TrueFalsandor ()]+\Z')
            delegated=eval(expression,{'__builtins__':{}},{})
            original=dict(creation=4,page=9);generic_cache=dict(creation=4,page=7)
            chosen=original if delegated else generic_cache
            if surface=='world' and (generation or historical):self.assertEqual(original,chosen)
            else:self.assertFalse(delegated)
        # Recreation remains owned by the unchanged original historical guard.
        original=source.split('QVariantMap IOSWebView::featureWorldIdentity(bool historical) const {',1)[1].split('void IOSWebViewNative::featureResponse(',1)[0]
        self.assertIn('actual.featureWorldLastIdentity.value("creation").toULongLong()==actual.featureCreation',original)
        scheduled=source.split('void IOSWebView::scheduleOpen() {',1)[1].split('bool IOSWebView::active()',1)[0]
        self.assertIn('_private->policy.close(); _private->generation = 0;',scheduled)


if __name__=='__main__':unittest.main()
