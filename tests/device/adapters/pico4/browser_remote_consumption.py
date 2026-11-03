"""Common cleanup consumption from the original separately owned runner.

The received Journey projection is historical data. It is never instantiated
as a Journey or returned as a fresh native observation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import ChatSourceChunks, json_digest
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_cleanup_consumption import PicoBrowserCleanupConsumption
from adapters.pico4.browser_common_export import SAMPLE_FIELDS, PHASE_FIELDS
from adapters.pico4.browser_common_return import OriginalBrowserConsumptionReturn
from adapters.script_journey.history import canonical, same
from feature_journeys.contract import json_document

VERSION = 2
UNRESOLVED = []


class PicoBrowserRemoteCleanupConsumption(PicoBrowserCleanupConsumption):
    """Same primary history, final clocks and existing bounded consumption root."""
    def __init__(self, primary):
        super().__init__(primary)
        self.returned = self._returned = None

    def attach(self, _journey):
        need(False)  # This explicit version consumes the actual cross-process return.

    @staticmethod
    def methods(returned):
        need(type(returned) is OriginalBrowserConsumptionReturn)
        for name in ('guard', 'receipt', 'read_record', 'authority', 'holders', 'host_handles'):
            need(getattr(getattr(returned, name), '__func__', None)
                is getattr(OriginalBrowserConsumptionReturn, name))

    def consume(self, returned):
        try:
            need(not self.started and not self.failed)
            self.started = True
            need(type(returned) is OriginalBrowserConsumptionReturn
                and self.returned is self._returned is None)
            self.methods(returned)
            returned.guard()
            self.returned = self._returned = returned
            f = self.primary
            need(returned.scope['runId'] == f.run and returned.scope['fixtureUrl'] == f.fixture_url)
            raw = returned.common_raw
            value = json_document(raw)
            projected = returned.record['journey']
            json_digest(value); json_digest(projected)
            need(type(value['sequenceSucceeded']) is bool
                and value['sequenceSucceeded'] is projected['sequenceSucceeded']
                and value['samples'] and value['phase']['phase'] == 'cleanup-restored-baseline'
                and value['phase']['stableSeconds'] >= 3
                and same({key:value['phase'][key] for key in PHASE_FIELDS}, projected['phases'][-1])
                and same([{key:sample[key] for key in SAMPLE_FIELDS} for sample in value['samples']],
                    projected['samples'][-len(value['samples']):])
                and value['finalSequence'] == projected['finalSequence'])
            with f.lock.held():
                owner = f.owner(); role = f.role_state(); history = f.source_history(owner); history.matches(role)
                need(owner['phase'] == 'cleaned' and role['sequence'] == value['finalSequence'])
                original = {row['sequence']:row['original'] for row in history.rows if row['event'] == 'sample'}
                if value['sequenceSucceeded']:
                    from feature_journeys.scenarios import SCENARIOS, expand
                    from feature_journeys.fixtures import context as fixture_context
                    steps = SCENARIOS['tablet-web']['steps']; activations = role['phase']['activations']
                    need(len(projected['phases']) == len(activations) == len(steps) + 2
                        and activations[0]['stimulus'] == dict(verb='baseline', inputs={})
                        and activations[-1]['stimulus'] == dict(verb='cleanup', inputs={})
                        and all(row['stimulus'] == dict(verb=step['verb'],
                            inputs=expand(step['inputs'], fixture_context(f.run)))
                            for row, step in zip(activations[1:-1], steps)))
                for sample in projected['samples'] if value['sequenceSucceeded'] else value['samples']:
                    saved = original[sample['sequence']]; measured = saved['sample']
                    need(all(same(sample[key], measured[key])
                        for key in ('sequence', 'capturedEpochMs', 'state', 'resources', 'lifecycle'))
                        and saved['phaseBefore']['activations'][-1]['ticket'] == sample['ticket'])
                need(all(sample['ticket'] == value['ticket']
                    and sample['actionBarrierEpochMs'] == value['actionBarrierEpochMs'] for sample in value['samples']))
                returned.guard()
                self.raw = raw
                self.scope = dict(picoBrowserCleanupConsumptionVersion=VERSION, runId=f.run, fixtureUrl=f.fixture_url,
                    binding=deepcopy(owner['binding']), ownerToken=owner['ownerToken'],
                    commonProducer=deepcopy(returned.scope), commonExportRootSha256=returned.request['rootSha256'],
                    commonExportRecordSha256=returned.request['recordSha256'])
                self.chunks = ChatSourceChunks(self.store, self.scope); self.chunks.inventory(0)
                header = {key:deepcopy(field) for key, field in value.items() if key != 'samples'}
                self.save('reading', [], header)
                for sample in value['samples']:
                    chunks = self.chunks.append(sample, self.previous['chunks']); self.save('reading', chunks, header)
                self.save('ready', self.previous['chunks'], header)
                returned.guard()
                f.completion_fence(owner, originals=lambda:f.sample_originals(role, history))
                self._sealed_raw = self.raw
                self.sealed = canonical(dict(scope=self.scope, root=self.previous, stamp=self.root_stamp))
                self.control()
            self.control(); reply = returned.receipt(); self.control()
            self.final_clocks(); self.complete = True
            return reply
        except BaseException:
            self.failed = True
            if not any(owner is self for owner in UNRESOLVED): UNRESOLVED.append(self)
            raise NativeUIError('Original remote Browser cleanup consumption is unresolved; sources remain') from None

    def receipt(self):
        need(self.returned is self._returned and type(self.returned) is OriginalBrowserConsumptionReturn)
        self.methods(self.returned)
        self.returned.guard()
        return super().receipt()
