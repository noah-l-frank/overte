"""Legacy entry-only originals remain readable but cannot qualify new input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import world_web_source as native
from ios.self_tests.world_web_source_fixture import OriginalSources


class WorldWebDeathVersionTests(unittest.TestCase):
    def test_source_two_preserves_actual_document_and_legacy_one_is_historical_only(self):
        legacy=OriginalSources(transcript_version=1);old=legacy.ledger();native.original(old)
        current=OriginalSources();new=current.ledger();native.original(new);self.assertEqual(2,new['iosWorldWebVersion'])
        next_original=deepcopy(old);next_original.update(iosWorldWebVersion=2,sequence=old['sequence']+1,commandId='ios-'+'e'*32)
        for clock in ('clockBefore','clockAfter'):
            next_original[clock]={key:value+2 for key,value in next_original[clock].items()}
        query=dict(schemaVersion=1,commandId=next_original['commandId'],action=native.ACTION,runId=old['runId'],fixtureUrl=old['fixtureUrl'])
        with self.assertRaises(NativeUIError):native.validate(next_original,query,42,previous=old)
    def test_native_source_hooks_actual_qobject_destroyed_signal_not_derived_destructor_entry(self):
        cpp=(Path(__file__).resolve().parents[4]/'ios/web/IOSWebView.mm').read_text();body=cpp.split('IOSWebView::~IOSWebView() {',1)[1].split('QString IOSWebView::url()',1)[0]
        self.assertIn('QObject::connect(this,&QObject::destroyed,[identity]',body)
        self.assertNotIn('event(featureWorldIdentity(true),"owner-destroyed")',body)
        # An actual host weak lifetime illustrates the counterexample to an
        # entry-only hook. No native Qt execution is claimed by this test.
        observed=[]
        class Owner:
            def __del__(self):observed.append(('entry',reference() is not None))
        value=Owner();reference=weakref.ref(value,lambda _dead:observed.append(('destroyed',reference() is None)))
        del value;self.assertEqual([('entry',True),('destroyed',True)],observed)


if __name__=='__main__':unittest.main()
