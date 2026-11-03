"""Opt-in next normal Assets Upload; native/server/GPU remain declared models.

The first-four test is a SOURCE DIAGNOSTIC, never a default green whole test.
Actual Prefix3 current budget/failure, immutable files and kernel worker exit
are retained regardless of whether the composed path can finish within bounds.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import cProfile
import pstats
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from copy import deepcopy

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
import test_normal_scripts as normal
from self_tests.pico_assets_upload_fixture import AssetsUploadModel
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals


class AssetsUploadPrefixTests(unittest.TestCase):
    def setUp(self):
        self.normal=normal.PicoNormalScriptsTests(methodName='runTest');self.normal.setUp()
        self.addCleanup(self.normal.doCleanups)
        self.normal.native.identity='123:314159'
        numeric=patch.object(self.normal.native,'require_process_identity',
            side_effect=lambda identity:self.assertEqual('123:314159',identity))
        numeric.start();self.addCleanup(numeric.stop)
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-upload-prefix-'));self.root.chmod(0o700)
        temporary=self.normal.fixture.fixture.fixture.temporary
        temporary._finalizer.detach();temporary.cleanup=lambda:None
        (self.root/'canonical-original-root.txt').write_text(temporary.name+'\n')
        self.model=AssetsUploadModel(self,self.root,self.normal,binary_transport=True,canonical_prefix=True);self.owner=self.model.owner
        print('Retained modeled normal upload originals:',self.owner.store.path,flush=True)

    def first_three(self,*,trace_cancel=False,profile_cancel=False):
        m,p=self.model,self.owner;m.activate('baseline');self.assertFalse(p.observe()['open'])
        self.assertTrue(p.act(m.activate('open'))['openDelivered'])
        self.assertTrue(p.act(m.activate('upload-picker-open',{'resource':'gltf-bundle/main.gltf'}))['pickerObserved'])
        fields=m.activate('upload-picker-cancel');previous_trace=sys.gettrace();exceptions=[]
        original_sample=p.child.sample;sample_times=[];sample_calls=0;profile=cProfile.Profile()
        def measured_sample():
            nonlocal sample_calls
            sample_calls+=1;started=time.monotonic()
            try:return profile.runcall(original_sample) if sample_calls==2 else original_sample()
            finally:sample_times.append(dict(sample=sample_calls,seconds=time.monotonic()-started,profiled=sample_calls==2))
        if profile_cancel:p.child.sample=measured_sample
        def traced(frame,event,arg):
            if event=='exception' and issubclass(arg[0],(NativeUIError,ValueError,AssertionError)) and '/overte-pico-consolidated-' in frame.f_code.co_filename:
                exceptions.append(dict(file=frame.f_code.co_filename,line=frame.f_lineno,
                    function=frame.f_code.co_name,error=arg[0].__name__,message=str(arg[1])))
            return traced
        try:
            if trace_cancel:sys.settrace(traced)
            self.assertTrue(p.act(fields)['filesRetired'])
        finally:
            sys.settrace(previous_trace)
            if profile_cancel:
                p.child.sample=original_sample
                profile.dump_stats(str(self.root/'cancel-second-sample.pstats'))
                with (self.root/'cancel-second-sample.txt').open('w') as output:
                    pstats.Stats(profile,stream=output).sort_stats('cumulative').print_stats(45)
                (self.root/'cancel-sample-times.json').write_text(json.dumps(dict(sourceDiagnosticOnly=True,
                    originalQuietGapLimitMs=500,originalSourceSeconds=1.5,samples=sample_times),indent=2)+'\n')
            if trace_cancel or profile_cancel:
                (self.root/'cancel-source-exceptions.json').write_text(json.dumps(exceptions,indent=2)+'\n')
                (self.root/'cancel-source-terminal.json').write_text(json.dumps(dict(
                    sourceDiagnosticOnly=True,nativeQualified=False,completeCommonObservation=False,
                    nativeQueries=len(m.calls),normalInputs=len(m.inputs),sdkCalls=len(m.sdk_calls),
                    responsibility=p.responsibility()),indent=2)+'\n')
        with p.lock.held():bill=p.bill()
        (self.root/'before-upload-bill.json').write_text(json.dumps(dict(bill=bill,queryCount=len(m.calls),inputCount=len(m.inputs)),indent=2)+'\n')

    def test_three_step_cancel_source_component_diagnostic(self):
        # This explicit diagnostic does not qualify uninstrumented timing or
        # the fourth upload, whole29, device/Native/Actor/bake/render success.
        self.first_three(profile_cancel=True)

    def test_first_four_normal_originals_under_same_parent_global_caps(self):
        started=time.monotonic();self.first_three();fields=self.model.activate('upload',{'resource':'gltf-bundle/main.gltf'})
        try:
            result=self.owner.act(fields)
        except BaseException as error:
            with self.owner.lock.held():bill=self.owner.bill()
            (self.root/'unresolved-upload-result.json').write_text(json.dumps(dict(
                nativeQualified=False,completeCommonObservation=False,errorType=type(error).__name__,
                elapsed=time.monotonic()-started,bill=bill,responsibility=self.owner.responsibility(),
                nativeQueries=len(self.model.calls),normalInputs=len(self.model.inputs),sdkCalls=len(self.model.sdk_calls)),indent=2)+'\n')
            raise
        self.assertTrue(result['normalUploadObserved'] and result['exactDownloadedBytes'] and result['stagedFilesRetired'])
        self.assertFalse(result['completeCommonObservation'])
        self.assertEqual(4,len(self.owner.state['steps']));self.assertTrue(all(row['status']=='returned' for row in self.owner.state['steps']))
        with self.owner.lock.held():bill=self.owner.bill()
        self.assertLessEqual(bill['frames'],512);self.assertLessEqual(bill['decodedBytes'],16*1024*1024)
        self.assertLess(time.monotonic()-started,120)
        (self.root/'completed-upload-component.json').write_text(json.dumps(dict(result=result,bill=bill,elapsed=time.monotonic()-started,
            nativeQualified=False,wholeCommonQualified=False),indent=2)+'\n')


if __name__=='__main__':unittest.main()
