"""Separately credentialed Create actor: own native originals and no input path."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os

from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client,WITNESS_KEYS
from fixture.messages_mixer import start_identity
from overte_phone_create_role import PhoneCreateRole
from overte_phone_create_measurements import CreatePending
from overte_phone_script_history import pack,unpack,same


def quiet_window(previous,now,sequence):
    """Require a new real three-second window after any freshness gap."""
    need(number(now,0,1e15) and type(sequence) is int and 0<sequence<=256)
    if previous is not None:
        need(now>=previous['last'] and sequence>previous['sequences'][-1])
    if previous is None or now-previous['last']>1.5:
        previous=dict(started=now,last=now,sequences=[],complete=False,final=None)
    value=deepcopy(previous);value['last']=now;value['sequences'].append(sequence)
    value['complete']=now-value['started']>=3 and len(value['sequences'])>=3
    return value


class PhoneCreateActor:
    def __init__(self,feature):
        need(feature.role=='actor' and isinstance(feature.phase.client,Client))
        self.feature=feature;self.client=feature.phase.client
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-create-actor-lifecycle.json'))
        self.previous=self.state=None

    def load(self):
        f=self.feature;f.bound();self.previous=self.store.read()
        if self.previous is None:
            self.state=dict(process=dict(pid=os.getpid(),start=start_identity(os.getpid())),phase='watching',pending=None,last=None,
                dropped=[],quiet=None,closure=None)
            need(self.state['process']!=f.state['hostProcess']);self.save()
        else:
            exact(self.previous,{'createActorVersion','runId','binding','payload'})
            need(type(self.previous['createActorVersion']) is int and self.previous['createActorVersion']==1
                and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,{'process','phase','pending','last','dropped','quiet','closure'})
            need(self.state['process']==dict(pid=os.getpid(),start=start_identity(os.getpid()))
                and self.state['phase'] in ('watching','retired'))

    def save(self):
        self.feature.bound();need(same(self.store.read(),self.previous))
        value=dict(createActorVersion=1,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def receipt(self,pending):
        value=self.client.request('/runs/'+self.feature.run)
        exact(value,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.feature.run and value['area']=='create')
        matches=[row for row in value['entries'] if row['actorSequence']==pending['sample']['actorSequence']]
        need(len(matches)<=1)
        if not matches:return None
        row=matches[0];need(same({key:row[key] for key in pending['sample']},pending['sample']));return deepcopy(row)

    def deliver(self):
        try:return self._deliver()
        except (ValueError,RuntimeError):
            status=self.feature.phase.status()
            if status['active']:raise
            self.drop_closed(status)

    def drop_closed(self,status):
        need(not status['active'] and self.state['pending'] is not None)
        pending=deepcopy(self.state['pending']);need(any(row['ticket']==pending['sample']['ticket'] for row in status['activations']))
        self.state['dropped'].append(dict(pending,retiredProvider=deepcopy(status)))
        self.state['pending']=None;self.save()

    def _deliver(self):
        f=self.feature;pending=deepcopy(self.state['pending']);need(pending is not None)
        receipt=self.receipt(pending)
        if receipt is None:
            status=f.phase.status();current=status['activations'][-1]
            stale=not status['active'] or current['ticket']!=pending['sample']['ticket'] or f.phase.epoch_ms()-pending['sample']['capturedEpochMs']>1500
            if stale:
                self.state['dropped'].append(pending);self.state['pending']=None;self.save();return
            need(not pending['issued']);self.state['pending']['issued']=True;self.save();pending=deepcopy(self.state['pending'])
            try:
                reply=self.client.request('/runs/'+f.run+'/samples',pending['sample']);need(reply=={})
            except ValueError:
                receipt=self.receipt(pending)
                if receipt is None:raise
            receipt=self.receipt(pending);need(receipt is not None)
        self.state.update(last=dict(original=pending,receipt=receipt),pending=None);self.save()

    def step(self):
        f=self.feature
        with f.lock.held(),f.adapter.existing_input_session(f.selector):
            f.load();need(f.state is not None);self.load()
            status=f.phase.status(self.state['closure'])
            if not status['active']:
                need(f.state['phase']=='cleaned' and self.state['quiet'] is not None and self.state['quiet']['complete'])
                if self.state['pending'] is not None:self.drop_closed(status)
                need(self.state['last'] is not None and self.state['last']['original']['sample']['ticket']==status['activations'][-1]['ticket'])
                proof=f.restored();role=PhoneCreateRole(f,'actor');need(role.state['phase']=='ready')
                self.state.update(phase='retired',closure=status);self.state['quiet']['final']=proof;self.save();return True
            need(self.state['phase']=='watching')
            if self.state['pending'] is not None:self.deliver();return False
            if f.state['phase'] not in ('baseline','active','cleaned'):return False
            current=status['activations'][-1]
            verb=current['stimulus']['verb']
            # A new provider ticket may precede the primary's ordinary input.
            # Gate acquisition on its completed input barrier only; every fact
            # still comes from this actor's new native/UI/cell/pixel originals.
            if verb=='baseline' and f.state['phase']!='baseline':return False
            if verb not in ('baseline','cleanup') and (not f.state['actions'] or
                    f.state['actions'][-1]['ticket']!=current['ticket'] or f.state['actions'][-1]['phase']!='acknowledged'):return False
            if current['stimulus']['verb']=='cleanup' and f.state['phase']!='cleaned':return False
            if current['stimulus']['verb']!='cleanup' and f.state['phase']=='cleaned':return False
            role=PhoneCreateRole(f,'actor')
            if role.state['phase']=='reading':role.recover()
            try:measured=role.read(role.state['sequence'])
            except CreatePending:return False
            sample=dict(ticket=current['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['create']})
            need(role.frames[-1]['ticket']==current['ticket'])
            if current['stimulus']['verb']=='cleanup':
                proof=f.restored(snapshot=role.frames[-1]);now=f.monotonic();quiet=self.state['quiet']
                need(measured['resources']==[])
                quiet=quiet_window(quiet,now,measured['sequence'])
                quiet['final']=proof;self.state['quiet']=quiet
                if not quiet['complete']:self.save();return False
            self.state['pending']=dict(sample=sample,issued=False);self.save();self.deliver();return False
