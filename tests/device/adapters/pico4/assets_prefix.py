"""One retained normal Assets baseline/Open/picker/Cancel composition.

This private source DTO is deliberately smaller than a Common observation. It
cannot supply missing independent Actor, Model, byte, bake or stereo facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import os

from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks, json_digest
from adapters.chat_journey.remote_publication import _warm_signature
from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import decode, fresh, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.observer_return import parent_node, state as file_state, raw_file
from adapters.phase_input_fence import PhaseInputFence
from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
from adapters.pico4.assets_inventory import original as inventory
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.pico4.assets_uploads import PicoAssetsUploads
from adapters.pico4.assets_raw_archive import AssetsRawArchive, compact, expanded, pack_receipt, unpack_receipt
from adapters.pico4.assets_ui import project
from adapters.pico4.navigation import validate_snapshot
from adapters.script_journey.history import canonical, same, unpack, MAX_FRAMES, MAX_RAW
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_assets_ui import TokenAssetsUI
from adapters.token_create_ui import TokenCreateUI, scope
from feature_journeys.contract import VERSION as CONTRACT, arguments
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet

VERSION = 2
STEPS = ({'verb': 'open', 'inputs': {}},
         {'verb': 'upload-picker-open', 'inputs': {'resource': 'gltf-bundle/main.gltf'}},
         {'verb': 'upload-picker-cancel', 'inputs': {}})
UPLOAD_STEP={'verb':'upload','inputs':{'resource':'gltf-bundle/main.gltf'}}


class PrefixFence(PhaseInputFence):
    def original(self):
        return self.owner.original(self.owner.disk['steps'][-1]['before'])


class PicoAssetsPrefix:
    def __init__(self, path, binding, phases, source_lock, mappings, uploads,
                 raw_ui, controls, create_controls, cancel_factory, guard, clock_ms,*,upload_factory=None,receipt_layout=0):
        need(type(phases) is PhaseFixtureReader and phases.area == 'assets'
             and type(source_lock) is ScriptSourceLock
             and type(mappings) is PicoAssetsSource and not mappings.is_download and not mappings.is_resolve
             and type(uploads) is PicoAssetsUploads and mappings.pid == uploads.pid
             and all(callable(value) for value in (raw_ui, controls, create_controls, cancel_factory, guard, clock_ms))
             and (upload_factory is None or callable(upload_factory)))
        need(not mappings.history and mappings.pending is None and mappings.intent is None
             and not uploads.history and uploads.pending is None and uploads.intent is None)
        need(type(receipt_layout) is int and receipt_layout in (0,1) and (receipt_layout==0 or upload_factory is not None))
        self.receipt_layout=self.original_receipt_layout=receipt_layout
        self.store = PrivateFeatureState(path)
        self.phases, self.lock = phases, source_lock
        self.original_phase_client = phases.client
        self.binding, self.run, self.url = deepcopy(context(binding)), phases.run, phases.fixture_url
        self.pid = mappings.pid
        need(self.binding['processIdentity'].split(':')[0] == str(self.pid))
        self.mappings, self.uploads = mappings, uploads
        self.raw_ui, self.controls, self.create_controls = raw_ui, controls, create_controls
        self.cancel_factory, self.guard, self.clock_ms = cancel_factory, guard, clock_ms
        self.version=VERSION if upload_factory is None else 3
        self.recipe=STEPS if upload_factory is None else (*STEPS,UPLOAD_STEP)
        self.upload_factory,self.upload_owner=upload_factory,None
        self.wire=None;self.child_ui=None;self.upload_ui=None
        self.scope = dict(assetsPrefixVersion=self.version, assetsRawOriginalLayoutVersion=1 if self.version==2 else 2, contractVersion=CONTRACT,
                          binding=deepcopy(self.binding), runId=self.run, fixtureUrl=self.url)
        if self.version==3:self.scope.update(assetsWireOriginalLayoutVersion=1,startedMonotonic=phases.monotonic(),startedEpochMs=phases.epoch_ms(),
            producerHostProcessIdentity=host_identity())
        if self.receipt_layout:self.scope['assetsRawReceiptLayoutVersion']=1
        self.parent, self.disk, self.stamp = parent_node(self.store), None, None
        self.control_candidate=self.original_control_candidate=None
        self.history = ChatSourceChunks(self.store, self.scope)
        self.state = dict(**self.scope, phase='reading', chunks=[], bundles=[], pendingBundle=None, baseline=None,
                          steps=[], pendingSource=None, pendingChildSource=None, pendingInput=None, inputs=[], observations=0,
                          nestedFrames=0, nestedDecodedBytes=0, pendingRawRead=None, rawReads=[], cleanup=None)
        if self.version==3:self.state.update(upload=None,transportReceipts=[])
        self.raw_archive = None
        self.failed, self.child, self.last_phase, self.anchor = False, None, None, None
        self.original_sources = (mappings.original, uploads.original)
        self.fence = PrefixFence(phases)
        self.fence.owner = self
        with self.lock.held():
            need(self.store.read() is None)
            prefixes = tuple(self.store.path.name+suffix for suffix in ('.pending-', '.frame-', '.child-', '.chunk-', '.partial-'))
            with os.scandir(self.store.path.parent) as entries:
                for index, entry in enumerate(entries):
                    need(index < 4096 and not entry.name.startswith(prefixes))
            self.history.load([])  # Orphan originals forbid a new live owner.
            self.save()
            self.raw_archive = AssetsRawArchive(self)
        for role, reader, original in zip(('mappings', 'uploads'), (mappings, uploads), self.original_sources):
            send = reader.send
            reader.intent = lambda command, role=role: self.source_intent(role, command)
            reader.send = lambda command, send=send:self.send_source(command, send)
            reader.original = lambda role=role, original=original: self.raw_source(role, original)

    def bind_wire(self,adapter,target):
        # Explicit opt-in; historical/default Prefix2 factories never call it.
        from adapters.pico4.assets_wire_owner import AssetsWireOwner
        with self.lock.held():
            self.bound();need(self.wire is None)
            wire=AssetsWireOwner(self,adapter,target);self.wire=wire
            self.uploads.bind_raw_reader(lambda:wire.read('uploads'))
            # Mapping has no inner capture closure. Uploads' existing capture
            # stays above its new original reader and executes exactly once.
            self.mappings.original=lambda:self.raw_source('mappings',lambda:wire.read('mappings'))
        return self

    def scope_identity(self):
        need(type(self.receipt_layout) is int and self.receipt_layout is self.original_receipt_layout
            and self.receipt_layout in (0,1) and self.scope.get('assetsRawReceiptLayoutVersion',0)==self.receipt_layout)
        need(parent_node(self.store) == self.parent
             and self.phases.run == self.run and self.phases.area == 'assets'
             and self.phases.fixture_url == self.url and self.phases.client is self.original_phase_client
             and context(self.binding) == self.scope['binding'] and json_digest(self.scope) == self.history.scope)
        if self.version==3:need(self.scope['producerHostProcessIdentity']==host_identity())
    def identity(self):
        self.scope_identity()
        if self.disk is not None:
            if self.version==3:
                candidate=self.control_candidate
                need(candidate is self.original_control_candidate and type(candidate) is tuple and len(candidate)==4
                    and self.disk_raw==candidate[0] and self.stamp==candidate[2] and self.history.scope==candidate[3]
                    and _warm_signature(self.disk)==candidate[1])
                # Keep BOTH complete current byte/stamp windows. JSON was
                # strictly admitted at this same original control's own CAS.
                first,one=raw_file(self.store);second,two=raw_file(self.store)
                need(first==second==candidate[0] and tuple(one)==tuple(two)==candidate[2])
            else:
                value, _raw, stamp = file_state(self.store)
                need(same(value, self.disk) and tuple(stamp) == self.stamp)
        else:
            need(self.store.read() is None)
        self.history.verify()

    def archival_identity(self):
        self.scope_identity()
        raw,physical=raw_file(self.store)
        need(raw==self.disk_raw and tuple(physical)==self.stamp)
        self.history.verify()

    def bound(self):
        self.lock.assert_held()
        self.identity()

    def business(self):
        # Archival durability uses identity(), never this business-time fence.
        if self.version==3:
            need(number(self.phases.monotonic(),self.scope['startedMonotonic'],self.scope['startedMonotonic']+120)
                 and number(self.phases.epoch_ms(),self.scope['startedEpochMs'],self.scope['startedEpochMs']+120000))
            if self.upload_owner is not None:self.upload_owner.age()

    def save(self):
        self.bound()
        self.store.write(deepcopy(self.state), self.disk)
        value, _raw, stamp = file_state(self.store)
        need(same(value, self.state))
        self.disk, self.stamp, self.disk_raw = deepcopy(value), tuple(stamp), _raw
        if self.version==3:
            json_digest(value)  # Strict JSON admission, never a warm verdict.
            self.control_candidate=self.original_control_candidate=(_raw,_warm_signature(self.disk),tuple(stamp),self.history.scope)

    def archive(self, value, *, on_seal=None):
        # Fact-free archival does not query a candidate or renew source age.
        self.bound()
        need(self.disk['pendingBundle'] is None)
        need(on_seal is None or callable(on_seal))
        ref, parts = source_bundles.prepare(value, len(self.state['bundles']), self.state['bundles'])
        index = len(self.state['bundles'])
        if len(parts) > 1:
            # A single immutable part is itself a complete recoverable copy.
            # The existing reading/query intent already owns any orphan if
            # its one final root CAS is uncertain. Multi-part copies also pin
            # the complete expected reference before their first part.
            self.state['pendingBundle'] = dict(index=index, reference=deepcopy(ref),
                                               firstPart=len(self.state['chunks']))
            self.save()
        for position, part in enumerate(parts):
            self.state['chunks'] = self.history.append(part, self.state['chunks'])
            if position == len(parts)-1:
                # One final CAS transfers the complete immutable source and
                # its receipt. No issued query or raw part is lost or retried.
                self.state['bundles'].append(ref)
                self.state['pendingBundle'] = None
                if on_seal is not None:
                    on_seal(index)
            self.save()
        self.bill()
        return index

    def bill(self):
        """All retained parent copies plus the still-owned source/child copies."""
        count = len(self.state['chunks']) + self.state['nestedFrames']+len(self.state['rawReads'])
        size = source_bundles.logical_bytes(self.state['bundles']) + self.state['nestedDecodedBytes']+len(canonical(self.state['rawReads']))
        raw = dict(parts=0, bytes=0) if self.raw_archive is None else self.raw_archive.bill()
        count += raw['parts']
        size += raw['bytes']
        paths = [self.store.path, *[self.history._path(index) for index in range(len(self.history.identities))]]
        for reader in (self.mappings, self.uploads):
            count += len(reader.history)
            size += len(canonical(reader.history))
        for ui_raw in (self.child_ui,self.upload_ui):
            if ui_raw is not None:size+=ui_raw.bill(self)
        if self.child is not None:
            cancel, files = self.child.store.read(), self.child.files.store.read()
            if cancel is not None:
                paths.append(self.child.store.path)
                size += len(canonical(cancel))
                for key in ('originals', 'inputs', 'uiOriginals'):
                    count += len(unpack(cancel[key]))
                    size += cancel[key]['bytes']
            if files is not None:
                paths.append(self.child.files.store.path)
                size += len(canonical(files))
                count += len(unpack(files['originals']))
                size += files['originals']['bytes']
        if self.upload_owner is not None:
            extra=self.upload_owner.bill();count+=extra['frames'];size+=extra['decodedBytes'];paths+=extra['paths']
        need(count <= MAX_FRAMES and size <= MAX_RAW)
        return dict(frames=count, decodedBytes=size, storedBytes=sum(path.stat().st_size for path in paths)+raw['bytes'])

    def original(self, index):
        self.bound()
        return source_bundles.original(self.history, self.disk['chunks'], self.disk['bundles'], index)[0]

    def phase(self, expected, *, next_step=False):
        previous = None if self.last_phase is None else self.original(self.last_phase)
        result = self.phases.read(previous)
        # Preserve even a foreign/skipped/late activation before rejecting it.
        index = self.archive(result['status'])
        self.last_phase = index
        wanted = [{'verb': 'baseline', 'inputs': {}}, *self.recipe[:len(self.state['steps']) + int(next_step)]]
        need(result['status']['active'] and result['verb'] == expected
             and [row['stimulus'] for row in result['status']['activations']] == wanted)
        return result, index

    def command_original(self,value):
        if self.scope['assetsRawOriginalLayoutVersion']!=2 or value.get('assetsCommandOriginalVersion')!=1:
            return deepcopy(value)
        need(set(value)=={'assetsCommandOriginalVersion','bundle','bytes','sha256','commandId'}
            and type(value['assetsCommandOriginalVersion']) is int and value['assetsCommandOriginalVersion']==1)
        command=self.original(value['bundle']);raw=canonical(command)
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
            and command.get('commandId')==value['commandId'])
        return command

    def command_reference(self,command):
        if self.scope['assetsRawOriginalLayoutVersion']!=2 or len(canonical(command))<=4096:
            return deepcopy(command)
        raw=canonical(command);digest=hashlib.sha256(raw).hexdigest()
        for name in ('pendingSource','pendingChildSource'):
            pending=self.state[name]
            if pending is not None:
                ref=pending['command']
                if ref.get('assetsCommandOriginalVersion')==1 and ref['sha256']==digest:
                    need(same(self.command_original(ref),command));return deepcopy(ref)
        index=self.archive(command)
        return dict(assetsCommandOriginalVersion=1,bundle=index,bytes=len(raw),sha256=digest,commandId=command.get('commandId'))

    def source_intent(self, role, command):
        self.bound()
        need(self.disk['pendingSource'] is None)
        expected = 'baseline' if not self.state['steps'] else self.recipe[len(self.state['steps'])-1]['verb']
        self.phase(expected)
        self.query_age()
        self.state['pendingSource'] = dict(role=role, command=self.command_reference(command), raw=[])
        self.raw_archive.reserve(role, command)

    def query_age(self):
        # Reservation, original-file checks and the native clock all consume
        # the same sample window. No new authority is granted after expiry.
        self.bound()
        self.business()
        need(not self.failed and self.guard() is not False)
        started, epoch = self.query_anchor
        native = self.clock_ms()
        need(number(self.phases.monotonic(), started, started+1.5)
             and integer(native, epoch, epoch+1499))

    def send_source(self, command, send):
        need(self.disk['pendingSource'] is not None
             and same(command, self.command_original(self.disk['pendingSource']['command'])))
        self.query_age()
        return send(command) if self.wire is None else self.wire.dispatch(command,send)

    def raw_source(self, role, original):
        pending = self.disk['pendingSource']
        need(pending is not None and pending['role'] == role)
        if self.raw_archive.active is None:
            self.raw_archive.reserve(role, self.command_original(pending['command']))
        self.query_age()
        raw = original()
        if self.wire is None:
            reference = self.raw_archive.retain(raw)
            self.raw_receipt(dict(role=role,rawOriginal=compact(reference)),self.state['pendingSource']['raw'])
        else:self.wire.consume(role,raw)
        self.raw_archive.parser_capacity(raw, self.command_original(pending['command']))
        return raw

    def read_source(self, role, reader):
        value = reader.read(self.run)
        need(self.command_original(self.disk['pendingSource']['command']) == reader.history[-1]['command'])
        self.state['pendingSource'] = None
        self.save()
        self.bill()
        return value

    def complete_child_query(self, *, save=True):
        pending = self.disk['pendingChildSource']
        if pending is None:
            return
        reader = self.child_readers[pending['role']]
        need(pending['raw'] and reader.history and reader.history[-1]['command'] == self.command_original(pending['command'])
             and getattr(reader, 'pending', None) is None)
        self.state['pendingChildSource'] = None
        if save:
            self.save()

    def retain_child_queries(self):
        # Keep the existing child readers/intents/validators and their exact
        # clocks. Only fact-free archival is interposed on their original wire.
        self.child_readers = dict(mappings=self.child.mappings, uploads=self.child.uploads,
                                  files=self.child.files.native)
        for role, reader in self.child_readers.items():
            send, original = reader.send, reader.original
            if self.wire is not None:
                if type(reader) is PicoAssetsUploads:reader.bind_raw_reader(lambda role=role:self.wire.read(role))
                else:original=lambda role=role:self.wire.read(role)
            def issue(command, role=role, send=send):
                if self.wire is not None:self.query_anchor=(self.phases.monotonic(),self.clock_ms())
                self.complete_child_query(save=False)
                self.state['pendingChildSource'] = dict(role=role, command=self.command_reference(command), raw=[])
                self.raw_archive.reserve('child-'+role, command)
                if self.wire is None:send(command)
                else:self.wire.dispatch(command,send)
            def retain(role=role, original=original):
                pending = self.disk['pendingChildSource']
                need(pending is not None and pending['role'] == role)
                if self.raw_archive.active is None:
                    self.raw_archive.reserve('child-'+role, self.command_original(pending['command']))
                raw = original()
                if self.wire is None:
                    reference = self.raw_archive.retain(raw)
                    self.raw_receipt(dict(childSource=role,rawOriginal=compact(reference)),self.state['pendingChildSource']['raw'])
                else:self.wire.consume(role,raw)
                self.raw_archive.parser_capacity(raw, self.command_original(pending['command']))
                return raw
            reader.send, reader.original = issue, retain

    def intent(self, value):
        self.bound()
        need(not self.failed and self.disk['pendingInput'] is None
             and self.disk['steps'][-1]['status'] == 'issued')
        scope(value['scope'])
        need(value['scope']['processId'] == self.pid and value['scope']['instance'] == self.binding['sessionId']
             and value['action'] == 'activate' and len(self.state['inputs']) < 128)
        self.fence.mark()
        self.state['pendingInput'] = dict(reference=deepcopy(value), native=None)
        self.save()
        self.fence.check()

    def before_send(self, command, navigation):
        self.bound()
        self.fence.check()
        pending = self.disk['pendingInput']
        need(pending is not None and pending['native'] is None)
        ref = pending['reference']
        need(all(command[key] == ref[key] for key in ('controlId', 'controlToken', 'action'))
             and command['bridgeId'] == ref['scope']['instance']
             and command['generation'] == ref['scope']['generation']
             and command['sequence'] == ref['scope']['sequence'] + 1
             and command['observedElapsedMs'] == ref['scope']['elapsedMs'])
        self.state['pendingInput']['native'] = deepcopy(command)
        self.archive(deepcopy(self.state['pendingInput']), on_seal=lambda index:self.state['inputs'].append(index))
        self.fence.check()

    def consumed_intent(self, value):
        # TokenCreateUI issues its next intent only after a fresh advanced
        # original capture. Keep prior input, but never treat an ACK as a fact.
        if self.disk['pendingInput'] is not None:
            pending = self.disk['pendingInput']
            need(pending['native'] is not None
                 and value['scope']['sequence'] >= pending['native']['sequence'])
            self.state['pendingInput'] = None
            self.save()
        self.intent(value)

    def sample(self):
        self.bound()
        self.business()
        need(not self.failed and self.disk['pendingSource'] is None)
        started, epoch = self.phases.monotonic(), self.clock_ms()
        need(number(started, 0, 1e15) and integer(epoch, 1) and self.guard() is not False)
        self.query_anchor = (started, epoch)
        expected = 'baseline' if not self.state['steps'] else self.recipe[len(self.state['steps'])-1]['verb']
        before, _index = self.phase(expected)
        mapping = self.read_source('mappings', self.mappings)
        upload = self.read_source('uploads', self.uploads)
        self.phase(expected)
        need(self.guard() is not False)
        ui_command = dict(source='navigation-ui', ticket=before['ticket'])
        self.raw_archive.reserve('ui', ui_command)
        self.query_age()
        raw = self.raw_ui() if self.wire is None else self.wire.read('ui-observation')
        if self.wire is None:
            reference = self.raw_archive.retain(raw)
            ui_index = self.raw_receipt(dict(role='ui',rawOriginal=compact(reference)))
        else:ui_index=self.wire.consume('ui',raw)
        self.raw_archive.parser_capacity(raw, ui_command)
        packet = decode(raw)
        validate_snapshot(packet, self.pid, self.clock_ms())
        ui = project(packet)
        inv = inventory(packet)
        need(ui['scope']['instance'] == self.binding['sessionId'] and inv['complete']
             and all(value >= before['afterEpochMs'] for value in
                     (mapping['capturedEpochMs'], upload['capturedEpochMs'], packet['updatedEpochMs'], inv['capturedEpochMs']))
             and mapping['instance'] == upload['instance']
             and all(mapping['source'][key] == value for key, value in upload['source']['connection'].items()))
        after, _index = self.phase(expected)
        need(same(before['status']['activations'], after['status']['activations']))
        page = next((row for row in ui['controls'] if row['id'] == 'assets.page'), None)
        result = dict(assetsPrefixObservationVersion=self.version, runId=self.run, sequence=self.state['observations']+1,
                      ticket=before['ticket'], open=page is not None, picker=TokenAssetsUI.file_picker(ui) is not None,
                      sourceUi=ui_index, retained=True, completeCommonObservation=False)
        self.state['observations'] += 1
        self.save()
        self.anchor = (started, epoch, (mapping['capturedEpochMs'], upload['capturedEpochMs'], packet['updatedEpochMs']))
        self.fresh()
        return result

    def fresh(self):
        self.bound()
        self.raw_archive.verify()
        started, epoch, captures = self.anchor
        need(self.guard() is not False)
        now, native = self.phases.monotonic(), self.clock_ms()
        need(number(now, started, started+1.5) and integer(native, epoch))
        effective = max(native, epoch+math.ceil((now-started)*1000))
        for capture in captures:
            fresh(capture, effective)

    def observe(self):
        try:
            with self.lock.held():
                need(not self.failed and (not self.disk['steps'] or self.disk['steps'][-1]['status'] == 'returned'))
                result = self.sample()
                if self.state['baseline'] is None:
                    need(not result['open'] and not result['picker'])
                    self.state['baseline'] = self.last_phase
                    self.save()
            # Check after the real kernel lock exit without nesting it again.
            self.final_fresh()
            return result
        except Exception:
            self.failed = True
            raise NativeUIError('Assets prefix observation unresolved; no further query permitted') from None

    def final_fresh(self):
        need(same(self.store.read(), self.disk) and parent_node(self.store) == self.parent)
        _value, _raw, stamp = file_state(self.store)
        need(tuple(stamp) == self.stamp)
        self.history.verify()
        self.raw_archive.verify(held=False)
        need(self.guard() is not False)
        started, epoch, captures = self.anchor
        now, native = self.phases.monotonic(), self.clock_ms()
        need(number(now, started, started+1.5) and integer(native, epoch))
        for capture in captures:
            fresh(capture, max(native, epoch+math.ceil((now-started)*1000)))

    def act(self, fields):
        arguments('feature.assets.act', fields)
        # Charge the existing Upload20 window from this actual action entry,
        # including lock admission, phase storage and cold runtime creation.
        upload_started=self.phases.monotonic() if self.version==3 and self.wire is not None and fields['verb']=='upload' else None
        upload_carrier=None
        try:
            with self.lock.held():
                self.bound();self.business()
                index = len(self.disk['steps'])
                need(not self.failed and self.disk['baseline'] is not None and index < len(self.recipe)
                     and fields['runId'] == self.run and fields['fixtureUrl'] == self.url
                     and {'verb': fields['verb'], 'inputs': fields['inputs']} == self.recipe[index]
                     and (index == 0 or self.disk['steps'][-1]['status'] == 'returned'))
                phase, original = self.phase(fields['verb'], next_step=True)
                need(phase['ticket'] == fields['ticket'])
                self.state['steps'].append(dict(ticket=fields['ticket'], before=original, status='issued', result=None))
                self.save()  # No normal recipe can start before this durable reservation.
                if index == 0:
                    assets = self.controls(self.consumed_intent, before_send=self.before_send)
                    create = self.create_controls(self.consumed_intent, before_send=self.before_send)
                    need(type(assets) is TokenAssetsUI and type(create) is TokenCreateUI)
                    assets.open_assets(create)
                    actual = assets.capture()
                    pending = self.disk['pendingInput']
                    need(pending is not None and pending['native'] is not None
                         and actual['scope']['sequence'] >= pending['native']['sequence'])
                    self.archive(dict(openReceipt=deepcopy(actual)))
                    self.state['pendingInput'] = None
                    result = dict(openDelivered=True, retained=True)
                elif index==3:
                    from adapters.pico4.assets_upload_owner import OwnedAssetsUpload
                    need(self.version==3 and self.upload_owner is None)
                    if self.wire is None:self.upload_owner=self.upload_factory(self)
                    else:
                        from adapters.pico4.assets_wire_owner import AssetsChildUiRaw
                        captured=self.phases.monotonic();need(number(captured,upload_started,upload_started+20) and captured<upload_started+20)
                        epoch=self.clock_ms();completed=self.phases.monotonic()
                        need(integer(epoch,1) and number(completed,captured,upload_started+20) and completed<upload_started+20)
                        action=self.archive(dict(assetsUploadActionAnchorVersion=1,ticket=fields['ticket'],
                            startedHostMonotonic=upload_started,nativeEpochMs=epoch,
                            nativeClockStartedHostMonotonic=captured,nativeClockCompletedHostMonotonic=completed))
                        need(self.phases.monotonic()<upload_started+20)
                        self.upload_ui=upload_carrier=AssetsChildUiRaw(self,operation='upload',action_original=action)
                        self.upload_owner=self.upload_factory(self,ui_raw=self.upload_ui)
                        self.upload_ui.attach(self.upload_owner)
                    need(type(self.upload_owner) is OwnedAssetsUpload and self.upload_owner.parent is self)
                    result=self.upload_owner.run(fields)
                else:
                    if index == 1:
                        need(self.child is None)
                        if self.wire is None:self.child = self.cancel_factory()
                        else:
                            from adapters.pico4.assets_wire_owner import AssetsChildUiRaw
                            self.child_ui=AssetsChildUiRaw(self)
                            self.child=self.cancel_factory(ui_raw=self.child_ui)
                            self.child_ui.attach(self.child)
                        need(type(self.child) is OwnedAssetsCancel and self.child.run == self.run
                             and same(self.child.binding, self.binding) and self.child.url == self.url)
                        self.retain_child_queries()
                    need(self.child is not None)
                    result = self.child.open() if index == 1 else self.child.cancel()
                    self.complete_child_query()
                    self.archive_children()
                self.state['steps'][-1].update(status='returned', result=self.archive(result))
                self.save()
                self.sample()
                result = deepcopy(result)
            self.final_fresh()
            if self.version==3 and index==3:
                self.upload_owner.age();self.upload_owner.call_returned=True
            return result
        except Exception:
            self.failed = True
            # Retain the ACTUAL pre-factory carrier, not a possibly replaced
            # public holder. Its graph includes successfully opened file/raw
            # owners even when a later business/CAS boundary fails.
            if upload_carrier is not None:upload_carrier.fail()
            raise NativeUIError('Assets prefix action unresolved; no further input permitted') from None

    def archive_children(self):
        cancel, files = self.child.state(), self.child.files.store.read()
        # Copy both literal child roots under their actual physical identities.
        # Their compressed originals are charged again when decoded; do not
        # persist a redundant second decoded copy of every child transcript.
        decoded = [unpack(cancel[key]) for key in ('originals', 'inputs', 'uiOriginals')]
        decoded.append(unpack(files['originals']))
        copies = sum(len(rows) for rows in decoded)
        nested = sum(cancel[key]['bytes'] for key in ('originals', 'inputs', 'uiOriginals')) + files['originals']['bytes']
        payload = {}
        for role, store, expected in (('cancel', self.child.store, cancel), ('files', self.child.files.store, files)):
            value, raw, stamp = file_state(store)
            need(same(value, expected))
            payload[role] = dict(raw=raw.decode('utf-8'), sha256=hashlib.sha256(raw).hexdigest(), physical=list(stamp))
        need(len(self.disk['chunks']) + self.disk['nestedFrames'] + copies <= MAX_FRAMES
             and source_bundles.logical_bytes(self.disk['bundles']) + self.disk['nestedDecodedBytes']
                 + nested + len(canonical(payload)) <= MAX_RAW)
        self.state['nestedFrames'] += copies
        self.state['nestedDecodedBytes'] += nested
        self.save()
        self.archive(payload)

    def responsibility(self):
        # This is inspectable after failure. No close/cleanup phase is invented,
        # no source is queried and no surviving QObject/Model is called retired.
        with self.lock.held():
            self.bound()
            result=dict(assetsPrefixResponsibilityVersion=self.version, retained=True,
                        completedCleanup=False, failed=self.failed, owner=str(self.store.path),
                        steps=deepcopy(self.disk['steps']), pendingInput=deepcopy(self.disk['pendingInput']),
                        pendingSource=deepcopy(self.disk['pendingSource']),
                        pendingChildSource=deepcopy(self.disk['pendingChildSource']),
                        pendingBundle=deepcopy(self.disk['pendingBundle']), childOwned=self.child is not None)
            if self.version==3:result['upload']=deepcopy(self.disk['upload'])
            return result

    def literal(self, index):
        value = self.raw_record(index)
        raw=self.raw_archive.literal(expanded(value['rawOriginal'],self.store.path.name))
        if 'wireView' in value:
            from adapters.pico4.assets_wire_owner import body_view
            need(self.scope['assetsRawOriginalLayoutVersion']==2);raw=body_view(raw,value['wireView'])
        return raw

    def raw_record(self,index):
        self.bound()
        need(integer(index,0,len(self.disk['rawReads'])-1))
        value=self.disk['rawReads'][index]
        return unpack_receipt(value) if self.receipt_layout else deepcopy(value)

    def raw_receipt(self,row,receipts=None):
        index=len(self.state['rawReads'])
        self.state['rawReads'].append(pack_receipt(row) if self.receipt_layout else row)
        if receipts is not None:receipts.append(index)
        self.raw_archive.clear_intent()
        self.save()
        self.raw_archive.delivered(index)
        self.bill()
        return index
