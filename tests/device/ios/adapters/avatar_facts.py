"""Nine Avatar facts composed from independently retained SDK originals.

The decoder receives complete historical source owners, original peer owners
and the observing role's immutable Vulkan samples. It never reads an SDK or
copies an action acknowledgement or another observer's normalized answer.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.original_frame_store import OriginalFrameStore,BLOCK
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import same
from feature_journeys.contract import identifier,result
from ios.adapters import avatar_observation as appearance,avatar_peer,avatar_social,avatar_renderers,avatar_images
from ios.adapters.avatar_authority import AvatarAuthorityReader
from ios.adapters.avatar_samples import IOSAvatarSamples
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_peer_sources import IOSAvatarPeerSources
from ios.adapters.emote_peer import acquisition
from ios.adapters.graphics_history import follow_native

VERSION=1
ROLES=('primary','actor')


def inside(inner,outer):
    for first,last in (('hostBeforeEpochMs','hostAfterEpochMs'),('hostBeforeMonotonic','hostAfterMonotonic')):
        need(outer[first]<=inner[first]<=inner[last]<=outer[last])


def retained(owner,reference):
    """Reopen the exact immutable original instead of trusting a Python cache."""
    owner.lock.assert_held()
    exact(reference,{'index','sha256'});need(integer(reference['index'],1,len(owner.frames)))
    live=owner.originals
    archive=OriginalFrameStore(live.root,live.binding,live.run,live.role,lambda:True,lambda *_:need(False),
        namespace=live.namespace,schema_prefix=live.schema_prefix,kind=live.kind)
    entries=archive.manifest(owner.state['manifests'][(reference['index']-1)//BLOCK])
    value=archive.read(archive.expand(entries[(reference['index']-1)%BLOCK]))
    need(same(value,owner.frames[reference['index']-1]) and digest(value)==reference['sha256'])
    return value


class IOSAvatarFacts:
    def __init__(self,sources,peers,samples,authority,*,role,phase_instance,expected_code):
        exact(sources,set(ROLES));exact(peers,set(ROLES));need(role in ROLES and isinstance(authority,AvatarAuthorityReader)
            and isinstance(samples,IOSAvatarSamples) and samples.historical and samples.role==role)
        self.sources,self.peers,self.samples,self.authority=sources,peers,samples,authority
        self.role,self.run,self.phase_instance,self.expected_code=role,authority.run,identifier(phase_instance),deepcopy(expected_code)
        for subject in ROLES:
            source,peer=sources[subject],peers[subject]
            need(isinstance(source,IOSAvatarSources) and source.historical and source.run==self.run and source.role==role
                and isinstance(peer,IOSAvatarPeerSources) and peer.historical and peer.run==self.run and peer.role==role
                and same(source.binding,peer.binding))
            source.lock.assert_held();peer.lock.assert_held()
        need(same(samples.binding,sources[role].binding) and samples.run==self.run)
        a,b=(context(sources[subject].binding) for subject in ROLES)
        need(a['sessionId']!=b['sessionId'] and a['targetFingerprint']!=b['targetFingerprint']
            and all(a[key]==b[key] for key in ('artifactSha256','sourceRevision')))

    def source(self,subject,reference,ticket):
        owner=self.sources[subject];frame=retained(owner,reference);need(owner.validate_frame(frame))
        for side in ('phaseBefore','phaseAfter'):
            phase=frame[side];need(phase['instance']==self.phase_instance and phase['activations'][-1]['ticket']==ticket)
        avatar_peer.state_original(frame,owner.binding);return frame

    def peer(self,subject,reference,ticket):
        owner=self.peers[subject];frame=retained(owner,reference);need(owner.validate_frame(frame))
        for side in ('phaseBefore','phaseAfter'):
            need(frame[side]['instance']==self.phase_instance and frame[side]['activations'][-1]['ticket']==ticket)
        return frame['peer']

    def provider(self,value,clock,ticket):
        exact(value,{'status','acquisition'});window=PhaseWitnessPublisher.acquisition(value['acquisition']);inside(window,clock)
        status=self.authority.validate(value['status'],window['hostAfterEpochMs'])
        need(status['phase']=='ready' and status['ticket']==ticket and status['social'] is not None and 'sessionBinding' in status)
        for child in status['accounts'].values():
            need(window['hostBeforeEpochMs']-1500<=child['capturedEpochMs']<=window['hostAfterEpochMs']+250)
        social=status['social'];need(window['hostBeforeEpochMs']-1500<=social['capturedEpochMs']<=window['hostAfterEpochMs']+250)
        principals={subject:'e2e-'+status['accounts'][subject]['runId'] for subject in ROLES}
        return status,principals

    def derive(self,value):
        for owner in list(self.sources.values())+list(self.peers.values())+[self.samples]:owner.lock.assert_held()
        exact(value,{'iosAvatarFactsOriginalVersion','runId','role','sequence','ticket','phaseInstance','baseline','current',
            'primaryPeer','actorBefore','actorAfter','provider','barriers','image','imageBefore','acquisition'})
        need(type(value['iosAvatarFactsOriginalVersion']) is int and value['iosAvatarFactsOriginalVersion']==VERSION
            and value['runId']==self.run and value['role']==self.role and value['phaseInstance']==self.phase_instance
            and integer(value['sequence'],1,512))
        ticket=identifier(value['ticket']);clock=PhaseWitnessPublisher.acquisition(value['acquisition'])
        exact(value['baseline'],set(ROLES));exact(value['current'],set(ROLES));exact(value['barriers'],set(ROLES))
        current={subject:self.source(subject,value['current'][subject],ticket) for subject in ROLES}
        baseline={subject:retained(self.sources[subject],value['baseline'][subject]) for subject in ROLES}
        phase=current['primary']['phaseAfter'];activation=phase['activations'][-1]
        need(activation['activatedEpochMs']<=clock['hostBeforeEpochMs']
            and same(phase['activations'],current['actor']['phaseAfter']['activations']))
        for frame in current.values():inside(frame['clockJoin'],clock)
        status,principals=self.provider(value['provider'],clock,ticket)
        measured=appearance.appearance(self.sources['primary'],value['baseline']['primary']['index'],value['current']['primary']['index'],
            fixture_url=self.authority.client.url+'/runs/'+self.run+'/',expected_code=self.expected_code)
        # The independent consenting SDK keeps its own actual appearance and
        # unowned inventory; remote primary effects never relabel its self.
        old,new=(frame['originals'] for frame in (baseline['actor'],current['actor']))
        for key in ('sessionId','requestedUrl','resourceUrl','geometryLoaded','rigReady','targetScale','modelScale'):
            need(old['state']['source'][key]==new['state']['source'][key])
        need(same(old['state']['source']['bookmarks'],new['state']['source']['bookmarks'])
            and same(appearance.bookmark_file(old['state']['source'],allow_missing=True),
                appearance.bookmark_file(new['state']['source'],allow_missing=True)))
        avatar_renderers.preserve_unowned(old['renderers'],new['renderers'],set(measured['ownedWearables']))
        ppeer=self.peer('primary',value['primaryPeer'],ticket)
        before=self.peer('actor',value['actorBefore'],ticket);after=self.peer('actor',value['actorAfter'],ticket)
        for peer,binding in ((ppeer,self.sources['primary'].binding),(before,self.sources['actor'].binding),(after,self.sources['actor'].binding)):
            inside(acquisition(peer,binding),clock)
        wearables={identity:row['resource'] if row['present'] else None for identity,row in measured['ownedWearables'].items()}
        replicated=avatar_peer.replication(current['primary'],ppeer,before,after,current['actor'],
            self.sources['primary'].binding,self.sources['actor'].binding,wearables=wearables)
        sessions={subject:current[subject]['originals']['state']['source']['sessionId'] for subject in ROLES}
        from ios.adapters.emote_world import actual_domain
        need(status['sessionBinding']['sessions']==sessions
            and status['sessionBinding']['domain']==actual_domain(ppeer['world'])['domainId'])
        kwargs=dict(principals=principals,owned_origin=self.authority.client.url.split('/feature-fixture/v1')[0],
            provider_instance=status['socialInstance'],run=self.run,ticket=ticket,expected_code=self.expected_code)
        models=[frame['originals']['people']['source']['roots'] for frame in current.values()]
        phases=[next(root['connectionState']['phase'] for root in rows if root['active']) for rows in models]
        bindings=[self.sources[subject].binding for subject in ROLES]
        if phases==['outgoing','incoming']:
            social=avatar_social.pending(current['primary'],current['actor'],*bindings,status['social'],**kwargs)
        elif status['social']['connected']:
            social=avatar_social.connected(current['primary'],current['actor'],*bindings,status['social'],**kwargs,barriers=value['barriers'])
        else:
            social=avatar_social.absent(current['primary'],current['actor'],*bindings,status['social'],**kwargs,
                barriers=value['barriers'],require_delete=activation['stimulus']['verb']=='connection-remove')
        for subject in ROLES:
            frame=current[subject];pages=[row for row in frame['ui']['controls'] if row['id']=='people.page'];need(len(pages)==1)
            model=avatar_social.people_model.current(frame['originals']['people'])
            need(pages[0]['rootId']==model['rootId'] and pages[0]['connectionState']==model['connectionState']
                and (pages[0]['dialog']=='connection')==social['pendingDialog'])
        row=value['image'];need(type(row) is dict and row['ticket']==ticket and row in self.samples.state['rows'])
        frame,raw,image=self.samples.archive(row);need(image is not None);inside(frame['clockJoin'],clock)
        own=self.sources[self.role].binding;remote=self.role=='actor';identity=sessions['primary']
        need(image['sessionId']==identity and image['remote'] is remote and image['modelLoaded']==measured['state']['modelLoaded']
            and row['avatarId']==(identity if remote else None))
        original=current['primary']['originals']['state']['source'];observed=avatar_renderers.avatar(frame['renderersBefore'],identity,remote=remote)
        resource=(current['actor']['originals']['state']['source']['defaultResourceUrl']
            if remote and original['resourceUrl']==original['defaultResourceUrl'] else original['resourceUrl'])
        need(observed['requestedUrl']==original['requestedUrl'] and observed['resourceUrl']==resource
            and abs(observed['modelScale']-original['modelScale'])<.0001)
        from ios.adapters.avatar_world import actual_domain as image_domain
        own_peer=after if remote else ppeer
        for side in ('worldBefore','worldAfter'):need(image_domain(frame[side])==actual_domain(own_peer['world']))
        inventory=after['renderers'] if remote else current['primary']['originals']['renderers']
        for side in ('renderersBefore','renderersAfter'):
            avatar_renderers.preserve_unowned(inventory,frame[side],set(wearables))
            for entity_id,resource in wearables.items():
                if resource is None:
                    need(all(row['id']!=entity_id for row in frame[side]['source']['tree']['entities'])
                        and all(row['id']!=entity_id for row in frame[side]['source']['avatarEntities']))
                else:need(avatar_renderers.wearable(frame[side],entity_id,identity,resource,remote=remote))
        follow_native((acquisition(after,own)['nativeAfter'] if remote else current['primary']['clockJoin']['nativeAfter']),
            frame['clockJoin']['nativeBefore'])
        marker=self.samples.state['markerOwner'];scope=self.samples.read_record(row)
        for side in ('phaseBefore','phaseAfter'):
            image_phase=scope['partial'][side]
            need(image_phase['instance']==self.phase_instance and same(image_phase['activations'],phase['activations']))
        changed=None
        if activation['stimulus']['verb'] in ('avatar-scale','wearable-add','avatar-bookmark-choose'):
            previous=value['imageBefore'];need(previous is not None and len(phase['activations'])>=2
                and previous['ticket']==phase['activations'][-2]['ticket'] and previous in self.samples.state['rows'])
            old_frame,old_raw,old_image=self.samples.archive(previous);need(old_image is not None)
            marker_scope=self.samples.Marker.archive(marker,root=self.samples.root,binding=self.samples.binding,run=self.run,
                role=self.role,lock=self.samples.lock,require_ready=True)
            basis=None;prior=self.samples.read_record(previous)
            if prior['basisIndex'] is not None:
                basis_row=self.samples.state['rows'][prior['basisIndex']-1];bframe,braw,_=self.samples.archive(basis_row)
                basis=(bframe,braw,basis_row['ticket'])
            changed=avatar_images.changed(self.run,own,old_frame,old_raw,previous['ticket'],frame,raw,ticket,self.samples.policy,
                marker_nonce=marker_scope.state['fileOwnership']['nonce'],marker_url=marker_scope.state['admission']['marker']['sourceUrl'],
                avatar_id=identity if remote else None,owned_ids=set(wearables),absence_basis=basis)
        else:need(value['imageBefore'] is None)
        state=measured['state']|dict(connection=social['connection'],dialog=social['pendingDialog'])
        resources=['panel:people','script:avatar-marker','entity:avatar-marker','file:avatar-marker-inputs']
        if state['wearable']:resources.append('entity:avatar-wearable')
        if state['bookmarked']:resources.append('file:avatar-bookmark')
        if state['connection']!='none':resources.append('connection:owned-peer')
        if state['dialog']:resources.append('panel:connection-consent')
        public=result('feature.avatar-people.observe',dict(schemaVersion=1,contractVersion=16,runId=self.run,
            sequence=value['sequence'],capturedEpochMs=clock['hostBeforeEpochMs'],state=state,
            artifacts=[dict(kind='image',name=scope['owner']['name'],sequence=value['sequence'],ticket=ticket,
                capturedEpochMs=image['capturedEpochMs'],source='world-render-target')],resources=resources,
            lifecycle=deepcopy(current[self.role]['originals']['native']['lifecycle'])))
        return dict(ticket=ticket,public=public,acquisition=deepcopy(clock),
            originals=dict(appearance=measured,social=social,peer=replicated,image=image,changed=changed))
