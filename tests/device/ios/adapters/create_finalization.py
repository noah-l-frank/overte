"""Existing installed-adapter teardown hook; no forgotten Create ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from pathlib import Path
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import unpack,same
from feature_journeys.contract import identifier
from ios.adapters.graphics_configuration import settings as image_settings
from ios.adapters.peer_admission import validate as peer_admission
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.create_final_archive import CreateFinalArchive


def no_orphan_carriers(directory,config):
    """Missing coordinator metadata cannot erase retained ownership originals."""
    directories={directory}
    if type(config) is dict and 'create' in config.get('areas',[]):
        from ios.adapters.feature_configuration import validate
        validate(config)
        from ios.adapters.create_configuration import settings
        directories.add(Path(settings(config['create'])['artifactRoot']))
    prefixes=('ios-create-','phase-publication-create-','phase-retirement-create-')
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
    from ios.adapters.create_runtime import IOSCreateRuntime
    need(isinstance(runtime,IOSCreateRuntime));directory=runtime.state_path(selector).parent
    found=[]
    for role in ('primary','actor'):
        value=PrivateFeatureState(directory/('ios-create-'+role+'-feature.json')).read()
        if value is not None:found.append((role,value))
    if not found:
        no_orphan_carriers(directory,config)
        return False
    need(len(found)==1);role,value=found[0]
    exact(value,{'iosCreateFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
    rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosCreateFeatureVersion']) is int and value['iosCreateFeatureVersion']==1 and value['role']==role)
    identifier(value['runId']);image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
    state=rows[0]
    exact(state,{'phase','binding','primaryBinding','phaseInstance','initialTicket','actorAdmission','beforeImage','images','exports','retirement'})
    binding=context(state['binding']);context(state['primaryBinding']);identifier(state['phaseInstance']);identifier(state['initialTicket'])
    need(state['phase'] in ('preparing','ready','cleaning','cleaned','paired','retired')
        and type(state['images']) is list and len(state['images'])<=80 and type(state['exports']) is list and len(state['exports'])<=32)
    for request in state['images']+state['exports']+([] if state['beforeImage'] is None else [state['beforeImage']]):
        need(type(request) is str and request.startswith('ios-'));identifier(request[4:])
    if role=='primary':peer_admission(state['actorAdmission'],binding)
    else:need(state['actorAdmission'] is state['beforeImage'] is None and state['images']==state['exports']==[])

    scope={key:item for key,item in binding.items() if key!='processIdentity'}
    # Check the actual retained candidate/target without starting an app or
    # reconstructing a lost SDK session. This is a canonical adapter boundary.
    runtime.adapter._retired_candidate_scope(selector,scope)
    if state['phase']=='retired':
        lock=ScriptSourceLock(directory/'script-feature-sources.lock')
        with lock.held():
            archive=CreateFinalArchive(PrivateFeatureState(directory/('ios-create-'+role+'-'+value['runId']+'-final.json')),
                value['artifactRoot'],binding,value['runId'],role,lock)
            frame=archive.verify();need(frame['binding']==binding and same(frame['feature'],dict(state,phase=frame['feature']['phase']))
                and frame['feature']['phase']==('paired' if role=='primary' else 'cleaned')
                and frame['phaseOriginal']['runId']==value['runId']
                and same(frame['coordinatorHeader'],{key:item for key,item in value.items() if key!='payload'}))
        return True
    need(role=='primary' and type(config) is dict and config.get('iosFeatureAdapterVersion',0)>=3 and 'create' in config['areas'])
    flow=runtime._create_feature(selector,value['runId'],role=role,client=client,settings=config['create'])
    with flow.held():
        flow.load();status=flow.phase.status();need(status['active'] is False);flow.finalize(status)
    return True
