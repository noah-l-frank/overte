"""Composed actual VM/DOM/Qt/GPU/file originals for whole Web retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import unittest
import uuid
from adapters.native_script_files import NativeScriptFiles
from feature_journeys.fixtures import context
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_retirement import WorldWebRetirement
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb
from ios.self_tests.world_web_gpu_fixture import sample


class Files:
    """Native file-reader model observes actual staged bytes/directory state."""
    def __init__(self,whole):self.whole=whole;self.last=None;self.sequence=0
    def send(self,query):
        sdk=self.whole.sdk;self.sequence+=1;before=sdk.tick();source=self.whole.domain.files.request(query['operation'],query['runId'],query['ownerToken'])
        self.last=dict(schemaVersion=1,requestId=query['commandId'],instance='b'*32,sequence=self.sequence,requestedEpochMs=before,capturedEpochMs=sdk.tick(),processId=sdk.pid,
            runId=sdk.run,operation=query['operation'],source=source)
    def read(self):return json.dumps(self.last)


class WorldWebRetirementTests(unittest.TestCase):
    def test_whole_original_native_files_keys_pointer_weak_and_fenced_pixels_then_repeated_quiet(self):
        whole=ComposedWorldWeb();self.addCleanup(whole.close);sdk,source,scope=whole.sdk,whole.source,whole.scope
        samples={}
        def image(request):
            if request not in samples:samples[request]=sample(whole,request)
            return samples[request]
        baseline=image('ios-'+uuid.uuid4().hex);baseline.capture(sdk.ticket)
        actions=whole.actions();call=sdk.activate('open',{});actions.act(call);entry=actions.state['calls'][-1]
        lease=WorldWebLease(scope,source,entry['before'],entry['after']);actions.inputs.entity=lease.packet()['returned']['returned']['entityId']
        actions.act(sdk.activate('focus-type',dict(text=context(sdk.run)['unicode'])))
        actions.act(sdk.activate('clear-text',{}))
        fixture=Files(whole);files=NativeScriptFiles(fixture.send,fixture.read,sdk.tick,lambda:True,sdk.pid,ios=True,monotonic=lambda:sdk.time,sleep=sdk.sleep)
        receipt=WorldWebFileReceipts(PrivateFeatureState(scope.root/'ios-world-web-primary-files.json'),scope.root,sdk.binding,sdk.run,'primary',scope.lock,lambda:True,
            native=source.native,files=files,epoch_ms=sdk.host_epoch,monotonic=lambda:sdk.time)
        owner=WorldWebRetirement(PrivateFeatureState(scope.root/'ios-world-web-primary-retirement.json'),lease,baseline,receipt,image,actions.inputs,sdk.origins,sleep=sdk.sleep)
        ticket=sdk.activate('cleanup',{})['ticket'];owner.cleanup(ticket);self.assertEqual('retired',owner.state['phase'])
        first=owner.qualification(owner.state);self.assertEqual([],first['public']['resources']);self.assertEqual(0,first['pixels']['changedPixels'])
        intentions=deepcopy(whole.domain.io.actions);owner.cleanup(ticket);self.assertEqual(intentions,whole.domain.io.actions)
        self.assertGreater(owner.qualification(owner.state)['public']['sequence'],first['public']['sequence'])
        rebuilt=WorldWebRetirement(owner.store,lease,baseline,receipt,image,actions.inputs,sdk.origins,sleep=sdk.sleep)
        self.assertEqual(owner.previous,rebuilt.previous)
        # Source originals are retained; manipulating an in-memory latest DTO
        # cannot substitute its native immutable source record.
        ref=source.state['records'][-1];raw=source.frame(ref);raw['originals']['keys']['source']['complete']=False
        self.assertTrue(source.frame(ref)['originals']['keys']['source']['complete'])


if __name__=='__main__':unittest.main()
