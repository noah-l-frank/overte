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
from overte_phone_script_lock import PhoneScriptSourceBusy
from overte_phone_snapshots_role import PhoneSnapshotsRole
from overte_phone_snapshots_measurements import SnapshotPending


class PhoneSnapshotsActor(PhoneAssetsActor):
    def __init__(self,feature):
        need(feature.role=='actor' and isinstance(feature.phase.client,Client))
        self.feature,self.client=feature,feature.phase.client
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-actor-lifecycle.json'))
        self.previous=self.state=None
        self._cleanup_reader=None;self._cleanup_anchor=None;self._cleanup_failed=False;self._cleanup_started=False

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
        need(not self._cleanup_failed)
        self._cleanup_entered=False
        try:return self.step_owned()
        except PhoneScriptSourceBusy:
            if self._cleanup_entered:
                self._cleanup_reader=None
                if self._cleanup_started:self._cleanup_failed=True
            raise
        except Exception:
            self._cleanup_reader=None
            if self._cleanup_started:self._cleanup_failed=True
            raise

    def cleanup_owners(self,role,prepared,*,loaded=False):
        f=self.feature;store=role.store if hasattr(role,'store') else role
        if loaded:
            need(same(f.previous,prepared['feature']) and same(self.previous,prepared['actor'])
                and same(role.previous if hasattr(role,'previous') else store.read(),prepared['role']) and same(f.binding,prepared['binding']))
        else:
            need(same(f.store.read(),prepared['feature']) and same(self.store.read(),prepared['actor'])
                and same(store.read(),prepared['role']) and same(f.binding,prepared['binding']))

    def cleanup_anchor(self,role,phase):
        f=self.feature
        need(role.state['phase']=='ready' and role.state['pending'] is None and not role._host_publication)
        # Trust only this flow's verified saves, never a newly read owner.
        prepared=dict(feature=deepcopy(f.previous),actor=deepcopy(self.previous),role=deepcopy(role.previous),
            binding=deepcopy(f.binding),phase=deepcopy(phase))
        self.cleanup_owners(role,prepared);self._cleanup_anchor=(role.store,prepared);return prepared

    def retain_cleanup(self,role,phase):
        self._cleanup_reader=(role,self.cleanup_anchor(role,phase))

    def step_owned(self):
        f=self.feature
        # The facade supplies either its original foreground binding or the
        # explicit passive OS scope. Never establish a foreground-only scope
        # while the real Android chooser/receiver owns the active component.
        with f.lock.held():
            self._cleanup_entered=True;started=f.monotonic();retained=self._cleanup_reader;anchor=self._cleanup_anchor
            if anchor is not None:self.cleanup_owners(*anchor)
            f.load();need(f.state is not None);self.load()
            if anchor is not None:self.cleanup_owners(*anchor,loaded=True)
            if retained is not None:
                self.cleanup_owners(*retained,loaded=True)
                f.bound();retained[0].bound();retained[0].history_authority()
            status=f.phase.status(self.state['closure'])
            if f.state['phase']=='partial-cleaned':
                need(f.state['partial'] is True and self.state['pending'] is self.state['last'] is self.state['quiet'] is None)
                if status['active']:return False
                proof=f.partial_restored();need(type(proof) is dict)
                self.state.update(phase='retired',closure=status,partialClosure=proof);self.save();return True
            need(self.state['partialClosure'] is None)
            if not status['active']:
                if anchor is not None:
                    for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','activations'):
                        need(same(status[key],anchor[1]['phase'][key]))
                    self._cleanup_reader=None;self._cleanup_anchor=None
                need(f.state['phase'] in ('cleaned','retiring') and self.state['quiet'] is not None and self.state['quiet']['complete'])
                if self.state['pending'] is not None:self.drop_closed(status)
                need(self.state['last'] is not None and self.state['last']['original']['sample']['ticket']==status['activations'][-1]['ticket'])
                role=PhoneSnapshotsRole(f,'actor',**({} if anchor is None else {'expected_previous':anchor[1]['role']}))
                if anchor is not None:need(same(role.previous,anchor[1]['role']))
                if role.state['phase']=='reading':role.recover()
                measured=role.read(role.state['sequence']);need(measured['resources']==[])
                proof=f.restored(snapshot=role.frames[-1]);role.retire()
                self.state.update(phase='retired',closure=status);self.state['quiet']['final']=proof;self.save();return True
            if anchor is not None:
                self.cleanup_phase(status,anchor[1]['phase'])
                need(f.state['phase']=='cleaned' and self.state['phase']=='watching' and self.state['pending'] is None
                    and self.state['closure'] is None and self.state['partialClosure'] is None)
            if retained is not None:
                self.cleanup_phase(status,retained[1]['phase'])
                need(f.state['phase']=='cleaned' and self.state['phase']=='watching' and self.state['pending'] is None
                    and self.state['closure'] is None and self.state['partialClosure'] is None)
                return self.quiet_batch(retained[0],retained[1],started)
            need(self.state['phase']=='watching')
            if self.state['pending'] is not None:self.deliver();return False
            if f.state['phase'] not in ('baseline','active','cleaned'):return False
            current=status['activations'][-1];verb=current['stimulus']['verb']
            if verb=='baseline' and f.state['phase']!='baseline':return False
            if verb not in ('baseline','cleanup') and (not f.state['actions'] or f.state['actions'][-1]['ticket']!=current['ticket'] or f.state['actions'][-1]['phase']!='acknowledged'):return False
            if verb=='cleanup' and f.state['phase']!='cleaned':return False
            if verb!='cleanup' and f.state['phase']=='cleaned':return False
            if verb=='cleanup':self._cleanup_started=True
            role=PhoneSnapshotsRole(f,'actor',**({} if anchor is None else {'expected_previous':anchor[1]['role']}))
            if anchor is not None:need(same(role.previous,anchor[1]['role']))
            if role.state['phase']=='reading':role.recover()
            if verb=='cleanup':
                need(same(f.store.read(),f.previous))
                prepared=dict(feature=deepcopy(f.previous),actor=deepcopy(self.previous),role=deepcopy(role.previous),
                    binding=deepcopy(f.binding),phase=deepcopy(status))
            else:
                try:measured=role.read(role.state['sequence'])
                except SnapshotPending:return False
                sample=dict(ticket=current['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                    facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['snapshots']})
                need(role.frames[-1]['ticket']==current['ticket'])
                self.state['pending']=dict(sample=sample,issued=False);self.save();self.deliver();return False
        # Preparation may replay a long immutable history. Release its lock
        # before the bounded current quiet interval so another role can run.
        # No measurement or publication authority survives this boundary.
        f.sleep(.1)
        return self.cleanup_batch(role,prepared)

    def cleanup_batch(self,role,prepared):
        f=self.feature
        with f.lock.held():
            started=f.monotonic()
            # Pin all three actual owners before loading any changed state.
            self.cleanup_owners(role,prepared)
            f.load();self.load();self.cleanup_owners(role,prepared,loaded=True)
            f.bound();role.bound();role.history_authority()
            need(f.state['phase']=='cleaned' and self.state['phase']=='watching' and self.state['pending'] is None
                and self.state['closure'] is None and self.state['partialClosure'] is None)
            status=f.phase.status();self.cleanup_phase(status,prepared['phase'])
            return self.quiet_batch(role,prepared,started)

    def quiet_batch(self,role,prepared,started):
        f=self.feature
        while True:
            f.bound();role.history_authority()
            # Reuse only normal reader continuity. Every old file still
            # passes its complete original inode/byte/hash validation.
            need(same(role.restore_originals(),role.frames))
            status=f.phase.status();self.cleanup_phase(status,prepared['phase'])
            try:measured=role.read(role.state['sequence'])
            except SnapshotPending:
                self._cleanup_reader=None;self.cleanup_anchor(role,status);return False
            need(measured['resources']==[] and role.frames[-1]['ticket']==status['activations'][-1]['ticket'])
            proof=f.restored(snapshot=role.frames[-1]);now=f.monotonic()
            quiet=quiet_window(self.state['quiet'],now,measured['sequence']);quiet['final']=proof;self.state['quiet']=quiet
            self.save()
            if quiet['complete']:
                sample=dict(ticket=status['activations'][-1]['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                    facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['snapshots']})
                self.state['pending']=dict(sample=sample,issued=False);self.save();self.deliver()
                self.retain_cleanup(role,status);return False
            if f.monotonic()-started>=3.5:
                self.retain_cleanup(role,status);return False
            f.sleep(.1)

    @staticmethod
    def cleanup_phase(status,prepared):
        need(status['active'] and prepared['active'] and status['activations']
            and status['activations'][-1]['stimulus']['verb']=='cleanup')
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations'):
            need(same(status[key],prepared[key]))
