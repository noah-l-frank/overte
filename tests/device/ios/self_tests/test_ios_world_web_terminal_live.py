"""Actual staged JS/files/PNG originals; native/GPU/cache are explicit models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from adapters.native_script_files import NativeScriptFiles
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.adapters.world_web_terminal_live import WorldWebTerminalLive
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.world_web_gpu_fixture import sample
from ios.self_tests.test_ios_world_web_retirement import Files


class WorldWebTerminalLiveTests(unittest.TestCase):
    def test_original_restored_pixels_and_held_groups_survive_repeated_cleanup_journal_reconstruction_and_alias_attacks(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close)
        sdk,source,scope=whole.sdk,whole.source,whole.scope;samples={}
        def image(request):
            if request not in samples:samples[request]=sample(whole,request)
            return samples[request]
        baseline=image('ios-'+uuid.uuid4().hex);baseline.capture(sdk.ticket)
        actions=whole.actions();actions.act(sdk.activate('open',{}));entry=actions.state['calls'][-1]
        lease=WorldWebLease(scope,source,entry['before'],entry['after']);actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
        native=Files(whole);files=NativeScriptFiles(native.send,native.read,sdk.tick,lambda:True,sdk.pid,ios=True,monotonic=lambda:sdk.time,sleep=sdk.sleep)
        receipts=WorldWebFileReceipts(PrivateFeatureState(scope.root/'ios-world-web-primary-files.json'),scope.root,sdk.binding,sdk.run,'primary',scope.lock,lambda:True,
            native=source.native,files=files,epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
        owner=WorldWebRetirement(PrivateFeatureState(scope.root/'ios-world-web-primary-retirement.json'),lease,baseline,receipts,image,actions.inputs,sdk.origins,sleep=sdk.sleep)
        ticket=sdk.activate('cleanup',{})['ticket'];first_original=owner.cleanup(ticket);journal=WorldWebTerminalLive(owner)
        first=journal.append(first_original);self.assertTrue(first['resources']);self.assertTrue(all(name.startswith('panel:world-web-') for name in first['resources']))
        before=deepcopy(whole.domain.io.actions);original=owner.cleanup(ticket);second=journal.append(original)
        self.assertEqual(before,whole.domain.io.actions);self.assertGreater(second['sequence'],first['sequence']);self.assertEqual(first['resources'],second['resources'])
        rebuilt=WorldWebTerminalLive(owner);queries=deepcopy(sdk.counts)
        self.assertEqual(first,rebuilt.selected(first)['public']);self.assertEqual(second,rebuilt.selected(second)['public'])
        self.assertEqual(queries,sdk.counts);self.assertEqual(0,owner.qualification(owner.state)['pixels']['changedPixels'])
        forged=deepcopy(first);forged['resources']=[]
        with self.assertRaises(NativeUIError):rebuilt.selected(forged)
        returned=rebuilt.selected(first);returned['held'].clear();returned['public']['resources'].clear()
        self.assertEqual(first,rebuilt.selected(first)['public']);self.assertEqual(queries,sdk.counts)


if __name__=='__main__':unittest.main()
