"""Canonical cleanup admission from actual ended Avatar originals only.

These hooks never Stop, delete an SDK or remove a graph file. The installed
adapter exclusively owns its SDK/Installed metadata CAS after this proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import unpack,same
from feature_journeys.contract import identifier
from ios.adapters.avatar_runtime import IOSAvatarRuntime
from ios.adapters.avatar_session_carriers import configured_roots,scoped


def finalize_existing(runtime,selector,config,client,*,membership=None,check=lambda:None):
    """True means an existing SDK is already proven ended; False means unowned."""
    need(isinstance(runtime,IOSAvatarRuntime) and callable(check));check();directory=runtime.state_path(selector).parent
    found=[]
    for role in ('primary','actor'):
        value=PrivateFeatureState(directory/('ios-avatar-'+role+'-feature.json')).read()
        if value is not None:found.append((role,value))
    if not found:
        explicit=configured_roots(config,target=selector);need(not scoped(directory,{directory}|explicit,explicit=bool(explicit)))
        return False
    need(len(found)==1);role,value=found[0]
    exact(value,{'iosAvatarFeatureVersion','runId','role','selectors','artifactRoot','imagePolicy','fixtureUrl','payload'})
    run=identifier(value['runId']);need(value['role']==role and value['selectors'][role]==selector)
    rows=unpack(value['payload']);need(len(rows)==1)
    need(membership is None or type(membership) is set)
    membership=set() if membership is None else membership
    if rows[0]['phase'] in ('preparing','ready'):
        from ios.adapters.avatar_failed_archive import verify
        failed=PrivateFeatureState(directory/('ios-avatar-'+role+'-'+run+'-failed-preparation.json')).read();need(failed is not None)
        binding=verify(runtime.adapter,selector,value,failed,membership=membership,check=check)
    else:
        need(rows[0]['phase']=='terminal-ready')
        from ios.adapters.avatar_ended_archive import verify
        primary=runtime.state_path(value['selectors']['primary']).parent
        coordinator=PrivateFeatureState(primary/'ios-avatar-primary-feature.json').read()
        terminal=PrivateFeatureState(primary/('ios-avatar-primary-'+run+'-terminal.json')).read()
        need(coordinator is not None and terminal is not None and coordinator['runId']==run and same(coordinator['selectors'],value['selectors']))
        binding=verify(runtime.adapter,selector,coordinator,terminal,membership=membership,check=check)
    need(same(binding,rows[0]['bindings'][role]))
    # The root canonical caller must independently check this exact candidate
    # scope and CAS only its actual session/installed originals. Preserve all
    # graph paths so repeated cleanup can perform the same full typed replay.
    need(runtime.adapter._retired_candidate_scope(selector,{key:item for key,item in binding.items() if key!='processIdentity'}) is not False)
    check();return True


def retire_existing(runtime,selector,config,client):
    """Authorize the caller's metadata CAS, with no second SDK DELETE."""
    if not finalize_existing(runtime,selector,config,client):return None
    return dict(performed=True)
