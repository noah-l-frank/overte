"""Historical Avatar originals and appearance; no action/ACK-derived effects.

The full observation additionally owns independent social, peer, pixels and
cleanup evidence. This module never publishes or starts a live SDK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import BLOCK
from adapters.script_feature.history import same
from feature_journeys.navigation_scene import resource_root
from ios.adapters import avatar_state,avatar_renderers,avatar_bookmarks,avatar_entities
from ios.adapters.avatar_peer import state_original
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_source_recovery import IOSAvatarSourceRecovery

VERSION=1


def source_history(value,recovery,*,store,root,binding,run,role,lock):
    """Read exact retained source/recovery bytes without a current SDK/guard."""
    need(isinstance(store,PrivateFeatureState));lock.assert_held()
    class Frozen(PrivateFeatureState):
        def read(_self):return deepcopy(value)
        def write(_self,*_args):need(False)
        def discard(_self,*_args):need(False)
    sources=IOSAvatarSources(Frozen(store.path),root,binding,run,role,lock,lambda:True,None,historical=True)
    need(sources.state['phase']=='ready' and sources.state['pending'] is None)
    if recovery is not None:
        abandoned=IOSAvatarSourceRecovery.archive(recovery,sources)
        need(abandoned.state['pending'] is None)
        for frame in sources.frames:abandoned.follow(frame,historical=True)
    return sources


def frame(sources,index):
    need(isinstance(sources,IOSAvatarSources) and sources.historical and integer(index,1,len(sources.frames)))
    sources.lock.assert_held();reference=sources.state['manifests'][(index-1)//BLOCK]
    entries=sources.originals.manifest(reference);value=sources.originals.read(sources.originals.expand(entries[(index-1)%BLOCK]))
    need(same(value,sources.frames[index-1]))
    need(value.get('avatarSourceGroupVersion')==2)
    state_original(value,sources.binding);return value


def aliases(status,fixture_url,original_url):
    """Controlled input metadata labels only actual observed native URLs."""
    result={original_url:'original'}
    for row in status['activations']:
        stimulus=row['stimulus']
        if stimulus['verb']!='avatar-url':continue
        resource=stimulus['inputs']['resource'];need(resource in ('avatar-a.fst','missing.fst'))
        url=fixture_url+'tickets/'+row['ticket']+'/'+resource
        label='A' if resource=='avatar-a.fst' else 'missing';need(url not in result or result[url]==label);result[url]=label
    return result


def bookmark_file(source,*,allow_missing):
    loaded=source['bookmarks'];need(not loaded['loadError'])
    actual=avatar_bookmarks.entries(source['bookmarkFile'])
    if actual['status']=='missing':need(allow_missing and not loaded['entries']);return {}
    return avatar_bookmarks.persisted(source['bookmarkFile'],loaded)


def appearance(sources,baseline_index,current_index,*,fixture_url,expected_code):
    """Derive seven appearance fields from independent original source reads.

    Returned UUID ownership comes from actual native addEntity returns and
    separately reviewed submitted VM code, never primary action metadata.
    Source/renderer/file originals establish effects and complete absence.
    """
    need(integer(baseline_index,1,current_index));baseline=frame(sources,baseline_index);current=frame(sources,current_index)
    resource_root(fixture_url,sources.run);b,bc=state_original(baseline,sources.binding);s,sc=state_original(current,sources.binding)
    old,now=b['source'],s['source'];need(b['runId']==s['runId']==sources.run and old['sessionId']==now['sessionId'])
    initial=baseline['phaseBefore'];need(len(initial['activations'])==1 and initial['activations'][0]['stimulus']==dict(verb='baseline',inputs={}))
    need(old['geometryLoaded'] and old['rigReady'] and old['shouldRender'] and old['requestedUrl']==old['resourceUrl']
        and abs(old['targetScale']-1.)<.0001 and abs(old['modelScale']-1.)<.0001)
    avatar_renderers.loaded(baseline['originals']['renderers'],old['sessionId'],old['resourceUrl'],old['modelScale'])
    mapping=aliases(current['phaseBefore'],fixture_url,old['requestedUrl']);requested=mapping.get(now['requestedUrl']);need(requested is not None)
    history=now['modelHistory'];need(history['complete'] and abs(now['targetScale']-now['modelScale'])<.0001)
    loaded=now['geometryLoaded'] and now['rigReady'];renderer=avatar_renderers.avatar(current['originals']['renderers'],now['sessionId'])
    if loaded:need(renderer['addedToScene'] and renderer['shouldRender'])
    else:need(not now['geometryLoaded'] and not now['rigReady'] and not renderer['addedToScene'])
    failures=[event for event in history['events'] if event['kind']=='finished' and event['generation']==history['currentGeneration']
        and event['requestedUrl']==event['resourceUrl']==now['requestedUrl'] and event['success'] is False]
    failed=bool(failures) if requested=='missing' else False
    if requested=='missing':need(failed)
    if not loaded:avatar='unavailable'
    elif requested=='missing' and now['resourceUrl']==now['defaultResourceUrl']:avatar='fallback'
    else:avatar=mapping.get(now['resourceUrl']);need(avatar in ('original','A') and avatar==requested)

    owned={};events=current['originals']['entities']['source']['events']
    for activation in current['phaseBefore']['activations']:
        stimulus=activation['stimulus']
        if stimulus['verb']!='wearable-add':continue
        resource=fixture_url+'tickets/'+activation['ticket']+'/'+stimulus['inputs']['resource']
        candidates=[event for event in events if event['kind']=='add-returned' and event['entity']['modelUrl']==resource
            and event['clock']['epochMs']>=bc['nativeAfter']['capturedEpochMs']]
        if not candidates:continue
        returned=avatar_entities.returned(current['originals']['entities'],baseline['originals']['renderers'],current['originals']['scripts'],expected_code,
            avatar_id=now['sessionId'],resource=resource,after_epoch=bc['nativeAfter']['capturedEpochMs'])
        entity_id=returned['entity']['entityId'];need(entity_id not in owned);owned[entity_id]=dict(resource=resource,original=returned,present=False)
    rendered=current['originals']['renderers'];avatar_renderers.preserve_unowned(baseline['originals']['renderers'],rendered,set(owned))
    native_ids={row['id'] for row in rendered['source']['avatarEntities']};tree_ids={row['id'] for row in rendered['source']['tree']['entities']}
    for identity,row in owned.items():
        if identity not in native_ids and identity not in tree_ids:continue
        need(identity in native_ids and identity in tree_ids)
        need(avatar_renderers.wearable(rendered,identity,now['sessionId'],row['resource']))
        row['present']=True
    name='e2e-'+sources.run;base_rows=bookmark_file(old,allow_missing=True);need(name not in base_rows)
    current_rows=bookmark_file(now,allow_missing=not base_rows and not now['bookmarks']['entries'])
    need({key:value for key,value in current_rows.items() if key!=name}==base_rows)
    saved=None
    for index in range(baseline_index,current_index+1):
        item=frame(sources,index)
        source=item['originals']['state']['source'];rows=source['bookmarks']['entries']
        if name not in rows:continue
        bookmark_file(source,allow_missing=False)
        metadata=item['phaseBefore']['activations']
        need(any(row['stimulus']==dict(verb='avatar-bookmark-save',inputs=dict(name=name)) for row in metadata))
        if saved is None:
            saved=deepcopy(rows[name]);need(type(saved) is dict and saved.get('avatarUrl')==source['requestedUrl']
                and type(saved.get('avatarScale')) in (int,float) and abs(saved['avatarScale']-source['modelScale'])<.0001)
        else:need(same(rows[name],saved))
    if name in current_rows:need(saved is not None and same(current_rows[name],saved))
    state=dict(requestedAvatar=requested,avatar=avatar,modelLoaded=loaded,loadFailed=failed,scale=now['modelScale'],
        wearable=any(row['present'] for row in owned.values()),bookmarked=name in current_rows)
    return dict(iosAvatarAppearanceVersion=VERSION,state=state,sessionId=now['sessionId'],ownedWearables=owned,bookmarkEntry=saved,
        baselineSha256=digest(baseline),sourceSha256=digest(current),sourceIndex=current_index,baselineIndex=baseline_index)
