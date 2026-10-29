"""Private same-SDK Actor app-original ownership, never feature effects.

Primary uses this only to release the lock before stopping a live app that the
Actor still needs to observe. No public state, readiness timestamp, current VM
fact or permission to Stop is created. Missing/foreign ownership blocks Stop.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from ios.adapters.tablet_web_app_origin import admitted

VERSION=1


def store_for(source,metadata):return PrivateFeatureState(source.root/('tabletweb-app-ready-'+source.run+'-actor-'+metadata['runId']+'.json'))


def validate(runtime,value,metadata):
    source=runtime.observer.source;source.bound()
    exact(value,{'tabletWebAppReadinessVersion','binding','runId','role','inputScope','nativeInstance','processSource','admission'})
    need(type(value['tabletWebAppReadinessVersion']) is int and value['tabletWebAppReadinessVersion']==VERSION
        and same(value['binding'],source.binding) and value['runId']==source.run and value['role']=='actor' and same(value['inputScope'],metadata)
        and value['nativeInstance']==runtime.bootstrap.original()['instance']
        and same(value['processSource'],runtime.admission['installedAfter']['source']))
    actor=None;lease=None
    from ios.adapters.tablet_web_aggregate_root import root_name,source_owner
    if os.path.lexists(source.root/root_name(source.run,'actor')):
        # Existing owned root only: freshly decode actual parent/children and
        # same-SDK app originals, never promote canonical Source3 metadata.
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        lease=EmoteOriginalLease(source.root,[])
        actor=source_owner(source.root,source.binding,source.run,'actor',source.fixture,source.pid,source.lock,
            lambda:need(False),monotonic=source.monotonic,epoch_ms=lambda:need(False),historical=True)
        need(value['admission'] in actor.state['apps'] and actor.state['appPending'] is actor.state['appIntent'] is None)
    else:
        from ios.adapters.tablet_web_source_owner import READS
        header=PrivateFeatureState(source.root/('tabletweb-source-owner-'+source.run+'-actor.json')).read()
        need(type(header) is dict and type(header.get('tabletWebSourceOwnerVersion')) is int and header['tabletWebSourceOwnerVersion'] in READS
            and same(header.get('binding'),source.binding) and header.get('runId')==source.run and header.get('role')=='actor'
            and header.get('fixtureUrl')==source.fixture and header.get('processId')==int(source.binding['processIdentity'])
            and value['admission'] in header.get('apps',[]) and header.get('appPending') is header.get('appIntent') is None)
    originals=OriginalFrameStore(source.root,source.binding,source.run,'actor',source.guard,lambda *_args:need(False),
        namespace='tabletweb-app-origins',schema_prefix='tabletWebAppAdmission',monotonic=source.monotonic)
    app=originals.read(originals.expand(value['admission']));need(same(app['owner'],metadata))
    admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],source.binding,after_epoch=app['afterEpochMs'])
    if actor is not None:
        actor._parent_guard();need(same(actor.store.read(),actor.saved));lease.guard()
    return deepcopy(value)


def retain(runtime,metadata,reference):
    source=runtime.observer.source;source.bound();need(source.role=='actor' and reference in source.state['apps'])
    value=dict(tabletWebAppReadinessVersion=VERSION,binding=deepcopy(source.binding),runId=source.run,role='actor',inputScope=deepcopy(metadata),
        nativeInstance=runtime.bootstrap.original()['instance'],processSource=deepcopy(runtime.admission['installedAfter']['source']),admission=deepcopy(reference))
    validate(runtime,value,metadata);store=store_for(source,metadata);previous=store.read()
    if previous is None:store.write(value,None)
    else:need(same(previous,value))
    need(same(store.read(),value));return deepcopy(value)


def ready(runtime,scopes):
    source=runtime.observer.source;source.bound();need(source.role=='primary')
    for metadata in scopes:
        value=store_for(source,metadata).read()
        if value is None:return False
        validate(runtime,value,metadata)
    return True
