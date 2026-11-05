"""Private passive World input trace; dispatch is never independent DOM effect.

The transport retains every acquired original before parsing it. Arm resolves
an existing warm focus query; observe only reads the next native-owned frame.
Neither operation generates a key, edits text, renews an attempt or retires it.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.pico4 import world_current_document as document
from adapters.pico4.world_current_input import PicoWorldCurrentInput, same, validate as validate_focus

VERSION = 1
FILE = 'feature-world-current-consumption.json'
LIMIT = 65536
HEAD = {'picoWorldCurrentConsumptionVersion', 'commandId', 'runId', 'ownerToken', 'instance', 'sequence', 'processId',
        'requestedEpochMs', 'requestedMonotonicMs', 'capturedEpochMs', 'capturedMonotonicMs', 'status', 'source'}
SOURCE = {'attemptReference', 'focusReference', 'nativeBefore', 'nativeAfter', 'lifetime', 'frame', 'availableFrames', 'terminal'}
REASONS = {'expired', 'weak-unavailable', 'authority-changed', 'source-changed', 'event-overrun', 'raw-overrun',
           'wrong-thread', 'incomplete-dispatch', 'encoding-unavailable'}
ORIGINS = {'vr-key', 'keyboard-dispatch', 'qt-key', 'qt-ime'}
UUID = r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}'


def nonce(value):
    return type(value) is str and re.fullmatch(document.HEX, value) is not None


def entity(value):
    return type(value) is str and re.fullmatch(UUID, value) is not None


def command(value):
    document.strict(value)
    arm = value.get('operation') == 'arm-current-consumption' if type(value) is dict else False
    exact(value, {'schemaVersion', 'commandId', 'action', 'runId', 'fixtureUrl', 'operation', 'ownerToken'}
          | ({'focusNonce'} if arm else {'attemptNonce', 'afterSequence'}))
    need(value['operation'] in ('arm-current-consumption', 'observe-current-consumption'))
    ref = value['focusNonce' if arm else 'attemptNonce']
    need(nonce(ref) and ref != value['commandId'])
    if not arm:
        need(integer(value['afterSequence'], 0, 16))
    base = {k: v for k, v in value.items() if k not in ('focusNonce', 'attemptNonce', 'afterSequence')}
    base['operation'] = 'observe-current-document'
    document.command(base)
    return value


def focus_original(original, pid):
    exact(original, {'raw', 'request', 'documentOriginal'})
    need(type(original['raw']) is str and len(original['raw'].encode()) <= LIMIT)
    packet = decode(original['raw'])
    validate_focus(packet, original['request'], pid, packet['capturedEpochMs'], original['documentOriginal'])
    need(original['request']['operation'] == 'observe-current-focus' and packet['status'] == 'ready'
         and packet['source']['nativeEditor']['focused'] is True)
    return packet


def u16(value):
    need(type(value) is str and len(value) <= 32768 and re.fullmatch(r'(?:[0-9a-f]{4})*', value) is not None)
    return bytes.fromhex(value)


def encoding(raw, *, unavailable=False):
    """Compare exact standard UTF-8 to original big-endian UTF-16 units.

    An unpaired surrogate is retained only as encoding-unavailable evidence;
    equality between two replacement encodings cannot qualify it.
    """
    units = u16(raw['commandUtf16Hex'])
    encoded = raw['commandUtf8Hex']
    need(type(encoded) is str and len(encoded) <= 32768 and re.fullmatch(r'(?:[0-9a-f]{2})*', encoded) is not None)
    try:
        text = units.decode('utf-16-be', errors='strict')
    except UnicodeError:
        need(unavailable)
        return
    need(unavailable or text.encode('utf-8').hex() == encoded)


def event_u16(value, *, unavailable=False):
    units = u16(value)
    try:
        units.decode('utf-16-be', errors='strict')
    except UnicodeError:
        need(unavailable)


def native(value, focus, packet, *, historical=False):
    exact(value, document.NATIVE)
    document.identity(value)
    need(same(document.semantic(value), document.semantic(focus['source']['authorityAfter']['native']))
         and integer(value['capturedMonotonicMs']) and integer(value['capturedEpochMs'], 1))
    if historical:
        need(value['capturedEpochMs'] <= packet['capturedEpochMs'] + 250)
    else:
        fresh(value['capturedEpochMs'], packet['capturedEpochMs'])
        need(packet['requestedMonotonicMs'] <= value['capturedMonotonicMs'] <= packet['capturedMonotonicMs'])


def java(value, focus, packet):
    exact(value, document.JAVA)
    document.identity(value)
    need(same(document.semantic(value), document.semantic(focus['source']['authorityAfter']['java']))
         and integer(value['capturedElapsedMs']) and integer(value['capturedEpochMs'], 1)
         and value['capturedEpochMs'] <= packet['capturedEpochMs'] + 250)


def frame_original(frame, focus, packet):
    exact(frame, {'sequence', 'eventId', 'kind', 'origin', 'epochMs', 'monotonicMs', 'raw'})
    need(integer(frame['sequence'], 1, 16) and nonce(frame['eventId']) and type(frame['origin']) is str and frame['origin'] in ORIGINS
         and integer(frame['epochMs'], 1) and integer(frame['monotonicMs'])
         and frame['epochMs'] <= packet['capturedEpochMs'] + 250
         and frame['monotonicMs'] <= packet['capturedMonotonicMs']
         and type(frame['raw']) is str and len(frame['raw'].encode()) <= 8192)
    raw = decode(frame['raw']); document.strict(raw)
    kind = frame['kind']; unavailable = packet['status'] == 'unavailable' and packet['source']['reason'] == 'encoding-unavailable'
    target = focus['source']['authorityAfter']['native']; target_id = target['sourceIdentity'][len('web-entity:'):]
    if kind == 'keyboard-event':
        exact(raw, {'keyboardObject', 'keyEntity', 'keyType', 'eventType', 'key', 'modifiers', 'textUtf16Hex', 'requestedEntity'})
        need(frame['origin'] in ('vr-key', 'keyboard-dispatch') and nonce(raw['keyboardObject'])
             and raw['eventType'] in ('press', 'release') and integer(raw['key']) and integer(raw['modifiers'])
             and raw['requestedEntity'] == target_id)
        need((entity(raw['keyEntity']) and integer(raw['keyType'])) if frame['origin'] == 'vr-key'
             else raw['keyEntity'] is None and raw['keyType'] is None)
        event_u16(raw['textUtf16Hex'], unavailable=unavailable)
    elif kind == 'application-target':
        exact(raw, {'eventType', 'requestedEntity', 'focusedBefore', 'handlerMatchesWindow', 'focusItemMatches', 'handled', 'focusedAfter'})
        need(raw['eventType'] in ('press', 'release') and entity(raw['focusedBefore'])
             and (raw['focusedAfter'] is None or entity(raw['focusedAfter']))
             and (raw['requestedEntity'] is None or raw['requestedEntity'] == target_id)
             and all(type(raw[k]) is bool for k in ('handlerMatchesWindow', 'focusItemMatches', 'handled'))
             and frame['origin'] != 'qt-ime')
    elif kind == 'native-input':
        exact(raw, {'authority', 'editor', 'eventType', 'key', 'modifiers', 'textUtf16Hex', 'commitUtf16Hex', 'preeditUtf16Hex',
                    'replacementStart', 'replacementLength', 'attributes', 'accepted'})
        native(raw['authority'], focus, packet, historical=True)
        editor = raw['editor']
        exact(editor, {'text', 'cursor', 'anchor', 'absoluteCursor', 'kind', 'sensitive', 'focused', 'enabled'})
        need(type(editor['text']) is str and editor['sensitive'] is False
             and type(editor['focused']) is bool and type(editor['enabled']) is bool
             and editor['kind'] in ('', 'text', 'url') and type(raw['accepted']) is bool)
        units = len(editor['text'].encode('utf-16-le', errors='surrogatepass')) // 2
        need(units <= 512 and all(integer(editor[k], 0, units) for k in ('cursor', 'anchor'))
             and integer(editor['absoluteCursor'], 0, 16384))
        need(type(raw['attributes']) is list and len(raw['attributes']) <= 128)
        if raw['eventType'] == 'key-press':
            need(frame['origin'] != 'qt-ime' and integer(raw['key']) and integer(raw['modifiers'])
                 and all(raw[k] is None for k in ('commitUtf16Hex', 'preeditUtf16Hex', 'replacementStart', 'replacementLength'))
                 and raw['attributes'] == [])
            event_u16(raw['textUtf16Hex'], unavailable=unavailable)
        else:
            need(raw['eventType'] == 'ime' and frame['origin'] == 'qt-ime' and all(raw[k] is None for k in ('key', 'modifiers', 'textUtf16Hex'))
                 and integer(raw['replacementStart'], -2**31, 2**31-1) and integer(raw['replacementLength'], -2**31, 2**31-1))
            event_u16(raw['commitUtf16Hex'], unavailable=unavailable)
            event_u16(raw['preeditUtf16Hex'], unavailable=unavailable)
            for item in raw['attributes']:
                exact(item, {'type', 'start', 'length'})
                need(all(integer(item[k], -2**31, 2**31-1) for k in item))
    elif kind == 'jni-command':
        exact(raw, {'handle', 'creation', 'grant', 'page', 'url', 'sourceIdentity', 'commandUtf16Hex', 'commandUtf8Hex'})
        need(all(type(raw[k]) is type(target[k]) and raw[k] == target[k] for k in ('handle', 'creation', 'grant', 'page', 'url', 'sourceIdentity')))
        encoding(raw, unavailable=unavailable)
    elif kind in ('java-entry', 'java-consume'):
        exact(raw, {'handle', 'grant', 'page', 'url', 'commandUtf16Hex', 'commandUtf8Hex'}
              | ({'isMainThread', 'capturedEpochMs', 'capturedElapsedMs'} if kind == 'java-entry' else {'before', 'after'}))
        need(all(type(raw[k]) is type(target[k]) and raw[k] == target[k] for k in ('handle', 'grant', 'page', 'url')))
        encoding(raw, unavailable=unavailable)
        if kind == 'java-entry':
            need(type(raw['isMainThread']) is bool and integer(raw['capturedEpochMs'], 1)
                 and raw['capturedEpochMs'] <= frame['epochMs'] + 250 and integer(raw['capturedElapsedMs']))
        else:
            java(raw['before'], focus, packet); java(raw['after'], focus, packet)
            need(raw['before']['capturedElapsedMs'] <= raw['after']['capturedElapsedMs']
                 and raw['before']['capturedEpochMs'] - 250 <= raw['after']['capturedEpochMs'] <= frame['epochMs'] + 250)
    else:
        need(False)
    return raw


def validate(value, request, pid, epoch, original, *, attempt=None):
    command(request); document.strict(value); exact(value, HEAD)
    focus = focus_original(original, pid)
    need(type(value['picoWorldCurrentConsumptionVersion']) is int and value['picoWorldCurrentConsumptionVersion'] == VERSION
         and all(type(value[k]) is str and value[k] == request[k] for k in ('commandId', 'runId', 'ownerToken'))
         and all(request[k] == original['request'][k] for k in ('runId', 'ownerToken', 'fixtureUrl'))
         and integer(value['processId'], 1) and value['processId'] == pid and nonce(value['instance'])
         and integer(value['sequence'], 1) and type(value['status']) is str and value['status'] in ('pending', 'ready', 'unavailable')
         and all(integer(value[k], 1) for k in ('requestedEpochMs', 'capturedEpochMs'))
         and all(integer(value[k]) for k in ('requestedMonotonicMs', 'capturedMonotonicMs'))
         and 0 <= value['capturedMonotonicMs'] - value['requestedMonotonicMs'] <= 1500)
    fresh(value['requestedEpochMs'], value['capturedEpochMs']); fresh(value['capturedEpochMs'], epoch)
    if value['status'] == 'pending':
        need(request['operation'] == 'observe-current-consumption')
        exact(value['source'], set())
        return value
    source = value['source']; unavailable = value['status'] == 'unavailable'
    exact(source, SOURCE | ({'reason'} if unavailable else set()))
    if unavailable:
        need(type(source['reason']) is str and source['reason'] in REASONS)
    exact(source['focusReference'], {'commandId', 'instance', 'sequence'})
    need(same(source['focusReference'], {k: focus[k] for k in ('commandId', 'instance', 'sequence')}))
    exact(source['attemptReference'], {'nonce', 'itemInstance', 'sourceInstance'})
    arm_nonce = request['commandId'] if request['operation'] == 'arm-current-consumption' else request['attemptNonce']
    need(source['attemptReference']['nonce'] == arm_nonce
         and source['attemptReference']['itemInstance'] == focus['source']['authorityAfter']['native']['itemInstance']
         and source['attemptReference']['sourceInstance'] == focus['instance']
         and type(source['terminal']) is bool and integer(source['availableFrames'], 0, 16))
    exact(source['lifetime'], {'itemAlive', 'contextAlive', 'windowAlive', 'receiverAlive', 'activeAttempt'})
    need(all(type(v) is bool for v in source['lifetime'].values()))
    if not unavailable:
        need(all(source['lifetime'][k] is True for k in ('itemAlive', 'contextAlive', 'windowAlive', 'receiverAlive'))
             and source['lifetime']['activeAttempt'] == (not source['terminal']))
    for side in ('nativeBefore', 'nativeAfter'):
        snapshot = source[side]
        if snapshot is None:
            need(unavailable)
        else:
            exact(snapshot, {'native', 'finish'})
            need(same(snapshot['finish'], focus['source']['originalFinish']))
            native(snapshot['native'], focus, value)
    if source['nativeBefore'] is not None and source['nativeAfter'] is not None:
        need(source['nativeBefore']['native']['capturedMonotonicMs'] <= source['nativeAfter']['native']['capturedMonotonicMs'])
    frame = source['frame']
    if request['operation'] == 'arm-current-consumption':
        need(frame is None and source['availableFrames'] == 0 and request['focusNonce'] == focus['commandId'])
    elif frame is not None:
        frame_original(frame, focus, value)
        need(frame['sequence'] == request['afterSequence'] + 1 and frame['sequence'] <= source['availableFrames'])
    else:
        need(unavailable or (source['terminal'] and request['afterSequence'] == source['availableFrames']))
    if attempt is not None:
        need(value['instance'] == attempt['instance'] and value['sequence'] > attempt['sequence']
             and value['requestedMonotonicMs'] >= attempt['requestedMonotonicMs'])
        if not unavailable:
            need(0 <= value['capturedMonotonicMs'] - attempt['requestedMonotonicMs'] <= 5000)
        if frame is not None:
            need(attempt['requestedMonotonicMs'] <= frame['monotonicMs'] <= attempt['requestedMonotonicMs'] + 5000
                 and attempt['requestedEpochMs'] - 250 <= frame['epochMs'] <= attempt['requestedEpochMs'] + 5250)
            raw = frame_original(frame, focus, value)
            originals = []
            if frame['kind'] == 'native-input':
                originals = [raw['authority']]
                need(attempt['requestedMonotonicMs'] <= raw['authority']['capturedMonotonicMs'] <= frame['monotonicMs'])
            elif frame['kind'] == 'java-entry':
                originals = [raw]
            elif frame['kind'] == 'java-consume':
                originals = [raw['before'], raw['after']]
            need(all(attempt['requestedEpochMs'] - 250 <= row['capturedEpochMs'] <= frame['epochMs'] + 250
                     for row in originals))
    return value


class PicoWorldCurrentConsumption:
    """One owned arm and strictly forward source reads over the existing lock.

    ``retain`` persists request/raw originals before any parser or refusal and
    must be supplied by the existing owner. Failure preserves issued ownership;
    this object cannot resend an uncertain query or create a replacement arm.
    """
    def __init__(self, focus, send, read, retain, *, capacity=None, resource_provider=None):
        need(type(focus) is PicoWorldCurrentInput and all(callable(f) for f in (send, read, retain))
             and (capacity is None or callable(capacity)))
        if resource_provider is not None:
            from adapters.pico4.world_current_host_stage import WorldRootCurrentParticipant2
            need(type(resource_provider) is WorldRootCurrentParticipant2)
        self.resource_provider=resource_provider
        self.focus, self.send, self.read_raw, self.retain = focus, send, read, retain
        self.capacity = capacity
        self.lock, self.guard, self.clock_ms, self.pid = focus.lock, focus.guard, focus.clock_ms, focus.pid
        self.monotonic, self.sleep = focus.monotonic, focus.sleep
        self.issued = self.failed = False
        self.arm_packet = self.focus_original = self.last = None
        self.cursor = self.queries = 0
        self.events = {}
        self._attempt_started = self._attempt_epoch = self._query_anchor = None
        self._sequence = self._available = 0

    def arm(self):
        if self.resource_provider is None:return self._arm_original()
        return self.resource_provider.trace_arm(self)

    def _arm_original(self):
        need(not self.issued and not self.failed)
        original = deepcopy(self.focus.original()); focus_original(original, self.pid)
        self.focus.require_warm(original)
        self.focus_original = original
        call = {k: original['request'][k] for k in ('schemaVersion', 'action', 'runId', 'fixtureUrl', 'ownerToken')}
        call.update(commandId=uuid.uuid4().hex, operation='arm-current-consumption', focusNonce=original['request']['commandId'])
        self.issued = True
        try:
            result = self._query(call)
            self.focus.require_warm(original)
            self.arm_packet = deepcopy(result)
            self._finish(result)
            return result
        except BaseException:
            self.failed = True
            raise

    def observe(self, after_sequence):
        if self.resource_provider is None:return self._observe_original(after_sequence)
        return self.resource_provider.trace_observe(self,after_sequence)

    def _observe_original(self, after_sequence):
        need(self.issued and not self.failed and self.arm_packet is not None
             and integer(after_sequence, 0, 16) and after_sequence == self.cursor)
        call = {k: self.focus_original['request'][k] for k in ('schemaVersion', 'action', 'runId', 'fixtureUrl', 'ownerToken')}
        call.update(commandId=uuid.uuid4().hex, operation='observe-current-consumption',
                    attemptNonce=self.arm_packet['commandId'], afterSequence=after_sequence)
        try:
            result = self._query(call)
            frame = result['source']['frame']
            if frame is not None:
                self._correlate(frame, result)
            self._finish(result)
            if frame is not None:
                self.cursor = frame['sequence']
            return result
        except BaseException:
            self.failed = True
            raise

    def _correlate(self, frame, packet):
        raw = frame_original(frame, focus_original(self.focus_original, self.pid), packet)
        event = self.events.setdefault(frame['eventId'], {})
        need(frame['kind'] not in event)
        if event:
            need(all(row[0] == frame['origin'] for row in event.values()))
        if frame['kind'] in ('java-entry', 'java-consume'):
            need('jni-command' in event)
            original = event['jni-command'][1]
            need(all(same(raw[k], original[k]) for k in ('handle', 'grant', 'page', 'url', 'commandUtf16Hex', 'commandUtf8Hex')))
            if frame['kind'] == 'java-consume':
                need('java-entry' in event)
                entry = event['java-entry'][1]
                need(entry['capturedElapsedMs'] <= raw['before']['capturedElapsedMs']
                     and entry['capturedEpochMs'] - 250 <= raw['before']['capturedEpochMs'])
        event[frame['kind']] = (frame['origin'], deepcopy(raw))

    def _query(self,call):
        if self.resource_provider is None:return self._query_original(call)
        return self.resource_provider.trace_query(self,call)

    def _query_original(self, call):
        command(call)
        need(self.lock._owner is None and self.guard() is not False and self.queries < 4096)
        started, epoch = self.monotonic(), self.clock_ms()
        need(number(started, 0, 1e15) and integer(epoch, 1))
        if call['operation'] == 'arm-current-consumption':
            self._attempt_started, self._attempt_epoch = started, epoch
        self.queries += 1
        self.retain(dict(kind='request', request=deepcopy(call), focusOriginal=deepcopy(self.focus_original)))
        if self.capacity is not None:
            self.capacity()
        with self.lock.held():
            need(self.guard() is not False)
            if call['operation'] == 'arm-current-consumption':
                self.focus.require_warm(self.focus_original)
            # Retention, lock acquisition, focus parsing and the lifetime guard
            # all precede dispatch and charge the original query/arm anchors.
            # An expired request must not create a native recorder attempt.
            current_epoch, now = self.clock_ms(), self.monotonic()
            need(number(now, started, started + 1.5))
            fresh(epoch, current_epoch)
            if self.arm_packet is not None:
                need(number(now, self._attempt_started, self._attempt_started + 5)
                     and max(current_epoch - self.arm_packet['requestedEpochMs'],
                             self._attempt_epoch - self.arm_packet['requestedEpochMs']
                             + (now - self._attempt_started) * 1000) <= 5000)
            self.send(deepcopy(call))
            latest = result = None
            for poll in range(31):
                need(self.guard() is not False)
                if self.capacity is not None:
                    self.capacity()
                    # An optional durable owner preflight charges THIS original
                    # query/attempt. It cannot renew an anchor or permit a late
                    # getter under a frozen target clock.
                    self.guard()
                    current_epoch, now = self.clock_ms(), self.monotonic()
                    need(number(now, started, started + 1.5)); fresh(epoch, current_epoch)
                    if self.arm_packet is not None:
                        need(number(now, self._attempt_started, self._attempt_started + 5)
                             and max(current_epoch - self.arm_packet['requestedEpochMs'],
                                     self._attempt_epoch - self.arm_packet['requestedEpochMs']
                                     + (now - self._attempt_started) * 1000) <= 5000)
                raw = self.read_raw()
                # Preserve malformed/foreign originals before invoking decode.
                self.retain(dict(kind='raw', request=deepcopy(call), raw=raw))
                need(type(raw) is str and len(raw.encode()) <= LIMIT)
                packet = decode(raw) if raw else None
                if type(packet) is dict and packet.get('commandId') == call['commandId']:
                    validate(packet, call, self.pid, self.clock_ms(), self.focus_original, attempt=self.arm_packet)
                    need(packet['requestedEpochMs'] >= epoch - 250)
                    if latest is not None:
                        need(packet['instance'] == latest['instance']
                             and all(packet[k] == latest[k] for k in ('requestedEpochMs', 'requestedMonotonicMs'))
                             and packet['sequence'] >= latest['sequence']
                             and packet['capturedMonotonicMs'] >= latest['capturedMonotonicMs']
                             and packet['capturedEpochMs'] >= latest['capturedEpochMs']
                             and (packet['sequence'] != latest['sequence'] or same(packet, latest)))
                    latest = deepcopy(packet)
                    need(packet['status'] != 'unavailable')
                    if packet['status'] == 'ready':
                        result = deepcopy(packet)
                        break
                now = self.monotonic()
                need(number(now, started, started + 1.5) and poll < 30)
                self.sleep(min(.05, 1.5 - (now - started)))
            need(result is not None)
        need(result['sequence'] > self._sequence and result['source']['availableFrames'] >= self._available)
        self._query_anchor = (started, epoch, deepcopy(call))
        self._finish(result)
        self.last = dict(raw=raw, request=deepcopy(call), focusOriginal=deepcopy(self.focus_original))
        self._sequence, self._available = result['sequence'], result['source']['availableFrames']
        return result

    def _finish(self, result):
        # Charge the real outer exit, full parse/copy and event correlation to
        # the original request and arm. Frozen native/host epochs cannot hide
        # cumulative host time or create a renewed five-second attempt.
        started, epoch, call = self._query_anchor
        validate(result, call, self.pid, self.clock_ms(), self.focus_original,
                 attempt=self.arm_packet if call['operation'] != 'arm-current-consumption' else None)
        need(self.guard() is not False)
        clocks = [result['requestedEpochMs'], result['capturedEpochMs']]
        clocks.extend(result['source'][side]['native']['capturedEpochMs'] for side in ('nativeBefore', 'nativeAfter'))
        finished_epoch, now = self.clock_ms(), self.monotonic()
        need(number(now, started, started + 1.5)
             and max(finished_epoch - min(clocks), epoch - min(clocks) + (now - started) * 1000) <= 1500)
        for captured in clocks:
            fresh(captured, finished_epoch)
        if self.arm_packet is not None:
            need(number(now, self._attempt_started, self._attempt_started + 5)
                 and max(finished_epoch - self.arm_packet['requestedEpochMs'],
                         self._attempt_epoch - self.arm_packet['requestedEpochMs'] + (now - self._attempt_started) * 1000) <= 5000)

    def original(self):
        need(not self.failed and self.last is not None)
        return deepcopy(self.last)
