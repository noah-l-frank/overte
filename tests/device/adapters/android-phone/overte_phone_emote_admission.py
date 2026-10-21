"""Own original baseline world/Script/passive-cache admission observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.emote_admission import executable,world,policy as admission_policy
from adapters.emote_animation_readiness import ready as animation_ready
from adapters.emote_rig_measurements import asset_urls
from adapters.native_animation_inventory import NativeAnimationInventory,validate as inventory_packet
from adapters.native_animation_source import controlled_model
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_roots import NativeScriptRoots,validate as roots_packet
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_effects import PhoneEmoteEffects
from overte_phone_emote_originals import PhoneEmoteOriginals
from overte_phone_script_history import pack,unpack,same,canonical

VERSION=1
LIMIT=32


class AdmissionOriginals(PhoneEmoteOriginals):
    KINDS=frozenset({'admission'})


class PhoneEmoteAdmission:
    def __init__(self,source,policy):
        need(isinstance(source,PhoneEmoteSources) and source.historical is False and source.segment==0)
        source.lock.assert_held();self.source=source;self.policy=admission_policy(policy)
        self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-admission.json'))
        self.previous=self.store.read();self.state=dict(phase='ready',records=[],pending=None,window=None)
        self.started=self.clock=None;self.failed=False
        self.originals=AdmissionOriginals(source.artifact_root,source.binding,source.run,source.role,self.bound,
            self.storage_intent,kind='admission',monotonic=source.monotonic)
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def bound(self):
        source=self.source;source.lock.assert_held()
        need(not self.failed and source.guard() is not False and same(self.store.read(),self.previous)
            and same(source.store.read(),source.previous))
        now=source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<5));self.clock=now

    def frame(self,reference):return PhoneEmoteEffects.stored(self.source,reference)

    def baseline(self,value,ticket=None):
        phase_packet(value,run=self.source.run,area='emotes',request=value['requestId'],epoch=value['capturedEpochMs'])
        need(value['active'] and len(value['activations'])==1)
        row=value['activations'][0];need(row['stimulus']==dict(verb='baseline',inputs={}) and (ticket is None or row['ticket']==ticket))
        return row['ticket']

    def measure(self,row,previous=None):
        exact(row,{'source','inventory','rootsAfter','probe','phaseAfter','epochMs','hostEpochMs','monotonicMs'})
        need(integer(row['epochMs'],1) and number(row['hostEpochMs'],1,1e15) and number(row['monotonicMs'],0,1e15))
        source=self.source;frame=self.frame(row['source']);ticket=self.baseline(frame['phaseBefore']);self.baseline(frame['phaseAfter'],ticket)
        roots=row['rootsAfter'];roots_packet(roots,dict(schemaVersion=1,commandId=roots['commandId'],action='feature-script-roots-observe'),
            source.pid,row['epochMs'],previous=frame['group']['rootsAfter'])
        inventory=row['inventory'];inventory_packet(inventory,dict(schemaVersion=1,commandId=inventory['commandId'],action='feature-animation-inventory-observe'),
            source.pid,row['epochMs'],previous=previous['inventory'] if previous else None)
        need(frame['group']['rootsAfter']['capturedEpochMs']<=inventory['requestedEpochMs']<=inventory['capturedEpochMs']<=roots['requestedEpochMs']
            and inventory['instance']==frame['group']['rootsBefore']['instance'])
        group=dict(rootsBefore=frame['group']['rootsBefore'],script=frame['group']['script'],inventory=inventory,rootsAfter=roots)
        selected,probe_engine,_originals=executable(group,pid=source.pid,epoch=row['epochMs'],probe_url=self.policy['probeUrl'])
        top=max(item['compiledEpochMs'] for item in probe_engine['compiled']['compilations'] if item['resourceName']==self.policy['probeUrl']
            and item['sha256']==probe_engine['code']['sha256'])
        observed=world(row['probe'],self.policy,epoch=row['epochMs'],after_epoch=top)
        phase_packet(row['phaseAfter'],run=source.run,area='emotes',request=row['phaseAfter']['requestId'],epoch=row['hostEpochMs'],previous=frame['phaseAfter'])
        self.baseline(row['phaseAfter'],ticket)
        # Missing/loading actual cache entries are the only cache warmup case.
        # Duplicates, failures or wrong consumed bytes remain permanent errors.
        warm=False
        for url,name in asset_urls(selected).items():
            matches=[item for item in inventory['source']['resources'] if item['urlSha256']==hashlib.sha256(url.encode()).hexdigest()]
            need(len(matches)<=1)
            if not matches:warm=True;continue
            item=matches[0];need(not item['failed'])
            if not item['loaded'] or item['model'] is None:warm=True
            else:controlled_model(item['model'],name,url,inventory['capturedEpochMs'])
        if not warm:animation_ready(group,pid=source.pid,epoch=row['epochMs'])
        if previous is not None:
            old=previous['probe'];need(row['source']['revision']>previous['source']['revision'] and row['epochMs']>=previous['epochMs']
                and row['hostEpochMs']>=previous['hostEpochMs'] and row['monotonicMs']>=previous['monotonicMs']
                and observed['sampleSequence']>=old['sampleSequence'] and observed['sampleEpochMs']>=old['sampleEpochMs'])
            if observed['sampleSequence']==old['sampleSequence']:need(same(row['probe'],old))
        eligible=(not warm and observed['sampleEpochMs']>=frame['group']['rootsBefore']['requestedEpochMs'])
        return dict(cacheReady=not warm,eligible=eligible,probe=observed)

    def records(self,state):return [self.originals.read(self.originals.expand(ref)) for ref in state['records']]

    def window(self,records):
        indices=[];prior=None
        for index,row in enumerate(records):
            measured=self.measure(row,prior);prior=row
            if not measured['cacheReady']:indices=[];continue
            if indices and measured['probe']['scene']['entityCount']!=records[indices[-1]-1]['probe']['scene']['entityCount']:indices=[]
            if not measured['eligible']:continue
            if indices and measured['probe']['sampleSequence']==records[indices[-1]-1]['probe']['sampleSequence']:continue
            indices.append(index+1);indices=indices[-3:]
        return dict(records=indices) if len(indices)==3 else None

    def decode(self,value):
        source=self.source
        exact(value,{'emoteAdmissionVersion','runId','fixtureUrl','role','binding','artifactRoot','policy','payload'})
        need(type(value['emoteAdmissionVersion']) is int and value['emoteAdmissionVersion']==VERSION
            and value['runId']==source.run and value['fixtureUrl']==source.phase.fixture_url and value['role']==source.role
            and same(value['binding'],source.binding) and value['artifactRoot']==str(source.artifact_root) and same(value['policy'],self.policy))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'phase','records','pending','window'})
        need(state['phase'] in ('ready','reading','admitted') and type(state['records']) is list and len(state['records'])<=LIMIT)
        for index,ref in enumerate(state['records'],1):self.originals.expand(ref);need(ref['index']==index)
        records=self.records(state);window=self.window(records)
        if state['phase']=='reading':
            exact(state['pending'],{'index','original'});need(state['pending']['index']==len(records)+1 and len(records)<LIMIT)
            if state['pending']['original'] is not None:
                self.originals.original(state['pending']['original']);need(state['pending']['original']['index']==len(records)+1)
            need(state['window'] is None)
        else:need(state['pending'] is None and same(window,state['window']) and (window is not None)==(state['phase']=='admitted'))
        reader=NativeAnimationInventory(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),source.pid)
        self.restore_inventory(reader,records)
        return deepcopy(state)

    @staticmethod
    def restore_inventory(reader,records):
        for row in records:
            packet=row['inventory']
            if reader.last is None:reader.restore(packet)
            else:
                inventory_packet(packet,dict(schemaVersion=1,commandId=packet['commandId'],action='feature-animation-inventory-observe'),
                    reader.pid,packet['capturedEpochMs'],previous=reader.last)
                reader.models,reader.urls=reader.accept(packet);reader.last=deepcopy(packet)

    def save(self):
        try:
            self.bound();source=self.source
            value=dict(emoteAdmissionVersion=VERSION,runId=source.run,fixtureUrl=source.phase.fixture_url,role=source.role,
                binding=deepcopy(source.binding),artifactRoot=str(source.artifact_root),policy=deepcopy(self.policy),payload=pack([self.state]))
            self.decode(value);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        need(kind=='original' and self.state['phase']=='reading');pending=self.state['pending'];old=pending['original']
        self.originals.original(value);need(value['index']==pending['index'])
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[key],old[key]) for key in value if key not in ('phase','file'))
            and (old['phase']=='planned' or same(old['file'],value['file'])))
        pending['original']=deepcopy(value);self.save()

    def read(self):
        source=self.source;need(self.started is None);self.started=source.monotonic()
        try:
            self.bound();need(self.state['phase'] in ('ready','admitted') and len(self.state['records'])<LIMIT)
            if self.previous is not None:need(same(self.decode(self.previous),self.state))
            prior=self.records(self.state)
            self.state.update(phase='reading',pending=dict(index=len(prior)+1,original=None),window=None);self.save()
            frame=source.read();ticket=self.baseline(frame['phaseAfter'])
            reference=dict(revision=len(source.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest())
            inventory=source.adapter._animation_inventory(source.selector,read_only=True)
            roots=source.adapter._script_roots(source.selector,read_only=True)
            need(isinstance(inventory,NativeAnimationInventory) and isinstance(roots,NativeScriptRoots)
                and inventory.pid==roots.pid==source.pid and inventory.ios is False and roots.ios is False)
            self.restore_inventory(inventory,prior);cache=inventory.read(inventory.last['sequence'] if inventory.last else 0)
            roots.restore(frame['group']['rootsAfter']);after=roots.read(roots.last['sequence'])
            with source.adapter.existing_input_session(source.selector):probe=source.adapter.invoke(source.selector,'probe.snapshot',{})
            status=source.phase.status(frame['phaseAfter']);self.baseline(status,ticket)
            epoch=inventory.clock_ms();row=dict(source=reference,inventory=cache,rootsAfter=after,probe=probe,phaseAfter=status,
                epochMs=epoch,hostEpochMs=source.phase.epoch_ms(),monotonicMs=source.monotonic()*1000)
            measured=self.measure(row,prior[-1] if prior else None);self.bound()
            ref=self.originals.write(len(prior)+1,row);self.state['records'].append(ref)
            window=self.window(prior+[row]);self.state.update(phase='admitted' if window else 'ready',pending=None,window=window);self.save()
            result=deepcopy(measured);epoch=inventory.clock_ms();host=source.phase.epoch_ms();self.bound();end=source.monotonic()
            floor=frame['group']['rootsBefore']['requestedEpochMs'];provider=frame['phaseBefore']['capturedEpochMs']
            fresh(floor,epoch);need(number(host,1,1e15) and number(end,row['monotonicMs']/1000,1e15))
            elapsed=end*1000-row['monotonicMs']
            need(-250<=host-provider<=1500 and max(epoch-floor,row['epochMs']-floor+elapsed)<=1500
                and row['hostEpochMs']-provider+elapsed<=1500);return result
        finally:self.started=None

    def wait(self,*,sleep=time.sleep):
        need(callable(sleep));started=previous=self.source.monotonic()
        if self.state['phase']=='reading':self.recover_pending()
        for attempt in range(LIMIT):
            now=self.source.monotonic();need(number(now,previous,1e15) and now-started<30);previous=now
            self.read();self.bound()
            if self.state['phase']=='admitted':return deepcopy(self.previous)
            need(attempt<LIMIT-1);sleep(.25)
        need(False)

    def recover_pending(self):
        """Finish only an original file which was actually fully committed.

        Replay is historical. A subsequent fresh read is mandatory for wait;
        missing/partial bytes or an uncertain read without an original stay red.
        """
        need(self.started is None);self.started=self.source.monotonic()
        try:
            self.bound();need(self.state['phase']=='reading' and self.previous is not None
                and same(self.decode(self.previous),self.state))
            original=self.state['pending']['original'];need(original is not None and original['phase'] in ('opened','saved'))
            row=self.originals.read(original);prior=self.records(self.state);self.measure(row,prior[-1] if prior else None)
            if original['phase']=='opened':
                original=deepcopy(original);original['phase']='saved';self.storage_intent('original',original)
            self.state['records'].append(self.originals.compact(original));window=self.window(prior+[row])
            self.state.update(phase='admitted' if window else 'ready',pending=None,window=window);self.save()
            return deepcopy(self.previous)
        finally:self.started=None
