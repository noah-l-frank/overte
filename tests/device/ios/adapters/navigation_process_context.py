"""Original Worlds source transfer across an independently proven app restart.

The first admission remains the restoration baseline. Each process owns its
own native clocks, source births and counters; none is copied into the other.
This pure validator sends no input and cannot complete or publish a restart.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit

from adapters.native_clock_join import digest,validate_join
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys.navigation_scene import validate_status as scene_status
from feature_journeys.navigation_scene import resource_root
from ios.adapters import navigation_scene_admission as admission
from ios.adapters import navigation_places_state as places,navigation_error_state as errors
from ios.adapters import navigation_product_state as product,places_model,places_http,location_bookmarks
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_restart_proof import validate as restart_proof
from ios.adapters.navigation_scene_scope import owned as owned_scene
from ios.adapters.navigation_address_inputs import transfer_original as address_original
from navigation_observation import same_viewpoint

VERSION=3
READS=(1,2,3)


def snapshot(initial,binding,value,fixture_url,*,floor=None):
    """Validate one retained read group; the provider supplies no product fact."""
    need(type(value) is dict and {'originals','clockJoin','provider','missing'}<=set(value)
        <={'originals','clockJoin','provider','missing','addressOwner','surfaceOwner'})
    raw=value['originals'];exact(raw,admission.ORIGINALS);clock=validate_join(value['clockJoin'],raw)
    need(raw['navigation']['source']['view']['mode']==initial['originals']['navigation']['source']['view']['mode'])
    basis=dict(binding=binding,runId=initial['runId'],providerInstance=initial['providerInstance'],
        providerInputs=initial['providerInputs'])
    if floor is not None:basis.update(originals=floor['originals'],clockJoin=floor['clockJoin'])
    selected,view=product.validation_view(clock,raw,{'inventory','navigation','ui'})
    scene=owned_scene(basis,selected,view,value['provider'],fixture_url,floor=floor is not None)
    selected,view=product.validation_view(clock,raw,places.ORIGINALS)
    actual=places.compose(initial['runId'],binding,selected,view,baseline=initial['bookmarkBaseline'],
        provider_inputs=initial['providerInputs'])
    need(actual['fields']['panel'] is False and actual['fields']['addressDialog'] is False
         and raw['model']['complete']
         and same(raw['model']['preferences'],initial['originals']['model']['preferences']))
    places_roots=None
    if 'surfaceOwner' in value:
        from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
        need(floor is not None)
        places_roots=NavigationSurfaceActions.retained_roots(value['surfaceOwner'],initial,raw['model'],raw['ui'],fixture_url)
    else:need(not raw['model']['roots'])
    selected,view=product.validation_view(clock,raw,errors.ORIGINALS)
    error=errors.compose(initial['runId'],binding,selected,view,missing=value['missing'])
    need(error['fields']==dict(error='none',addressDialog=False) and not raw['replies']['currentLookupActive'])
    address=None
    if 'addressOwner' in value:
        need(floor is not None)
        address=address_original(value['addressOwner'],binding,initial['runId'],raw['ui'])
    else:need(not raw['ui']['navigationInventory']['roots'])
    if floor is not None:
        for name,module in (('bookmarks',location_bookmarks),
                            ('model',places_model),('http',places_http)):
            packet=raw[name];action='feature-ios-location-bookmarks' if name=='bookmarks' else module.ACTION
            module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=action,runId=initial['runId']),
                int(binding['processIdentity']),clock['nativeAfter']['capturedEpochMs'],floor['originals'][name])
        errors.continuation(raw,floor['originals'],initial['runId'],int(binding['processIdentity']),clock['nativeAfter']['capturedEpochMs'])
    return dict(scene=scene,bookmark=places.bookmark_entries(raw['bookmarks'],initial['runId'],int(binding['processIdentity'])),
        originalsSha256=digest(raw),clockJoinSha256=digest(clock),**({} if address is None else dict(addressRoot=address)),
        **({} if places_roots is None else dict(placesRoots=places_roots)))


def transfer(initial,before,receipt,after,owner_files,fixture_url,*,version=VERSION):
    """Retain exact old baseline, actual persisted map and new source floors.

    Only an actually reloaded owned run scene is supported here. A default or
    foreign startup world requires separate fresh admission and normal entry;
    a restart acknowledgment cannot make it an owned run scene.
    """
    need(type(version) is int and version in READS)
    if version==1:need('addressOwner' not in before and 'addressOwner' not in after)
    if version<3:need('surfaceOwner' not in before and 'surfaceOwner' not in after)
    initial=admission.validate(initial);resource_root(fixture_url,initial['runId'])
    origin=urlsplit(initial['providerInputs']['sceneUrl'])
    need(fixture_url==origin.scheme+'://'+origin.netloc+'/feature-fixture/v1/runs/'+initial['runId']+'/')
    proof=restart_proof(receipt,owner_files);old,new=proof['input']['oldBinding'],proof['input']['newBinding']
    need(same(old,initial['binding']))
    left=snapshot(initial,old,before,fixture_url,floor=initial)
    follow_native(before['clockJoin']['nativeAfter'],proof['oldNative'])
    follow_native(proof['native'],after['clockJoin']['nativeBefore'])
    right=snapshot(initial,new,after,fixture_url)
    # Preserve exact original persisted semantics. A fresh new-process sample
    # must independently retain the actual old map; it cannot report a desired
    # bookmark name based on the earlier input or a fixture activation.
    need(same(left['bookmark'],right['bookmark'])
         and same_viewpoint(before['originals']['navigation']['source']['sceneUrl'],after['originals']['navigation']['source']['sceneUrl'])
         and before['clockJoin']['hostAfterMonotonic']<=after['clockJoin']['hostBeforeMonotonic']
         and before['clockJoin']['hostAfterEpochMs']<=after['clockJoin']['hostBeforeEpochMs'])
    scene_status(after['provider'],instance=initial['providerInstance'],run=initial['runId'],
        scene_url=initial['providerInputs']['sceneUrl'],previous=before['provider'])
    need(before['provider']['ticket']==after['provider']['ticket'])
    # A new source birth is mandatory for each process-local channel. The
    # persistence file's stable bytes/identity are intentionally not reset.
    for name in admission.ORIGINALS:
        need(before['originals'][name]['instance']!=after['originals'][name]['instance'])
    for source in ('sceneLoads','commitOrigin'):
        need(before['originals']['inventory']['source'][source]['instance']!=
             after['originals']['inventory']['source'][source]['instance'])
    need(before['originals']['inventory']['source']['tree']['treeInstance']!=
         after['originals']['inventory']['source']['tree']['treeInstance'])
    return dict(iosNavigationProcessContextVersion=version,initialAdmission=deepcopy(initial),
        before=deepcopy(before),restart=deepcopy(proof),after=deepcopy(after),ownerFiles=list(owner_files),
        fixtureUrl=fixture_url,oldScope=left,currentScope=right)


def validate(value,owner_files):
    exact(value,{'iosNavigationProcessContextVersion','initialAdmission','before','restart','after','ownerFiles',
        'fixtureUrl','oldScope','currentScope'})
    version=value['iosNavigationProcessContextVersion']
    need(type(version) is int and version in READS
         and same(value['ownerFiles'],list(owner_files)))
    expected=transfer(value['initialAdmission'],value['before'],value['restart'],value['after'],owner_files,value['fixtureUrl'],version=version)
    need(same(value,expected));return deepcopy(expected)


def source_basis(value,owner_files):
    """A typed new-process source basis, explicitly distinct from admission."""
    value=validate(value,owner_files);initial=value['initialAdmission'];current=value['after']
    return dict(iosNavigationProcessSourceBasisVersion=value['iosNavigationProcessContextVersion'],binding=deepcopy(value['restart']['input']['newBinding']),
        runId=initial['runId'],providerInstance=initial['providerInstance'],providerInputs=deepcopy(initial['providerInputs']),
        base=deepcopy(initial['base']),bookmarkBaseline=deepcopy(initial['bookmarkBaseline']),
        originals=deepcopy(current['originals']),clockJoin=deepcopy(current['clockJoin']),
        processContextSha256=digest(value))
