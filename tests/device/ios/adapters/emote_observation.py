"""Historical Emote originals to public facts, without SDK reads or inputs.

An actor uses its own independently acquired primary SDK source archive for
clip/caller/range/rate facts and its other target for received poses and pixels.
No primary public result, requested name, or expected Sit variant is accepted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.emote_rig_measurements import playback,restoration,source,continuation
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.original_frame_store import OriginalFrameStore,BLOCK
from adapters.original_avatar_peer_recovery import OriginalAvatarPeerRecovery
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier,result
from ios.adapters import avatar_renderers
from ios.adapters.emote_images import changed as changed_pixels
from ios.adapters.emote_marker_measurements import body_preserved
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_peer import acquisition as peer_acquisition,movement,session_sha
from ios.adapters.emote_peer_sources import IOSEmotePeerSources
from ios.adapters.emote_samples import archived_sample
from ios.adapters.emote_sources import IOSEmoteSources
from ios.adapters.emote_source_recovery import IOSEmoteSourceRecovery
from ios.adapters.emote_ui_inventory import absent as absent_chooser,validate as ui_inventory
from ios.adapters.emote_world import actual_domain
from ios.adapters.emote_native_prefix import follow as follow_native

VERSION=1


class IOSEmoteObservationDecoder:
    def __init__(self,sources,binding,role,root,policy,lock,*,phase_instance,peers=None):
        need(isinstance(sources,IOSEmoteSources) and sources.role==role and role in ('primary','actor')
            and isinstance(lock,ScriptSourceLock) and (role=='primary' or isinstance(peers,IOSEmotePeerSources)))
        self.sources,self.binding,self.role=sources,deepcopy(context(binding)),role
        self.root,self.policy,self.lock=Path(root),deepcopy(policy),lock
        self.run,self.primary_binding,self.peers=sources.run,sources.binding,peers
        self.phase_instance=identifier(phase_instance)
        self.pid=int(self.primary_binding['processIdentity']);lock.assert_held();sources.lock.assert_held()
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir()
            and policy.get('source')=='world-render-target')
        if role=='primary':need(same(binding,sources.binding) and peers is None)
        else:
            need(same(peers.binding,binding) and peers.run==self.run
                and self.primary_binding['targetFingerprint']!=binding['targetFingerprint']
                and self.primary_binding['sessionId']!=binding['sessionId']
                and all(self.primary_binding[k]==binding[k] for k in ('sourceRevision','artifactSha256')))

    def source(self,reference):
        original=self.retained(self.sources,reference)
        need(self.sources.validate_frame(original) and 'world' in original
            and original['phaseBefore']['instance']==original['phaseAfter']['instance']==self.phase_instance)
        return original

    @staticmethod
    def retained(owner,reference):
        exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(owner.frames)))
        live=owner.originals
        archive=OriginalFrameStore(live.root,live.binding,live.run,live.role,lambda:True,lambda *_:need(False),
            namespace=live.namespace,schema_prefix=live.schema_prefix,kind=live.kind)
        entries=archive.manifest(owner.state['manifests'][(reference['index']-1)//BLOCK])
        original=archive.read(archive.expand(entries[(reference['index']-1)%BLOCK]))
        need(same(original,owner.frames[reference['index']-1]) and digest(original)==reference['sha256'])
        return original

    def state(self,current,proof,ticket):
        """Replay actual original caller/loaded clip/pose or closed episode."""
        exact(proof,{'kind','baseline','before','played','inputBarrier'})
        need(proof['kind'] in ('idle','playback','restoration','retired'))
        baseline=self.source(proof['baseline']);native=current['group']['native'];join=current['clockJoin']
        if not same(current,baseline):continuation(baseline['group']['native'],native,self.pid)
        need(baseline['group']['native']['animation']['overrideActive'] is False)
        if proof['kind']=='idle':
            need(proof['before'] is proof['played'] is proof['inputBarrier'] is None
                and native['animation']['overrideActive'] is False
                and native['animation']['history']['callSequence']==baseline['group']['native']['animation']['history']['callSequence'])
            state=dict(animation='idle',sit='none',override=False,poseProgress=0.,restoredBeforeNominalEnd=False)
        else:
            before,played=self.source(proof['before']),self.source(proof['played'])
            need(proof['before']['index']<proof['played']['index'])
            measured=playback(played['group'],before['group']['native'],pid=self.pid,
                epoch=played['clockJoin']['nativeAfter']['capturedEpochMs'])
            if proof['kind']=='playback':
                need(proof['inputBarrier'] is None)
                state=playback(current['group'],before['group']['native'],pid=self.pid,
                    epoch=join['nativeAfter']['capturedEpochMs'])['state']
                need(state['override'] is True)
            else:
                barrier=None if proof['inputBarrier'] is None else self.source(proof['inputBarrier'])['group']['native']
                state=restoration(current['group'],measured,pid=self.pid,
                    epoch=join['nativeAfter']['capturedEpochMs'],native_barrier=barrier)['state']
                if proof['kind']=='retired':
                    # Retirement drops only this adapter's current episode.
                    # Native event/pose/caller histories remain unchanged.
                    activation=current['phaseAfter']['activations'][-1]
                    need(activation['ticket']==ticket and activation['stimulus']==dict(verb='cleanup',inputs={})
                        and not current['widgets']['tabletShown'] and absent_chooser(current['widgets']))
                    state['restoredBeforeNominalEnd']=False
        pages=[row for row in current['ui']['controls'] if row['id']=='emote.page'];need(len(pages)<=1)
        panel=bool(pages) and current['ui']['open']
        if state['override']:
            need(panel and pages[0]['activeName']==state['animation'])
        state=dict(state,panel=panel)
        return state

    def image(self,value,marker):
        exact(marker,{'nonce','url','scope'});identifier(marker['nonce'])
        scope=IOSEmoteMarkerScope.archive(marker['scope'],root=self.root,binding=self.binding,run=self.run,role=self.role,
            lock=self.lock,require_ready=True)
        frame,raw,image,name=archived_sample(value,root=self.root,binding=self.binding,run=self.run,role=self.role,
            lock=self.lock,policy=self.policy,marker_nonce=marker['nonce'],marker_url=marker['url'])
        for key in ('worldBefore','worldAfter'):
            need(scope.bind_image_world(frame[key])=={k:marker[k] for k in ('nonce','url')})
        return frame,raw,image,name

    def derive(self,value):
        """Strict original callback for PhaseWitnessPublisher; entirely read-only."""
        self.lock.assert_held();self.sources.lock.assert_held()
        exact(value,{'iosEmoteObservationOriginalVersion','runId','role','binding','primaryBinding','sequence','ticket',
            'source','sourceRecovery','peerRecovery','proof','peerBefore','peerAfter','marker','imageBefore','image','acquisition'})
        need(type(value['iosEmoteObservationOriginalVersion']) is int and value['iosEmoteObservationOriginalVersion']==VERSION
            and value['runId']==self.run and value['role']==self.role and same(value['binding'],self.binding)
            and same(value['primaryBinding'],self.primary_binding) and integer(value['sequence'],1,512))
        ticket=identifier(value['ticket']);current=self.source(value['source']);clock=PhaseWitnessPublisher.acquisition(value['acquisition'])
        recovery_path=self.sources.store.path.with_name('ios-emote-'+self.role+'-source-recovery.json')
        live_recovery=value['sourceRecovery'] if self.sources.historical else PrivateFeatureState(recovery_path).read()
        actual_recovery=None if live_recovery is None else IOSEmoteSourceRecovery.archive(live_recovery,self.sources)
        known=[]
        if value['sourceRecovery'] is not None:
            need(actual_recovery is not None)
            recovered=IOSEmoteSourceRecovery.archive(value['sourceRecovery'],self.sources)
            recovered.follow(current,historical=True);known=recovered.state['records']
        if actual_recovery is not None:
            for reference in actual_recovery.state['records']:
                record=actual_recovery.record(reference)
                if actual_recovery.attempt(record)['revision']<value['source']['index']:need(reference in known)
        join=current['clockJoin'];activation=current['phaseAfter']['activations'][-1]
        need(activation['ticket']==ticket and activation['activatedEpochMs']<=clock['hostBeforeEpochMs']
            and clock['hostBeforeEpochMs']<=join['hostBeforeEpochMs']<=join['hostAfterEpochMs']<=clock['hostAfterEpochMs']
            and clock['hostBeforeMonotonic']<=join['hostBeforeMonotonic']<=join['hostAfterMonotonic']<=clock['hostAfterMonotonic'])
        state=self.state(current,value['proof'],ticket);peer=None
        if self.role=='actor':
            need(value['peerAfter'] is not None);after=self.retained(self.peers,value['peerAfter'])
            need(self.peers.validate_frame(after) and after['phaseBefore']['instance']==after['phaseAfter']['instance']==self.phase_instance
                and after['phaseAfter']['activations'][-1]['ticket']==ticket)
            path=self.peers.store.path.with_name('ios-emote-actor-peer-recovery.json')
            live_peer_recovery=value['peerRecovery'] if self.peers.historical else PrivateFeatureState(path).read()
            actual_peer_recovery=None if live_peer_recovery is None else OriginalAvatarPeerRecovery.archive(live_peer_recovery,self.peers)
            peer_records=[]
            if value['peerRecovery'] is not None:
                need(actual_peer_recovery is not None)
                recovered_peer=OriginalAvatarPeerRecovery.archive(value['peerRecovery'],self.peers)
                recovered_peer.follow(after,historical=True);peer_records=recovered_peer.state['records']
            if actual_peer_recovery is not None:
                for ref in actual_peer_recovery.state['records']:
                    record=actual_peer_recovery.record(ref)
                    if actual_peer_recovery.attempt(record)['revision']<value['peerAfter']['index']:need(ref in peer_records)
            acquired=peer_acquisition(after['peer'],self.binding);primary=actual_domain(current['world']);actor=actual_domain(after['peer']['world'])
            need(primary['domainId']==actor['domainId'] and primary['avatarMixerSha256']==actor['avatarMixerSha256']
                and primary['selfSha256']!=actor['selfSha256'])
            candidates=[r for r in after['peer']['renderers']['source']['avatars'] if session_sha(r['sessionId'])==primary['selfSha256']]
            need(len(candidates)==1);remote=candidates[0]['sessionId']
            avatar_renderers.external(after['peer']['renderers'],remote,after_epoch=acquired['nativeBefore']['capturedEpochMs'])
            need(clock['hostBeforeEpochMs']<=acquired['hostBeforeEpochMs']<=acquired['hostAfterEpochMs']<=clock['hostAfterEpochMs']
                and clock['hostBeforeMonotonic']<=acquired['hostBeforeMonotonic']<=acquired['hostAfterMonotonic']<=clock['hostAfterMonotonic'])
            if value['proof']['kind'] in ('playback','restoration'):
                need(value['peerBefore'] is not None)
                peer=movement(current['world'],self.primary_binding,self.retained(self.peers,value['peerBefore'])['peer'],after['peer'],self.binding)
            if value['image'] is not None:need(value['image']['avatarId']==remote)
        else:need(value['peerBefore'] is value['peerAfter'] is value['peerRecovery'] is None)
        artifacts=[]
        if value['image'] is not None:
            need(value['marker'] is not None);frame,raw,image,name=self.image(value['image'],value['marker'])
            need(image is not None and value['image']['ticket']==ticket)
            image_clock=frame['clockJoin']
            need(clock['hostBeforeEpochMs']<=image_clock['hostBeforeEpochMs']<=image_clock['hostAfterEpochMs']<=clock['hostAfterEpochMs']
                and clock['hostBeforeMonotonic']<=image_clock['hostBeforeMonotonic']<=image_clock['hostAfterMonotonic']<=clock['hostAfterMonotonic'])
            if self.role=='primary':
                follow_native(join['nativeAfter'],image_clock['nativeBefore']);body_preserved(current['world'],frame['worldBefore'])
                need(value['image']['avatarId'] is None)
            else:
                follow_native(acquired['nativeAfter'],image_clock['nativeBefore'])
                body_preserved(after['peer']['world'],frame['worldBefore'])
            if value['proof']['kind'] in ('playback','restoration'):
                need(value['imageBefore'] is not None)
                before,old_raw,old,_name=self.image(value['imageBefore'],value['marker']);need(old is not None)
                changed_pixels(self.run,self.binding,before,old_raw,value['imageBefore']['ticket'],frame,raw,ticket,self.policy,
                    marker_nonce=value['marker']['nonce'],marker_url=value['marker']['url'],avatar_id=value['image']['avatarId'])
            artifacts=[dict(kind='image',name=name,sequence=value['sequence'],capturedEpochMs=image['capturedEpochMs'],ticket=ticket,source='world-render-target')]
        else:
            need(value['imageBefore'] is None and value['marker'] is None
                and value['proof']['kind'] in ('idle','retired'))
        resources=[]
        if current['widgets'].get('emoteControlsVersion')==2:
            inventory=ui_inventory(current['widgets']['emoteInventory']);need(inventory['complete'])
            if inventory['roots']:resources.append('panel:emote-chooser')
        elif state['panel']:resources.append('panel:emote-chooser')
        if value['proof']['kind']=='retired':need(not resources)
        public=result('feature.emotes.observe',dict(schemaVersion=1,contractVersion=16,runId=self.run,sequence=value['sequence'],
            capturedEpochMs=clock['hostBeforeEpochMs'],state=state,artifacts=artifacts,resources=resources,
            lifecycle=deepcopy(current['group']['native']['lifecycle'])))
        return dict(ticket=ticket,public=public,acquisition=deepcopy(clock))
