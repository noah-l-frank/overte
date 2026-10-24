"""Pure original decoder for one exact frozen-to-fresh rooted Emote fence.

Actual Scope/key/pointer files are independently reopened. No current clock,
SDK/native getter, retimed envelope, changed frozen copy or process action exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_rooted_fence import _seal,inactive,inactive_prefixes,clock_shape
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_rooted_quiet import validate as quiet_original


def phase_link(value,seal,*,run,role,binding,instance,floor,retired,archive_sha):
    """Join an original fence to the already qualified paired proof context."""
    need(value['runId']==run and value['role']==role and same(value['binding'],binding)
        and value['archiveSha256']==archive_sha and value['sealSha256']==digest(seal))
    ticket=seal['description']['ticket']
    inactive(retired,run=run,instance=instance,ticket=ticket,after=floor)
    for phase in (value['phaseBefore'],value['phaseAfter']):inactive(phase,run=run,instance=instance,ticket=ticket,after=floor)
    phase_packet(value['phaseBefore'],run=run,area='emotes',request=value['phaseBefore']['requestId'],epoch=value['phaseBefore']['capturedEpochMs'],previous=retired)
    phase_packet(value['phaseAfter'],run=run,area='emotes',request=value['phaseAfter']['requestId'],epoch=value['phaseAfter']['capturedEpochMs'],previous=value['phaseBefore'])
    need(same([{key:row[key] for key in ('resource','kind','originalSha256')} for row in value['held']],seal['description']['roles'][role]['heldResources'])
        and value['phaseBefore']['capturedEpochMs']<=value['acquisitions'][0]['hostBeforeEpochMs']
        and value['acquisitions'][-1]['hostAfterEpochMs']<=value['phaseAfter']['capturedEpochMs'])


def local(value,copies,*,root,binding,run,role,lock,retirement=None):
    """Decode exact local appends only; caller separately qualifies paired seal."""
    exact(value,{'iosEmoteRootedFenceVersion','runId','role','binding','phaseBefore','phaseAfter','scope','keys','pointers','held',
        'acquisitions','nativeClock','archiveSha256','sealSha256'})
    need(type(value['iosEmoteRootedFenceVersion']) is int and value['iosEmoteRootedFenceVersion']==1
        and value['runId']==run and value['role']==role and same(value['binding'],binding))
    lock.assert_held();root=Path(root);objects={};metadata={}
    for name,cls in (('scope',IOSEmoteRootedMarkerScope),('keys',IOSEmoteKeys),('pointers',IOSEmotePointers)):
        path=lock.path.with_name('ios-emote-'+role+'-'+('marker' if name=='scope' else name)+'.json')
        need(str(path) in copies and type(copies[str(path)]) is dict)
        if retirement is None:need(same(PrivateFeatureState(path).read(),value[name]))
        else:
            from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
            need(type(retirement) is IOSEmoteRootedEndArchive)
            need(same(retirement.store_for(path,value[name]).read(),value[name]))
        if name=='scope':
            old=cls.archive(copies[str(path)],root=root,binding=binding,run=run,role=role,lock=lock)
            new=cls.archive(value[name],root=root,binding=binding,run=run,role=role,lock=lock)
            need(len(new.frames)==len(old.frames)+1 and same(new.frames[:-1],old.frames)
                and same(new.state,dict(old.state,revision=old.state['revision']+1,manifests=new.state['manifests'],
                    quiet=old.state['quiet']+[len(new.frames)]))
                and new.frames[-1]['label']=='rooted-retirement-fresh-end')
            old_entries=[entry for ref in old.state['manifests'] for entry in old.originals.manifest(ref)]
            new_entries=[entry for ref in new.state['manifests'] for entry in new.originals.manifest(ref)]
            need(same(new_entries[:-1],old_entries) and len(new_entries)==len(old_entries)+1)
            need(same(new.held_originals(),old.held_originals()) and same(new.held_originals(),value['held']))
            quiet_original(new,new.frames[-1],old.frames[old.state['quiet'][-1]-1])
        else:
            store=PrivateFeatureState(path)
            old=cls.archive(copies[str(path)],store=store,root=root,binding=binding,run=run,role=role,lock=lock)
            new=cls.archive(value[name],store=store,root=root,binding=binding,run=run,role=role,lock=lock)
            need(old.state['pending'] is new.state['pending'] is None and len(new.state['records'])==len(old.state['records'])+2
                and same(new.state['records'][:-2],old.state['records']))
            expected=dict(old.state,records=new.state['records'])
            if name=='keys':
                expected['serial']=new.state['serial']
                indices={wire['index'] for ref in new.state['records'][-2:] for wire in new.original(ref)['wires']}
                need(indices==set(range(old.state['serial']+1,new.state['serial']+1)))
            need(same(new.state,expected))
        new.store,new.previous=PrivateFeatureState(path),deepcopy(value[name]);objects[name]=new;metadata[path]=deepcopy(value[name])
    scope,keys,pointers=(objects[name] for name in ('scope','keys','pointers'))
    need(keys.closed(scope) and pointers.closed(scope))
    key_rows=[keys.original(ref) for ref in keys.state['records'][-2:]]
    pointer_rows=[pointers.original(ref) for ref in pointers.state['records'][-2:]]
    acquisitions=[key_rows[0]['clockJoin'],pointer_rows[0]['clockJoin'],scope.frames[-1]['clockJoin'],pointer_rows[1]['clockJoin'],key_rows[1]['clockJoin']]
    first,last=[keys.packet(row) for row in key_rows];need(first['source']['instance']==last['source']['instance'])
    native_clock=dict(instance=first['source']['instance'],before=first['clockBefore'],after=last['clockAfter'])
    need(same(acquisitions,value['acquisitions']) and same(native_clock,value['nativeClock']));clock_shape(acquisitions,native_clock)
    return dict(metadata=metadata,scope=scope,keys=keys,pointers=pointers)


def validate(value,ownership,archive,seal,*,retirement=None):
    need(type(ownership) is IOSEmoteRootedOwnership and type(archive) is IOSEmoteRootedFinalArchive)
    roles=ownership.roles
    for lock in roles.locks.values():lock.assert_held()
    need(archive.state is not None and archive.state['phase']=='validated' and same(archive.store.read(),archive.previous)
        and same(archive.envelope(archive.state),archive.previous))
    archive.decode(archive.previous);copies=deepcopy(roles.copies);copies[str(ownership.path)]=deepcopy(ownership.terminal)
    need(same(archive.copies(),copies) and value['archiveSha256']==digest(archive.previous) and value['sealSha256']==digest(seal))
    if retirement is not None:
        from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
        need(type(retirement) is IOSEmoteRootedEndArchive and retirement.archive is archive
            and retirement.ownership is ownership and same(retirement.seal,seal))
        retirement.bound()
    proof,floor,prefixes=ownership.read_with_retirement_context();role=value['role'];lock=roles.locks[role]
    inactive_prefixes(archive.state['phaseOriginal'],prefixes,run=roles.run)
    feature=copies[str(lock.path.with_name('ios-emote-'+role+'-feature.json'))]
    from adapters.script_feature.history import unpack
    state=unpack(feature['payload'])[0];binding=state['binding'];instance=state['phaseInstance'];ticket=seal['description']['ticket']
    _seal(proof,seal,run=roles.run,role=role,binding=binding)
    phase_link(value,seal,run=roles.run,role=role,binding=binding,instance=instance,floor=floor,
        retired=archive.state['phaseOriginal'],archive_sha=digest(archive.previous))
    result=local(value,copies,root=feature['artifactRoot'],binding=binding,run=roles.run,role=role,lock=lock,retirement=retirement)
    return result
