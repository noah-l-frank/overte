"""Historical Favorite effect evidence for the next ordinary Avatar URL input.

This permits only a previously observed owned scale or bookmark change. It never alters a
native packet, substitutes requested values or supplies wearable authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from adapters.pico4 import avatar_state,avatar_preferences
from adapters.pico4.avatar_urls import PicoAvatarUrls
from adapters.script_journey.history import same
from adapters.token_create_ui import navigation,nonce,scope
from feature_journeys.fixtures import context as fixture_context


def original_preferences(before,after):
    """Exact original data, keeping current post-write identity independent."""
    a=avatar_preferences.baseline(before);b=avatar_preferences.baseline(after)
    avatar_preferences.continuity(before,after)
    need(before['processId']==after['processId'] and before['instance']==after['instance']
        and before['source']['instance']==after['source']['instance'] and a['instance']==b['instance'])
    need(same(a['cache']['rows'],b['cache']['rows']) and same(a['cache']['encodedRows'],b['cache']['encodedRows']))
    x,y=a['cache']['native'],b['cache']['native']
    need(all(same(x[key],y[key]) for key in ('handles','modelInstance','sessionId','live')))
    x,y=a['writer'],b['writer']
    need(all(same(x[key],y[key]) for key in ('instance','rows','encodedRows')))
    x,y=x['physical'],y['physical']
    need(all(same(x[key],y[key]) for key in ('format','pathSha256','fileSha256','rows')))
    # Native QSettings commits can replace the inode and timestamps. They are
    # real current identities, never an assertion that the old inode returned.
    need(x['file']['exists']==y['file']['exists'])
    if x['file']['exists']:need(all(x['file'][key]==y['file'][key] for key in ('mode','bytes')))
    return after


def original_bookmarks(before,after):
    from adapters.pico4.avatar_bookmarks import storage
    storage(before,before['capturedEpochMs']);storage(after,after['capturedEpochMs'])
    need(after['capturedEpochMs']>=before['capturedEpochMs']
        and all(same(before[key],after[key]) for key in
                ('pathSha256','present','rawBase64','rawSha256','cacheBase64','mapSha256','bookmarks')))
    # The normal original writer's revision is separately retained and checked
    # by the native source. Never invent restoration of its former timestamps.
    return after


def unchanged_preferences(before,after):
    """Admit the actual cached/Scale path without inventing a lazy write.

    Whole original MyAvatar setAvatarScale/setTargetScale and cached Favorite
    do not persist a Handle. Independent original sources must retain every
    typed Handle/cache/writer/physical value; only live scale may differ.
    """
    a=avatar_preferences.baseline(before);b=avatar_preferences.baseline(after)
    avatar_preferences.continuity(before,after)
    need(before['processId']==after['processId'] and before['instance']==after['instance']
        and before['source']['instance']==after['source']['instance']
        and a['instance']==b['instance'] and a['mutationSequence']==b['mutationSequence'])
    need(same(a['cache']['rows'],b['cache']['rows']) and same(a['cache']['encodedRows'],b['cache']['encodedRows']))
    x,y=a['cache']['native'],b['cache']['native']
    need(all(same(x[key],y[key]) for key in ('handles','modelInstance','sessionId')))
    need(same({key:value for key,value in x['live'].items() if key not in ('scale','targetScale')},
              {key:value for key,value in y['live'].items() if key not in ('scale','targetScale')}))
    x,y=a['writer'],b['writer']
    need(all(same(x[key],y[key]) for key in ('instance','rows','encodedRows')))
    x,y=x['physical'],y['physical']
    need(all(same(x[key],y[key]) for key in ('format','pathSha256','file','fileSha256','rows')))
    return after


def validate(proof,binding,run,fixture_url):
    # Imported only when an original effect proof is admitted; no factory,
    # UI, transport or native getter call during historical reconstruction.
    from adapters.pico4.avatar_favorites import validate_frame,input_frame,phase_original,SOURCES,PicoAvatarFavorites
    exact(proof,{'avatarFavoriteEffectVersion','binding','runId','fixtureUrl','ticket','phase','frames','before','quiet','inputs'})
    need(type(proof['avatarFavoriteEffectVersion']) is int and proof['avatarFavoriteEffectVersion']==1 and same(context(proof['binding']),context(binding))
        and proof['runId']==run and proof['fixtureUrl']==fixture_url and type(proof['frames']) is list and 3<=len(proof['frames'])<=128
        and integer(proof['before'],1,len(proof['frames'])) and type(proof['inputs']) is list and 0<len(proof['inputs'])<=128)
    pid=int(binding['processIdentity'].split(':')[0]);activation=phase_original(proof['phase'],run)
    need(activation['ticket']==proof['ticket'] and activation['stimulus']['verb'] in ('avatar-scale','avatar-bookmark-choose') and proof['phase']['active'])
    exact(proof['quiet'],{'first','last'});first,last=proof['quiet']['first'],proof['quiet']['last']
    need(integer(first,proof['before']+1,len(proof['frames'])) and integer(last,first+1,len(proof['frames'])) and last==len(proof['frames']))
    values=[validate_frame(frame,pid,binding,run) for frame in proof['frames']];original=values[proof['before']-1];name=fixture_context(run)['name']
    verb=activation['stimulus']['verb']
    before=original['native']['source'];record=original['bookmarks']['source']['storage']['bookmarks'].get(name)
    need(type(record) is dict and record==dict(version=3,avatarUrl=record.get('avatarUrl'),avatarScale=1,avatarEntites=[],avatarIcon=''))
    owned_a={fixture_url+'tickets/'+row['ticket']+'/avatar-a.fst' for row in proof['phase']['activations']
        if row['stimulus']==dict(verb='avatar-url',inputs=dict(resource='avatar-a.fst'))}
    need(record['avatarUrl'] in owned_a)
    if verb=='avatar-scale':need(before['scale']==before['targetScale']==1 and record['avatarUrl']==before['requestedUrl'])
    need(activation['stimulus']['inputs']==(dict(value=1.5) if verb=='avatar-scale' else dict(name=name)))
    previous=None
    for frame,current in zip(proof['frames'],values):
        PicoAvatarFavorites.empty_attachments(current);avatar_preferences.baseline(current['preferences'])
        need(same(frame['phaseAfter']['activations'],proof['phase']['activations']) and frame['phaseAfter']['active'])
        if previous is not None:
            for kind,module in SOURCES.items():module.continuity(previous[kind],current[kind])
        previous=current
    published=[]
    for row in proof['inputs']:
        exact(row,{'ticket','intent','command','frame'});need(row['ticket']==proof['ticket'] and integer(row['frame'],proof['before']+1,first-1) and row['command'] is not None)
        intent=row['intent'];exact(intent,{'avatarPeopleInputVersion','action','controlId','controlToken','scope'});scope(intent['scope'])
        allowed={'avatar.entry','avatar.settings','avatar.scale','avatar.settings.scrollbar','avatar.settings.confirm'} if verb=='avatar-scale' else {'avatar.entry','avatar.bookmark.manage','avatar.dialog.confirm'}
        if verb=='avatar-bookmark-choose':
            for actual in proof['frames'][row['frame']-1]['widgets']['controls']:
                if actual.get('bookmarkName')==name and actual.get('managing') is False:allowed.add(actual['id'])
        need(type(intent['avatarPeopleInputVersion']) is int and intent['avatarPeopleInputVersion']==1 and nonce(intent['controlToken'])
            and (navigation(intent['controlId']) or intent['controlId'] in allowed))
        input_frame(proof['frames'][row['frame']-1],row,binding,pid,run);PicoAvatarFavorites.command_original(row['command'],row['intent']);published.append(row['command'])
        command=row['command']
        if command['action']=='set-value':need(verb=='avatar-scale' and command['controlId']=='avatar.scale' and command['value']==15)
        elif command['action']=='scroll':need(verb=='avatar-scale' and command['controlId']=='avatar.settings.scrollbar' and command['direction']=='down')
        else:need(command['action']=='activate' and command['controlId'] not in ('avatar.scale','avatar.settings.scrollbar'))
    if verb=='avatar-scale':
        need(any(command['controlId']=='avatar.scale' and command['action']=='set-value' and command['value']==15 for command in published)
            and any(command['controlId']=='avatar.settings.confirm' and command['action']=='activate' for command in published))
    else:need(any(command['controlId'].startswith('avatar.bookmark.row.') for command in published) and any(command['controlId']=='avatar.dialog.confirm' for command in published))
    stable=None;previous_frame=None
    for frame,current in zip(proof['frames'][first-1:last],values[first-1:last]):
        native=current['native']['source'];widgets=frame['widgets']
        need(widgets['open'] and widgets['ready'] and any(row['id']=='avatar.page' for row in widgets['controls'])
            and not any(row['id'] in ('avatar.scale','avatar.settings.confirm','avatar.dialog.confirm','avatar.dialog.input') for row in widgets['controls']))
        if verb=='avatar-scale' or before['requestedUrl']==record['avatarUrl']:
            unchanged_preferences(original['preferences'],current['preferences'])
        if verb=='avatar-scale':
            need(all(native[key]==before[key] for key in ('requestedUrl','preferenceUrl','modelName','avatarEntityStorage','modelUrl','modelInstance','geometry','sessionId','hipsJoint','rigId','loaded','localRenderingEnabled'))
                and all(native[kind]['currentGeneration']==before[kind]['currentGeneration'] for kind in ('avatarLoads','modelLoads'))
                and all(abs(native[key]-1.5)<.0001 for key in ('scale','targetScale')))
        else:
            need(native['requestedUrl']==native['preferenceUrl']==native['modelUrl']==record['avatarUrl'] and native['loaded'] and native['geometry'] is not None)
            from adapters.pico4.avatar_urls import loaded_url
            need(native['geometry'] is not None and native['geometry']['url']==loaded_url(record['avatarUrl']) and native['hipsJoint']>=0 and not avatar_state.failed(native)
                and native['modelLoads']['requestedSha256']==avatar_state.sha(record['avatarUrl']) and all(abs(native[key]-1)<.0001 for key in ('scale','targetScale')))
            cached=before['requestedUrl']==record['avatarUrl']
            need(native['avatarLoads']['currentGeneration']==before['avatarLoads']['currentGeneration']+(0 if cached else 1)
                and native['modelLoads']['currentGeneration']==before['modelLoads']['currentGeneration']+(0 if cached else 1)
                and native['modelInstance']==before['modelInstance'] and native['sessionId']==before['sessionId'])
        need(all(current['bookmarks']['source']['storage'][key]==original['bookmarks']['source']['storage'][key]
            for key in ('bookmarks','pathSha256','rawSha256','file')))
        old_rows=original['loads']['source']['loads']['rows'];rows=current['loads']['source']['loads']['rows']
        for row in rows[len(old_rows):]:
            need(row['nameSha256']==avatar_state.sha(name) and row['urlSha256']==avatar_state.sha(record['avatarUrl']) and row['avatarInstance']==native['avatarLoads']['instance']
                and row['sessionId']==native['sessionId'] and row['connected'] and row['disconnected'] and row['completed'] and row['dispatches']==1 and not row['active'] and not row['captureAlive'] and row['ownerThreadOnly'])
        if verb=='avatar-bookmark-choose':need(len(rows)>len(old_rows))
        observed=dict(native=PicoAvatarUrls.stable(native),preferences=PicoAvatarUrls.preference_stable(current['preferences']),
            bookmarks={key:current['bookmarks']['source']['storage'][key] for key in ('bookmarks','pathSha256','rawSha256','file')},loads=rows)
        need(stable is None or same(stable,observed));stable=observed
        if previous_frame is not None:
            old,old_values=previous_frame;need(0<=frame['hostFinished']-old['hostFinished']<=.5)
            for kind in SOURCES:need(0<=current[kind]['capturedEpochMs']-old_values[kind]['capturedEpochMs']<=500)
        previous_frame=(frame,current)
    need(proof['frames'][last-1]['hostFinished']-proof['frames'][first-1]['hostFinished']>=3)
    for kind in SOURCES:need(values[last-1][kind]['capturedEpochMs']-values[first-1][kind]['capturedEpochMs']>=3000)
    return values[-1]


def current(proof,binding,run,fixture_url,native,preferences,phase):
    after=validate(proof,binding,run,fixture_url)
    need(len(phase['activations'])>len(proof['phase']['activations']) and phase['activations'][:len(proof['phase']['activations'])]==proof['phase']['activations'])
    before=after['native']['source'];actual=native['source']
    need(all(actual[key]==before[key] for key in ('requestedUrl','preferenceUrl','modelName','avatarEntityStorage','modelUrl','modelInstance','geometry','sessionId','hipsJoint','rigId','loaded','localRenderingEnabled','scale','targetScale'))
        and all(actual[kind]['currentGeneration']==before[kind]['currentGeneration'] for kind in ('avatarLoads','modelLoads'))
        and same(PicoAvatarUrls.preference_stable(preferences),PicoAvatarUrls.preference_stable(after['preferences'])))
    return after
