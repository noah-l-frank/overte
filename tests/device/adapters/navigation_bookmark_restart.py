"""Fresh original bookmark handoff after the existing one-send restart owner.

Ordinary Stop/Launch and normal Places opening stay with their original owners.
This component acquires their independent post-restart originals and transfers
only normal Delete authority. Every old input/source journal remains retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.native_feature_observation import NativeFeatureObservation, fresh, need, number
from adapters.native_location_bookmarks import NativeLocationBookmarks
from adapters.native_process_presence import NativeProcessPresence
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.restart_inputs import RestartInputs
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_places_ui import TokenPlacesUI
from feature_journeys.phase_fixture import PhaseFixtureReader

VERSION = 1


def adopt_restart(inputs, previous_store, destination_store, old_native, old_bookmark,
                  ui_factory, native, presence, bookmarks, binding, run, phase_source, lock):
    need(isinstance(inputs, RestartInputs) and not inputs.component_only
         and all(isinstance(store, PrivateFeatureState) for store in (previous_store, destination_store))
         and previous_store.path != destination_store.path
         and {previous_store.path, destination_store.path} <= {store.path for store in inputs.owners}
         and isinstance(native, NativeFeatureObservation) and isinstance(presence, NativeProcessPresence)
         and isinstance(bookmarks, NativeLocationBookmarks) and isinstance(lock, ScriptSourceLock)
         and isinstance(phase_source, PhaseFixtureReader) and phase_source.run == run
         and phase_source.area == 'world-navigation' and callable(ui_factory))
    lock.assert_held(); context(binding)
    pid = int(binding['processIdentity'].split(':')[0]); need(native.pid == presence.pid == bookmarks.pid == pid)
    started = previous = phase_source.monotonic(); requested = native.clock_ms()
    need(number(started, 0, 1e15))
    activation = phase_source.read(); need(activation['verb'] in ('open', 'bookmark-delete'))
    original = previous_store.read(); old = NavigationBookmarks.archive(original)
    need(old['runId'] == run and old['active'] is None and old.get('handoff') is None)
    plan = inputs.read(); need(plan['phase'] == 'observed' and plan['oldBinding'] == old['binding']
        and plan['newBinding'] == binding and old_bookmark['storage'] == old['lastNative']['storage'])
    existing = destination_store.read()

    def current(stamps):
        nonlocal previous
        lock.assert_held()
        need(previous_store.read() == original)
        for reader in (native, presence, bookmarks): need(reader.guard() is not False)
        phase = phase_source.read(activation['status'])
        need(phase['ticket'] == activation['ticket'] and phase['verb'] == activation['verb']
             and phase['inputs'] == activation['inputs']
             and phase['status']['activations'] == activation['status']['activations'])
        epoch = native.clock_ms(); now = phase_source.monotonic()
        need(number(now, previous, 1e15) and now - started <= 1.5 and epoch >= requested)
        previous = now; effective = max(epoch, requested + math.ceil((now - started) * 1000))
        for stamp in [*stamps, phase['status']['capturedEpochMs']]: fresh(stamp, effective)
        return effective

    if existing is not None:
        owner = NavigationBookmarks(ui_factory, bookmarks, destination_store.path, run, binding,
            monotonic=phase_source.monotonic, sleep=bookmarks.sleep)
        need(owner.state.get('handoff') is not None)
        from adapters.script_journey.history import unpack
        history = unpack(owner.state['handoff']); need(len(history) == 1 and history[0]['previous'] == original
            and history[0]['proof']['input']['ownerFiles'] == plan['ownerFiles']
            and history[0]['proof']['oldNative'] == old_native and history[0]['proof']['oldBookmark'] == old_bookmark)
        sample = owner.prepare(); current([sample['native']['capturedEpochMs'], sample['ui']['observedEpochMs']])
        need(destination_store.read() == owner.state)
        return owner

    packet = inputs.observe(binding, native)
    exited = presence.require_absent(int(old['binding']['processIdentity'].split(':')[0]))
    ui = ui_factory(lambda _value: need(False)); need(isinstance(ui, TokenPlacesUI))
    capture = ui.capture(); book = bookmarks.read(run)
    proof = dict(navigationBookmarkRestartProofVersion=1, input=inputs.read(), oldNative=deepcopy(old_native),
        native=packet, exit=exited, oldBookmark=deepcopy(old_bookmark), bookmark=book)
    sample = dict(ui=capture, page=ui.page(capture), native=book)
    proposed = NavigationBookmarks.restart_record(original, proof, sample)
    stamps = [packet['capturedEpochMs'], exited['capturedEpochMs'], capture['observedEpochMs'], book['capturedEpochMs']]
    current(stamps)
    destination_store.write(proposed, None)
    need(destination_store.read() == proposed)
    owner = NavigationBookmarks(ui_factory, bookmarks, destination_store.path, run, binding,
        monotonic=phase_source.monotonic, sleep=bookmarks.sleep)
    current(stamps)  # Original source age includes the actual durable host CAS.
    return owner
