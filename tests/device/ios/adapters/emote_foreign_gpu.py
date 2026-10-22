"""Recognize a different feature's actual GPU responsibility, never its effects.

Unknown or malformed carriers remain unresolved. No native command, cleanup,
file deletion, SDK factory, or foreign target selection is permitted here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import os
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import unpack,same
from feature_journeys.contract import identifier
from feature_journeys.graphics_resources import fixture_url
from ios.adapters.emote_archive_lock import ArchiveSourceLock
from ios.adapters.emote_retirement import Frozen
from ios.adapters.graphics_configuration import settings as image_settings


def source_url(value,run):
    suffix='/runs/'+run+'/'
    need(type(value) is str and value.endswith(suffix));base=value[:-len(suffix)];fixture_url(base);return base


def scopes(directory,lock):
    result=[]
    for role in ('primary','actor'):
        store=PrivateFeatureState(directory/('ios-create-'+role+'-feature.json'));value=store.read()
        if value is not None:
            from ios.adapters.create_feature import IOSCreateFeature
            exact(value,{'iosCreateFeatureVersion','runId','role','artifactRoot','fixtureUrl','imagePolicy','payload'})
            run=identifier(value['runId']);need(value['role']==role);source_url(value['fixtureUrl'],run)
            image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')})
            owner=object.__new__(IOSCreateFeature);owner.store,owner.lock=store,lock
            owner.role,owner.run,owner.root,owner.policy=role,run,Path(value['artifactRoot']),value['imagePolicy']
            owner.phase=SimpleNamespace(fixture_url=value['fixtureUrl']);owner.load()
            result.append((run,owner.root,role,[context(owner.state['binding'])]))
    store=PrivateFeatureState(directory/'ios-graphics-feature.json');value=store.read()
    if value is not None:
        from ios.adapters.graphics_feature import IOSGraphicsFeature
        exact(value,{'iosGraphicsFeatureVersion','runId','fixtureUrl','providerInstance','artifactRoot','imagePolicy','payload'})
        run=identifier(value['runId']);base=source_url(value['fixtureUrl'],run);identifier(value['providerInstance'])
        image_settings({key:value[key] for key in ('artifactRoot','imagePolicy')});rows=unpack(value['payload']);need(len(rows)==1)
        owner=object.__new__(IOSGraphicsFeature);owner.run,owner.fixture_url=run,value['fixtureUrl']
        owner.root,owner.policy=Path(value['artifactRoot']),value['imagePolicy']
        owner.source=SimpleNamespace(instance=value['providerInstance'],client=SimpleNamespace(url=base))
        need(same(value,owner.envelope(rows[0])));state=owner.validate_control(rows[0])
        if state['binding'] is not None:result.append((run,owner.root,'primary',[context(state['binding'])]))
    for role in ('primary','actor'):
        store=PrivateFeatureState(directory/('ios-graphics-'+role+'-observer.json'));value=store.read()
        if value is not None:
            from ios.adapters.graphics_observer import IOSGraphicsObserver
            scope=IOSGraphicsObserver._archive_scope(value,path=store.path,run=value['runId'],fixture_url=value['fixtureUrl'],
                provider_instance=value['providerInstance'],role=role,lock=lock,artifact_root=value['artifactRoot'],image_policy=value['imagePolicy'])
            bindings=[context(scope.state['binding'])]
            if scope.state['restart'] is not None:bindings.append(context(scope.state['restart']['oldBinding']))
            result.append((scope.run,scope.root,role,bindings))
    return result


def ignored(directory,candidates):
    directory=Path(directory)
    metadata=[path for path in candidates if path.parent==directory and path.name.startswith('graphics-world-frame-')]
    if not metadata:return set()
    if not (directory/'script-feature-sources.lock').exists():return set()
    lock=ArchiveSourceLock(directory/'script-feature-sources.lock');result=set()
    with lock.held():
        admitted=scopes(directory,lock)
        for path in metadata:
            value=PrivateFeatureState(path).read();need(value is not None)
            exact(value,{'vulkanWorldOwnerVersion','binding','runId','role','stage','requestId','root','name',
                'ticket','phase','file','frame','absence','transcript'})
            owner=VulkanWorldFrameOwner(Frozen(path,value),Path(value['root']),value['binding'],value['runId'],value['role'],
                value['stage'],value['requestId'],lambda *_:need(False),lambda:True,source_lock=lock)
            owner._load()
            need(path.name=='graphics-world-frame-'+owner.role+'-'+str(owner.stage)+'-'+owner.request_id[4:]+'.json')
            if any(owner.run==run and owner.root==root and owner.role==role and any(same(owner.binding,b) for b in bindings)
                   for run,root,role,bindings in admitted):
                result.add(path)
                png=owner.root/owner.name
                if png in candidates:
                    # Excluding responsibility is not a PNG/effect verdict,
                    # but still requires the actual previously owned inode.
                    descriptor=os.open(png,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                    with os.fdopen(descriptor,'rb') as stream:owner._file(stream.fileno())
                    result.add(png)
            need(same(PrivateFeatureState(path).read(),value))
    return result
