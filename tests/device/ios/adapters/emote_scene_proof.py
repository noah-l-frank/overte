"""Original local scene preconditions; no feature projection or SDK operation.

The shared scene does not replicate the local marker. A normal camera switch
can still change the outbound avatar's skeleton offset. Both actual initial
fences must therefore exist before either camera changes, and both original
retired scene endpoints must precede restoration fences.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import validate as phase_original
from ios.adapters.emote_marker_entities import IOSEmoteMarkerEntities
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_retirement import Frozen

VERSION=1


def phase(value,run,instance,ticket,stage):
    phase_original(value,run=run,area='emotes',request=value['requestId'],epoch=value['capturedEpochMs'])
    need(value['instance']==instance and value['activations'] and value['activations'][-1]['ticket']==ticket)
    if stage=='initial':need(value['active'] and value['activations'][-1]['stimulus']['verb']!='cleanup')
    else:need(stage=='scene-retired' and value['activations'][-1]['stimulus']['verb']=='cleanup')
    return value


def _validate(value,*,stage,root,binding,run,role,instance,ticket,state_root,lock,Marker,version):
    """Replay actual immutable owners under the caller's existing source lease.

    The lease serializes this reader. It supplies no authority over the other
    target; every remote original keeps its own actual binding and inode.
    """
    need(type(version) is int and version in (1,2))
    if version==1:need(Marker is IOSEmoteMarkerScope)
    else:
        from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
        need(Marker is IOSEmoteRootedMarkerScope)
    need(stage in ('initial','scene-retired') and role in ('primary','actor'));context(binding)
    root=Path(root);identifier(run);identifier(instance);identifier(ticket);lock.assert_held()
    common={'iosEmoteSceneProofVersion','stage','phase'}
    exact(value,common|({'restoration','reference','ownerPath'} if stage=='initial' else {'scope','entities','ownerPath'}))
    need(type(value['iosEmoteSceneProofVersion']) is int and value['iosEmoteSceneProofVersion']==version and value['stage']==stage)
    phase(value['phase'],run,instance,ticket,stage)
    path=Path(value['ownerPath']);need(path.is_absolute() and path.resolve()==path and path.parent==Path(state_root))
    if stage=='initial':
        owner=IOSEmoteRestorationFrames.archive(value['restoration'],store=Frozen(path,value['restoration']),
            root=root,binding=binding,run=run,role=role,lock=lock)
        need(owner.state['pending'] is None and value['reference'] in owner.state['records'])
        original=owner.original(value['reference']);need(original['kind']=='initial' and original['phase']=='captured')
        frame,_raw=owner.frame(value['reference']);packet=frame['clockJoin']['nativeAfter']
        need(frame['clockJoin']['nativeBefore']['animation']['overrideActive'] is False and packet['animation']['overrideActive'] is False)
        # This is a genuine complete world fence, never a marker/challenge PNG
        # retitled as the unmodified initial background.
        need(not frame['worldBefore']['source']['markers'] and not frame['worldAfter']['source']['markers'])
        original_sha=digest(original)
    else:
        scope=Marker.archive(value['scope'],root=root,binding=binding,run=run,role=role,lock=lock)
        need(scope.state['phase']=='released' and scope.state['pending'] is None and scope.state['quiet'][-1]==len(scope.frames))
        first,last=scope.frames[scope.state['baseline']-1],scope.frames[-1]
        scope.components.body_preserved(first['world'],last['world']);scope.components.view_preserved(first['world'],last['world'])
        scope.ui_absent(last);scope.dialog_drained(last)
        entities=IOSEmoteMarkerEntities.archive(value['entities'],store=Frozen(path,value['entities']),
            root=root,binding=binding,run=run,role=role,lock=lock)
        entities.closed(scope);packet=entities.latest()['clockJoin']['nativeAfter']
        follow(last['clockJoin']['nativeAfter'],packet);original_sha=digest(dict(scope=value['scope'],entities=value['entities']))
    need(packet['processId']==int(binding['processIdentity']))
    return dict(stage=stage,binding=deepcopy(binding),runId=run,role=role,phaseInstance=instance,ticket=ticket,
        artifactRoot=str(root),originalSha256=original_sha,nativeEndpoint=deepcopy(packet))


def validate(value,*,stage,root,binding,run,role,instance,ticket,state_root,lock):
    return _validate(value,stage=stage,root=root,binding=binding,run=run,role=role,instance=instance,
        ticket=ticket,state_root=state_root,lock=lock,Marker=IOSEmoteMarkerScope,version=1)


def rooted(value,*,stage,root,binding,run,role,instance,ticket,state_root,lock):
    from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
    return _validate(value,stage=stage,root=root,binding=binding,run=run,role=role,instance=instance,
        ticket=ticket,state_root=state_root,lock=lock,Marker=IOSEmoteRootedMarkerScope,version=2)


def ack(value,*,root,binding,run,role,state_root,lock):
    """Actual own passive native-clock endpoint after the peer-ready read."""
    from ios.adapters.emote_keys import IOSEmoteKeys
    from ios.adapters import world_web_keys
    exact(value,{'keys','reference','ownerPath'});path=Path(value['ownerPath']);need(path.parent==Path(state_root))
    owner=IOSEmoteKeys.archive(value['keys'],store=Frozen(path,value['keys']),root=root,binding=binding,run=run,role=role,lock=lock)
    need(owner.state['pending'] is None and value['reference'] in owner.state['records'])
    original=owner.original(value['reference']);world_web_keys.drained(owner.packet(original));owner.keyboard_hidden(original)
    packet=original['clockJoin']['nativeAfter'];need(packet['animation']['overrideActive'] is False)
    return deepcopy(packet)
