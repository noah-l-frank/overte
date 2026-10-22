"""Durable original failed-source ownership for enclosing Emote cleanup.

No failure is a successful source sample. No evidence file is deleted here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from overte_phone_emote_originals import PhoneEmoteOriginals,BLOCK,MAX_FRAMES
from overte_phone_emote_sources import PhoneEmoteSources,source_name
from overte_phone_script_history import canonical,pack,unpack,same

VERSION=1


class FailureOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'source-failures'})


class PhoneEmoteFailures:
    def __init__(self,run):
        from overte_phone_emote_run import PhoneEmoteRun
        need(isinstance(run,PhoneEmoteRun));run.lock.assert_held();need(run.state is not None)
        self.run=run
        _ui,_service,binding,self.guard,_installed=run.adapter.normal_feature_runtime(run.selector,read_only=True)
        self.binding=deepcopy(context(binding));need(same(self.binding,run.state['binding']))
        self.store=PrivateFeatureState(run.store.path.with_name('phone-emote-failures.json'))
        self.previous=self.store.read();self.state=dict(count=0,manifests=[],pending=None)
        self.failed=False;self.started=self.clock=None
        self.originals=FailureOriginals(run.root,self.binding,run.run,'primary',self.bound,self.storage_intent,
            kind='source-failures',monotonic=run.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def bound(self):
        self.run.lock.assert_held()
        need(not self.failed and not self.run.failed and self.guard() is not False
            and same(self.store.read(),self.previous) and same(self.run.store.read(),self.run.previous)
            and same(self.binding,self.run.state['binding']))
        now=self.run.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<20));self.clock=now

    def decode(self,value):
        exact(value,{'emoteFailureOwnerVersion','runId','fixtureUrl','binding','artifactRoot','payload'})
        need(type(value['emoteFailureOwnerVersion']) is int and value['emoteFailureOwnerVersion']==VERSION
            and value['runId']==self.run.run and value['fixtureUrl']==self.run.fixture_url
            and same(value['binding'],self.binding) and value['artifactRoot']==str(self.run.root))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'count','manifests','pending'});need(integer(state['count'],0,MAX_FRAMES) and type(state['manifests']) is list
            and len(state['manifests'])<=MAX_FRAMES//BLOCK)
        count=0
        for index,reference in enumerate(state['manifests'],1):
            self.originals.manifest_reference(reference);need(reference['block']==index and (index==len(state['manifests']) or reference['count']==BLOCK))
            count+=len(self.originals.manifest(reference))
        need(count==state['count'])
        pending=state['pending']
        if pending is not None:
            exact(pending,{'role','segment','headerSha256','archive','original','manifest'})
            need(pending['role'] in ('primary','actor') and integer(pending['segment'],0,15) and count<MAX_FRAMES
                and type(pending['headerSha256']) is str and len(pending['headerSha256'])==64
                and all(c in '0123456789abcdef' for c in pending['headerSha256']))
            if pending['archive'] is not None:
                proof=pending['archive'];need(type(proof) is dict and type(proof.get('emoteSourceFailureArchiveVersion')) is int
                    and proof['emoteSourceFailureArchiveVersion']==1 and proof.get('segment')==pending['segment']
                    and type(proof.get('header')) is dict and proof['header'].get('role')==pending['role']
                    and hashlib.sha256(canonical(proof['header'])).hexdigest()==pending['headerSha256'])
            if pending['original'] is not None:
                self.originals.original(pending['original']);need(pending['original']['index']==count+1 and pending['archive'] is not None)
            if pending['manifest'] is not None:
                intent=pending['manifest'];exact(intent,{'emoteManifestVersion','reference','phase'})
                need(type(intent['emoteManifestVersion']) is int and intent['emoteManifestVersion']==1 and intent['phase'] in ('planned','saved')
                    and pending['original'] is not None and pending['original']['phase']=='saved')
                self.originals.manifest_reference(intent['reference'])
                need(intent['reference']['block']==count//BLOCK+1 and intent['reference']['count']==count%BLOCK+1)
        return deepcopy(state)

    def save(self):
        try:
            self.bound();value=dict(emoteFailureOwnerVersion=VERSION,runId=self.run.run,fixtureUrl=self.run.fixture_url,
                binding=self.binding,artifactRoot=str(self.run.root),payload=pack([self.state]))
            self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        pending=self.state['pending'];need(pending is not None and kind in ('original','manifest'))
        old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==self.state['count']+1)
            need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
                and (old['phase']=='planned' or same(value['file'],old['file'])))
        else:
            exact(value,{'emoteManifestVersion','reference','phase'});self.originals.manifest_reference(value['reference'])
            need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion']==1
                and value['reference']['block']==self.state['count']//BLOCK+1 and value['reference']['count']==self.state['count']%BLOCK+1
                and pending['original'] is not None and pending['original']['phase']=='saved')
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved' and same(value['reference'],old['reference']))
        pending[kind]=deepcopy(value);self.save()

    def record(self,value,index):
        exact(value,{'emoteFailureRecordVersion','index','kind','archive'})
        need(type(value['emoteFailureRecordVersion']) is int and value['emoteFailureRecordVersion']==1
            and type(value['index']) is int and value['index']==index and value['kind']=='source')
        proof=value['archive'];source=self.run.source(proof['header']['role'],segment=proof['segment'])
        source.failure_archive(proof);return value

    def collect(self,source):
        need(isinstance(source,PhoneEmoteSources) and source.lock.path==self.run.lock.path and same(source.binding,self.binding)
            and source.segment==self.run.state['segment'])
        need(self.started is None);self.started=self.run.monotonic()
        try:
            self.bound();need(self.run.state['phase']=='cleaning-inputs');self.run.active('cleanup')
            pending=self.state['pending']
            if pending is None:
                need(source.state['phase']=='reading' and self.state['count']<MAX_FRAMES)
                self.state['pending']=dict(role=source.role,segment=source.segment,
                    headerSha256=hashlib.sha256(canonical(source.previous)).hexdigest(),archive=None,original=None,manifest=None);self.save()
            else:need(pending['role']==source.role and pending['segment']==source.segment)
            retained=self.state['pending']['archive'];manifests=None
            def retain(proof):
                nonlocal manifests
                pending=self.state['pending']
                need(proof['header']['role']==pending['role'] and proof['segment']==pending['segment']
                    and hashlib.sha256(canonical(proof['header'])).hexdigest()==pending['headerSha256'])
                row=dict(emoteFailureRecordVersion=VERSION,index=self.state['count']+1,kind='source',archive=deepcopy(proof))
                self.record(row,row['index'])
                if pending['archive'] is None:pending['archive']=deepcopy(proof);self.save()
                else:need(same(pending['archive'],proof))
                if pending['original'] is None:ref=self.originals.write(row['index'],row)
                else:ref=self.originals.resume_write(row['index'],row,pending['original'])
                manifests=self.originals.resume_manifest(self.state['manifests'],ref,pending['manifest'])
            source.transfer_failed(retain,retained=retained)
            self.bound();need(manifests is not None and source.state['phase']=='ready');self.run.active('cleanup')
            self.state.update(count=self.state['count']+1,manifests=deepcopy(manifests),pending=None);self.save()
        finally:self.started=None

    def collect_sources(self):
        self.bound();need(self.run.state['phase']=='cleaning-inputs')
        if self.state['pending'] is not None:
            pending=self.state['pending'];self.collect(self.run.source(pending['role'],segment=pending['segment']))
        for role in ('primary','actor'):
            path=self.store.path.with_name(source_name(role,self.run.state['segment']))
            if PrivateFeatureState(path).read() is not None:
                source=self.run.source(role)
                if source.state['phase']=='reading':self.collect(source)
