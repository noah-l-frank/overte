"""Retire only actual stopped SDK/Installed metadata after full Avatar replay.

No process reader, SDK factory, Stop or DELETE exists on this path. The full
ended/failed graph and original process provenance must precede either CAS;
all feature originals remain available for independent repeated cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same,unpack
from ios.adapters.avatar_existing import finalize_existing
from ios.adapters.avatar_session_carriers import covered
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.installed_code import source
from ios.adapters.avatar_api_entry import check as api_check
from ios.adapters.avatar_session_cleanup import check as cleanup_check


def retire_existing(runtime,selector,config,client=None):
    base=runtime.adapter;directory=runtime.state_path(selector).parent
    def check():api_check();cleanup_check(base,selector)
    check()
    owners=[(role,PrivateFeatureState(directory/('ios-avatar-'+role+'-feature.json')).read()) for role in ('primary','actor')]
    owners=[(role,value) for role,value in owners if value is not None]
    if not owners:
        need(not finalize_existing(runtime,selector,config,client,check=check));return None
    need(len(owners)==1);role,owner=owners[0]
    # A private inventory surrounds the full decoder and the metadata CAS.
    # Discovering roots grants no success; admission below types every owner.
    need(type(owner) is dict and type(owner.get('selectors')) is dict and set(owner['selectors'])=={'primary','actor'})
    paths={target:Path(runtime.state_path(target)) for target in owner['selectors'].values()}
    roots={path.parent for path in paths.values()};originals=[]
    for subject,target in owner['selectors'].items():
        store=PrivateFeatureState(paths[target].with_name('ios-avatar-'+subject+'-feature.json'))
        value=store.read();need(type(value) is dict and type(value.get('artifactRoot')) is str)
        roots.add(Path(value['artifactRoot']));originals.append((store,deepcopy(value)))
    mutable=[item for path in paths.values() for item in (path,path.with_name('installed-code-binding.json'))]
    sdk_store=PrivateFeatureState(runtime.state_path(selector));sdk=sdk_store.read()
    installed_store=base._binding_store(selector);installed=installed_store.read()
    need(same(base.read_session(selector),sdk))
    leases=[EmoteOriginalLease(root,mutable) for root in sorted(roots)]
    membership=set();need(finalize_existing(runtime,selector,config,client,membership=membership,check=check))
    covered(directory,roots,membership)
    for store,value in originals:need(same(store.read(),value))
    rows=unpack(owner['payload']);need(len(rows)==1);binding=context(rows[0]['bindings'][role])
    scope={key:value for key,value in binding.items() if key!='processIdentity'}
    suffix='terminal-process' if rows[0]['phase']=='terminal-ready' else 'abort'
    process_store=PrivateFeatureState(directory/('ios-avatar-'+role+'-'+owner['runId']+'-'+suffix+'.json'))
    process=process_store.read();need(process_store.path in membership and process is not None and same(process['binding'],binding)
        and process['runId']==owner['runId'] and process['role']==role)
    state=unpack(process['payload']);need(len(state)==1 and state[0]['phase']==('ended' if suffix=='terminal-process' else 'aborted'))
    provenance=source(process['source']);target=base._retired_candidate_scope(selector,scope)
    need(target['appId']==process['bundleId'])
    need(same(base.read_session(selector),sdk) and same(sdk_store.read(),sdk) and same(installed_store.read(),installed))
    if sdk is not None:
        # The original final stopped check removes every launch/process flag.
        # Unknown component ownership is retained rather than erased here.
        required={'sessionId','generation','targetFingerprint'}
        need(required<=set(sdk)<=required|{'physicalTargetAttested'}
            and all(sdk[key]==binding[key] and type(sdk[key]) is type(binding[key]) for key in required)
            and ('physicalTargetAttested' not in sdk or sdk['physicalTargetAttested'] is True))
    if installed is not None:
        actual=base._avatar_retired_binding_record(selector,scope,installed)
        need(actual['phase']=='retired' and same(actual['source'],provenance)
            and actual['process']['bundleId']==process['bundleId'] and str(actual['process']['pid'])==binding['processIdentity'])
    def unchanged():
        check()
        need(same(process_store.read(),process) and same(base.read_session(selector),sdk_store.read()))
        for store,value in originals:need(same(store.read(),value))
        for lease in leases:lease.guard()
        base._retired_candidate_scope(selector,scope)
        check()
    unchanged()
    need(same(sdk_store.read(),sdk) and same(installed_store.read(),installed))
    if sdk is not None:sdk_store.discard(sdk)
    if installed is not None:installed_store.discard(installed)
    unchanged();need(base.read_session(selector) is None and installed_store.read() is None)
    return {'cleaned':True}
