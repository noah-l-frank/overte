"""Original historical common export, received from a known live producer.

This proves receipt and lexical ownership only. Native history, actual Witness,
image/Actor joins and final feature retirement remain the consumer's duties.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import re
import stat

from adapters.chat_journey.source_chunks import ChatSourceChunks, json_digest
from adapters.chat_journey.source_bundles import original as original_bundle, reference
from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.browser_common_export import VERSION, SAMPLE_FIELDS, PHASE_FIELDS
from adapters.pico4.browser_common_process import OriginalBrowserRunnerProcess
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.operation_protocol import dto_bytes, REQUEST_LIMIT
from adapters.script_journey.history import unpack, MAX_RAW, MAX_FRAMES, same
from feature_journeys.contract import identifier, json_document
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION

UNRESOLVED = []


class OriginalBrowserConsumptionReturn:
    """Bind the producer's initial physical pins before decoding any child.

    No search for a producer, input, clock reset, callback retry or live native
    observation occurs here. Production callers must admit their actual fixed
    common entrypoint and original parent before the first feature input.
    """
    def __init__(self, producer, request, run, fixture_url, nonce, guard):
        identifier(run); identifier(nonce)
        need(type(producer) is OriginalBrowserRunnerProcess and callable(guard)
            and fixture_url.endswith('/runs/' + run + '/'))
        self.producer = self._producer = producer
        self.external_guard = self._external_guard = guard
        self.failed = self.closure_lost = False
        self.file = self._file = None
        self.raw = self.record_raw = self.common_raw = None
        self.request = deepcopy(request)
        self.request_sha = json_digest(self.request)
        self.scope = dict(journeyConsumptionExportVersion=VERSION, contractVersion=CONTRACT_VERSION,
            area='tablet-web', runId=run, fixtureUrl=fixture_url, nonce=nonce,
            producerHostProcessIdentity=producer.process_identity)
        self.scope_sha = json_digest(self.scope)
        try:
            self.authority()
            dto_bytes(self.request, REQUEST_LIMIT, arguments=True)
            exact(self.request, {'journeyConsumptionExportVersion', 'name', 'rootSha256', 'rootStamp',
                'recordSha256', 'commonSha256', 'nonce', 'chunkPins'})
            need(type(self.request['journeyConsumptionExportVersion']) is int
                and self.request['journeyConsumptionExportVersion'] == VERSION
                and self.request['nonce'] == nonce
                and self.request['name'] == 'tablet-web-' + run + '-common-export-' + nonce + '.json')
            for key in ('rootSha256', 'recordSha256', 'commonSha256'):
                need(type(self.request[key]) is str and re.fullmatch('[0-9a-f]{64}', self.request[key]))
            stamp = self.request['rootStamp']
            need(type(stamp) is list and len(stamp) == 8
                and all(integer(value, 0, 2**64 - 1) for value in stamp))
            pins = self.request['chunkPins']
            need(type(pins) is dict and integer(pins.get('bytes'), 2, MAX_FRAMES * (8 * 21 + 3) + 4))
            decoded = unpack(pins)
            need(len(decoded) == 1 and type(decoded[0]) is list and 0 < len(decoded[0]) <= MAX_FRAMES)
            rows = decoded[0]
            for row in rows:
                need(type(row) is list and len(row) == 8
                    and all(integer(value, 0, 2**64 - 1) for value in row)
                    and integer(row[2], 1, 65536) and row[3] == os.geteuid()
                    and stat.S_ISREG(row[4]) and stat.S_IMODE(row[4]) == 0o600 and row[5] == 1)
            self.pins = tuple(tuple(row) for row in rows)
            self.store = PrivateFeatureState(producer.path / self.request['name'])
            self.file = self._file = object.__new__(LifecycleProcessFile)
            LifecycleProcessFile.__init__(self.file, self.store)
            self.file.guard(); need(self.file.file is not None)
            self.original_holders = self._original_holders = (self.file, self.store, self.file.file, self.file.parent,
                self.producer.fd_owner, self.producer.entry_owner)
            self.raw = self.file.raw
            need(list(self.file.stamp) == stamp
                and hashlib.sha256(self.raw).hexdigest() == self.request['rootSha256'])
            self.root = json_document(self.raw)
            exact(self.root, set(self.scope) | {'phase', 'chunks', 'reference'})
            need(all(same(self.root[key], value) for key, value in self.scope.items())
                and self.root['phase'] == 'sealed' and type(self.root['chunks']) is list
                and len(self.root['chunks']) == len(self.pins))
            reference(self.root['reference'])
            need(self.root['reference']['parts'] == len(self.pins)
                and self.root['reference']['sha256'] == self.request['recordSha256'])
            # Account the complete physical originals and codec/copy overlap
            # before materializing the bundled historical record. Same 16MiB.
            physical = len(self.raw) + sum(row[2] for row in self.pins)
            need(4 * physical + 5 * self.root['reference']['bytes'] + 65536 <= MAX_RAW)
            self.history = ChatSourceChunks(self.store, self.scope)
            self.history.identities = list(self.pins)
            self.history.verify()  # initial remote pins, never first-read adoption
            record, self.record_raw = self.read_record()
            exact(record, set(self.scope) | {'commonRaw', 'journey'})
            need(all(same(record[key], value) for key, value in self.scope.items())
                and type(record['commonRaw']) is str)
            self.common_raw = record['commonRaw'].encode('utf-8')
            need(hashlib.sha256(self.common_raw).hexdigest() == self.request['commonSha256'])
            common = json_document(self.common_raw)
            exact(common, {'cleanupConsumptionVersion', 'contractVersion', 'area', 'runId', 'fixtureUrl',
                'ticket', 'actionBarrierEpochMs', 'sequenceSucceeded', 'phase', 'samples', 'finalSequence'})
            need(type(common['cleanupConsumptionVersion']) is int and common['cleanupConsumptionVersion'] == 1
                and type(common['contractVersion']) is int and common['contractVersion'] == CONTRACT_VERSION
                and common['area'] == 'tablet-web' and common['runId'] == run and common['fixtureUrl'] == fixture_url)
            journey = record['journey']
            exact(journey, {'phases', 'samples', 'finalSequence', 'sequenceSucceeded'})
            need(type(journey['phases']) is list and journey['phases']
                and type(journey['samples']) is list and journey['samples']
                and type(journey['sequenceSucceeded']) is bool
                and journey['sequenceSucceeded'] is common['sequenceSucceeded']
                and integer(journey['finalSequence'], 1)
                and journey['finalSequence'] == common['finalSequence'])
            for row in journey['phases']: exact(row, set(PHASE_FIELDS))
            for row in journey['samples']: exact(row, set(SAMPLE_FIELDS))
            self.record = record
            self.guard()
        except BaseException:
            self.failed = True
            UNRESOLVED.append(self)
            raise

    def authority(self):
        need(not self.failed and self.producer is self._producer
            and self.external_guard is self._external_guard
            and json_digest(self.request) == self.request_sha and json_digest(self.scope) == self.scope_sha)
        self.external_guard(); self.producer.guard()

    def read_record(self):
        self.authority(); self.holders(); self.file.guard()
        json_digest(self.root)
        need(self.file.raw == self.raw and list(self.file.stamp) == self.request['rootStamp']
            and same(json_document(self.file.raw), self.root)
            and tuple(self.history.identities) == self.pins)
        result = original_bundle(self.history, self.root['chunks'], [self.root['reference']], 0)
        self.authority(); self.file.guard()
        return result

    def holders(self):
        need(self.file is self._file and self.original_holders is self._original_holders
            and type(self.original_holders) is tuple
            and (self.file, self.store, self.file.file, self.file.parent,
            self.producer.fd_owner, self.producer.entry_owner) == self.original_holders
            and all(current is original for current, original in zip(
                (self.file, self.store, self.file.file, self.file.parent,
                    self.producer.fd_owner, self.producer.entry_owner), self.original_holders))
            and self.file.file is self.file._file and self.file.parent is self.file._parent)

    def host_handles(self):
        """Known original pairs after their files entered the actual archive.

        This does not reopen deleted/moved source names or grant another read.
        The archive owns current immutable bytes; only these original OFDs may
        be handed to the existing final host-closure owner.
        """
        self.authority(); self.holders()
        result = self.original_holders[2:]
        for owner in result: owner.require(owner.fd)
        return result

    def guard(self):
        try:
            value, raw = self.read_record()
            json_digest(self.record)
            need(raw == self.record_raw and same(value, self.record)
                and value['commonRaw'].encode('utf-8') == self.common_raw)
            return True
        except BaseException:
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            raise

    def receipt(self):
        self.guard()
        return dict(journeyConsumptionReceivedVersion=VERSION,
            **{key:self.request[key] for key in ('nonce', 'recordSha256', 'commonSha256')})

    def close_host(self):
        if self.closure_lost: return False
        try:
            need(self.file is self._file)
            if self.file is None: return True
            if hasattr(self, 'original_holders'): self.holders()
            return self.file.close_host()
        except Exception:
            self.failed = self.closure_lost = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            return False
