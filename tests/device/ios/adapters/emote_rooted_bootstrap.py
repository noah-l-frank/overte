"""Read retained role configuration before the complete historical verifier.

The copied configuration only permits constructing a passive typed reader.
It is not a process/resource absence proof and authorizes no lifecycle input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.graphics_resources import fixture_url
from feature_journeys.witness import Client
from ios.adapters.emote_configuration import settings
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_rooted_end_lock import held_existing
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive


def forbidden(*_args,**_kwargs):need(False)


def passive(url,run):
    identifier(run);need(type(url) is str and url.endswith('/runs/'+run+'/'))
    base=url[:-len('/runs/'+run+'/')];fixture_url(base)
    client=object.__new__(Client);client.url=base;client.request=forbidden;return client


def primary(runtime,selector,run,chosen,*,monotonic=None,epoch_ms=None,sleep=None):
    """Reopen exact saved configuration, then construct no live components."""
    chosen=settings(chosen,role='primary',target=selector);identifier(run)
    directory=runtime.state_path(selector).parent;peer_directory=runtime.state_path(chosen['actorTarget']).parent
    root=Path(chosen['artifactRoot']);lock=ScriptSourceLock(directory/'script-feature-sources.lock')
    actor_lock=ScriptSourceLock(peer_directory/'script-feature-sources.lock')
    store=PrivateFeatureState(directory/('ios-emote-primary-'+run+'-rooted-final.json'))
    with held_existing(actor_lock),held_existing(lock):
        leases=[EmoteOriginalLease(path,[]) for path in {root,directory,peer_directory}]
        def check():
            lock.assert_held();actor_lock.assert_held()
            for lease in leases:lease.guard()
            return True
        value=store.read();exact(value,{'iosEmoteRootedFinalArchiveVersion','runId','role','binding','artifactRoot','paths','payload'})
        need(type(value['iosEmoteRootedFinalArchiveVersion']) is int and value['iosEmoteRootedFinalArchiveVersion']==1
            and value['runId']==run and value['role']=='primary' and value['artifactRoot']==str(root)
            and type(value['paths']) is list and 1<=len(value['paths'])<=256)
        binding=context(value['binding']);paths=[]
        for name in value['paths']:
            need(type(name) is str);path=Path(name)
            need(path.is_absolute() and path.resolve()==path and path.parent in {directory,peer_directory})
            paths.append(PrivateFeatureState(path))
        # The actual archive type checks its literal metadata, original copy
        # hashes/indices/paths and inactive phase. Its effect qualifier is
        # deliberately unavailable here; full verification follows separately.
        archive=IOSEmoteRootedFinalArchive(store,root,binding,run,'primary',lock,lock,paths,check,forbidden)
        need(archive.state is not None and archive.state['phase']=='validated')
        feature=archive.copies().get(str(directory/'ios-emote-primary-feature.json'))
        exact(feature,{'iosEmoteFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
        need(type(feature['iosEmoteFeatureVersion']) is int and feature['iosEmoteFeatureVersion']==2
            and feature['runId']==run and feature['role']=='primary' and feature['artifactRoot']==str(root)
            and same(feature['imagePolicy'],chosen['imagePolicy']))
        client=passive(feature['fixtureUrl'],run);check();need(same(store.read(),value))
    clocks={key:fn for key,fn in (('monotonic',monotonic),('epoch_ms',epoch_ms),('sleep',sleep)) if fn is not None}
    return IOSEmoteRootedFeature(runtime,selector,client,run,'primary',root,chosen['imagePolicy'],
        actor_selector=chosen['actorTarget'],**clocks)
