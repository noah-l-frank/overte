"""Choose a concrete cleanup input only from actual retained Avatar sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters import avatar_entities,avatar_renderers,avatar_observation,people_model
from ios.adapters.avatar_sources import IOSAvatarSources
from ios.adapters.avatar_peer import state_original
from ios.adapters.avatar_state import session,identity as source_identity


def next_step(sources,baseline_index,peer,*,fixture_url,expected_code,directory_verified=False):
    need(isinstance(sources,IOSAvatarSources) and sources.historical and type(directory_verified) is bool)
    sources.lock.assert_held();exact(peer,{'sessionId','username'})
    session(peer['sessionId']);need(type(peer['username']) is str and peer['username'].startswith('e2e-') and source_identity(peer['username'][4:]))
    from feature_journeys.navigation_scene import resource_root
    resource_root(fixture_url,sources.run)
    need(integer(baseline_index,1,len(sources.frames)))
    baseline=avatar_observation.frame(sources,baseline_index);current=avatar_observation.frame(sources,len(sources.frames))
    activation=current['phaseAfter']['activations'][-1];need(activation['stimulus']==dict(verb='cleanup',inputs={}))
    before,bc=state_original(baseline,sources.binding);after,_clock=state_original(current,sources.binding)
    old,now=before['source'],after['source'];need(old['sessionId']==now['sessionId'] and old['geometryLoaded'] and old['rigReady'])
    page=next((row for row in current['ui']['controls'] if row['id'] in ('avatar.page','people.page')),None)
    if page is not None and page['dialog']!='none':
        if page['id']=='avatar.page':return dict(step='dismiss-avatar',inputs=dict(rootId=page['rootId'],dialog=page['dialog']))
        state=page['connectionState'];need(state.get('peer')==peer['sessionId'])
        return dict(step='dismiss-people',inputs=dict(rootId=page['rootId'],**{key:state[key] for key in ('peer','requestId','phase')}))
    owned={};events=current['originals']['entities']['source']['events'];barrier=bc['nativeAfter']['capturedEpochMs']
    for row in current['phaseBefore']['activations']:
        stimulus=row['stimulus']
        if stimulus['verb']!='wearable-add':continue
        resource=fixture_url+'tickets/'+row['ticket']+'/'+stimulus['inputs']['resource']
        if not any(event['kind']=='add-returned' and event['clock']['epochMs']>=barrier and event['entity']['modelUrl']==resource for event in events):continue
        actual=avatar_entities.returned(current['originals']['entities'],baseline['originals']['renderers'],current['originals']['scripts'],expected_code,
            avatar_id=now['sessionId'],resource=resource,after_epoch=barrier)
        owned[actual['entity']['entityId']]=actual
    avatar_renderers.preserve_unowned(baseline['originals']['renderers'],current['originals']['renderers'],set(owned))
    present={row['id'] for row in current['originals']['renderers']['source']['avatarEntities']}
    for identity in sorted(owned):
        if identity in present:return dict(step='remove-wearable',inputs=dict(entityId=identity))
    if now['requestedUrl']!=old['requestedUrl']:return dict(step='restore-model',inputs=dict(url=old['requestedUrl']))
    if not now['geometryLoaded'] or not now['rigReady'] or now['resourceUrl']!=old['resourceUrl']:
        return dict(wait='original-model')
    if now['targetScale']!=old['targetScale']:return dict(step='restore-scale',inputs=dict(value=old['targetScale']))
    if now['modelScale']!=old['modelScale']:return dict(wait='original-scale')
    base=avatar_observation.bookmark_file(old,allow_missing=True)
    bookmarks=avatar_observation.bookmark_file(now,allow_missing=not base and not now['bookmarks']['entries']);name='e2e-'+sources.run
    need(name not in base and {key:value for key,value in bookmarks.items() if key!=name}==base)
    if name in bookmarks:
        saved=None
        for index in range(baseline_index,len(sources.frames)+1):
            frame=avatar_observation.frame(sources,index);entry=frame['originals']['state']['source']['bookmarks']['entries'].get(name)
            if entry is None:continue
            need(any(row['stimulus']==dict(verb='avatar-bookmark-save',inputs=dict(name=name)) for row in frame['phaseBefore']['activations']))
            if saved is None:saved=entry
            else:need(same(saved,entry))
        need(saved is not None and same(saved,bookmarks[name]));return dict(step='delete-bookmark',inputs=dict(name=name))
    if not directory_verified:return dict(step='connections',inputs={})
    roots=current['originals']['people']['source']['roots'];active=[root for root in roots if root['active']]
    if not active or active[0]['activeTab']!='connectionsTab':return dict(step='connections',inputs={})
    root=people_model.current(current['originals']['people']);pagination=root['pagination']
    if (not pagination['initialized'] or not pagination['retrievedAtLeastOnePage'] or pagination['requestPending']
            or pagination['additionalFirstPageRequested'] or pagination['delayedClear'] or pagination['currentPageToRetrieve']!=-1
            or pagination['totalEntries']!=len(root['connectionRows']) or root['httpCallbacks']):return dict(wait='connections-page')
    rows=[row for row in root['connectionRows'] if row['userName']==peer['username']];need(len(rows)<=1)
    if rows:
        need(rows[0]['connection']=='connection');return dict(step='remove-connection',inputs=dict(username=peer['username']))
    return None
