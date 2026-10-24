"""Real host cache/weak-holder model remains explicitly HELD before OS exit."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_held_resources import primary,public
from ios.adapters.world_web_identity import WorldWebLease
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebHeldResourcesTests(unittest.TestCase):
    def test_released_renderer_retains_actual_root_QSG_QImage_and_GPU_groups_with_stable_private_originals(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close)
        actions=whole.actions();actions.act(whole.sdk.activate('open',{}));call=actions.state['calls'][-1]
        lease=WorldWebLease(whole.scope,whole.source,call['before'],call['after'])
        with self.assertRaises(NativeUIError):primary(lease,call['after'])
        whole.sdk.activate('cleanup',{});whole.scope.cleanup();first=whole.source.capture('held-original')
        original=primary(lease,first);visible=public(original)
        self.assertTrue({'qt-root','qsg-root','qimage','native-holder'}<={row['kind'] for row in visible})
        self.assertEqual(2,sum(row['kind']=='qt-root' for row in visible));self.assertFalse(any(row['kind']=='wk-view' for row in visible))
        self.assertTrue(all(row['originalSha256'] and row['original']['owner'] for row in original))
        raw=whole.source.frame(first)['originals'];before=deepcopy(raw['closures']['contexts'])
        self.assertTrue(raw['surfaces']['source']['surfaces'][0]['cached']);self.assertTrue(raw['surfaces']['source']['surfaces'][0]['rootAlive'])
        self.assertTrue(any(row['resources']['native-bitmap']['pending'] for row in before))
        visible[0]['resource']='panel:forged';original[0]['original']['owner'].clear()
        self.assertEqual(before,whole.source.frame(first)['originals']['closures']['contexts'])
        whole.sdk.sleep(.1);second=whole.source.capture('still-held-original')
        self.assertEqual(public(primary(lease,first)),public(primary(lease,second)))
        self.assertNotIn('complete',primary(lease,second)[0]);self.assertNotIn('resources',raw['surfaces'])

    def test_untyped_aliases_cannot_be_submitted_as_native_private_originals(self):
        with self.assertRaises(NativeUIError):primary(object(),{'index':1,'sha256':'0'*64})
        with self.assertRaises(NativeUIError):public([dict(resource='panel:forged',kind='qimage',originalSha256='0'*64,original={'expected':True})])


if __name__=='__main__':unittest.main()
