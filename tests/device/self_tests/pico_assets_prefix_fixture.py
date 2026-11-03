"""Declared Qt/SDK/native models behind the real normal Pico Assets owners.

No compiler, native QObject, GPU, backend or device qualification is provided.
The ordinary navigation/input factories, phase reader, files/Cancel owners,
source validators and durable coordinator execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
from unittest.mock import patch

from adapters.assets_input import DIRECTORIES, NAMES
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from adapters.pico4.assets_files import NativeAssetsFiles
from adapters.pico4.assets_prefix import PicoAssetsPrefix
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.pico4.assets_uploads import PicoAssetsUploads
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client, Journal


class OriginalPhases(Client):
    def __init__(self, journal, run):
        super().__init__('http://127.0.0.1:1/feature-fixture/v1', 'h'*32)
        self.journal, self.run = journal, run

    def request(self, path, value=None, method=None, *, phase_nonce=None, **options):
        assert path == '/runs/'+self.run+'/phase' and phase_nonce is not None and value is None
        return self.journal.phase(self.run, phase_nonce)


class AssetsPrefixModel:
    def __init__(self, case, root, normal_fixture, *, manual_owner=True):
        self.case, self.root, self.normal = case, Path(root), normal_fixture
        self.adapter, self.native = normal_fixture.instance, normal_fixture.native
        self.original_read = self.native.read_debug_app_file
        self.native.opened = True
        self.clock, self.origin, self.real_time_start = 0., int(time.time()*1000), None
        self.page, self.tab, self.browser = 'home', 0, None
        self.focus, self.folder, self.selected = '', '', []
        self.calls, self.inputs, self.query_sequence = [], [], 0
        self.raw, self.lose, self.ignore, self.corrupt = '', False, False, None
        self.directory = None
        self.retired = False
        self.before_query, self.before_input = None, None
        self.after_original = None
        self.journal = Journal(clock=self.epoch)
        self.run = self.journal.register('assets')
        self.client = OriginalPhases(self.journal, self.run)
        self.url = self.client.url+'/runs/'+self.run+'/'
        self.binding = dict(sourceRevision='f'*40, artifactSha256='a'*64,
                            processIdentity=self.native.identity, sessionId=self.native.bridge_id,
                            generation=0, targetFingerprint='d'*64)
        for active in (patch.object(self.native, 'snapshot', side_effect=self.snapshot),
                       patch.object(self.native, 'read_debug_app_file', side_effect=self.read),
                       patch.object(self.native, 'write_debug_app_file', side_effect=self.write),
                       patch.object(self.native, 'epoch_milliseconds', side_effect=lambda _target: self.epoch())):
            active.start()
            case.addCleanup(active.stop)
        self.phase = PhaseFixtureReader(self.client, self.run, 'assets', epoch_ms=self.epoch, monotonic=lambda: self.clock)
        self.lock = ScriptSourceLock(self.root/'assets-original-sources.lock')
        _ui, _observe, self.binding = self.adapter._script_runtime(self.native.target)
        self.owner = None
        if manual_owner:
            self.owner = PicoAssetsPrefix(self.root/'assets-prefix.json', self.binding, self.phase, self.lock,
                self.mappings(), self.uploads(), lambda: json.dumps(self.snapshot()), self.controls, self.create_controls,
                self.cancel, self.guard, self.epoch)
            case.addCleanup(self.owner.raw_archive.close_host)

    @property
    def clock(self):
        return self._clock if getattr(self, 'real_time_start', None) is None else time.monotonic()-self.real_time_start

    @clock.setter
    def clock(self, value):
        self._clock = value

    def epoch(self):
        return self.origin+round(self.clock*1000)

    def sleep(self, seconds):
        if self.real_time_start is None:
            self.clock += seconds
        else:
            time.sleep(seconds)
        self.native.native_elapsed = 100+round(self.clock*1000)

    def guard(self):
        assert self.native.running

    def activate(self, verb, inputs=None, ticket=None):
        ticket = uuid.uuid4().hex if ticket is None else ticket
        self.journal.activate(self.run, ticket, verb, {} if inputs is None else inputs)
        return dict(contractVersion=16, runId=self.run, verb=verb, inputs={} if inputs is None else inputs,
                    ticket=ticket, fixtureUrl=self.url)

    def snapshot(self):
        self.native.native_elapsed = 100+round(self.clock*1000)
        rows = []

        def add(identifier, **fields):
            row = dict(id=identifier, enabled=True, focused=self.focus == identifier, inputReady=True) | fields
            row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps(row, sort_keys=True)))
            rows.append(row)
        if self.page == 'home':
            add('create.entry')
        elif self.page == 'create':
            add('create.page', inputReady=False, profile='native-create-v1', tab=self.tab, selectedIds=[],
                statusError=False, statusText='', componentSourceSha256='e'*64)
            add('create.tab.3')
            if self.tab == 3:
                add('create.assets')
        elif self.page == 'assets':
            add('assets.page', inputReady=False, profile='native-assets-v1', canWrite=True, canImport=True,
                busy=False, status='', selectedPath='', selectedUrl='', selection=[], selectedStatus='', treeRevision=1,
                uploadedPrimaryUrl='', uploadActive=False, pendingBundle=False)
            add('assets.upload')
            add('assets.close')
        if self.browser is not None and self.browser['rootAlive']:
            picker = dict(caption='Select an asset and its companion files', directory=Path(self.folder).as_uri() if self.folder else 'file:///tmp',
                          error='', closing=False, pendingDocuments=False, selectedUrls=deepcopy(self.selected),
                          review=False, bundleRoot='', bundleUrls=[], relativePaths=[])
            for identifier in ('assets-file.folder', 'assets-file.cancel'):
                add(identifier, picker=deepcopy(picker), **({'text':self.folder} if identifier.endswith('folder') else {}))
            if self.directory is not None and self.folder == str(self.directory/'gltf-bundle'):
                add('assets-file.row.0', picker=deepcopy(picker), sourceUrl=(self.directory/'gltf-bundle/main.gltf').as_uri(),
                    directory=False, selected=bool(self.selected))
        inventory = dict(assetsUiInventoryVersion=1, instance='b'*32, sequence=self.query_sequence+1,
                         elapsedMs=self.native.native_elapsed, capturedEpochMs=self.epoch(), complete=True,
                         browsers=[] if self.browser is None else [deepcopy(self.browser)])
        value = dict(schemaVersion=1, bridgeId=self.native.bridge_id, generation=self.native.generation,
                    processId=123, elapsedMs=self.native.native_elapsed, updatedEpochMs=self.epoch(),
                    lastCommandSequence=self.native.sequence, open=True, ready=True, featureControlsVersion=1,
                    createControlsVersion=1, assetsControlsVersion=1, assetsUiInventoryVersion=1,
                    assetsUiInventory=inventory, controls=rows)
        if any(row['id']=='create.assets' for row in rows):
            value['picoAssetsCreateControlsVersion']=1
        return value

    def read(self, target, package, path, **options):
        if Path(path).name in ('feature-pico-assets-observation.json', 'feature-pico-assets-uploads.json', 'feature-pico-assets-files.json'):
            return self.raw
        if path.endswith('navigation-ui-observation.json'):
            return json.dumps(self.snapshot())
        if path.endswith('navigation-ui-status.json'):
            return '' if self.lose else json.dumps(self.native.status)
        return self.original_read(target, package, path, **options)

    def write(self, target, package, path, raw):
        command = json.loads(raw)
        if path.endswith('android-control-command.json') and command.get('action', '').startswith('feature-pico-assets-'):
            return self.send(command)
        assert path.endswith('navigation-ui-command.json')
        if self.before_input is not None:
            self.before_input(command)
        row = next(row for row in self.snapshot()['controls'] if row['id'] == command['controlId'])
        assert row['token'] == command['controlToken'] and command['sequence'] == self.native.sequence+1
        self.inputs.append(deepcopy(command))
        self.native.sequence += 1
        identifier = command['controlId']
        if not self.ignore:
            if identifier == 'create.entry':
                self.page = 'create'
            elif identifier == 'create.tab.3':
                self.tab = 3
            elif identifier == 'create.assets':
                self.page = 'assets'
            elif identifier == 'assets.upload':
                self.browser = dict(id='1'*32, modelId='2'*32, contextId='3'*32, windowId='4'*32,
                    componentSource='qrc:/dialogs/NativeFileBrowser.qml', bornEpochMs=self.epoch(), rootAlive=True,
                    modelAlive=True, contextAlive=True, windowAlive=True, inCurrentTree=True, visible=True,
                    pendingDocuments=False, closing=False)
            elif identifier == 'assets-file.folder':
                self.focus = identifier
                if command['action'] == 'replace':
                    self.folder = command['text']
            elif identifier == 'assets-file.row.0':
                self.selected = [row['sourceUrl']]
            elif identifier == 'assets-file.cancel':
                self.browser.update(rootAlive=False, modelAlive=False, inCurrentTree=False, visible=False, closing=True)
        self.native.status = dict(schemaVersion=1, bridgeId=self.native.bridge_id, commandId=command['commandId'],
                                 sequence=command['sequence'], performed=True, error='', processId=123, updatedEpochMs=self.epoch())

    def connection(self):
        domain = '11111111-1111-4111-8111-111111111111'
        return dict(domainId=domain, sessionId='22222222-2222-4222-8222-222222222222',
            assetServerId='33333333-3333-4333-8333-333333333333', canWrite=True,
            domainSession=dict(domainSessionVersion=1, instance='c'*32, revision=1, connected=True,
                domainSha256=hashlib.sha256((self.run+':').encode()+uuid.UUID(domain).bytes).hexdigest(),
                connectionBirth='d'*32, connectedEpochMs=self.origin))

    @staticmethod
    def identity(path):
        row = path.stat()
        return dict(device=str(row.st_dev), inode=str(row.st_ino), size=str(row.st_size),
                    modifiedNs=str(row.st_mtime_ns), changedNs=str(row.st_ctime_ns))

    def files_source(self, command):
        self.directory = self.root/('feature-assets-'+self.run+'-stage1')
        operation = command['operation']
        if operation == 'stage':
            self.directory.mkdir(mode=0o700)
            for name, encoded in command['files'].items():
                path = self.directory/name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(base64.b64decode(encoded))
        elif operation == 'release':
            shutil.rmtree(self.directory)
            self.retired = True
        exists = self.directory.exists()
        return dict(assetsFilesVersion=1, exists=exists, retiring=self.retired, retired=self.retired,
            directory=self.directory.as_uri(), rootIdentity=self.identity(self.directory) if exists else None,
            directories=[dict(name=name, identity=self.identity(self.directory/name)) for name in DIRECTORIES] if exists else [],
            files=[dict(name=name, exists=True, identity=self.identity(self.directory/name),
                bytes=(self.directory/name).stat().st_size, sha256=hashlib.sha256((self.directory/name).read_bytes()).hexdigest())
                for name in NAMES] if exists else [], primaryRetired=False)

    def send(self, command):
        if self.before_query is not None:
            self.before_query(command)
        self.calls.append(deepcopy(command))
        self.query_sequence += 1
        common = dict(schemaVersion=1, requestId=command['commandId'], runId=self.run, instance='a'*32,
                      sequence=self.query_sequence, processId=123, requestedEpochMs=self.epoch(), capturedEpochMs=self.epoch())
        if command['action'] == 'feature-pico-assets-observe':
            source = dict(picoAssetsObservationVersion=1, complete=True, mappings=[], **self.connection(),
                          clientInstance='5'*32, nodeListInstance='6'*32, assetServerInstance='7'*32)
            common.update(activeRequests=0, retainedResults=0, source=source)
        elif command['action'] == 'feature-pico-assets-uploads-observe':
            common['source'] = dict(picoAssetsUploadsVersion=1, instance='8'*32, runId=self.run, valid=True, retired=False,
                activeBundles=0, liveRequests=0, retainedBundles=0, bundles=[], totalCalls=0, calls=[],
                connection=self.connection(), originalActiveBundles=0)
        else:
            assert command['action'] == 'feature-pico-assets-files'
            common.update(operation=command['operation'], source=self.files_source(command))
        if self.corrupt is not None:
            self.corrupt(common)
        self.raw = json.dumps(common)

    def mappings(self):
        return PicoAssetsSource(self.send, self.original, self.epoch, self.guard, 123,
                                monotonic=lambda:self.clock, sleep=self.sleep)

    def uploads(self):
        return PicoAssetsUploads(self.send, self.original, self.epoch, self.guard, 123,
                                 monotonic=lambda:self.clock, sleep=self.sleep)

    def original(self):
        value = self.raw
        if self.after_original is not None:
            self.after_original()
        return value

    def controls(self, intent, **options):
        return self.adapter._assets_controls(self.native.target, intent, **options)

    def create_controls(self, intent, **options):
        return self.adapter._assets_create_controls(self.native.target, intent, **options)

    def cancel(self):
        ticket = self.phase.read()['ticket']
        native = NativeAssetsFiles(self.send, self.original, self.epoch, self.guard, 123,
                                  monotonic=lambda:self.clock, sleep=self.sleep, stage=1)
        files = OwnedAssetsFiles(native, PrivateFeatureState(self.root/'assets-files.json'),
                                 self.binding, self.run, ticket, self.url)
        self.cancel_owner = OwnedAssetsCancel(PrivateFeatureState(self.root/'assets-cancel.json'), self.binding,
            self.run, self.url, files, self.mappings(), self.uploads(), self.snapshot, self.controls, self.phase,
            self.guard, self.epoch, monotonic=lambda:self.clock, sleep=self.sleep)
        return self.cancel_owner

    def canonical(self):
        # The native transport remains declared. Execute every original factory
        # and candidate/installation guard; use real advancing host time for its
        # unchanged default clocks and the actual Cancel sleep/quiet loop.
        self.real_time_start = time.monotonic()
        self.origin = int(time.time()*1000)
        self.lock = self.adapter._script_journey()._lock(self.native.target)
        with self.lock.held():
            owner = self.adapter._assets_prefix(self.native.target, self.run, self.url, self.phase, source_lock=self.lock)
        self.owner = owner
        self.case.addCleanup(owner.raw_archive.close_host)
        self.binding = deepcopy(owner.binding)
        return owner
