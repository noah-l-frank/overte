"""Independent Snapshot publisher with original files and strict own closure.

The separately provisioned Client owns publisher credentials. A primary ACK or
retirement plan can never replace this actor's acquisition or quiet interval.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client,WITNESS_KEYS
from fixture.messages_mixer import start_identity
from overte_phone_assets_actor import PhoneAssetsActor
from overte_phone_create_actor import quiet_window
from overte_phone_script_history import pack,unpack,same
from overte_phone_snapshots_role import PhoneSnapshotsRole
from overte_phone_snapshots_measurements import SnapshotPending


class PhoneSnapshotsActor(PhoneAssetsActor):
    def __init__(self,feature):
        need(feature.role=='actor' and isinstance(feature.phase.client,Client))
        self.feature,self.client=feature,feature.phase.client
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-actor-lifecycle.json'))
        self.previous=self.state=None

    def load(self):
        f=self.feature;f.bound();self.previous=self.store.read()
        if self.previous is None:
            self.state=dict(process=dict(pid=os.getpid(),start=start_identity(os.getpid())),phase='watching',pending=None,last=None,dropped=[],quiet=None,closure=None,partialClosure=None)
            need(self.state['process']!=f.state['hostProcess']);self.save()
        else:
            exact(self.previous,{'snapshotsActorVersion','runId','binding','payload'})
            need(type(self.previous['snapshotsActorVersion']) is int and self.previous['snapshotsActorVersion']==1
                and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,{'process','phase','pending','last','dropped','quiet','closure','partialClosure'})
            need(self.state['process']==dict(pid=os.getpid(),start=start_identity(os.getpid())) and self.state['phase'] in ('watching','retired')
                and type(self.state['dropped']) is list and len(self.state['dropped'])<=256)
            if self.state['partialClosure'] is not None:
                need(self.state['phase']=='retired' and self.state['pending'] is self.state['last'] is self.state['quiet'] is None
                    and self.state['closure'] is not None and self.state['closure']['active'] is False)

    def save(self):
        self.feature.bound();need(same(self.store.read(),self.previous))
        value=dict(snapshotsActorVersion=1,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def receipt(self,pending):
        value=self.client.request('/runs/'+self.feature.run)
        exact(value,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.feature.run and value['area']=='snapshots')
        matches=[row for row in value['entries'] if row['actorSequence']==pending['sample']['actorSequence']]
        need(len(matches)<=1)
        if not matches:return None
        row=matches[0];need(same({key:row[key] for key in pending['sample']},pending['sample']));return deepcopy(row)

    def step(self):
        f=self.feature
        # The facade supplies either its original foreground binding or the
        # explicit passive OS scope. Never establish a foreground-only scope
        # while the real Android chooser/receiver owns the active component.
        with f.lock.held():
            f.load();need(f.state is not None);self.load();status=f.phase.status(self.state['closure'])
            if f.state['phase']=='partial-cleaned':
                need(f.state['partial'] is True and self.state['pending'] is self.state['last'] is self.state['quiet'] is None)
                if status['active']:return False
                proof=f.partial_restored();need(type(proof) is dict)
                self.state.update(phase='retired',closure=status,partialClosure=proof);self.save();return True
            need(self.state['partialClosure'] is None)
            if not status['active']:
                need(f.state['phase'] in ('cleaned','retiring') and self.state['quiet'] is not None and self.state['quiet']['complete'])
                if self.state['pending'] is not None:self.drop_closed(status)
                need(self.state['last'] is not None and self.state['last']['original']['sample']['ticket']==status['activations'][-1]['ticket'])
                role=PhoneSnapshotsRole(f,'actor')
                if role.state['phase']=='reading':role.recover()
                measured=role.read(role.state['sequence']);need(measured['resources']==[])
                proof=f.restored(snapshot=role.frames[-1]);role.retire()
                self.state.update(phase='retired',closure=status);self.state['quiet']['final']=proof;self.save();return True
            need(self.state['phase']=='watching')
            if self.state['pending'] is not None:self.deliver();return False
            if f.state['phase'] not in ('baseline','active','cleaned'):return False
            current=status['activations'][-1];verb=current['stimulus']['verb']
            if verb=='baseline' and f.state['phase']!='baseline':return False
            if verb not in ('baseline','cleanup') and (not f.state['actions'] or f.state['actions'][-1]['ticket']!=current['ticket'] or f.state['actions'][-1]['phase']!='acknowledged'):return False
            if verb=='cleanup' and f.state['phase']!='cleaned':return False
            if verb!='cleanup' and f.state['phase']=='cleaned':return False
            role=PhoneSnapshotsRole(f,'actor')
            if role.state['phase']=='reading':role.recover()
            held_started=f.monotonic()
            while True:
                try:measured=role.read(role.state['sequence'])
                except SnapshotPending:return False
                sample=dict(ticket=current['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                    facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['snapshots']})
                need(role.frames[-1]['ticket']==current['ticket'])
                if verb=='cleanup':
                    proof=f.restored(snapshot=role.frames[-1]);now=f.monotonic();need(measured['resources']==[])
                    quiet=quiet_window(self.state['quiet'],now,measured['sequence']);quiet['final']=proof;self.state['quiet']=quiet
                    if not quiet['complete']:
                        self.save()
                        if f.monotonic()-held_started>=3.5:return False
                        f.sleep(.1);continue
                self.state['pending']=dict(sample=sample,issued=False);self.save();self.deliver();return False
