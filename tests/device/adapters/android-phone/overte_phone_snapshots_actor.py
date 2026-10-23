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
from feature_journeys.contract import number
from fixture.messages_mixer import start_identity
from overte_phone_assets_actor import PhoneAssetsActor
from overte_phone_create_actor import quiet_window
from overte_phone_script_history import pack,unpack,same,canonical
from overte_phone_script_lock import PhoneScriptSourceBusy
from overte_phone_snapshots_role import PhoneSnapshotsRole,SnapshotPhaseDeferred,role_state,validate_read_ready_mode,validate_read_ready_slot,validate_read_ready_slot_owner
from overte_phone_snapshots_constructor_history import graph_digest,passive_scope,SnapshotConstructorHistoryPass
from overte_phone_snapshots_actor_history import SnapshotActorHistoryPass
from overte_phone_snapshots_measurements import SnapshotPending
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_emote_originals import BLOCK

ACTOR_VERSION=3
STATE_FIELDS={'process','phase','pending','last','dropped','quiet','closure','partialClosure'}
TRANSITION_LIMIT=64


def actor_fields(version):
    need(type(version) is int and version in (1,2,ACTOR_VERSION))
    return STATE_FIELDS|({'transitions'} if version>=2 else set())|({'primaryCue'} if version>=3 else set())


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def cue_state(feature,cue):
    exact(cue,{'snapshotPrimaryCueVersion','header'})
    need(type(cue['snapshotPrimaryCueVersion']) is int and cue['snapshotPrimaryCueVersion']==1)
    state=role_state(cue['header'],feature.binding,feature.run,'primary')
    need(cue['header'] is not None and state['phase']=='ready' and state['pending'] is None and state['sequence']>0)
    return state


def primary_manifests(host,state):
    rows=[]
    for block,reference in enumerate(state['manifests'],1):
        need(reference['block']==block and (block==len(state['manifests']) or reference['count']==BLOCK))
        rows.extend(host.manifest(reference))
    need(len(rows)==state['sequence']);return rows


def validate_primary_cue(feature,cue,primary_header,*,history_guard,current_guard=None):
    """Validate only a scheduling floor against actual immutable originals.

    Retirement supplies its verified archived Primary header and explicit
    guards. No Primary measurement is ever returned as this actor's fact.
    """
    need(callable(history_guard) and (current_guard is None or callable(current_guard)))
    if cue is None:return
    feature.lock.assert_held();old=cue_state(feature,cue)
    current=role_state(primary_header,feature.binding,feature.run,'primary')
    need(primary_header is not None and current['sequence']>=old['sequence'])
    target=feature.bound if current_guard is None else current_guard
    need(target() is True and history_guard() is True)
    host=SnapshotsOriginals(feature.root,feature.binding,feature.run,'primary',history_guard,lambda *_:need(False),kind='snapshots')
    before=primary_manifests(host,old);after=primary_manifests(host,current)
    need(same(after[:len(before)],before));need(target() is True and history_guard() is True)



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
        self._cleanup_reader=None;self._cleanup_anchor=None;self._cleanup_history=None;self._cleanup_failed=False;self._cleanup_started=False
        self._ordinary_failed=False;self._ordinary_primary=None;self._ordinary_publication=None;self._cleanup_publication=None

    def load(self):
        f=self.feature;f.bound();actual=self.store.read()
        # This journal has one writer. A retained process must never adopt a
        # formally valid rollback of its own last acknowledged durable save.
        if self.previous is not None:need(same(actual,self.previous))
        self.previous=actual
        if self.previous is None:
            self.state=dict(process=dict(pid=os.getpid(),start=start_identity(os.getpid())),phase='watching',pending=None,last=None,dropped=[],quiet=None,closure=None,partialClosure=None,transitions=[],primaryCue=None)
            need(self.state['process']!=f.state['hostProcess']);self.save()
        else:
            exact(self.previous,{'snapshotsActorVersion','runId','binding','payload'})
            version=self.previous['snapshotsActorVersion']
            need(type(version) is int and version in (1,2,ACTOR_VERSION)
                and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
            rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
            exact(self.state,actor_fields(version))
            # Exact legacy shapes preserve every pending/receipt/quiet field.
            # Neither an old transition nor a consumed Primary cue is inferred.
            if version==1:self.state['transitions']=[]
            if version<3:self.state['primaryCue']=None
            if self.state['primaryCue'] is not None:cue_state(f,self.state['primaryCue'])
            need(self.state['process']==dict(pid=os.getpid(),start=start_identity(os.getpid())) and self.state['phase'] in ('watching','retired')
                and type(self.state['dropped']) is list and len(self.state['dropped'])<=256)
            if self.state['partialClosure'] is not None:
                need(self.state['phase']=='retired' and self.state['pending'] is self.state['last'] is self.state['quiet'] is None
                    and self.state['closure'] is not None and self.state['closure']['active'] is False)
            validate_transition_history(f,self.state,expected_actor=self.previous)

    def primary_owner(self):
        if self._ordinary_primary is not None:
            store=PrivateFeatureState(self.feature.store.path.with_name('phone-snapshots-primary-originals.json'))
            need(same(store.read(),self._ordinary_primary))

    def save(self):
        # Enrolled cleanup must not adopt lifecycle/quiet edits made by a
        # current guard callback. Pin the intended DTO before that callback.
        stages=self.feature.state.get('cleanupStages',{})
        desired=graph_digest(self.state) if type(stages) is dict and 'readReadyMode' in stages else None
        self.feature.bound();self.primary_owner();self.ordinary_publication();self.cleanup_publication();self.read_ready_mode();need(same(self.store.read(),self.previous))
        if desired is not None:need(graph_digest(self.state)==desired)
        value=dict(snapshotsActorVersion=ACTOR_VERSION,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.primary_owner();self.previous=deepcopy(value)

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
            self.discard_cleanup_history()
            if self._cleanup_entered:
                self._cleanup_reader=None
                if self._cleanup_started:self._cleanup_failed=True
            raise
        except Exception:
            self.discard_cleanup_history()
            self._cleanup_reader=None
            if self._cleanup_started:self._cleanup_failed=True
            elif self._ordinary_entered:self._ordinary_failed=True
            raise
        finally:self._ordinary_primary=None;self._ordinary_publication=None;self._cleanup_publication=None

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

    def read_ready_mode(self):
        """A versioned owner marker enrolls cleanup, never a target fact."""
        f=self.feature;stages=f.state.get('cleanupStages',{});need(type(stages) is dict)
        if f.previous is not None:
            original=unpack(f.previous['payload']);need(len(original)==1)
            owned=original[0].get('cleanupStages',{});need(type(owned) is dict)
            need(('readReadyMode' in stages)==('readReadyMode' in owned))
            if 'readReadyMode' in stages:need(same(stages['readReadyMode'],owned['readReadyMode']))
        if 'readReadyMode' not in stages:return None
        return validate_read_ready_mode(stages['readReadyMode'],actor_process=self.state['process'])

    def read_ready_cue(self,header,frame,historical,*,status=None):
        f=self.feature;mode=self.read_ready_mode();need(mode is not None)
        validate_read_ready_slot(frame,f.run,phase=status,actor_process=self.state['process'])
        validate_read_ready_slot_owner(f,header,frame,historical)
        need(frame['readReadySlot']['featureOwnerSha256']==digest(f.previous))
        return frame['readReadySlot']

    def cleanup_maintenance(self,status):
        """Permit unpublished reads only after a consumed slot's real successor."""
        f=self.feature;f.lock.assert_held()
        if self.read_ready_mode() is None or self.state['last'] is None:return None
        last=self.state['last'];sample=last['original']['sample'];ticket=status['activations'][-1]['ticket']
        if sample['ticket']!=ticket:return None
        need(self.state['pending'] is None and last['original']['issued'] is True
            and same({key:last['receipt'][key] for key in sample},sample))
        cue=self.state['primaryCue'];need(cue is not None)
        store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
        header=store.read();state=role_state(header,f.binding,f.run,'primary');actor_header=deepcopy(self.previous)
        def historical():
            f.lock.assert_held();f.header_authority()
            need(same(self.store.read(),actor_header) and same(store.read(),header));return True
        validate_primary_cue(f,cue,header,history_guard=historical)
        old=cue_state(f,cue)
        if state['phase']!='ready' or state['pending'] is not None or state['sequence']<=old['sequence']:return None
        host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',historical,lambda *_:need(False),kind='snapshots')
        previous=primary_manifests(host,old);need(previous)
        self.read_ready_cue(cue['header'],host.read(host.expand(previous[-1])),historical,status=status)
        entries=primary_manifests(host,state);need(entries)
        frame=host.read(host.expand(entries[-1]))
        if 'diagnostic' in frame or 'readReadySlot' in frame or type(frame.get('measurement')) is not dict:return None
        before,after=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(before,run=f.run,area='snapshots',request=before['requestId'],epoch=before['capturedEpochMs'])
        phase_packet(after,run=f.run,area='snapshots',request=after['requestId'],epoch=after['capturedEpochMs'],previous=before)
        need(before['active'] and after['active'] and before['activations'] and frame['ticket']==ticket
            and before['activations'][-1]['ticket']==ticket and before['activations'][-1]['stimulus']['verb']=='cleanup')
        for packet in (before,after):
            for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations','active'):
                need(same(packet[key],status[key]))
        need(f.bound() is True and historical() is True)
        return deepcopy(header)

    def primary_continuity(self,status=None):
        """A saved publication may resume, but cannot forget its known owner."""
        f=self.feature;cue=self.state['primaryCue']
        if cue is None:return
        store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
        header=store.read();actor_header=deepcopy(self.previous)
        def historical():
            f.lock.assert_held();f.header_authority()
            need(same(self.store.read(),actor_header) and same(store.read(),header));return True
        validate_primary_cue(f,cue,header,history_guard=historical)
        mode=self.read_ready_mode()
        if mode is not None and self.state['pending'] is not None:
            current=f.phase.status() if status is None else status
            # An earlier ordinary pending sample may only be dropped by the
            # existing stale-ticket path. Current cleanup delivery needs the
            # original read-ready slot, including after an accepted lost POST.
            if self.state['pending']['sample']['ticket']==current['activations'][-1]['ticket']:
                host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',historical,lambda *_:need(False),kind='snapshots')
                entries=primary_manifests(host,cue_state(f,cue));need(entries)
                self.read_ready_cue(cue['header'],host.read(host.expand(entries[-1])),historical,status=current)
        self._ordinary_primary=deepcopy(header);self.primary_owner()

    def primary_cue(self,status):
        """Permit ordinary acquisition only after a real Primary advance."""
        f=self.feature;f.lock.assert_held()
        store=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
        header=store.read();previous=self.state['primaryCue']
        if header is None:
            need(self.read_ready_mode() is None)
            need(previous is None
                and not any(f.root.glob('emote-frame-snapshots-'+f.run+'-primary-*.json'))
                and not any(f.root.glob('emote-index-snapshots-'+f.run+'-primary-*.json'))
                and not any(f.root.glob('snapshots-'+f.run+'-primary-*.png'))
                and not any(f.root.glob('snapshots-file-'+f.run+'-primary-*.bin'))
                and not any(f.root.glob('snapshots-primary-transfer-*'))
                and not os.path.lexists(f.root/'phone-snapshots-primary-files-observer.json'))
            return None
        state=role_state(header,f.binding,f.run,'primary');need(state['phase'] in ('ready','reading'))
        actor_header=deepcopy(self.previous)
        def historical():
            f.lock.assert_held();f.header_authority()
            need(same(self.store.read(),actor_header) and same(store.read(),header));return True
        validate_primary_cue(f,previous,header,history_guard=historical)
        if state['phase']!='ready' or state['pending'] is not None or state['sequence']==0:return None
        if previous is not None and state['sequence']==cue_state(f,previous)['sequence']:
            need(same(header,previous['header']));return None
        host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',historical,lambda *_:need(False),kind='snapshots')
        entries=primary_manifests(host,state);need(entries)
        frame=host.read(host.expand(entries[-1]))
        mode=self.read_ready_mode()
        if mode is not None:
            need(status['active'] and status['activations'][-1]['stimulus']['verb']=='cleanup')
            # Once enrolled, a normal cleanup measurement or unrelated partial
            # frame can never publish before the Primary's completed slot.
            if 'readReadySlot' not in frame:return None
            slot=self.read_ready_cue(header,frame,historical,status=status)
            if previous is not None:
                old_entries=primary_manifests(host,cue_state(f,previous));need(old_entries)
                old=host.read(host.expand(old_entries[-1]))
                if 'readReadySlot' in old:
                    validate_read_ready_slot(old,f.run,actor_process=self.state['process'])
                    need(old['readReadySlot']['slotId']!=slot['slotId'])
            need(f.bound() is True and historical() is True)
            return dict(snapshotPrimaryCueVersion=1,header=deepcopy(header))
        if frame.get('diagnostic') is True:return None
        need(type(frame.get('measurement')) is dict)
        before,after=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(before,run=f.run,area='snapshots',request=before['requestId'],epoch=before['capturedEpochMs'])
        phase_packet(after,run=f.run,area='snapshots',request=after['requestId'],epoch=after['capturedEpochMs'],previous=before)
        need(before['active'] and after['active'] and before['activations']
            and same(before['activations'],after['activations']) and frame['ticket']==before['activations'][-1]['ticket'])
        if frame['ticket']!=status['activations'][-1]['ticket']:return None
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations','active'):
            need(same(after[key],status[key]))
        need(f.bound() is True and historical() is True)
        return dict(snapshotPrimaryCueVersion=1,header=deepcopy(header))

    def ordinary_pin(self,cue):
        f=self.feature;scope=getattr(f.adapter,'_existing_input_scope',None)
        self._ordinary_primary=deepcopy(cue['header']);self.primary_owner()
        return dict(primary=deepcopy(cue['header']),feature=deepcopy(f.previous),actor=deepcopy(self.previous),binding=deepcopy(f.binding),
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
        f.bound();role.bound();role.history_authority();self.primary_owner()
        need(same(self._ordinary_primary,pin['primary']))

    def ordinary_prepare(self,role,status,cue,pin):
        """Seal only preparation; no current sample survives the lock gap."""
        self.ordinary_owners(role,pin)
        need(role.state['phase']=='ready' and role.state['pending'] is None and not role._host_publication)
        f=self.feature
        passive=(SnapshotConstructorHistoryPass._system_snapshot(passive_scope(f))
            if role.system and f.state['phase'] in ('baseline','active') and f.state.get('current',False) is None
            and f.state['handoff'] is not None else None)
        prepared=dict(passive=passive,pin=pin,phase=deepcopy(status),cue=deepcopy(cue),role=deepcopy(role.previous),
            roleState=digest(role.state),frames=graph_digest(role.frames),count=len(role.frames),
            featureState=digest(self.feature.state),actorState=digest(self.state),configuration=deepcopy(self.feature.config))
        self.ordinary_prepared_owners(role,prepared);return prepared

    def ordinary_passive_owners(self,role,prepared):
        if prepared['passive'] is not None:
            need(role.system is True and passive_scope(self.feature) is prepared['pin']['system'])
            SnapshotConstructorHistoryPass._system_matches(prepared['pin']['system'],prepared['passive'])
            prepared['passive']['clock']=prepared['pin']['system'].last_clock

    def ordinary_prepared_owners(self,role,prepared,*,feature_header=True,verify_graph=True):
        """Pure owner/graph checks before a current target guard can run."""
        f=self.feature;f.lock.assert_held();pin=prepared['pin'];self.ordinary_passive_owners(role,prepared)
        need(same(f.previous,pin['feature']) and same(self.previous,pin['actor'])
            and same(self.store.read(),pin['actor']) and same(role.previous,prepared['role'])
            and same(role.store.read(),prepared['role']) and same(f.binding,pin['binding'])
            and same(self.state['process'],pin['process']) and same(f.config,prepared['configuration'])
            and getattr(f,'guard',None) is pin['guard'] and getattr(f,'_system_scope',None) is pin['system']
            and getattr(f.adapter,'_existing_input_scope',None) is pin['sdk']
            and same(getattr(f.adapter,'_existing_input_scope',None),pin['sdkValue'])
            and same(self._ordinary_primary,pin['primary']) and digest(f.state)==prepared['featureState']
            and digest(self.state)==prepared['actorState'] and digest(role.state)==prepared['roleState']
            and len(role.frames)==prepared['count'] and not role._host_publication)
        if verify_graph:need(graph_digest(role.frames)==prepared['frames'])
        actual=f.store.read()
        if feature_header:need(same(actual,pin['feature']))
        else:
            # A new ordinary activation may precede its normal Primary input.
            # Never adopt that input or its new SDK/OS scope on this reader.
            need(actual is not None and set(actual)==set(pin['feature'])
                and same({key:value for key,value in actual.items() if key!='payload'},
                {key:value for key,value in pin['feature'].items() if key!='payload'}))
        return True

    def ordinary_prepared_advance(self,role,prepared,status):
        """Discard preparation for one actual new activation, without facts."""
        f=self.feature;before=prepared['phase'];confirmed=f.phase.status(status)
        previous=None
        for packet in (before,status,confirmed):
            phase_packet(packet,run=f.run,area='snapshots',request=packet['requestId'],epoch=packet['capturedEpochMs'],previous=previous)
            need(packet['active'] and packet['activations']);previous=packet
        old,new=before['activations'],status['activations']
        need(len(new)==len(old)+1 and same(new[:-1],old) and same(new,confirmed['activations'])
            and old[-1]['stimulus']['verb']!='cleanup' and new[-1]['stimulus']['verb']!='baseline')
        self.ordinary_prepared_owners(role,prepared,feature_header=False)
        primary=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
        header=primary.read()
        def historical():
            self.ordinary_prepared_owners(role,prepared,feature_header=False,verify_graph=False)
            need(same(primary.read(),header));return True
        # This is only a known immutable scheduling floor. A changed scope
        # cannot perform a native query on behalf of the abandoned reader.
        validate_primary_cue(f,prepared['cue'],header,history_guard=historical,current_guard=historical)
        historical();self.ordinary_prepared_owners(role,prepared,feature_header=False);return False

    def ordinary_batch(self,role,prepared):
        f=self.feature
        with f.lock.held():
            self.ordinary_prepared_owners(role,prepared,feature_header=False)
            status=f.phase.status(prepared['phase'])
            if not same(status['activations'],prepared['phase']['activations']):
                return self.ordinary_prepared_advance(role,prepared,status)
            need(status['active'] and prepared['phase']['active'])
            self.ordinary_prepared_owners(role,prepared)
            # Requalify the actually prepared candidate, including a legitimate
            # newer ready Primary frame. An unfinished Primary read only waits.
            primary=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
            header=primary.read()
            def historical():
                self.ordinary_prepared_owners(role,prepared,verify_graph=False)
                need(same(primary.read(),header));return True
            validate_primary_cue(f,prepared['cue'],header,history_guard=historical)
            cue=self.primary_cue(status)
            if cue is None:
                historical();self.ordinary_prepared_owners(role,prepared);return False
            self._ordinary_primary=deepcopy(cue['header']);prepared['pin']['primary']=deepcopy(cue['header'])
            self.ordinary_prepared_owners(role,prepared)
            need(same(role.restore_originals(),role.frames))
            self.ordinary_prepared_owners(role,prepared)
            after=f.phase.status(status)
            if not same(after['activations'],status['activations']):
                return self.ordinary_prepared_advance(role,prepared,after)
            need(after['active']);status=after
            self.ordinary_owners(role,prepared['pin'])
            self.ordinary_prepared_owners(role,prepared)
            current=status['activations'][-1]
            try:measured=role.read(role.state['sequence'],phase_admission=lambda reader,phase:self.ordinary_admission(reader,status,prepared['pin'],phase))
            except SnapshotPhaseDeferred:return self.ordinary_transition(role,status,prepared['pin'],kind='before-sources')
            except SnapshotPending:return False
            self.ordinary_owners(role,prepared['pin'])
            # A late current-reader callback must not mutate any old original
            # graph before the new own sample and scheduling cue are committed.
            need(len(role.frames)==prepared['count']+1 and graph_digest(role.frames[:prepared['count']])==prepared['frames']
                and digest(f.state)==prepared['featureState'] and digest(self.state)==prepared['actorState']
                and same(f.config,prepared['configuration'])
                and same(role.state,role_state(role.previous,f.binding,f.run,'actor')))
            if role.frames[-1]['ticket']!=current['ticket']:
                return self.ordinary_transition(role,status,prepared['pin'])
            self._ordinary_publication=(role,prepared,deepcopy(role.previous))
            sample=dict(ticket=current['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['snapshots']})
            self.state.update(primaryCue=cue,pending=dict(sample=sample,issued=False));self.save();self.deliver();return False

    def ordinary_publication(self):
        """Check the old graph after the last save guard, before its CAS."""
        context=self._ordinary_publication
        if context is None:return
        role,prepared,header=context;f=self.feature;pin=prepared['pin'];f.lock.assert_held()
        self.ordinary_passive_owners(role,prepared)
        need(same(f.previous,pin['feature']) and same(f.store.read(),pin['feature'])
            and same(role.previous,header) and same(role.store.read(),header)
            and same(role.state,role_state(header,f.binding,f.run,'actor'))
            and same(f.binding,pin['binding']) and same(f.config,prepared['configuration'])
            and digest(f.state)==prepared['featureState'] and same(self.state['process'],pin['process'])
            and getattr(f,'guard',None) is pin['guard'] and getattr(f,'_system_scope',None) is pin['system']
            and getattr(f.adapter,'_existing_input_scope',None) is pin['sdk']
            and same(getattr(f.adapter,'_existing_input_scope',None),pin['sdkValue'])
            and len(role.frames)==prepared['count']+1 and graph_digest(role.frames[:prepared['count']])==prepared['frames'])

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
        self.discard_cleanup_history()
        self._cleanup_reader=(role,self.cleanup_anchor(role,phase))
        if self.read_ready_mode() is not None:
            # Prepare under this turn's existing lock, after our known saves.
            # The next full host replay can overlap the Primary's slot lock.
            self._cleanup_history=SnapshotActorHistoryPass(self,role,self._cleanup_reader[1])

    def discard_cleanup_history(self):
        if self._cleanup_history is not None:self._cleanup_history.close()
        self._cleanup_history=None

    def retained_cleanup_step(self,history):
        f=self.feature;role=history.role;prepared=history.prepared
        try:
            # No lock acquisition or native query precedes this actual replay.
            history.read()
            with f.lock.held():
                status=history.finish()
                if not status['active']:return self.defer_cleanup_close(role,status,prepared['phase'])
                warm=self.cleanup_warm_pin(role,prepared,None)
                warm.update(guard=getattr(f,'guard',None),system=getattr(f,'_system_scope',None),history=history)
                return self.quiet_batch(role,prepared,f.monotonic(),warm=warm,history=history)
        finally:history.close()

    def step_owned(self):
        f=self.feature
        if self._cleanup_history is not None:
            history=self._cleanup_history;self._cleanup_history=None
            self._cleanup_entered=True;self._cleanup_started=True
            return self.retained_cleanup_step(history)
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
            status=f.phase.status(self.state['closure']);mode=self.read_ready_mode()
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
                # A finished interval still needs a new own acquisition.
                # Release preparation so a waiting Primary can replay its
                # immutable history before this actor captures the next fact.
                published=(mode is not None and self.state['last'] is not None
                    and self.state['last']['original']['sample']['ticket']==status['activations'][-1]['ticket'])
                cue=self.primary_cue(status) if published or self.state['quiet'] is not None and self.state['quiet']['complete'] else None
                if published and cue is None and self.cleanup_maintenance(status) is None:
                    # Do not seize the source lock for another measurement
                    # while the Primary is still consuming our exact receipt.
                    self.retain_cleanup(retained[0],status);return False
                if cue is None:return self.quiet_batch(retained[0],retained[1],started)
                role,prepared=retained;verb='cleanup'
                warm=self.cleanup_warm_pin(role,prepared,cue)
            else:
                warm=None
                need(self.state['phase']=='watching')
                if self.state['pending'] is not None:
                    self.primary_continuity(status);self.deliver();return False
                if f.state['phase'] not in ('baseline','active','cleaned'):return False
                current=status['activations'][-1];verb=current['stimulus']['verb']
                if verb=='baseline' and f.state['phase']!='baseline':return False
                if verb not in ('baseline','cleanup') and (not f.state['actions'] or f.state['actions'][-1]['ticket']!=current['ticket'] or f.state['actions'][-1]['phase']!='acknowledged'):return False
                if verb=='cleanup' and f.state['phase']!='cleaned':return False
                if verb!='cleanup' and f.state['phase']=='cleaned':return False
                if verb=='cleanup':self._cleanup_started=True
                if (verb=='cleanup' and mode is not None and self.state['last'] is not None
                        and self.state['last']['original']['sample']['ticket']==current['ticket']
                        and self.primary_cue(status) is None and self.cleanup_maintenance(status) is None):return False
                self._ordinary_entered=verb!='cleanup'
                cue=None if verb=='cleanup' else self.primary_cue(status)
                if verb!='cleanup' and cue is None:return False
                ordinary=None if verb=='cleanup' else self.ordinary_pin(cue)
                role=PhoneSnapshotsRole(f,'actor',**({} if anchor is None else {'expected_previous':anchor[1]['role']}))
                if anchor is not None:need(same(role.previous,anchor[1]['role']))
                if role.state['phase']=='reading':role.recover()
                if verb=='cleanup':
                    need(same(f.store.read(),f.previous))
                    prepared=dict(feature=deepcopy(f.previous),actor=deepcopy(self.previous),role=deepcopy(role.previous),
                        binding=deepcopy(f.binding),phase=deepcopy(status))
                else:
                    prepared=self.ordinary_prepare(role,status,cue,ordinary)
                    # Overlap only the exact foreground or passive scope
                    # admitted by the Primary constructor-history pass. A
                    # pending input retains the original continuous lock.
                    foreground=(f.state['handoff'] is None and not role.system and getattr(f,'_system_scope',None) is None)
                    split=(f.state['phase'] in ('baseline','active') and f.state.get('current',False) is None
                        and (foreground or prepared['passive'] is not None))
                    if not split:return self.ordinary_batch(role,prepared)
        # Preparation may replay a long immutable history. Release its lock
        # before the bounded current quiet interval so another role can run.
        # No measurement or publication authority survives this boundary.
        f.sleep(.1)
        if verb!='cleanup':return self.ordinary_batch(role,prepared)
        return self.cleanup_batch(role,prepared,warm=warm)

    def cleanup_warm_pin(self,role,prepared,cue):
        f=self.feature;f.lock.assert_held();self.cleanup_owners(role,prepared,loaded=True)
        scope=getattr(f.adapter,'_existing_input_scope',None)
        warm=dict(cue=deepcopy(cue),featureState=digest(f.state),actorState=digest(self.state),
            roleState=deepcopy(role.state),frames=graph_digest(role.frames),count=len(role.frames),configuration=deepcopy(f.config),
            sdk=scope,sdkValue=deepcopy(scope))
        self.cleanup_warm_owners(role,prepared,warm);return warm

    def cleanup_warm_owners(self,role,prepared,warm,*,verify_graph=True):
        """Same-call preparation only; no current fact survives the yield."""
        f=self.feature;f.lock.assert_held();self.cleanup_owners(role,prepared);self.cleanup_owners(role,prepared,loaded=True)
        need(same(role.state,warm['roleState'])
            and same(role.state,role_state(prepared['role'],f.binding,f.run,'actor'))
            and same(self.state,unpack(prepared['actor']['payload'])[0])
            and same(f.state,unpack(prepared['feature']['payload'])[0])
            and digest(f.state)==warm['featureState'] and digest(self.state)==warm['actorState']
            and same(f.config,warm['configuration']) and not role._host_publication
            and getattr(f.adapter,'_existing_input_scope',None) is warm['sdk']
            and same(getattr(f.adapter,'_existing_input_scope',None),warm['sdkValue']))
        if 'guard' in warm:
            need(getattr(f,'guard',None) is warm['guard'] and getattr(f,'_system_scope',None) is warm['system'])
        if verify_graph:need(graph_digest(role.frames)==warm['frames'])
        return True

    def cleanup_publication(self):
        """Preserve the old graph through the last actual Actor save guard."""
        if self._cleanup_publication is None:return
        role,prepared,warm,header=self._cleanup_publication;f=self.feature;f.lock.assert_held()
        need(same(f.previous,prepared['feature']) and same(f.store.read(),prepared['feature'])
            and same(f.state,unpack(prepared['feature']['payload'])[0])
            and same(role.previous,header) and same(role.store.read(),header)
            and same(role.state,role_state(header,f.binding,f.run,'actor'))
            and same(f.binding,prepared['binding']) and same(f.config,warm['configuration'])
            and same(self.state['process'],unpack(prepared['actor']['payload'])[0]['process'])
            and getattr(f,'guard',None) is warm['guard'] and getattr(f,'_system_scope',None) is warm['system']
            and getattr(f.adapter,'_existing_input_scope',None) is warm['sdk']
            and same(getattr(f.adapter,'_existing_input_scope',None),warm['sdkValue'])
            and len(role.frames)>warm['count']
            and graph_digest(role.frames[:warm['count']])==warm['frames'])
        if 'history' in warm:warm['history']._verify_files()

    def cleanup_batch(self,role,prepared,*,warm=None):
        f=self.feature
        with f.lock.held():
            started=f.monotonic()
            # Pin all three actual owners before loading any changed state.
            self.cleanup_owners(role,prepared)
            if warm is not None:self.cleanup_warm_owners(role,prepared,warm)
            f.load();self.load();self.cleanup_owners(role,prepared,loaded=True)
            if warm is not None:
                self.cleanup_warm_owners(role,prepared,warm)
                # load() legitimately rebuilds its foreground guard once.
                # Its newly qualified scope must then survive every callback.
                warm.update(guard=getattr(f,'guard',None),system=getattr(f,'_system_scope',None))
            f.bound();role.bound();role.history_authority()
            need(f.state['phase']=='cleaned' and self.state['phase']=='watching' and self.state['pending'] is None
                and self.state['closure'] is None and self.state['partialClosure'] is None)
            status=f.phase.status()
            if not status['active']:return self.defer_cleanup_close(role,status,prepared['phase'])
            self.cleanup_phase(status,prepared['phase'])
            if warm is not None:
                primary=PrivateFeatureState(f.store.path.with_name('phone-snapshots-primary-originals.json'))
                header=primary.read()
                def historical():
                    self.cleanup_warm_owners(role,prepared,warm,verify_graph=False)
                    need(same(primary.read(),header));return True
                # Candidate N was actually observed before the gap. It may
                # advance, but cannot disappear or roll back to consumed N-1.
                validate_primary_cue(f,warm['cue'],header,history_guard=historical)
                self.cleanup_warm_owners(role,prepared,warm)
            if warm is None:return self.quiet_batch(role,prepared,started)
            return self.quiet_batch(role,prepared,started,warm=warm)

    def defer_cleanup_close(self,role,status,prepared):
        """A completed own quiet receipt may close between fresh phase reads.

        This does not establish new closure authority or publish a sample. The
        following normal step still acquires its full closed-phase proof.
        """
        need(not status['active'] and prepared['active'] and number(status['retiredEpochMs'],1)
            and self.state['phase']=='watching' and self.state['pending'] is None
            and self.state['closure'] is None and self.state['partialClosure'] is None
            and self.state['quiet'] is not None and self.state['quiet']['complete'] is True)
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','activations'):
            need(same(status[key],prepared[key]))
        need(prepared['activations'] and prepared['activations'][-1]['stimulus']['verb']=='cleanup')
        durable=unpack(self.previous['payload']);need(len(durable)==1
            and same(durable[0]['quiet'],self.state['quiet']) and same(durable[0]['last'],self.state['last']))
        last=self.state['last'];need(last is not None and last['original']['issued'] is True)
        sample=last['original']['sample'];receipt=last['receipt']
        need(sample['ticket']==prepared['activations'][-1]['ticket']
            and same({key:receipt[key] for key in sample},sample)
            and integer(receipt['sequence'],1) and number(receipt['receivedEpochMs'],1))
        need((role.state['phase']=='ready' and role.state['pending'] is None)
            or (role.state['phase']=='reading' and type(role.state['pending']) is dict))
        pin=dict(feature=deepcopy(self.feature.previous),actor=deepcopy(self.previous),role=deepcopy(role.previous),
            binding=deepcopy(self.feature.binding),phase=deepcopy(prepared))
        self.cleanup_owners(role,pin)
        # A partial read remains an actual owned recovery obligation. The
        # ordinary closed branch reconstructs and recovers it before proving
        # fresh absence; no warmed reader or old role header is reused.
        self._cleanup_reader=None;self._cleanup_anchor=(role.store,pin);return False

    def quiet_batch(self,role,prepared,started,*,warm=None,history=None):
        f=self.feature;publication_warm=warm
        while True:
            f.bound();role.history_authority()
            # Reuse only normal reader continuity. Every old file still
            # passes its complete original inode/byte/hash validation.
            if history is None:need(same(role.restore_originals(),role.frames))
            else:history.check()
            status=f.phase.status()
            if not status['active']:return self.defer_cleanup_close(role,status,prepared['phase'])
            self.cleanup_phase(status,prepared['phase'])
            cue=None;maintenance=None
            published=(self.read_ready_mode() is not None and self.state['last'] is not None
                and self.state['last']['original']['sample']['ticket']==status['activations'][-1]['ticket'])
            if published:
                cue=self.primary_cue(status)
                if cue is None:maintenance=self.cleanup_maintenance(status)
                if cue is None and maintenance is None:
                    self.retain_cleanup(role,status);return False
            elif self.state['quiet'] is not None and self.state['quiet']['complete']:
                # A completed interval cannot create an unconsumed backlog.
                # The Primary header is scheduling authority only; the next
                # fact still comes from a new full independent acquisition.
                cue=self.primary_cue(status)
                if cue is None:
                    self.retain_cleanup(role,status);return False
            if maintenance is not None:
                self._ordinary_primary=deepcopy(maintenance);self.primary_owner()
            elif cue is not None:
                self._ordinary_primary=deepcopy(cue['header']);self.primary_owner()
            if warm is not None:self.cleanup_warm_owners(role,prepared,warm)
            if history is not None:history.check()
            try:measured=role.read(role.state['sequence'])
            except SnapshotPending:
                after=f.phase.status(status)
                if not after['active']:return self.defer_cleanup_close(role,after,prepared['phase'])
                self._cleanup_reader=None;self.cleanup_anchor(role,status);return False
            except Exception:
                after=f.phase.status(status)
                if after['active']:raise
                return self.defer_cleanup_close(role,after,prepared['phase'])
            if publication_warm is not None:
                self._cleanup_publication=(role,prepared,publication_warm,deepcopy(role.previous))
            warm=None # The old role state changed, but its graph prefix remains pinned.
            need(measured['resources']==[] and role.frames[-1]['ticket']==status['activations'][-1]['ticket'])
            after=role.frames[-1]['phaseAfter']
            if not after['active']:return self.defer_cleanup_close(role,after,prepared['phase'])
            proof=f.restored(snapshot=role.frames[-1]);now=f.monotonic()
            if history is not None:history.actor_unchanged();history._verify_files()
            quiet=quiet_window(self.state['quiet'],now,measured['sequence']);quiet['final']=proof;self.state['quiet']=quiet
            self.save()
            if maintenance is not None:
                # One genuinely new quiet sample, never a publication. Yield
                # even after a real gap reset; no cached fact satisfies a slot.
                self.retain_cleanup(role,status);return False
            if quiet['complete']:
                if cue is None:cue=self.primary_cue(status)
                if cue is None:
                    self.retain_cleanup(role,status);return False
                self._ordinary_primary=deepcopy(cue['header']);self.primary_owner()
                sample=dict(ticket=status['activations'][-1]['ticket'],actor='owned-observer',actorSequence=measured['sequence'],capturedEpochMs=measured['capturedEpochMs'],
                    facts={key:deepcopy(measured['state'][key]) for key in WITNESS_KEYS['snapshots']})
                self.state.update(primaryCue=cue,pending=dict(sample=sample,issued=False));self.save();self.deliver()
                self.retain_cleanup(role,status);return False
            # Enrolled cleanup yields after each genuine sample so the next
            # retained history replay can overlap another role's lock turn.
            # Legacy cleanup keeps its original four-second scheduling slice.
            if self.read_ready_mode() is not None or f.monotonic()-started>=4.0:
                self.retain_cleanup(role,status);return False
            f.sleep(.1)

    @staticmethod
    def cleanup_phase(status,prepared):
        need(status['active'] and prepared['active'] and status['activations']
            and status['activations'][-1]['stimulus']['verb']=='cleanup')
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations'):
            need(same(status[key],prepared[key]))
