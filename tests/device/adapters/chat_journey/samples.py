"""Fresh role-owned Chat native/UI/storage/remote joins, never desired facts.

Cache creation/retirement, input, peer motion/send and service control belong to
their original owners. This reader inspects already owned caches only.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import time

from adapters.native_chat_observation import NativeChatObservation, validate as chat_packet
from adapters.native_chat_view import NativeChatView, measured_view, measured_keyboard, validate as view_packet
from adapters.native_feature_observation import (NativeFeatureObservation, exact, fresh, integer,
    need, number, validate as native_packet)
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.independent_chat_receiver import binding_pid, source_identity
from adapters.script_journey.history import pack, unpack, same, MAX_FRAMES
from adapters.script_journey.lock import ScriptSourceLock
from adapters.graphics_journey.source_history import restore_native
from feature_journeys.contract import identifier, state as chat_state

VERSION = 3
SOURCES = ('primary', 'peer', 'view', 'lifecycle')


def request(value, view=False):
    return dict(schemaVersion=1, action='feature-chat-view-observe' if view else 'feature-chat-observe',
        **{key: value[key] for key in (('commandId', 'runId') if view else ('commandId', 'runId', 'operation'))})


def compose(run, frame, primary_pid, peer_pid, *, vr):
    """Recompute only historical originals; live acquisition supplies freshness.

    Native peer and primary clocks remain distinct. The live reader bounds the
    whole multi-source transaction by actual host monotonic time separately.
    """
    identifier(run)
    exact(frame, {'ticket', 'afterEpochMs', 'primaryEpochMs', 'peerEpochMs', *SOURCES} | ({'settings'} if 'settings' in frame else set()) | ({'transition'} if 'transition' in frame else set()))
    need(('settings' not in frame or frame['settings'] is True) and ('transition' not in frame or frame['transition'] is True)
        and not ('settings' in frame and 'transition' in frame))
    identifier(frame['ticket'])
    need(type(vr) is bool and integer(frame['afterEpochMs'], 1))
    p, q, view, lifecycle = (frame[key] for key in SOURCES)
    need(integer(frame['primaryEpochMs'], 1) and integer(frame['peerEpochMs'], 1))
    for value, pid, epoch in ((p, primary_pid, frame['primaryEpochMs']), (q, peer_pid, frame['peerEpochMs'])):
        chat_packet(value, request(value), pid, epoch)
        need(value['runId'] == run and value['operation'] == 'inspect' and value['source']['scopePresent']
            and not value['source']['retired'] and value['source']['droppedEvents'] == 0)
    view_packet(view, request(view, True), primary_pid, frame['primaryEpochMs'])
    need(view['runId'] == run)
    if vr:
        need(view['chatViewVersion'] == 2 and view['source']['keyboard'].get('backend') == 'native-vr-entity-keyboard')
    native_packet(lifecycle, identifier(lifecycle.get('requestId')), primary_pid, frame['primaryEpochMs'])
    epochs = [value['capturedEpochMs'] for value in (p, view, lifecycle)]
    need(min(epochs) >= frame['afterEpochMs'] and max(epochs) - min(epochs) <= 1500)
    fresh(min(epochs), frame['primaryEpochMs'])
    ps, qs, source = p['source'], q['source'], view['source']
    need(p['instance'] != q['instance'] and ps['selfSha256'] != qs['selfSha256']
        and (frame.get('transition') or ps['mixerPresent'] == qs['mixerPresent']
            and (not ps['mixerPresent'] or ps['mixerSha256'] == qs['mixerSha256'])))
    if p['chatVersion']==2 or q['chatVersion']==2:
        need(p['chatVersion']==q['chatVersion']==2)
        sessions=[value['source']['session'] for value in (p,q)]
        need(all(source['connected'] and (frame.get('transition') or source['mixerActive']==value['source']['mixerPresent']) for source,value in zip(sessions,(p,q))))
        need(sessions[0]['domainSha256']==sessions[1]['domainSha256'] and sessions[0]['instance']!=sessions[1]['instance'])
    # Storage is the accepted history; the native receive cache also contains
    # rejected distant Local packets. Neither source may manufacture UI rows.
    stored = source['storage']; ui = source['ui']
    need(stored['unowned'] == 0)
    if frame.get('transition'):
        # Actual asynchronous node/model propagation is retained as original
        # source evidence. No joined Chat state or resource verdict is emitted.
        return deepcopy(dict(transition=True,capturedEpochMs=min(epochs),lifecycle=lifecycle['lifecycle']))
    local = [row['text'] for row in stored['events'] if row['channel'] == 'local']
    domain = [row['text'] for row in stored['events'] if row['channel'] == 'domain']
    arrivals = iter(row for row in ps['events'] if row['senderSha256'] in (ps['selfSha256'], qs['selfSha256']))
    for event in stored['events']:
        need(any(row['channel'] == event['channel'] and row['text'] == event['text'] for row in arrivals))
    if ui['present']:
        need(ui['localMessages'] == local and ui['domainMessages'] == domain
            and ui['localRowCount'] == len(local) and ui['domainRowCount'] == len(domain)
            and ui['visibleRowCount'] == len(ui['visibleMessages']))
    if frame.get('settings'):
        # Internal source checkpoint only. The shared Chat state has no Settings
        # channel, so never manufacture Local/closed state for this real page.
        need(ui['present'] and ui['channel']=='settings' and ui['draft']=='' and not ui['keyboardRequested']
            and not source['editorFocused'] and not source['editorHasDraft'] and not measured_keyboard(source['keyboard'])
            and not ui['visibleMessages'] and ui['visibleRowCount']==0)
        return deepcopy(dict(settings=True,capturedEpochMs=min(epochs),lifecycle=lifecycle['lifecycle'],
            resources=['connection:chat-primary-cache','connection:chat-peer-cache','panel:chat']))
    measured = measured_view(view)
    # Preserve global actual remote arrival order and multiplicity. A local
    # fallback echo, outgoing ACK or foreign sender is never remote receipt.
    measured.update(localMessages=local, domainMessages=domain, mixerConnected=ps['mixerPresent'],
        peerMessages=[row['text'] for row in qs['events']
            if row['senderSha256'] == ps['selfSha256'] and not row['localOnly']])
    chat_state('chat', measured, run)
    resources = ['connection:chat-primary-cache', 'connection:chat-peer-cache']
    if measured['open']: resources.append('panel:chat')
    if source['editorFocused']: resources.append('input:chat-editor')
    if measured['keyboard']: resources.append('input:chat-keyboard')
    return deepcopy(dict(state=measured, capturedEpochMs=min(epochs),
        lifecycle=lifecycle['lifecycle'], resources=sorted(resources)))



def transition_ready(samples):
    """Internal qualification only; a verdict still needs a NEW full read."""
    need(isinstance(samples,ChatSamples) and samples.frames and samples.frames[-1].get('transition') is True)
    frame=deepcopy(samples.frames[-1]);del frame['transition']
    try:compose(samples.run,frame,samples.primary.pid,samples.peer.pid,vr=samples.vr)
    except NativeUIError:return False
    return True


def continuity(frames, frame):
    """Immutable source histories, queries, storage and actual mixer recovery."""
    for key in SOURCES:
        nonce = 'requestId' if key == 'lifecycle' else 'commandId'
        need(all(frame[key][nonce] != old[key][nonce] for old in frames))
    p, q = frame['primary']['source'], frame['peer']['source']
    if not frames:
        need(frame.get('transition') or p['mixerPresent'] and q['mixerPresent'])
        return
    old = frames[-1]
    need(frame['primaryEpochMs'] >= old['primaryEpochMs'] and frame['peerEpochMs'] >= old['peerEpochMs'])
    for key in SOURCES:
        value, previous = frame[key], old[key]
        need(value['instance'] == previous['instance'] and value['sequence'] > previous['sequence']
            and value['capturedEpochMs'] >= previous['capturedEpochMs'])
        if key in ('primary', 'peer'):
            current, before = value['source'], previous['source']
            need(source_identity(value) == source_identity(previous)
                and current['events'][:len(before['events'])] == before['events'])
            if 'session' in previous['source']:
                need('session' in value['source'])
                need(all(value['source']['session'][field]==previous['source']['session'][field] for field in
                    ('instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs')))
        elif key == 'view':
            need(value['chatViewVersion'] >= previous['chatViewVersion'])
            current, before = value['source'], previous['source']
            need(current['storage']['configSha256'] == before['storage']['configSha256']
                and current['storage']['events'][:len(before['storage']['events'])] == before['storage']['events'])
            if before['keyboard'].get('backend') == 'native-vr-entity-keyboard':
                need(current['keyboard'].get('backend') == 'native-vr-entity-keyboard'
                    and current['keyboard']['instance'] == before['keyboard']['instance']
                    and current['keyboard']['sequence'] > before['keyboard']['sequence'])
        else:
            need(all(value['lifecycle'][k] >= previous['lifecycle'][k] for k in previous['lifecycle']))
    # Pin the last jointly usable mixer. Half-propagated source observations
    # are allowed only in internal transition frames, never shared Chat state.
    present=[(index,row) for index,row in enumerate(frames) if row['primary']['source']['mixerPresent']
        and row['peer']['source']['mixerPresent'] and row['primary']['source']['mixerSha256']==row['peer']['source']['mixerSha256']]
    if not present:
        need(all(row.get('transition') is True for row in frames));return
    last_index,last_present=present[-1];original=last_present['primary']['source']['mixerSha256']
    absent=any(not row['primary']['source']['mixerPresent'] and not row['peer']['source']['mixerPresent']
        for row in frames[last_index+1:])
    for actual in (p,q):
        if actual['mixerPresent']:need((actual['mixerSha256']!=original) if absent else (actual['mixerSha256']==original))



class ChatSamples:
    """Durable separate primary/actor original reads; interrupted intent stays.

    Callers supply distinct bound transports and shared source locks. This
    component never opens/retires native caches, sends Chat or drops its journal.
    """
    def __init__(self, run, role, binding, peer_binding, primary, peer, view, lifecycle, store,
                 primary_lock, peer_lock, *, vr=False, component_only=False, monotonic=time.monotonic):
        need(role in ('primary', 'actor') and type(vr) is bool and type(component_only) is bool
            and callable(monotonic) and isinstance(primary, NativeChatObservation)
            and isinstance(peer, NativeChatObservation) and isinstance(view, NativeChatView)
            and isinstance(lifecycle, NativeFeatureObservation) and view.vr == vr
            and all(isinstance(lock, ScriptSourceLock) for lock in (primary_lock, peer_lock))
            and primary_lock.path != peer_lock.path)
        identifier(run)
        self.run, self.role, self.vr, self.component_only = run, role, vr, component_only
        self.binding, self.peer_binding = (deepcopy(context(v, component_only=component_only)) for v in (binding, peer_binding))
        need(primary.pid == view.pid == lifecycle.pid == binding_pid(self.binding)
            and peer.pid == binding_pid(self.peer_binding) and self.binding['targetFingerprint'] != self.peer_binding['targetFingerprint']
            and primary_lock.path == store.path.with_name('script-sources.lock')
            and not primary.ios and not peer.ios and not view.ios and not lifecycle.ios)
        self.primary, self.peer, self.view, self.lifecycle = primary, peer, view, lifecycle
        self.store, self.locks, self.monotonic = store, (primary_lock, peer_lock), monotonic
        self.previous = store.read(); self.frames = []
        self.base = dict(chatSamplesVersion=VERSION, runId=run, role=role, binding=self.binding,
            peerBinding=self.peer_binding, vr=vr, phase='ready', revision=0, transcript=pack([]))
        if self.previous is not None:
            exact(self.previous, set(self.base))
            need(all(same(self.previous[k], self.base[k]) for k in set(self.base) - {'phase', 'revision', 'transcript'})
                and self.previous['phase'] == 'ready' and integer(self.previous['revision'], 0, 2 * MAX_FRAMES))
            frames = unpack(self.previous['transcript'])
            need(self.previous['revision'] == 2 * len(frames))
            for frame in frames:
                compose(run, frame, primary.pid, peer.pid, vr=vr); continuity(self.frames, frame); self.frames.append(frame)
            self.base = deepcopy(self.previous)
        self._restore()

    def _restore(self):
        for reader in (self.primary, self.peer):
            need(reader.run is None and reader.instance is None and reader.sequence == 0 and reader.source is None)
        need(self.view.run is None and self.view.instance is None and self.view.sequence == 0)
        if not self.frames: return
        frame = self.frames[-1]
        for name, reader in (('primary', self.primary), ('peer', self.peer)):
            value = frame[name]
            reader.run, reader.instance, reader.sequence, reader.captured = self.run, value['instance'], value['sequence'], value['capturedEpochMs']
            reader.source = deepcopy(value['source'])
        value = frame['view']; reader = self.view
        reader.run, reader.instance, reader.sequence, reader.captured = self.run, value['instance'], value['sequence'], value['capturedEpochMs']
        reader.version = value['chatViewVersion']
        if self.vr:
            reader.keyboard_instance, reader.keyboard_sequence = (value['source']['keyboard'][k] for k in ('instance', 'sequence'))
        restore_native(self.lifecycle, frame['lifecycle'])

    def _write(self, value):
        need(same(self.store.read(), self.previous))
        self.store.write(value, self.previous)
        need(same(self.store.read(), value))
        self.previous = self.base = deepcopy(value)

    def read_settings(self,ticket,after_epoch):
        return self.read(ticket,after_epoch,settings=True)

    def read_transition(self,ticket,after_epoch):
        return self.read(ticket,after_epoch,transition=True)

    def read(self, ticket, after_epoch, *, settings=False, transition=False):
        started = previous = self.monotonic(); need(number(started, 0, 1e15))
        def check():
            nonlocal previous
            for reader in (self.primary, self.peer, self.view, self.lifecycle): need(reader.guard() is not False)
            now = self.monotonic(); need(number(now, 0, 1e15) and previous <= now and now - started <= 1.5); previous = now
        try:
            identifier(ticket); need(integer(after_epoch, 1) and type(settings) is bool and type(transition) is bool and not (settings and transition)); check()
            with ExitStack() as held:
                for lock in sorted(self.locks, key=lambda item: str(item.path)): held.enter_context(lock.held())
                check(); need(self.base['phase'] == 'ready' and len(self.frames) < MAX_FRAMES)
                self._write({**self.base, 'phase': 'reading', 'revision': self.base['revision'] + 1}); check()
                p = self.primary.perform(self.run, 'inspect'); check()
                view = self.view.read(self.run); check()
                q = self.peer.perform(self.run, 'inspect'); check()
                lifecycle = self.lifecycle.read(self.lifecycle.sequence); check()
                frame = dict(ticket=ticket, afterEpochMs=after_epoch, primaryEpochMs=self.primary.clock_ms(),
                    peerEpochMs=self.peer.clock_ms(), primary=p, peer=q, view=view, lifecycle=lifecycle)
                if settings:frame['settings']=True
                if transition:frame['transition']=True
                check(); measured = compose(self.run, frame, self.primary.pid, self.peer.pid, vr=self.vr)
                continuity(self.frames, frame); frames = self.frames + [deepcopy(frame)]
                self._write({**self.base, 'phase': 'ready', 'revision': self.base['revision'] + 1, 'transcript': pack(frames)})
                self.frames = frames; check(); return measured
        except Exception:
            raise NativeUIError('Chat original observation failed; unresolved source intent is retained') from None
