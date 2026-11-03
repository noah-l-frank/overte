"""Real forward-clock original Node marker work acquisition, native model.

The two nested time fields alias one new actual start/completion. No retained
DTO or clock is rewritten. The original strict reader/validator remains intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib,json,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from adapters.native_script_work import NativeScriptWork,validate
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_marker_files import originals
from ios.self_tests import emote_marker_domain_fixture as marker
from ios.self_tests.avatar_installed_native_channels import RealtimeProducerClock


class ForwardClockDomain(marker.RunningDomain):
    @property
    def time(self):return self.clock[0]
    @time.setter
    def time(self,value):self.clock[0]=value
    def epoch(self):
        # A declared real acquisition cost makes millisecond boundaries
        # deterministic; returned values still come from the original real
        # forward-running producer clock, with no expected/stored timestamp.
        time.sleep(.003)
        return super().epoch()


class AvatarMarkerWorkAcquisitionTests(unittest.TestCase):
    def test_actual_forward_clock_node_work_joins_one_start_and_completion_then_original_reader_advances(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);root.chmod(0o700);(root/'script-bundle').mkdir(mode=0o700)
        run='1'*32;ticket='2'*32
        files=originals(run,'https://controlled.invalid/feature-fixture/v1/runs/'+run+'/',ticket,'3'*32)
        for name in ('script-bundle/main.js','script-bundle/companion.js'):
            path=root/name;path.write_bytes(files[name]);path.chmod(0o600)
        domain=object.__new__(ForwardClockDomain);domain.clock=RealtimeProducerClock()
        domain.files=SimpleNamespace(root=root);domain.marker_program=None;domain.sequences=dict(work=0)
        domain.scope=SimpleNamespace(work=SimpleNamespace(last=None));domain.start()
        self.assertEqual(1,len(domain.vm['added']));self.assertEqual([domain.marker['id']],domain.vm['deleted'])
        emitted=[];current=[]
        def send(query):
            # Ordinary original transport nonce assignment, BEFORE emission.
            # Inner/outer timestamps are never touched by this adapter seam.
            value=domain.work(query['managerInstance'],0)
            value['requestId']=query['commandId'];value['source']['work']['requestId']=query['commandId']
            raw=json.dumps(value,sort_keys=True,separators=(',',':'));emitted.append(raw);current[:]=[raw]
            path=root/('original-new-work-'+str(len(emitted))+'.json');path.write_text(raw);path.chmod(0o600)
        reader=NativeScriptWork(send,lambda:current[0],domain.epoch,lambda:True,31,ios=True,
            monotonic=time.monotonic,sleep=time.sleep)
        first=reader.read(domain.worker['instance']);original=emitted[0]
        for value in (first,):
            self.assertEqual(value['requestedEpochMs'],value['source']['work']['requestedEpochMs'])
            self.assertEqual(value['capturedEpochMs'],value['source']['work']['capturedEpochMs'])
            self.assertGreater(value['capturedEpochMs'],value['requestedEpochMs'])
        second=reader.read(domain.worker['instance'],first['sequence'])
        self.assertEqual(2,len(emitted));self.assertGreater(second['sequence'],first['sequence'])
        self.assertGreaterEqual(second['requestedEpochMs'],first['capturedEpochMs'])
        self.assertEqual(second['requestedEpochMs'],second['source']['work']['requestedEpochMs'])
        self.assertEqual(second['capturedEpochMs'],second['source']['work']['capturedEpochMs'])
        self.assertEqual(original,emitted[0]);self.assertEqual(original,(root/'original-new-work-1.json').read_text())
        # Independent strict validator still refuses a genuinely inconsistent
        # nested start. Preserve the exact unmodified original separately.
        foreign=deepcopy(second);foreign['source']['work']['requestedEpochMs']+=1
        request=dict(schemaVersion=1,action='feature-script-work-observe',commandId=foreign['requestId'],managerInstance=domain.worker['instance'])
        with self.assertRaises(NativeUIError):validate(foreign,request,31,second['capturedEpochMs'],previous=first)
        evidence=dict(originalFirstSha256=hashlib.sha256(original.encode()).hexdigest(),originalSecondSha256=hashlib.sha256(emitted[1].encode()).hexdigest(),
            firstStart=first['requestedEpochMs'],firstCompletion=first['capturedEpochMs'],secondStart=second['requestedEpochMs'],secondCompletion=second['capturedEpochMs'],
            exactOriginalClockAlias=True,oldOriginalUnchanged=True,inconsistentNestedStartRefused=True,nativeQualified=False,wholeQualified=False)
        path=root/'actual-work-acquisition-evidence.json';path.write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n');path.chmod(0o600)


if __name__=='__main__':unittest.main()
