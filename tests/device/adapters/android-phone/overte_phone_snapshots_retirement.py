"""Original-bound Snapshots journal retirement after actual actor process exit.

The final immutable archive retains every child header and original reference.
Missing controls alone are never evidence of restored product state or actor exit.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import os
import re

from adapters.native_feature_observation import exact,need,number,integer
from adapters.normal_feature_state import PrivateFeatureState
from fixture.messages_mixer import start_identity
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_snapshots_evidence import SnapshotsOriginals,SnapshotsImages,SnapshotsBinary
from overte_phone_script_history import pack,unpack,same,canonical
import hashlib
from overte_phone_snapshots_measurements import provider_quiet

NAMES=tuple('phone-snapshots-'+name+'.json' for name in ('feature','primary-originals','actor-originals','actor-lifecycle',
    'files-owner','primary-files-observer','actor-files-observer'))


def terminated(process):
    exact(process,{'pid','start'});need(type(process['pid']) is int and process['pid']>0 and type(process['start']) is str and process['start'].isdecimal())
    path=Path('/proc')/str(process['pid'])/'stat'
    try:fields=path.read_text().rsplit(')',1)[1].split()
    except FileNotFoundError:return True
    need(len(fields)>19 and fields[19].isdecimal())
    return fields[19]!=process['start'] or fields[0] in ('Z','X')


def completed_archive(root,binding,run,guard):
    """Find only this run's one immutable final receipt; no absent-owner ACK."""
    reader=SnapshotsOriginals(root,binding,run,'primary',guard,lambda *_:need(False),kind='snapshots-retirement')
    prefix='emote-frame-snapshots-retirement-'+run+'-primary-0001-'
    paths=list(Path(root).glob(prefix+'*.json'));need(len(paths)==1)
    path=paths[0];digest=path.name[len(prefix):-5];need(re.fullmatch('[0-9a-f]{64}',digest) is not None)
    info=path.lstat();value=dict(emoteOriginalVersion=1,kind='snapshots-retirement',binding=deepcopy(binding),runId=run,role='primary',index=1,
        sha256=digest,bytes=info.st_size,phase='saved',file=dict(device=info.st_dev,inode=info.st_ino))
    return reader.read(value)


class PhoneSnapshotsRetirement:
    def __init__(self,feature):
        self.feature=feature;self.store=PrivateFeatureState(feature.store.path.with_name('phone-snapshots-retirement.json'))
        self.previous=self.state=None
        self.originals=SnapshotsOriginals(feature.root,feature.binding,feature.run,'primary',self.bound,self.intent,kind='snapshots-retirement')

    def bound(self):
        f=self.feature;f.lock.assert_held();need(f.guard() is not False and same(self.store.read(),self.previous))
        owner=PrivateFeatureState(f.store.path).read()
        need(self.state is None or same(owner,self.state['owner']) or self.state['phase']=='retiring' and owner is None)
        return True

    def save(self):
        self.bound();value=dict(snapshotsRetirementVersion=1,runId=self.feature.run,binding=self.feature.binding,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def intent(self,kind,value):
        need(kind=='original' and self.state['phase']=='archiving');self.state['original']=deepcopy(value);self.save();return True

    def validate_archive(self,archive):
        f=self.feature;self.bound();exact(archive,{'owner','controls','proof','closure'})
        # Only this invocation's verified owner headers authorize historical
        # host IO. Current native authority brackets the complete pass.
        feature_header=deepcopy(f.previous);retirement_header=deepcopy(self.previous)
        binding=deepcopy(f.binding);config=deepcopy(f.config)
        archive_sha=hashlib.sha256(canonical(archive)).hexdigest()
        need(type(archive['controls']) is dict and set(archive['controls'])==set(NAMES))
        controls={name:PrivateFeatureState(f.store.path.with_name(name)).read() for name in NAMES}
        resumed=self.state is not None and self.state['phase']=='retiring' and same(self.state['archive'],archive)
        completed=self.state is None and self.previous is None and f.previous is None
        for name,actual in controls.items():
            need(same(actual,archive['controls'][name]) or actual is None and (resumed or completed))
        def history_guard():
            f.lock.assert_held()
            need(same(f.previous,feature_header) and same(self.previous,retirement_header)
                and same(f.store.read(),feature_header) and same(self.store.read(),retirement_header)
                and same(f.binding,binding) and same(f.config,config))
            for name,expected in controls.items():
                need(same(PrivateFeatureState(f.store.path.with_name(name)).read(),expected))
            return True
        history_guard()
        provider=archive['proof']['provider'];provider_quiet(provider,run=f.run,epoch=provider['capturedEpochMs'],closed=True)
        need(archive['owner']['runId']==f.run and same(archive['owner']['binding'],f.binding) and not archive['closure']['active'])
        need(set(archive['controls'])==set(NAMES) and same(archive['controls']['phone-snapshots-feature.json'],archive['owner']))
        owner=unpack(archive['owner']['payload'])[0]
        partial=owner['partial']
        need(owner['phase']==('partial-cleaned' if partial else 'cleaned') and owner['current'] is None and owner['inputStorage'] is None and owner['handoff'] is None
            and not any(owner['leases'].values()) and (not owner['inputs'] if partial and owner['settingsIntent'] is None else len(owner['quiet'])==2))
        inputs=SnapshotsOriginals(f.root,f.binding,f.run,'primary',history_guard,lambda *_:need(False),kind='snapshots-input').restore(owner['inputs'],owner['inputSequence'])
        if not partial:need(inputs and inputs[owner['settingsIndex']-1]['snapshotsSettingsCaptured']['runId']==f.run)
        if partial:
            need(not owner['actions'] and not owner['cancelJobs'] and not owner['handoffs'] and owner['marker'] is None
                and archive['proof']['snapshotPartialRetirementVersion']==1 and same(archive['proof']['owner'],archive['owner']))
        for job in owner['cancelJobs']:
            need(job['sourceIndex'] and job['retirementIndex'])
            initial=inputs[job['sourceIndex']-1]['snapshotCancel'];last=inputs[job['retirementIndex']-1]['snapshotCancelRetired']
            need(initial['source']['job']==last['source']['job']==job['id'] and initial['source']['phase']==last['source']['phase']=='complete'
                and last['source']['retired'] and not last['source']['timerActive'])
        for handoff in owner['handoffs']:
            f.check_handoff({key:value for key,value in handoff.items() if key!='retirementIndex'},inputs)
            last=inputs[handoff['retirementIndex']-1]['handoffEnd']
            need(last['handoffId']==handoff['id'] and last['source']['retired'] and not last['source']['timerActive'])
        role_frames={}
        for role in ('primary','actor'):
            header=archive['controls']['phone-snapshots-'+role+'-originals.json']
            if partial:need(header is None);continue
            need(header is not None)
            exact(header,{'snapshotsRoleVersion','runId','binding','role','payload'})
            need(type(header['snapshotsRoleVersion']) is int and header['snapshotsRoleVersion']==1 and header['runId']==f.run and same(header['binding'],f.binding) and header['role']==role)
            states=unpack(header['payload']);need(len(states)==1);state=states[0]
            exact(state,{'phase','sequence','manifests','pending'})
            need(state['phase']=='retired' and state['pending'] is None and integer(state['sequence'],1,256))
            originals=SnapshotsOriginals(f.root,f.binding,f.run,role,history_guard,lambda *_:need(False),kind='snapshots')
            frames=originals.restore(state['manifests'],state['sequence']);need(frames)
            role_frames[role]=frames
            for frame in frames:
                image=frame.get('image')
                if image is not None:history_guard();SnapshotsImages.archive(f.root,image);history_guard()
                for binary in frame.get('binaries',[]):history_guard();SnapshotsBinary.archive(f.root,binary);history_guard()
            final=frames[-1];need(not final.get('diagnostic'))
            live=final['state'];need(not live['open'] and not live['pending'] and live['captureHistory']==[]
                and live['files']==live['saved']==live['uploads']==live['shares']==0 and not live['saveSheet'] and not live['shareSheet'])
        for name in ('files-owner','primary-files-observer','actor-files-observer'):
            header=archive['controls']['phone-snapshots-'+name+'.json']
            if header is None:need(partial);continue
            need(header['scope']==f.run and header['retired'])
        from overte_phone_snapshots_actor import ACTOR_VERSION,actor_fields,validate_transition_history,validate_primary_cue
        actor_header=archive['controls']['phone-snapshots-actor-lifecycle.json'];need(actor_header is not None)
        exact(actor_header,{'snapshotsActorVersion','runId','binding','payload'})
        version=actor_header['snapshotsActorVersion']
        need(type(version) is int and version in (1,2,ACTOR_VERSION) and actor_header['runId']==f.run
            and same(actor_header['binding'],f.binding))
        states=unpack(actor_header['payload']);need(len(states)==1);actor=states[0]
        exact(actor,actor_fields(version))
        # A completed legacy archive is immutable. Its local validation graph
        # has no transition events; no archive or active journal is rewritten.
        actor=deepcopy(actor)
        if version==1:actor['transitions']=[]
        if version<3:actor['primaryCue']=None
        need(actor['phase']=='retired' and actor['pending'] is None and actor['process']!=owner['hostProcess'] and terminated(actor['process'])
            and type(actor['dropped']) is list and len(actor['dropped'])<=256)
        phase_packet(actor['closure'],run=f.run,area='snapshots',request=actor['closure']['requestId'],epoch=actor['closure']['capturedEpochMs'])
        phase_packet(archive['closure'],run=f.run,area='snapshots',request=archive['closure']['requestId'],epoch=archive['closure']['capturedEpochMs'])
        need(not actor['closure']['active'])
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','retiredEpochMs','activations'):
            need(same(actor['closure'][key],archive['closure'][key]))
        if partial:
            need(actor['partialClosure'] is not None and actor['partialClosure']['snapshotPartialRetirementVersion']==1
                and same(actor['partialClosure']['owner'],archive['owner']) and actor['last'] is actor['quiet'] is None
                and actor['transitions']==[] and actor['primaryCue'] is None)
        else:need(actor['last'] is not None and actor['quiet']['complete'] and actor['partialClosure'] is None)
        validate_transition_history(f,actor,history_guard=history_guard,
            role_header=archive['controls']['phone-snapshots-actor-originals.json'],current_guard=self.bound)
        validate_primary_cue(f,actor['primaryCue'],archive['controls']['phone-snapshots-primary-originals.json'],
            history_guard=history_guard,current_guard=self.bound)
        self.validate_read_ready_archive(archive,owner,actor,version,role_frames,history_guard)
        history_guard();need(hashlib.sha256(canonical(archive)).hexdigest()==archive_sha);self.bound()

        return archive

    def validate_read_ready_archive(self,archive,owner,actor,version,role_frames,guard):
        """Validate archived scheduling originals without a live ready owner.

        Current controls may already be absent. The final retired Primary
        history supplies actual manifest entries; no intermediate ready header
        is reconstructed or repacked, and no scheduling field supplies a fact.
        """
        from overte_phone_snapshots_role import role_state,validate_read_ready_mode,validate_read_ready_slot
        from overte_phone_snapshots_actor import cue_state,primary_manifests
        f=self.feature;f.lock.assert_held();need(guard() is True and type(owner['cleanupStages']) is dict)
        slots=[(role,index,frame) for role,frames in role_frames.items()
            for index,frame in enumerate(frames,1) if 'readReadySlot' in frame]
        if 'readReadyMode' not in owner['cleanupStages']:
            need(not slots);return
        validate_read_ready_mode(owner['cleanupStages']['readReadyMode'],actor_process=actor['process'])
        need(not owner['partial'] and version==3 and actor['primaryCue'] is not None
            and slots and all(role=='primary' for role,_index,_frame in slots))
        header=archive['controls']['phone-snapshots-primary-originals.json']
        state=role_state(header,f.binding,f.run,'primary')
        need(state['phase']=='retired' and state['pending'] is None)
        host=SnapshotsOriginals(f.root,f.binding,f.run,'primary',guard,lambda *_:need(False),kind='snapshots')
        current=primary_manifests(host,state)
        feature_sha=hashlib.sha256(canonical(archive['owner'])).hexdigest()
        indices=[]
        for _role,index,frame in slots:
            slot=validate_read_ready_slot(frame,f.run,actor_process=actor['process'])
            before=role_state(slot['preparedRoleHeader'],f.binding,f.run,'primary')
            need(before['phase']=='ready' and before['pending'] is None and before['sequence']==slot['preparedRoleSequence']==index-1
                and slot['featureOwnerSha256']==feature_sha and index<=len(current))
            original_prefix=primary_manifests(host,before)
            need(same(current[:index-1],original_prefix)
                and same(host.read(host.expand(current[index-1])),frame))
            for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','activations'):
                need(same(frame['phaseAfter'][key],archive['closure'][key]))
            indices.append(index)
        # The actual latest consumed cue is a saved ready header. Its prefix
        # was already joined above to the final retired header, not replaced
        # with that differently phased final control.
        cue=cue_state(f,actor['primaryCue']);need(cue['sequence']==max(indices))
        entries=primary_manifests(host,cue);need(entries)
        final_slot=host.read(host.expand(entries[-1]))
        validate_read_ready_slot(final_slot,f.run,actor_process=actor['process'])
        need(same(final_slot,role_frames['primary'][cue['sequence']-1]) and guard() is True)

    def finalize(self):
        f=self.feature;started=previous=f.monotonic()
        for attempt in range(241):
            now=f.monotonic();need(number(now,previous,started+60));previous=now
            with f.lock.held(),f.adapter.existing_input_session(f.selector):
                f.load();self.previous=self.store.read()
                if self.previous is not None:
                    exact(self.previous,{'snapshotsRetirementVersion','runId','binding','payload'})
                    need(type(self.previous['snapshotsRetirementVersion']) is int and self.previous['snapshotsRetirementVersion']==1
                        and self.previous['runId']==f.run and same(self.previous['binding'],f.binding))
                    rows=unpack(self.previous['payload']);need(len(rows)==1);self.state=rows[0]
                    exact(self.state,{'phase','owner','archive','original'});need(self.state['phase'] in ('archiving','retiring'))
                    if f.state is None:f.state=unpack(self.state['owner']['payload'])[0]
                    self.bound();archive=self.state['archive']
                else:
                    if f.state is None:
                        archive=completed_archive(f.root,f.binding,f.run,lambda:f.guard() is not False)
                        f.state=unpack(archive['owner']['payload'])[0];self.validate_archive(archive)
                        need(same(archive['owner']['configuration'],f.public_configuration()) and not f.phase.status()['active'])
                        need(all(PrivateFeatureState(f.store.path.with_name(name)).read() is None for name in NAMES))
                        f._retirement_authority=lambda:same(completed_archive(f.root,f.binding,f.run,lambda:f.guard() is not False),archive)
                        files=archive['controls']
                        (f.partial_restored(file_owners=files) if f.state['partial'] else f.restored(file_owners=files));need(not f.phase.provider()['active'])
                        for role in ('primary','actor'):need(f.adapter._world_render_capture(f.selector,read_only=True,role=role,require_trace=True,require_frame_view=True).owner.store.read() is None)
                        return {'performed':True}
                    need(f.state['phase'] in ('cleaned','partial-cleaned'));closure=f.phase.status();need(not closure['active'])
                    actor=PrivateFeatureState(f.store.path.with_name('phone-snapshots-actor-lifecycle.json')).read();need(actor is not None)
                    actor_state=unpack(actor['payload'])[0]
                    if actor_state['phase']!='retired' or not terminated(actor_state['process']):
                        need(attempt<240);archive=None
                    else:
                        from overte_phone_snapshots_role import PhoneSnapshotsRole
                        if not f.state['partial']:
                            for role in ('primary','actor'):PhoneSnapshotsRole(f,role).retire()
                        proof=f.partial_restored() if f.state['partial'] else f.restored()
                        proof['provider']=f.phase.provider();controls={name:PrivateFeatureState(f.store.path.with_name(name)).read() for name in NAMES}
                        archive=dict(owner=deepcopy(f.previous),controls=controls,proof=proof,closure=closure)
                        self.validate_archive(archive)
                        self.state=dict(phase='archiving',owner=deepcopy(f.previous),archive=archive,original=None);self.save()
                if archive is not None:
                    f._retirement_authority=lambda:same(self.store.read(),self.previous) and self.state is not None and same(self.state['archive'],archive)
                    self.validate_archive(archive)
                    if self.state['phase']=='archiving':
                        ref=(self.originals.write(1,archive) if self.state['original'] is None else
                             self.originals.resume_write(1,archive,self.state['original']))
                        need(same(self.originals.read(self.originals.expand(ref)),archive))
                        self.state.update(phase='retiring',original=self.originals.expand(ref));self.save()
                    else:need(same(self.originals.read(self.state['original']),archive))
                    files=archive['controls']
                    (f.partial_restored(file_owners=files) if f.state['partial'] else f.restored(file_owners=files));need(not f.phase.provider()['active'])
                    for role in ('primary','actor'):
                        owned=f.adapter._world_render_capture(f.selector,read_only=True,role=role,require_trace=True,require_frame_view=True)
                        need(owned.owner.store.read() is None)
                    # Owner is pruned last. Every absent child remains justified
                    # by the exact immutable archive retained before the unlink.
                    for name in tuple(name for name in NAMES if name!='phone-snapshots-feature.json')+('phone-snapshots-feature.json',):
                        store=PrivateFeatureState(f.store.path.with_name(name));actual=store.read();original=archive['controls'][name]
                        if actual is not None:need(same(actual,original));store.discard(original)
                        need(store.read() is None)
                    f.previous=None
                    f.partial_restored(file_owners=files) if f.state['partial'] else f.restored(file_owners=files)
                    self.bound()
                    metadata=deepcopy(self.previous);self.store.discard(metadata);need(self.store.read() is None)
                    return {'performed':True}
            need(attempt<240 and f.monotonic()-started<60);f.sleep(.25)
        need(False)
