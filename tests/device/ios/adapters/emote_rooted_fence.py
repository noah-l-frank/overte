"""Fresh passive rooted Emote fence after actual fixture retirement.

The frozen paired seal remains historical. New scope/key/pointer originals
prove that its held roots and quiet inputs still belong to this same live
process. This module cannot Stop, retire metadata, delete an SDK or declare
process death. Its result is not a process-end capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same,unpack
from feature_journeys import terminal
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_native_prefix import follow
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_pointers import IOSEmotePointers
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_marker_scope import IOSEmoteRootedMarkerScope
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_rooted_quiet import extend
from ios.adapters.emote_session_carriers import inventory


def _signature(path):
    PrivateFeatureState(path)._parent()
    try:return EmoteOriginalLease.signature(path.lstat())
    except FileNotFoundError:return None


def _current_metadata(paths,copies):
    """Frozen interpretation cannot substitute for every actual current WAL."""
    need(type(paths) is list and all(isinstance(store,PrivateFeatureState) for store in paths)
        and {str(store.path) for store in paths}==set(copies))
    signatures={}
    for store in paths:
        before=_signature(store.path)
        need(same(store.read(),copies[str(store.path)]) and _signature(store.path)==before)
        signatures[store.path]=before
    _metadata_unchanged(signatures)
    return signatures


def _metadata_unchanged(signatures,mutable=()):
    for path,signature in signatures.items():
        if path not in mutable:need(_signature(path)==signature)


def _seal(proof,seal,*,run,role,binding):
    exact(proof,{'seal','original'})
    description=proof['original']['description']
    terminal.sealed(seal,description,proof['original']['samples'])
    need(description['area']=='emotes' and description['runId']==run and role in terminal.ROLES
        and same(seal,proof['seal']) and digest(proof['original'])==seal['liveOriginalSha256']
        and same(binding_from_context(binding),description['roles'][role]['binding']))


def inactive(value,*,run,instance,ticket,after):
    """Only an original retired cleanup phase can authorize a fresh fence."""
    phase_packet(value,run=run,area='emotes',request=value['requestId'],epoch=value['capturedEpochMs'])
    need(value['active'] is False and value['instance']==instance and value['activations']
        and value['activations'][-1]['ticket']==ticket
        and value['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={})
        and number(after,1,1e15) and value['retiredEpochMs']>=after)
    return value


def current(acquisitions,native_clock,*,epoch_ms,monotonic):
    """Check four original clock spans and current host freshness, no retiming."""
    need(type(acquisitions) is list and len(acquisitions)==5)
    exact(native_clock,{'instance','before','after'})
    identifier(native_clock['instance'])
    for value in (native_clock['before'],native_clock['after']):
        exact(value,{'epochMs','monotonicMs'});need(all(number(item,0,1e15) for item in value.values()))
    first,last=acquisitions[0],acquisitions[-1]
    need(first['nativeBefore']['capturedEpochMs']<=native_clock['before']['epochMs']<=first['nativeAfter']['capturedEpochMs']
        and last['nativeBefore']['capturedEpochMs']<=native_clock['after']['epochMs']<=last['nativeAfter']['capturedEpochMs'])
    for left,right in zip(acquisitions,acquisitions[1:]):
        follow(left['nativeAfter'],right['nativeBefore'])
        need(left['hostAfterEpochMs']<=right['hostBeforeEpochMs']
            and left['hostAfterMonotonic']<=right['hostBeforeMonotonic'])
    spans=[last['hostAfterEpochMs']-first['hostBeforeEpochMs'],
        (last['hostAfterMonotonic']-first['hostBeforeMonotonic'])*1000,
        native_clock['after']['epochMs']-native_clock['before']['epochMs'],
        native_clock['after']['monotonicMs']-native_clock['before']['monotonicMs']]
    need(all(number(span,0,1500) and span<1500 for span in spans) and max(spans)-min(spans)<=250)
    epoch,mono=epoch_ms(),monotonic()
    need(number(epoch,last['hostAfterEpochMs'],first['hostBeforeEpochMs']+1500)
        and epoch-first['hostBeforeEpochMs']<1500
        and number(mono,last['hostAfterMonotonic'],first['hostBeforeMonotonic']+1.5)
        and mono-first['hostBeforeMonotonic']<1.5
        and abs(epoch-first['hostBeforeEpochMs']-(mono-first['hostBeforeMonotonic'])*1000)<=250)
    return True


def _local(scope,pointers,keys,phase,*,instance,ticket,after):
    """Local original acquisition only; this helper supplies no seal authority."""
    need(type(scope) is IOSEmoteRootedMarkerScope and type(pointers) is IOSEmotePointers
        and type(keys) is IOSEmoteKeys and type(phase) is PhaseFixtureReader
        and phase.run==scope.run and phase.area=='emotes' and phase.fixture_url==scope.fixture_url)
    need(scope.state['pending'] is pointers.state['pending'] is keys.state['pending'] is None)
    held=scope.held_originals();before=inactive(phase.status(),run=scope.run,instance=instance,ticket=ticket,after=after)
    counts={name:len(owner.state['records']) for name,owner in (('keys',keys),('pointers',pointers))}
    old_scope=scope.frames[-1]['clockJoin'];extend(scope,pointers,keys)
    # The extension's own typed owners durably append originals. Pin the
    # complete resulting local graph before reopening its bytes and before
    # another external phase read can change any contributing original.
    leases=[EmoteOriginalLease(root,[]) for root in {scope.root,scope.store.path.parent}]
    need(all(len(owner.state['records'])==counts[name]+2 for name,owner in (('keys',keys),('pointers',pointers))))
    key_rows=[keys.original(ref) for ref in keys.state['records'][-2:]]
    pointer_rows=[pointers.original(ref) for ref in pointers.state['records'][-2:]]
    latest=scope.frames[-1]['clockJoin'];follow(old_scope['nativeAfter'],latest['nativeBefore'])
    need(scope.held_originals()==held and pointers.closed(scope) and keys.closed(scope))
    acquisitions=[key_rows[0]['clockJoin'],pointer_rows[0]['clockJoin'],latest,
        pointer_rows[1]['clockJoin'],key_rows[1]['clockJoin']]
    # NativeFeatureObservation has no monotonic timestamp. Use the actual
    # same-instance global key source's native clocks, which span both key
    # reads around the pointer/scope originals; never invent a native clock.
    first_key,last_key=(keys.packet(row) for row in key_rows)
    need(first_key['source']['instance']==last_key['source']['instance'])
    native_clock=dict(instance=first_key['source']['instance'],before=deepcopy(first_key['clockBefore']),after=deepcopy(last_key['clockAfter']))
    final=inactive(phase.status(),run=scope.run,instance=instance,ticket=ticket,after=after)
    phase_packet(final,run=scope.run,area='emotes',request=final['requestId'],epoch=final['capturedEpochMs'],previous=before)
    need(before['capturedEpochMs']<=acquisitions[0]['hostBeforeEpochMs']
        and acquisitions[-1]['hostAfterEpochMs']<=final['capturedEpochMs'])
    for lease in leases:lease.guard()
    current(acquisitions,native_clock,epoch_ms=scope.epoch_ms,monotonic=scope.monotonic)
    return dict(iosEmoteRootedFenceVersion=1,runId=scope.run,role=scope.role,binding=deepcopy(scope.binding),
        phaseBefore=before,phaseAfter=final,scope=scope.snapshot(),keys=keys.store.read(),pointers=pointers.store.read(),
        held=deepcopy(held),acquisitions=deepcopy(acquisitions),nativeClock=native_clock)


def acquire(ownership,archive,seal,scope,pointers,keys,phase):
    """Join the actual frozen paired proof before acquiring any new original.

    The caller holds the actual Actor -> Primary locks. Every old immutable
    file stays pinned; only these three existing local WALs may change. New
    scoped carriers must be reached by the actual typed original readers.
    """
    need(type(ownership) is IOSEmoteRootedOwnership and type(archive) is IOSEmoteRootedFinalArchive
        and type(scope) is IOSEmoteRootedMarkerScope)
    roles=ownership.roles;need(scope.run==roles.run and scope.role in roles.locks
        and scope.lock is roles.locks[scope.role] and archive.lock is roles.locks['primary']
        and archive.primary_lock is archive.lock and archive.role=='primary')
    for lock in roles.locks.values():lock.assert_held()
    need(archive.state is not None and archive.state['phase']=='validated'
        and same(archive.store.read(),archive.previous) and same(archive.envelope(archive.state),archive.previous))
    archive.decode(archive.previous)
    copies=deepcopy(roles.copies);copies[str(ownership.path)]=deepcopy(ownership.terminal)
    need(same(archive.copies(),copies))
    mutable={scope.store.path,pointers.store.path,keys.store.path}
    metadata_signatures=_current_metadata(archive.paths,copies)
    with read_scope(fresh=True) as reads:
        proof,after=ownership.read_with_retirement_floor();_seal(proof,seal,run=scope.run,role=scope.role,binding=scope.binding)
        for owner in (scope,pointers,keys):
            need(str(owner.store.path) in copies and same(owner.store.read(),copies[str(owner.store.path)])
                and same(owner.store.read(),owner.previous) and same(owner.envelope(owner.state),owner.previous))
        role_feature=copies[str(scope.lock.path.with_name('ios-emote-'+scope.role+'-feature.json'))]
        state=unpack(role_feature['payload'])[0];instance=state['phaseInstance'];ticket=seal['description']['ticket']
        retired=inactive(archive.state['phaseOriginal'],run=scope.run,instance=instance,ticket=ticket,after=after)
        scope_held=[{key:row[key] for key in ('resource','kind','originalSha256')} for row in scope.held_originals()]
        need(same(scope_held,seal['description']['roles'][scope.role]['heldResources']))
        roots={lock.path.parent for lock in roles.locks.values()}
        for role,lock in roles.locks.items():roots.add(Path(copies[str(lock.path.with_name('ios-emote-'+role+'-feature.json'))]['artifactRoot']))
        found=inventory(roots)
        outputs={archive.store.path}|{archive.record_store(index).path for index in range(1,len(archive.paths)+1)}
        need(found<=reads|set(path.path for path in archive.paths)|outputs)
    _metadata_unchanged(metadata_signatures)
    pins={path:EmoteOriginalLease.signature(path.lstat()) for path in found-mutable}
    def unchanged():
        for lock in roles.locks.values():lock.assert_held()
        _metadata_unchanged(metadata_signatures,mutable)
        for path,signature in pins.items():
            PrivateFeatureState(path)._parent();need(EmoteOriginalLease.signature(path.lstat())==signature)
    unchanged()
    with read_scope(fresh=True) as new_reads:
        value=_local(scope,pointers,keys,phase,instance=instance,ticket=ticket,after=after)
        phase_packet(value['phaseBefore'],run=scope.run,area='emotes',request=value['phaseBefore']['requestId'],
            epoch=value['phaseBefore']['capturedEpochMs'],previous=retired)
        unchanged();need(inventory(roots)<=found|new_reads|mutable)
    value.update(archiveSha256=digest(archive.previous),sealSha256=digest(seal))
    current(value['acquisitions'],value['nativeClock'],epoch_ms=scope.epoch_ms,monotonic=scope.monotonic)
    return value
