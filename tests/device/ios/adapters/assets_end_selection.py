"""Select or reopen the same explicit target pair before Assets owner birth.

No target selector is inferred from a session, fingerprint or saved directory.
The caller's ordinary target map supplies both roles independently. Historical
completed replay does not acquire a live SDK/native/process source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters.assets_end_graph import AssetsFinalArchive,inventory,selection
from ios.adapters.assets_end_metadata import signature
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.installed_process_runtime import admitted_source


def roots(runtime,roles,locks):
    exact(roles,{'primary','actor'});exact(locks,{'primary','actor'});result={}
    for role in ('primary','actor'):
        value=roles[role];exact(value,{'target','artifactRoot'})
        from ios.adapters.emote_configuration import selector
        selector(value['target']);artifact=Path(value['artifactRoot']);state=runtime.state_path(value['target']).parent
        need(type(value['artifactRoot']) is str and artifact.is_absolute() and artifact.resolve()==artifact and artifact.is_dir()
            and state.is_absolute() and state.resolve()==state and state.is_dir()
            and locks[role].path==state/'script-feature-sources.lock');locks[role].assert_held()
        result[role]=dict(target=value['target'],artifactRoot=str(artifact),stateRoot=str(state))
    need(result['primary']['target']!=result['actor']['target'])
    paths=[(role,Path(row[key])) for role,row in result.items() for key in ('artifactRoot','stateRoot')]
    for role,path in paths:
        for other,right in paths:
            if role!=other:need(path!=right and not path.is_relative_to(right) and not right.is_relative_to(path))
    return result


def archive(runtime,run,fixture_url,ticket,roles,locks):
    """File-only open using separately selected roles, never a recovered URL map."""
    identifier(run);identifier(ticket);mapped=roots(runtime,roles,locks)
    store=PrivateFeatureState(Path(mapped['primary']['stateRoot'])/('ios-assets-'+run+'-primary-final.json'))
    raw=store.read();need(raw is not None);chosen=selection(raw.get('context'))
    need(chosen['runId']==run and chosen['fixtureUrl']==fixture_url and chosen['initialTicket']==ticket)
    for role,fields in mapped.items():need(all(chosen['roles'][role][key]==value for key,value in fields.items()))
    return construct(store,chosen,locks,[PrivateFeatureState(Path(path)) for path in raw.get('paths',[])])


def construct(store,chosen,locks,paths):
    # Pin directory identities only: mutable owned files are guarded by their
    # actual owners, never by an old whole-directory successful-verdict cache.
    parents={Path(row[key]) for row in chosen['roles'].values() for key in ('artifactRoot','stateRoot')}
    pins={p:signature(p) for p in parents}
    # Child creation changes directory timestamps. The identity/ownership/mode
    # contract is retained while mtime/ctime are checked by full graph leases.
    def identity_guard():
        for lock in locks.values():lock.assert_held()
        for path,pin in pins.items():
            current=signature(path);need(current is not None and all(current[index]==pin[index] for index in (0,1,2,4)))
        return True
    owner=AssetsFinalArchive(store,Path(chosen['roles']['primary']['artifactRoot']),chosen['roles']['primary']['binding'],
        chosen['runId'],'primary',locks['actor'],locks['primary'],paths,identity_guard,lambda copies:False,chosen=chosen)
    # qualify must be installed by the actual transaction before freeze; an
    # unbound archive cannot accidentally mark arbitrary copies validated.
    return owner


def select(runtime,run,fixture_url,ticket,roles,locks,*,phase):
    need(isinstance(runtime,IOSAssetsRuntime));identifier(run);identifier(ticket);mapped=roots(runtime,roles,locks)
    from feature_journeys.phase_fixture import PhaseFixtureReader
    need(isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='assets' and phase.fixture_url==fixture_url)
    active=phase.status();need(active['active'])
    store=PrivateFeatureState(Path(mapped['primary']['stateRoot'])/('ios-assets-'+run+'-primary-final.json'))
    if store.read() is not None:
        result=archive(runtime,run,fixture_url,ticket,roles,locks)
        need(active['instance']==result.context['inputPhaseOriginal']['instance']);result.select();return result
    need(active['activations'] and active['activations'][-1]['ticket']==ticket)
    # Do this BEFORE normal source construction, which retains its usual
    # InstalledBinding refresh. Old/orphan Assets duty cannot be adopted by a
    # newly fabricated early selection, including another run in these roots.
    all_roots={Path(row[key]) for row in mapped.values() for key in ('artifactRoot','stateRoot')}
    need(not any(p.name.startswith(('assets-','ios-assets-')) for p in inventory(all_roots,locks=locks.values())))
    chosen=dict(assetsPairedEndContextVersion=1,runId=run,fixtureUrl=fixture_url,initialTicket=ticket,inputPhaseOriginal=deepcopy(active),roles={})
    for role,fields in mapped.items():
        parts=runtime._assets_sources(fields['target'],locks[role]);need(parts['check']() is not False)
        source=admitted_source(runtime,fields['target'],parts['binding']);need(parts['check']() is not False)
        chosen['roles'][role]=dict(fields,binding=deepcopy(parts['binding']),source=source,bundleId=parts['target']['appId'])
    chosen=selection(chosen)
    paths=[PrivateFeatureState(Path(mapped['primary']['stateRoot'])/('ios-assets-'+run+'-primary-files.json'))]
    owner=construct(store,chosen,locks,paths);owner.select()
    for role,info in chosen['roles'].items():need(same(admitted_source(runtime,info['target'],info['binding']),info['source']))
    owner.selected_guard();return owner
