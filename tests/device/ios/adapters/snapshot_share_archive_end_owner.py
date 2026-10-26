"""Archive-only first-PID Stop, original OS quiet and SDK404/CAS retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.appium_adapter import WebDriverRequestError
from ios.adapters.installed_code import source as process_source
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.snapshot_capture_clock import operation
from ios.adapters.snapshot_photos_context import PhotosClientContext
from ios.adapters.snapshot_share_owner import IOSSnapshotShareOwner
from ios.adapters.snapshot_share_source_retirement_owner import SnapshotShareSourceRetirementOwner
from ios.adapters.snapshot_share_archive_end_context import SnapshotShareArchiveEndContext
from ios.adapters.snapshot_share_query_owner import host_clock
from ios.adapters.tablet_web_admission import installed_forward


class SnapshotShareArchiveEndOwner:
    def __init__(self,share,primary,archive,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep,historical=False):
        need(isinstance(share,IOSSnapshotShareOwner) and share.historical and type(historical) is bool)
        exact(archive,{'client','sessionStore','target','binding','artifactPath','admissionStore'})
        need(same(archive['binding'],share.archive_binding) and (historical or isinstance(primary,PhotosClientContext) and same(primary.binding,share.binding)))
        self.share,self.primary,self.archive,self.historical=share,primary,archive,historical
        self.binding,self.run,self.fixture_url,self.lock=deepcopy(share.archive_binding),share.run,share.fixture_url,share.archive_lock
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep;self.root=share.archive_root
        self.files=SnapshotShareSourceRetirementOwner.history(PrivateFeatureState(self.root/'share-source-retirement-owner.json'),share,archive['artifactPath'],archive['admissionStore'])
        self.files.proof();self.files_hash=digest(self.files.previous)
        self.store=PrivateFeatureState(self.root/'share-archive-end-owner.json');self.previous=self.store.read()
        self.state=dict(snapshot=None,before=None,stopIssued=False,processReady=False,processSha256=None,primaryBefore=None,primaryIssued=False,primaryAfter=None,
            sdkIssued=False,sdkChecks=[],sdkAbsent=False,localDiscarded=False,result=None)
        saved=None if self.previous is None else unpack(self.previous['payload'])[0]['snapshot']
        self.ctx=SnapshotShareArchiveEndContext(archive['client'],archive['sessionStore'],archive['target'],self.binding,archive['artifactPath'],archive['admissionStore'],
            self.lock,self.run,self.fixture_url,epoch_ms=epoch_ms,monotonic=monotonic,snapshot=saved,historical=historical)
        self.state['snapshot']=deepcopy(self.ctx.snapshot)
        if self.previous is not None:self.state=self.load(self.previous)
        else:need(not historical);self.inventory_paths()
    @classmethod
    def history(cls,share,archive):return cls(share,None,dict(archive,client=None),historical=True)
    def stamp(self):return host_clock(dict(epochMs=self.epoch_ms(),monotonicMs=self.monotonic()*1000))
    def bound(self):
        self.lock.assert_held();self.files.guard();self.ctx.local(allow_absent=self.state['sdkAbsent'])
        need(same(self.store.read(),self.previous) and digest(self.files.previous)==self.files_hash);return True
    def envelope(self):return dict(snapshotShareArchiveEndOwnerVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,
        sourceFilesOwnerSha256=self.files_hash,source=self.ctx.source,bundleId=self.ctx.target['appId'],payload=pack([self.state]))
    def save(self):
        need(not self.historical);self.bound();value=self.envelope();self.store.write(value,self.previous);need(same(value,self.store.read()));self.previous=deepcopy(value)
    def process_path(self):return self.root/filename('snapshotsharearchive','primary',0)
    def process(self):return IOSProcessRetirement(PrivateFeatureState(self.process_path()),self.ctx.process_reader(),self.binding,self.run,'primary',0,self.lock,profile='snapshotsharearchive')
    def process_history(self):
        value=PrivateFeatureState(self.process_path()).read();need(value is not None)
        state=IOSProcessRetirement.archive(value,path=self.process_path(),binding=self.binding,source=self.ctx.source,bundle=self.ctx.target['appId'],
            run=self.run,role='primary',stage=0,profile='snapshotsharearchive')
        allowed={self.process_path()}|{self.process_path().with_name(self.process_path().stem+'-'+str(row['ordinal'])+'.json') for row in state['records']}
        if state['pending'] is not None:allowed.add(self.process_path().with_name(self.process_path().stem+'-'+str(state['pending']['ordinal'])+'.json'))
        for path in self.root.iterdir():
            if path.name.startswith('ios-snapshot-share-archive-'):need(path in allowed)
        return value,state
    def inventory_paths(self):
        for path in self.root.iterdir():
            if path.name.startswith('share-archive-end-'):need(path==self.store.path)
    def primary_packet(self,value):
        fields={'binding','process','source'}|({'installed'} if 'installed' in value else set());exact(value,fields)
        need(same(value['binding'],self.share.binding));process=value['process'];exact(process,{'bundleId','pid','foreground'})
        need(type(process['pid']) is int and process['pid']==int(self.share.binding['processIdentity']) and type(process['foreground']) is bool
            and process['bundleId']==self.share.primary.target['appId']);process_source(value['source'])
        need(self.share.state['handoffs'] and same(value['source'],self.share.state['handoffs'][0]['before']['primary']['source']));return value
    def load(self,value):
        exact(value,{'snapshotShareArchiveEndOwnerVersion','binding','runId','fixtureUrl','sourceFilesOwnerSha256','source','bundleId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['snapshotShareArchiveEndOwnerVersion']) is int and value['snapshotShareArchiveEndOwnerVersion']==1)
        state=rows[0];exact(state,set(self.state));prior=self.state;self.state=state
        try:
            need(same(value,self.envelope()) and same(state['snapshot'],self.ctx.snapshot) and all(type(state[key]) is bool for key in
                ('stopIssued','processReady','primaryIssued','sdkIssued','sdkAbsent','localDiscarded')) and type(state['sdkChecks']) is list and len(state['sdkChecks'])<=128)
            if state['before'] is not None:
                exact(state['before'],{'process','source','hostBefore','hostAfter'});process=state['before']['process'];exact(process,{'bundleId','pid','foreground'})
                need(type(process['pid']) is int and process['pid']==int(self.binding['processIdentity']) and process['bundleId']==self.ctx.target['appId']
                    and type(process['foreground']) is bool and same(state['before']['source'],self.ctx.source))
                host_clock(state['before']['hostBefore']);host_clock(state['before']['hostAfter'],state['before']['hostBefore'])
            if state['stopIssued']:need(state['before'] is not None)
            if state['processReady']:
                need(state['stopIssued']);process,state_process=self.process_history();need(any(window['complete'] for window in state_process['windows']))
                if state['processSha256'] is not None:need(digest(process)==state['processSha256'] and state_process['windows'][-1]['complete'])
            else:need(state['processSha256'] is None)
            if state['primaryBefore'] is not None:self.primary_packet(state['primaryBefore']);need(state['processReady'])
            if state['primaryIssued']:need(state['primaryBefore'] is not None and state['primaryBefore']['process']['foreground'] is False)
            if state['primaryAfter'] is not None:
                before=self.primary_packet(state['primaryBefore']);after=self.primary_packet(state['primaryAfter'])
                need(after['process']['foreground'] is True and (before['process']['foreground'] or state['primaryIssued']) and same(before['source'],after['source']))
                if 'installed' in before:need('installed' in after);installed_forward(before['installed'],after['installed'])
            previous=None
            for index,row in enumerate(state['sdkChecks'],1):
                exact(row,{'index','status','sessionId','targetFingerprint','sdkStateSha256','hostBefore','hostAfter'})
                need(type(row['index']) is int and row['index']==index and type(row['status']) is int and row['status'] in (200,404)
                    and row['sessionId']==self.binding['sessionId'] and row['targetFingerprint']==self.binding['targetFingerprint'] and row['sdkStateSha256']==digest(self.ctx.snapshot['sdkState']))
                host_clock(row['hostBefore'],previous);host_clock(row['hostAfter'],row['hostBefore']);previous=row['hostAfter']
            if state['sdkIssued']:need(state['primaryAfter'] is not None and state['processSha256'] is not None)
            if state['sdkAbsent']:need(state['primaryAfter'] is not None and state['processSha256'] is not None and state['sdkChecks'] and state['sdkChecks'][-1]['status']==404)
            if state['localDiscarded']:need(state['sdkAbsent'] and self.ctx.session_store.read() is None)
            if state['result'] is not None:need(same(state['result'],self.proof()))
            self.inventory_paths()
        finally:self.state=prior
        return deepcopy(state)
    def sdk_probe(self):
        self.bound();before=self.stamp();status=200
        try:
            value=self.ctx.client.call('GET','/session/'+self.ctx.session)
            need(type(value) is dict and type(value.get('capabilities')) is dict and value['capabilities'].get('appium:bundleId')==self.ctx.target['appId'])
        except WebDriverRequestError as error:need(error.status==404);status=404
        after=self.stamp();need(len(self.state['sdkChecks'])<128)
        self.state['sdkChecks'].append(dict(index=len(self.state['sdkChecks'])+1,status=status,sessionId=self.ctx.session,targetFingerprint=self.binding['targetFingerprint'],
            sdkStateSha256=digest(self.ctx.snapshot['sdkState']),hostBefore=before,hostAfter=after));self.save();return status
    def proof(self):
        state=self.state;need(state['stopIssued'] and state['processReady'] and state['processSha256'] is not None and state['primaryAfter'] is not None
            and state['sdkAbsent'] and state['localDiscarded'] and self.ctx.session_store.read() is None)
        process,history=self.process_history();need(digest(process)==state['processSha256'] and history['windows'][-1]['complete']
            and state['sdkChecks'][-1]['status']==404)
        return dict(snapshotShareArchiveEndedVersion=1,runId=self.run,binding=self.binding,sourceFilesOwnerSha256=self.files_hash,processOwnerSha256=state['processSha256'],
            originalPID=int(self.binding['processIdentity']),archiveProcessRetired=True,archiveSDKAbsent=True,localSDKPointerRetired=True,primaryProcessStillOwned=True,
            primaryOSForeground=True,primaryPageRestorationRequired=True,primarySDKRetirementRequired=True,wholeFeatureRequired=True)
    @operation
    def finalize(self):
        need(not self.historical);self.bound()
        if self.state['result'] is not None:need(self.sdk_probe()==404);return self.proof()
        if not self.state['stopIssued']:
            before=self.stamp();actual=self.ctx.live();after=self.stamp();self.state['before']=dict(process=actual,source=deepcopy(self.ctx.source),hostBefore=before,hostAfter=after)
            self.state['stopIssued']=True;self.save();self.ctx.terminate()
        if not self.state['processReady']:
            process=self.process()
            while not process.advance():self.sleep(1.6)
            self.state['processReady']=True;self.save()
        if self.state['primaryAfter'] is None:
            if self.state['primaryBefore'] is None:self.state['primaryBefore']=self.primary.probe();self.primary_packet(self.state['primaryBefore']);self.save()
            if not self.state['primaryBefore']['process']['foreground'] and not self.state['primaryIssued']:
                self.state['primaryIssued']=True;self.save();self.primary.activate()
            self.state['primaryAfter']=self.primary.probe(True);self.primary_packet(self.state['primaryAfter']);self.save()
        if not self.state['sdkAbsent']:
            status=self.sdk_probe()
            if status==200:
                need(not self.state['sdkIssued']);process=self.process()
                while not process.advance():self.sleep(1.6)
                process.current();self.state['processSha256']=digest(process.previous);self.state['sdkIssued']=True;self.save()
                try:self.ctx.client.call('DELETE','/session/'+self.ctx.session)
                except WebDriverRequestError as error:
                    if error.status!=404:raise
                status=self.sdk_probe()
            else:
                process,state=self.process_history();need(state['windows'][-1]['complete']);self.state['processSha256']=digest(process)
            need(status==404);self.state['sdkAbsent']=True;self.save()
        current=self.ctx.session_store.read()
        if current is not None:self.ctx.local();self.ctx.session_store.discard(self.ctx.snapshot['sdkState'])
        need(self.ctx.session_store.read() is None);self.state['localDiscarded']=True;self.save()
        result=self.proof();self.state['result']=deepcopy(result);self.save();return result
