"""A read-only witness to actual Capture3 and independently observed retirement.

This creates no source query or deletion. Only actual original range literals
and the existing completed Capture3 proof can release native file allowance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need
from adapters.pico4.emote_stream_capture import PicoEmoteStreamCapture
from adapters.pico4.emote_stream_model_raw import literal
from adapters.pico4.emote_stream_wire import physical_stamp,strict_json
from adapters.script_journey.history import canonical,same


class PicoEmoteCapacityRetirement:
    def __init__(self,capacity,capture):
        need(type(capture) is PicoEmoteStreamCapture and capture.cycle.capacity is capacity
            and capture.cycle.originals.archive is capacity.archive and capture.state['phase']=='complete')
        capture.original() # Existing original images/draws/release/complete absence validators.
        proof=capture.state['retirement'];request=capture.state['captureIntent']['commandId']
        need(proof['memory']['present'] is False and proof['memory']['callbacks']==0 and proof['memory']['pngBytes']==0
            and proof['files']['removed']['source']['performed'] is True
            and proof['files']['absent']['source']['complete'] is True
            and all(row['exists'] is False for row in proof['files']['absent']['source']['receipts']))
        self.capacity=capacity;self.capture=capture;self.header=capture.previous;self.header_sha=json_digest(self.header)
        self.request=request;self.role=capture.role;self.receipts=tuple(proof['owner']['receipts']);self.references=[]
        targets=(('emote-stream-storage','inspect',proof['memory']),('emote-stream-inventory','remove',proof['files']['removed']),
            ('emote-stream-inventory','inspect',proof['files']['absent']))
        for role,operation,packet in targets:
            candidates=[row for page in capacity.archive.pages.values() for row in page['receipts'] if row is not None
                and row['role']==role and row['command'].get('requestId')==request
                and row['command'].get('operation')==operation and row['command'].get('wireNonce')
                and row['command'].get('commandId')==packet['commandId']]
            need(len(candidates)==1);row=candidates[0]
            reference=dict(audioRawRangeVersion=1,scopeSha256=capacity.archive.scope_sha,read=row['read'],sha256=row['sha256'])
            raw=capacity.archive.literal(reference);body,physical=literal(raw,row['command']['wireNonce'])
            need(physical_stamp(physical[0])[:5]==capture.source.state['nativeRootNode'] and same(strict_json(body),packet)
                and packet['processId']==capture.pid)
            self.references.append(reference)
        self.link=dict(picoEmoteCapacityRetirementVersion=1,captureJournal=str(capture.store.path),
            captureSha256=self.header_sha,rawReferences=deepcopy(self.references))
        self.references=tuple(self.references);self.seal=canonical(self.link)
        self._pins=(self.capacity,self.capture,self.capture.file,self.capture.store,self.header,self.header_sha,
            self.request,self.role,self.receipts,self.references,self.link,self.seal)
        self.require()

    def require(self):
        need(self.capacity is self._pins[0] and self.capture is self._pins[1] and self.capture.file is self._pins[2]
            and self.capture.store is self._pins[3] and self.header is self._pins[4] and self.header_sha==self._pins[5]
            and self.request==self._pins[6] and self.role==self._pins[7] and self.receipts is self._pins[8]
            and self.references is self._pins[9] and self.link is self._pins[10] and self.seal is self._pins[11])
        self.capacity.host_identity();need(self.capture.previous is self.header and json_digest(self.header)==self.header_sha
            and canonical(self.link)==self.seal and same(list(self.references),self.link['rawReferences']))
        self.capture.file.guard();need(same(self.capture.store.read(),self.header))
        for reference in self.references:self.capacity.archive.literal(reference)
        self.capacity.host_identity();return deepcopy(self.link)
