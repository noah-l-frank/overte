"""Original same-physical Tablet live seals, before the sole normal Stop.

Both roles keep their own native/source histories and actual publisher records.
No session, process read, input or product cleanup is performed by replay().
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal as protocol
from ios.adapters.tablet_web_tail import TabletWebTail
from ios.adapters.tablet_web_quiet import quiet
from ios.adapters.tablet_web_cleanup_observation import validate as cleanup_original

VERSION=1


def binding(value):
    context(value)
    return {key:deepcopy(value[key]) for key in ('sourceRevision','artifactSha256','targetFingerprint','generation','processIdentity')}|dict(
        sessionSha256=hashlib.sha256(value['sessionId'].encode('utf-8')).hexdigest())


class TabletWebTerminal:
    def __init__(self,feature,lock):
        from ios.adapters.tablet_web_feature import IOSTabletWebFeature
        need(type(feature) is IOSTabletWebFeature and feature.role in protocol.ROLES and lock.path==feature.root/'script-feature-sources.lock')
        self.feature,self.lock=feature,lock;lock.assert_held()
        self.store=PrivateFeatureState(feature.root/('tabletweb-terminal-'+feature.run+'.json'))
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(tabletWebTerminalVersion=VERSION,binding=self.feature.binding,runId=self.feature.run,payload=pack([state]))
    def decode(self,value):
        exact(value,{'tabletWebTerminalVersion','binding','runId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['tabletWebTerminalVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'description','references','seal','samples','live'})
        protocol.description(state['description'],area='tablet-web',run=self.feature.run)
        exact(state['references'],protocol.ROLES)
        if state['seal'] is None:need(state['samples'] is state['live'] is None)
        else:
            protocol.sealed(state['seal'],state['description'],state['samples'])
            need(type(state['live']) is dict and digest(state['live'])==state['seal']['liveOriginalSha256'])
        return deepcopy(state)
    def save(self):
        self.lock.assert_held();self.feature.clock();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def roles(self):
        from ios.adapters.tablet_web_feature import IOSTabletWebFeature
        f=self.feature;result={}
        for role in protocol.ROLES:
            history=f.runtime.historical_observer(f.selector,f.run,role,f.binding,f.setup,f.origins,self.lock,
                fixture_url=f.client.url+'/runs/'+f.run+'/',monotonic=f.monotonic)
            owner=IOSTabletWebFeature(f.runtime,f.selector,f.client,f.run,role,f.binding,f.setup,f.origins,
                monotonic=f.monotonic,epoch_ms=f.epoch_ms,sleep=f.sleep,screen=f.screen)
            owner.load(history,historical=True)
            need(owner.state is not None and owner.state['phase'] in ('quiet','sealed','ended') and owner.state['cleanupOriginal'] is not None)
            tail=TabletWebTail(history,historical=True)
            need(tail.state['pending'] is tail.state['original'] is None and owner.state['quiet']
                and owner.state['cleanupOriginal']['quiet'][-1]==owner.state['quiet'][-1]==tail.state['records'][-1])
            latest=tail.read(owner.state['quiet'][-1]);source=history.observer.source
            source.history();need(not source.blocked and source.state['pending'] is source.state['intent'] is None
                and latest['row']['source']['observation']['reference']==source.state['records'][-1])
            result[role]=(owner,history)
        hosts=[history.bootstrap.admission['hostProcessId'] for _owner,history in result.values()]
        need(hosts[0]!=hosts[1]);return result
    def phase_floors(self):
        proof=getattr(self,'checked_replay',None)
        if proof is not None:
            from ios.adapters.tablet_web_terminal_replay import TabletTerminalReplay
            need(type(proof) is TabletTerminalReplay and proof.terminal is self);proof.guard();return deepcopy(proof.floors)
        values={}
        for role,(owner,history) in self.roles().items():
            latest=TabletWebTail(history,historical=True).read(owner.state['cleanupOriginal']['quiet'][-1])
            values[role]=deepcopy(latest['source']['phaseAfter'])
        return values
    def original(self,owner,history,original):
        measured=cleanup_original(history,original);tail=TabletWebTail(history,historical=True)
        before,stop=tail.read(original['before']),tail.read(original['stop']);frames=[tail.read(ref) for ref in original['quiet']]
        row=frames[-1]['source'];source=tail.source()
        proof=quiet(before,stop,frames,source.app_sources(row['apps']))
        held=proof['proof']['heldResources'];need(protocol.held(held)==measured['public']['resources'])
        if owner.screen is not None:
            from pathlib import Path
            from ios.adapters.tablet_web_samples import TabletWebSamples
            TabletWebSamples(history,Path(owner.screen['artifactRoot']),owner.screen['policy'],historical=True).files_absent()
        return measured,dict(binding=binding(owner.binding),heldResources=held,originalSha256=digest(original))
    def inspect(self,observer):
        self.lock.assert_held();need(self.feature.role=='primary');observer.check();phase=observer.observer.phase.read()
        need(phase['verb']=='cleanup' and phase['inputs']=={})
        owners=self.roles();refs={role:deepcopy(owner.state['cleanupOriginal']) for role,(owner,_history) in owners.items()}
        actual={role:self.original(owner,history,refs[role])[1] for role,(owner,history) in owners.items()}
        if self.state is None:
            description=dict(featureTerminalVersion=1,profile=protocol.PROFILE,area='tablet-web',runId=self.feature.run,ticket=phase['ticket'],roles=actual)
            protocol.description(description);self.state=dict(description=description,references=refs,seal=None,samples=None,live=None);self.save()
        else:
            need(self.state['description']['ticket']==phase['ticket'])
            for role,(owner,history) in owners.items():need(same(self.original(owner,history,self.state['references'][role])[1],self.state['description']['roles'][role]))
        return deepcopy(self.state['description'])
    @staticmethod
    def cleanup_rows(owner,history):
        from ios.adapters.tablet_web_cleanup_observation import candidates
        state=owner.state;refs=state['quiet'];need(len(refs)>=3)
        return candidates(history,state['cleanupBefore'],state['cleanupStop'],refs)
    def live_original(self,descriptor,samples):
        """Full historical source decoding plus exact canonical actor receipts."""
        protocol.window(samples,descriptor);owners=self.roles();available={};references={}
        for role,(owner,history) in owners.items():
            _measured,original=self.original(owner,history,self.state['references'][role]);need(same(original,descriptor['roles'][role]))
            available[role]={};references[role]={}
            for reference in self.cleanup_rows(owner,history):
                measured,actual=self.original(owner,history,reference);sequence=measured['public']['sequence']
                need(same(actual['binding'],original['binding']) and protocol.held(actual['heldResources'])==protocol.held(original['heldResources']))
                need(sequence not in available[role]);available[role][sequence]=measured;references[role][sequence]=reference
        actor=owners['actor'][1];source=actor.observer.source
        latest=TabletWebTail(actor,historical=True).read(owners['actor'][0].state['cleanupOriginal']['quiet'][-1])
        _facts,row,_parts=source.facts_at(latest['row']['source']['observation']['reference'],actor.observer.origins)
        phase_instance=row['phaseAfter']['instance'];store=PrivateFeatureState(self.feature.root/('phase-publication-tablet-web-'+self.feature.run+'-actor.json'))
        saved=store.read();need(saved is not None)
        journal=PhaseWitnessPublisher.archive(saved,store=store,binding=self.feature.binding,run=self.feature.run,area='tablet-web',
            fixture_url=self.feature.client.url,phase_instance=phase_instance,validate_original=actor.publication_original)
        need(journal['pending'] is None)
        decoder=object.__new__(PhaseWitnessPublisher);decoder.store=store;decoder.binding=self.feature.binding;decoder.run=self.feature.run
        decoder.area='tablet-web';decoder.url=self.feature.client.url;decoder.instance=phase_instance;decoder.validate_original=actor.publication_original;decoder.live=False
        receipts=[(ref,decoder.load(ref)) for ref in journal['records']];records=[]
        for pair in samples:
            primary,remote=pair['primary'],pair['actor'];ps,as_=primary['sequence'],remote['actorSequence']
            need(ps in available['primary'] and as_ in available['actor'] and same(primary,available['primary'][ps]['public'])
                and available['actor'][as_]['ticket']==descriptor['ticket'])
            matches=[ref for ref,row in receipts if row['mode']=='published' and same(row['entry'],remote)
                and same(row['intent']['original'],references['actor'][as_])]
            need(len(matches)==1);records.append(dict(primary=references['primary'][ps],actor=references['actor'][as_],publication=matches[0]))
        return dict(tabletWebTerminalLiveVersion=1,runId=self.feature.run,descriptionSha256=digest(descriptor),windowSha256=digest(samples),samples=records)
    def seal(self,observer,descriptor,samples):
        self.lock.assert_held();need(self.feature.role=='primary');observer.check();need(self.state is not None and same(descriptor,self.state['description']))
        phase=observer.observer.phase.read();need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['ticket']==descriptor['ticket'])
        actual=self.live_original(descriptor,samples);value=dict(featureTerminalSealVersion=1,description=deepcopy(descriptor),
            windowSha256=digest(samples),liveOriginalSha256=digest(actual));protocol.sealed(value,descriptor,samples)
        if self.state['seal'] is None:self.state.update(seal=value,samples=deepcopy(samples),live=actual);self.save()
        else:need(same(value,self.state['seal']) and same(actual,self.state['live']) and same(samples,self.state['samples']))
        return deepcopy(self.state['seal'])
    def replay(self):
        proof=getattr(self,'checked_replay',None)
        if proof is not None:
            from ios.adapters.tablet_web_terminal_replay import TabletTerminalReplay
            need(type(proof) is TabletTerminalReplay and proof.terminal is self);return proof.guard()
        self.lock.assert_held();need(self.previous is not None and same(self.store.read(),self.previous) and self.state['seal'] is not None)
        self.state=self.decode(self.previous);actual=self.live_original(self.state['description'],self.state['samples'])
        need(same(actual,self.state['live']));protocol.sealed(self.state['seal'],self.state['description'],self.state['samples'])
        return deepcopy(self.state['seal'])
