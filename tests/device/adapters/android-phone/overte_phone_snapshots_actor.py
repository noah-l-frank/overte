"""Independent Snapshot publisher with original files and strict own closure.

The separately provisioned Client owns publisher credentials. A primary ACK or
retirement plan can never replace this actor's acquisition or quiet interval.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from adapters.native_feature_observation import exact,need,integer
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.witness import Client,WITNESS_KEYS
from feature_journeys.phase_fixture import validate as phase_packet
from fixture.messages_mixer import start_identity
from overte_phone_assets_actor import PhoneAssetsActor
from overte_phone_create_actor import quiet_window
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceBusy
from overte_phone_snapshots_role import PhoneSnapshotsRole,SnapshotPhaseDeferred
from overte_phone_snapshots_measurements import SnapshotPending
from overte_phone_snapshots_evidence import SnapshotsOriginals

ACTOR_VERSION=2
STATE_FIELDS={'process','phase','pending','last','dropped','quiet','closure','partialClosure'}
TRANSITION_LIMIT=64


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def ordinary_extension(before,phase_before,phase_after,confirmed,run):
    """Validate historical originals only; no expected state or new authority."""
    previous=None
    for packet in (before,phase_before,phase_after,confirmed):
        phase_packet(packet,run=run,area='snapshots',request=packet['requestId'],epoch=packet['capturedEpochMs'],previous=previous)
        need(packet['active'] and packet['activations'])
        previous=packet
    old,new=before['activations'],phase_before['activations']
    need(len(new)==len(old)+1 and same(new[:-1],old)
        and same(new,phase_after['activations']) and same(new,confirmed['activations'])
        and old[-1]['stimulus']['verb']!='cleanup' and new[-1]['stimulus']['verb']!='baseline')


def validate_transition_history(feature,state,*,history_guard=None,expected_actor=None,role_header=None,current_guard=None):
    """Reopen each actual immutable frame/manifest, including at retirement."""
    need(current_guard is None or callable(current_guard) and callable(history_guard))
    need(history_guard is None or callable(history_guard))
    rows=state['transitions'];need(type(rows) is list and len(rows)<=TRANSITION_LIMIT)
    if not rows:return
    feature.lock.assert_held();target_guard=feature.bound if current_guard is None else current_guard;need(target_guard() is True)
    if history_guard is None:
        actor=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-actor-lifecycle.json'))
        role=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-actor-originals.json'))
        actor_header=actor.read()
        if expected_actor is not None:need(same(actor_header,expected_actor))
        if role_header is None:role_header=role.read()
        def history_guard():
            feature.lock.assert_held();feature.header_authority()
            need(same(actor.read(),actor_header) and same(role.read(),role_header));return True
    host=SnapshotsOriginals(feature.root,feature.binding,feature.run,'actor',history_guard,lambda *_:need(False),kind='snapshots')
    role_state=None
    if rows:
        need(role_header is not None)
        exact(role_header,{'snapshotsRoleVersion','runId','binding','role','payload'})
        need(type(role_header['snapshotsRoleVersion']) is int and role_header['snapshotsRoleVersion']==1
            and role_header['runId']==feature.run and role_header['role']=='actor' and same(role_header['binding'],feature.binding))
        states=unpack(role_header['payload']);need(len(states)==1);role_state=states[0]
        exact(role_state,{'phase','sequence','manifests','pending'})
        need(role_state['phase'] in ('ready','reading','retired') and integer(role_state['sequence'],0,256)
            and type(role_state['manifests']) is list)
    previous=0
    for row in rows:
        exact(row,{'snapshotActorTransitionVersion','kind','before','confirmed','manifest','frameSequence','frameSha256',
            'binding','process','scope','featureOwnerSha256','actorOwnerSha256','roleOwnerSha256'})
        need(type(row['snapshotActorTransitionVersion']) is int and row['snapshotActorTransitionVersion']==1
            and integer(row['frameSequence'],previous+1,256) and same(row['binding'],feature.binding) and same(row['process'],state['process']))
        for key in ('frameSha256','featureOwnerSha256','actorOwnerSha256','roleOwnerSha256'):
            need(type(row[key]) is str and len(row[key])==64 and all(c in '0123456789abcdef' for c in row[key]))
        need(row['kind'] in ('before-sources','after-sources'))
        exact(row['scope'],{'kind','handoffId'})
        entries=host.manifest(row['manifest']);need(entries)
        reference=host.expand(entries[-1]);need(reference['index']==row['frameSequence'])
        block=row['manifest']['block'];need(role_state['sequence']>=row['frameSequence'] and block<=len(role_state['manifests']))
        current=host.manifest(role_state['manifests'][block-1])
        need(len(current)>=len(entries) and same(current[:len(entries)],entries))
        frame=host.read(reference);need(digest(frame)==row['frameSha256'])
        handoffs=frame.get('handoffOriginals',[])
        if row['kind']=='before-sources':
            exact(frame,{'ticket','phaseBefore','phaseAfter','phaseAdmission','diagnostic','image','binaries','retirement'})
            admission=frame['phaseAdmission'];exact(admission,{'snapshotPhaseAdmissionVersion','kind','before'})
            need(frame['diagnostic'] is True and frame['image'] is frame['retirement'] is None and frame['binaries']==[]
                and type(admission['snapshotPhaseAdmissionVersion']) is int and admission['snapshotPhaseAdmissionVersion']==1
                and admission['kind']=='before-sources' and same(admission['before'],row['before'])
                and row['scope']==dict(kind='unmeasured',handoffId=None))
        elif row['scope']['kind']=='handoff':
            need(not frame.get('diagnostic'))
            need(type(row['scope']['handoffId']) is str and len(row['scope']['handoffId'])==32 and handoffs
                and all(original['source']['handoffId']==row['scope']['handoffId'] for original in handoffs))
        else:need(not frame.get('diagnostic') and row['scope']['kind']=='foreground' and row['scope']['handoffId'] is None and not handoffs)
        ordinary_extension(row['before'],frame['phaseBefore'],frame['phaseAfter'],row['confirmed'],feature.run)
        need(frame['ticket']==frame['phaseBefore']['activations'][-1]['ticket'])
        previous=row['frameSequence']
    need(history_guard() is True);need(target_guard() is True)


class PhoneSnapshotsActor(PhoneAssetsActor):
    def __init__(self,feature):
        need(feature.role=='actor' and isinstance(feature.phase.client,Client))
        self.feature,self.client=feature,feature.phase.client
        self.store=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-actor-lifecycle.json'))
        self.previous=self.state=None
        self._cleanup_reader=None;self._cleanup_anchor=None;self._cleanup_failed=False;self._cleanup_started=False
        self._ordinary_failed=False

    def load(self):
        f=self.feature;f.bound();actual=self.store.read()
        # This journal has one writer. A retained process must never adopt a
        # formally valid rollback of its own last acknowledged durable save.
        if self.previous is not None:need(same(actual,self.previous))
        self.previous=actual
        if self.previous is None:
            self.state=dict(process=dict(pid=os.getpid(),start=start_identity(os.getpid())),phase='watching',pending=None,last=None,dropped=[],quiet=None,closure=None,partialClosure=None,transitions=[])
            need(self.state['process']!=f.state['hostProcess']);self.save()
        else:
            exact(self.previous,{'snapshotsActorVersion','runId','binding','payload'})
            version=self.previous['snapshotsActorVersion']
            need(type(version) is int and version in (1,ACTOR_VERSION)
                and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,STATE_FIELDS if version==1 else STATE_FIELDS|{'transitions'})
            # Exact process-bound v1 state predates transition recovery. Preserve
            # every old pending/receipt/quiet field; the next own CAS save writes
            # v2 with an empty transition history. Never infer a legacy event.
            if version==1:self.state['transitions']=[]
            need(self.state['process']==dict(pid=os.getpid(),start=start_identity(os.getpid())) and self.state['phase'] in ('watching','retired')
                and type(self.state['dropped']) is list and len(self.state['dropped'])<=256)
            if self.state['partialClosure'] is not None:
                need(self.state['phase']=='retired' and self.state['pending'] is self.state['last'] is self.state['quiet'] is None
                    and self.state['closure'] is not None and self.state['closure']['active'] is False)
            validate_transition_history(f,self.state,expected_actor=self.previous)

    def save(self):
        self.feature.bound();need(same(self.store.read(),self.previous))
        value=dict(snapshotsActorVersion=ACTOR_VERSION,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
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
        need(not self._cleanup_failed and not self._ordinary_failed)
        self._cleanup_entered=False;self._ordinary_entered=False
        try:return self.step_owned()
        except PhoneScriptSourceBusy:
            if self._cleanup_entered:
                self._cleanup_reader=None
                if self._cleanup_started:self._cleanup_failed=True
            raise
        except Exception:
            self._cleanup_reader=None
            if self._cleanup_started:self._cleanup_failed=True
            elif self._ordinary_entered:self._ordinary_failed=True
            raise

    def poll_delay(self):
        """Yield briefly only between this flow's verified cleanup samples.

        This is scheduling, not measurement authority. The following step still
        reopens every original and checks the current owners, phase and target.
        """
        if (self._cleanup_reader is not None and self._cleanup_anchor is not None and not self._cleanup_failed
                and not self._ordinary_failed and self.state is not None
                and self.state['phase']=='watching' and self.state['pending'] is None and self.state['quiet'] is not None):
            # The source-lock contender polls every 25 ms. Leave two polling
            # opportunities before this actor competes for the lock again.
            return .05
        return .25

    def ordinary_pin(self):
        f=self.feature;scope=getattr(f.adapter,'_existing_input_scope',None)
        return dict(feature=deepcopy(f.previous),actor=deepcopy(self.previous),binding=deepcopy(f.binding),
            process=deepcopy(self.state['process']),guard=getattr(f,'guard',None),system=getattr(f,'_system_scope',None),
            sdk=scope,sdkValue=deepcopy(scope))

    def ordinary_owners(self,role,pin):
        f=self.feature
        need(same(f.previous,pin['feature']) and same(f.store.read(),pin['feature'])
            and same(self.previous,pin['actor']) and same(self.store.read(),pin['actor'])
            and same(f.binding,pin['binding']) and same(self.state['process'],pin['process'])
            and getattr(f,'guard',None) is pin['guard'] and getattr(f,'_system_scope',None) is pin['system']
            and getattr(f.adapter,'_existing_input_scope',None) is pin['sdk']
            and same(getattr(f.adapter,'_existing_input_scope',None),pin['sdkValue']))
        f.bound();role.bound();role.history_authority()

    def ordinary_admission(self,role,status,pin,phase_before):
        if same(status['activations'],phase_before['activations']) and status['active']==phase_before['active']:return
        self.ordinary_owners(role,pin)
        confirmed=self.feature.phase.status(phase_before)
        # Admission has only two new original phase packets, not target facts.
        phase_packet(status,run=self.feature.run,area='snapshots',request=status['requestId'],epoch=status['capturedEpochMs'])
        phase_packet(phase_before,run=self.feature.run,area='snapshots',request=phase_before['requestId'],epoch=phase_before['capturedEpochMs'],previous=status)
        phase_packet(confirmed,run=self.feature.run,area='snapshots',request=confirmed['requestId'],epoch=confirmed['capturedEpochMs'],previous=phase_before)
        need(status['active'] and phase_before['active'] and confirmed['active']
            and len(phase_before['activations'])==len(status['activations'])+1
            and same(phase_before['activations'][:-1],status['activations'])
            and same(confirmed['activations'],phase_before['activations'])
            and status['activations'][-1]['stimulus']['verb']!='cleanup'
            and phase_before['activations'][-1]['stimulus']['verb']!='baseline')
        self.ordinary_owners(role,pin)
        role.checkpoint(phaseAfter=confirmed,phaseAdmission=dict(snapshotPhaseAdmissionVersion=1,kind='before-sources',before=deepcopy(status)))
        raise SnapshotPhaseDeferred()

    def ordinary_transition(self,role,status,pin,*,kind='after-sources'):
        """Retain one genuine pre-publication transition; acquire anew later."""
        f=self.feature;self.ordinary_owners(role,pin)
        need(self.state['phase']=='watching' and self.state['pending'] is None and self.state['closure'] is None
            and self.state['quiet'] is None and not self._cleanup_started and f.state['phase'] in ('baseline','active')
            and role.state['phase']=='ready' and role.state['pending'] is None and not role._host_publication
            and len(self.state['transitions'])<TRANSITION_LIMIT)
        manifest=deepcopy(role.state['manifests'][-1]);entries=role.originals.manifest(manifest)
        frame=role.originals.read(role.originals.expand(entries[-1]))
        need(same(frame,role.frames[-1]))
        need(frame.get('diagnostic') is True if kind=='before-sources' else not frame.get('diagnostic'))
        confirmed=f.phase.status(frame['phaseAfter'])
        ordinary_extension(status,frame['phaseBefore'],frame['phaseAfter'],confirmed,f.run)
        need(frame['ticket']==frame['phaseBefore']['activations'][-1]['ticket'])
        self.ordinary_owners(role,pin)
        row=dict(snapshotActorTransitionVersion=1,kind=kind,before=deepcopy(status),confirmed=confirmed,manifest=manifest,
            frameSequence=role.state['sequence'],frameSha256=digest(frame),binding=deepcopy(f.binding),process=deepcopy(self.state['process']),
            scope=(dict(kind='unmeasured',handoffId=None) if kind=='before-sources' else
                dict(kind='handoff' if role.system else 'foreground',handoffId=None if f.state['handoff'] is None else f.state['handoff']['id'])),featureOwnerSha256=digest(pin['feature']),
            actorOwnerSha256=digest(pin['actor']),roleOwnerSha256=digest(role.previous))
        self.state['transitions'].append(row);validate_transition_history(f,self.state,expected_actor=self.previous)
        self.ordinary_owners(role,pin);self.save();return False

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
            self._ordinary_entered=verb!='cleanup'
            ordinary=None if verb=='cleanup' else self.ordinary_pin()
            role=PhoneSnapshotsRole(f,'actor',**({} if anchor is None else {'expected_previous':anchor[1]['role']}))
            if anchor is not None:need(same(role.previous,anchor[1]['role']))
            if role.state['phase']=='reading':role.recover()
            if verb=='cleanup':
                need(same(f.store.read(),f.previous))
                prepared=dict(feature=deepcopy(f.previous),actor=deepcopy(self.previous),role=deepcopy(role.previous),
                    binding=deepcopy(f.binding),phase=deepcopy(status))
            else:
                try:measured=role.read(role.state['sequence'],phase_admission=lambda reader,phase:self.ordinary_admission(reader,status,ordinary,phase))
                except SnapshotPhaseDeferred:return self.ordinary_transition(role,status,ordinary,kind='before-sources')
                except SnapshotPending:return False
                self.ordinary_owners(role,ordinary)
                if role.frames[-1]['ticket']!=current['ticket']:return self.ordinary_transition(role,status,ordinary)
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
