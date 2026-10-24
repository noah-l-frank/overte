"""Existing installed-adapter teardown hook; no forgotten WorldWeb ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import unpack,same
from feature_journeys.contract import identifier
from ios.adapters.graphics_configuration import settings as image_settings
from ios.adapters.world_web_measurements import origin
from ios.adapters.peer_admission import validate as peer_admission
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_final_archive import WorldWebFinalArchive


def no_orphan_carriers(directory,config):
    """Missing coordinator metadata cannot erase retained ownership originals."""
    directories={directory}
    if type(config) is dict and 'world-web' in config.get('areas',[]):
        from ios.adapters.feature_configuration import validate
        validate(config)
        from ios.adapters.world_web_configuration import settings
        chosen=config['worldWeb'];role='primary' if 'actorTarget' in chosen else 'actor'
        directories.add(Path(settings(chosen,role=role)['artifactRoot']))
    prefixes=('ios-world-web-','ios-worldweb-','world-web-','worldweb-marker-read-abandoned-',
        'wwc-','wwrg-','wwsu-','phase-publication-world-web-','phase-retirement-world-web-')
    for folder in directories:
        try:
            entries=folder.iterdir()
            for index,entry in enumerate(entries):
                need(index<4096 and not entry.name.startswith(prefixes))
        except FileNotFoundError:
            # No directory and no retained original: no SDK was consulted.
            continue


def finalize_existing(runtime,selector,config,client):
    """Finish before SDK DELETE. An actor must finish in its independent flow."""
    from ios.adapters.world_web_runtime import IOSWorldWebRuntime
    need(isinstance(runtime,IOSWorldWebRuntime));directory=runtime.state_path(selector).parent
    found=[]
    for role in ('primary','actor'):
        value=PrivateFeatureState(directory/('ios-world-web-'+role+'-feature.json')).read()
        if value is not None:found.append((role,value))
    if not found:
        no_orphan_carriers(directory,config)
        return False
    need(len(found)==1);role,value=found[0]
    exact(value,{'iosWorldWebFeatureVersion','runId','role','peerTarget','artifactRoot','fixtureUrl','imagePolicy','origins','payload'})
    rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosWorldWebFeatureVersion']) is int and value['iosWorldWebFeatureVersion']==2 and value['role']==role)
    from ios.adapters.create_configuration import selector as validate_selector
    need(validate_selector(value['peerTarget'])!=selector)
    identifier(value['runId']);image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
    exact(value['origins'],{'primary','foreign'});need(origin(value['origins']['primary'])!=origin(value['origins']['foreign']))
    state=rows[0]
    exact(state,{'phase','binding','primaryBinding','phaseInstance','initialTicket','actorAdmission','baseline','lease','beforeImage','images','retirement'})
    binding=context(state['binding']);context(state['primaryBinding']);identifier(state['phaseInstance']);identifier(state['initialTicket'])
    need(state['phase'] in ('baseline','ready','cleaning','cleaned','paired','retired')
        and type(state['images']) is list and len(state['images'])<=64)
    for request in state['images']+([] if state['beforeImage'] is None else [state['beforeImage']]):
        need(type(request) is str and request.startswith('ios-'));identifier(request[4:])
    if role=='primary':peer_admission(state['actorAdmission'],binding)
    else:need(state['actorAdmission'] is state['beforeImage'] is None and state['images']==[])

    scope={key:item for key,item in binding.items() if key!='processIdentity'}
    # Check the actual retained candidate/target without starting an app or
    # reconstructing a lost SDK session. This is a canonical adapter boundary.
    runtime.adapter._retired_candidate_scope(selector,scope)
    if state['phase']=='retired':
        # No current SDK is reconstructed after death. Real retained phase,
        # Scene and OS originals are decoded through their owning types.
        from feature_journeys.witness import Client
        from ios.adapters.world_web_archived import forbidden
        passive=object.__new__(Client);passive.url=value['fixtureUrl'].split('/runs/')[0];passive.request=forbidden
        chosen={key:value[key] for key in ('artifactRoot','imagePolicy','origins')}
        chosen['actorTarget' if role=='primary' else 'primaryTarget']=value['peerTarget']
        flow=runtime._world_web_feature(selector,value['runId'],role=role,client=passive,settings=chosen)
        with flow.held():
            flow.load();archive=WorldWebFinalArchive(PrivateFeatureState(directory/('ios-world-web-'+role+'-'+value['runId']+'-final.json')),
                value['artifactRoot'],binding,value['runId'],role,flow.lock)
            frame=archive.verify();need(frame['feature']['phase']==('paired' if role=='primary' else 'cleaned'))
            need(flow.finalize(frame['phaseOriginal'])==dict(performed=True))
        return True
    need(role=='primary' and type(config) is dict and config.get('iosFeatureAdapterVersion',0)>=5 and 'world-web' in config['areas'])
    flow=runtime._world_web_feature(selector,value['runId'],role=role,client=client,settings=config['worldWeb'])
    with flow.held():
        flow.load();status=flow.phase.status();need(status['active'] is False);need(flow.finalize(status)==dict(performed=True))
    return True


def retire_existing(runtime,selector,config,client):
    """Canonical cleanup can only verify a fully completed original end.

    Unfinished ownership must use the explicit paired inspect/seal/finish
    protocol. This fallback never starts Stop or SDK deletion without it.
    """
    from copy import deepcopy
    from feature_journeys.graphics_resources import fixture_url
    from feature_journeys.witness import Client
    from ios.adapters.world_web_archived import forbidden
    from ios.adapters.world_web_feature import IOSWorldWebFeature
    from ios.adapters.world_web_runtime import IOSWorldWebRuntime
    from ios.adapters.world_web_terminal import WorldWebTerminal
    need(isinstance(runtime,IOSWorldWebRuntime));directory=runtime.state_path(selector).parent
    found=[]
    for role in ('primary','actor'):
        value=PrivateFeatureState(directory/('ios-world-web-'+role+'-feature.json')).read()
        if value is not None:found.append((role,value))
    if not found:
        no_orphan_carriers(directory,config);return None
    need(len(found)==1);role,value=found[0]
    exact(value,{'iosWorldWebFeatureVersion','runId','role','peerTarget','artifactRoot','fixtureUrl','imagePolicy','origins','payload'})
    need(type(value['iosWorldWebFeatureVersion']) is int and value['iosWorldWebFeatureVersion']==2 and value['role']==role)
    identifier(value['runId']);fixture_url(value['fixtureUrl'].split('/runs/')[0])
    passive=object.__new__(Client);passive.url=value['fixtureUrl'].split('/runs/')[0];passive.request=forbidden
    chosen={key:value[key] for key in ('artifactRoot','imagePolicy','origins')}
    chosen['actorTarget' if role=='primary' else 'primaryTarget']=value['peerTarget']
    flow=runtime._world_web_feature(selector,value['runId'],role=role,client=passive,settings=chosen)
    need(type(flow) is IOSWorldWebFeature)
    with flow.held():
        flow.load();need(flow.state is not None and flow.state['phase']=='retired' and same(flow.previous,value))
        requested_scope=deepcopy({key:item for key,item in flow.state['binding'].items() if key!='processIdentity'})
        runtime.adapter._retired_candidate_scope(selector,requested_scope)
    if role=='actor':
        chosen={key:value[key] for key in ('artifactRoot','imagePolicy','origins')}|dict(actorTarget=selector)
        flow=runtime._world_web_feature(value['peerTarget'],value['runId'],role='primary',client=passive,settings=chosen)
        need(type(flow) is IOSWorldWebFeature)
    terminal=WorldWebTerminal(flow)
    need(terminal.state is not None and terminal.state['phase']=='complete' and terminal.state['seal'] is not None and terminal.state['end'] is not None
        and terminal.state['pending'] is None and len(terminal.state['records'])==3)
    # The complete branch reopens both role originals and their sealed live
    # window, actual OS quiet and SDK deletion/archive. It has no live getter.
    result=terminal.finish(terminal.state['seal'])
    need(result==dict(stage='finish',end=terminal.state['end']))
    runtime.adapter._retired_candidate_scope(selector,requested_scope)
    return {'cleaned':True}
