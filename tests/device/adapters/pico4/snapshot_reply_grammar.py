"""Warm pure grammar for byte-identical old cancellation replies.

This cache is no source, effect, file, freshness or release receipt. Only the
actual owner may commit a candidate after its final fences and real lock exit.
Cold owners always start without an admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import context
from adapters.pico4.snapshot_originals import nonce,sha
from feature_journeys.contract import json_document,typed_equal
from adapters.pico4.snapshot_base_frame import original
from adapters.pico4.snapshot_cancel import validate as cancel_packet

PIN_PATH=Path(__file__).with_name('snapshot-script-pin.v1.json')


def validate_reply(saved,requests,pid):
    # The original complete reply grammar, unchanged. Current request-table
    # membership/equality also runs outside the memo in the owner on every call.
    exact(saved,{'raw','sha256','anchor','request'});need(saved['request']['commandId'] in requests)
    packet=original({key:saved[key] for key in ('raw','sha256')},262144)
    exact(packet,{'commandId','packet'});value=packet['packet'];request=requests[packet['commandId']]
    need(typed_equal(saved['request'],request));cancel_packet(value,request,pid,value['capturedEpochMs'])
    exact(saved['anchor'],{'hostMonotonic','nativeEpochMs'})
    need(number(saved['anchor']['hostMonotonic'],0,1e15) and integer(saved['anchor']['nativeEpochMs'],1))


def read_pins():
    path=PIN_PATH;descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    def signature(value):return (value.st_dev,value.st_ino,value.st_size,value.st_mode,value.st_uid,value.st_nlink,value.st_mtime_ns,value.st_ctime_ns)
    with os.fdopen(descriptor,'rb') as source:
        before=os.fstat(source.fileno());need(stat.S_ISREG(before.st_mode) and before.st_size<=4096 and before.st_nlink==1 and before.st_uid==os.geteuid())
        raw=source.read(4097);need(len(raw)<=4096 and signature(before)==signature(os.fstat(source.fileno()))==signature(path.lstat()))
    value=json_document(raw);exact(value,{'encoding','codeUnits','sha256'})
    need(value['encoding']=='utf-16le-code-units' and integer(value['codeUnits'],1) and sha(value['sha256']))
    return value,hashlib.sha256(raw).hexdigest()


def scope(run,binding,pid,pins,pins_sha):
    json_digest(dict(runId=run,binding=binding,pid=pid,scriptPins=pins,scriptPinsSha256=pins_sha))
    context(binding)
    need(nonce(run) and integer(pid,1) and str(pid)==binding['processIdentity'].split(':')[0] and sha(pins_sha))
    exact(pins,{'encoding','codeUnits','sha256'})
    need(pins['encoding']=='utf-16le-code-units' and integer(pins['codeUnits'],1) and sha(pins['sha256']))
    value=dict(runId=run,binding=deepcopy(binding),pid=pid,scriptPins=deepcopy(pins),scriptPinsSha256=pins_sha)
    json_digest(value);return value


class SnapshotReplyGrammar:
    def __init__(self):
        self.previous=self.pending=None;self.sha=json_digest(None);self.pending_sha=json_digest(None);self.failed=False

    def control(self):
        need(type(self.failed) is bool and not self.failed and type(self.sha) is str and type(self.pending_sha) is str
            and json_digest(self.previous)==self.sha and json_digest(self.pending)==self.pending_sha)

    def validate(self,current,rows,validator):
        self.control()
        try:
            need(type(current) is dict and type(rows) is list and len(rows)<=64 and callable(validator))
            exact(current,{'runId','binding','pid','scriptPins','scriptPinsSha256'})
            need(typed_equal(current,scope(current['runId'],current['binding'],current['pid'],current['scriptPins'],current['scriptPinsSha256'])))
            scope_sha=json_digest(current);hashes=[json_digest(row) for row in rows];count=0
            if self.previous is not None:
                need(typed_equal(current,self.previous['scope']) and scope_sha==self.previous['scopeSha256']
                    and hashes[:len(self.previous['rows'])]==self.previous['rows']);count=len(self.previous['rows'])
            for row in rows[count:]:validator(row)
            # The caller cannot lend mutable aliases and change them while a
            # new row is validated, including an old prefix or its scope.
            need(scope_sha==json_digest(current) and hashes==[json_digest(row) for row in rows]);self.control()
            self.pending=dict(previousSha256=self.sha,scope=deepcopy(current),scopeSha256=scope_sha,rows=hashes)
            self.pending_sha=json_digest(self.pending);return self.pending
        except BaseException:self.failed=True;raise

    def matches(self,candidate,current,rows):
        self.control();need(candidate is self.pending and json_digest(candidate)==self.pending_sha
            and candidate['previousSha256']==self.sha and typed_equal(current,candidate['scope'])
            and json_digest(current)==candidate['scopeSha256'] and [json_digest(row) for row in rows]==candidate['rows'])

    def commit(self,candidate):
        self.control();need(candidate is self.pending and candidate['previousSha256']==self.sha)
        self.previous=dict(scope=deepcopy(candidate['scope']),scopeSha256=candidate['scopeSha256'],rows=list(candidate['rows']))
        self.sha=json_digest(self.previous);self.pending=None;self.pending_sha=json_digest(None);self.control()

    def admitted(self,current,rows):
        self.control();need(self.previous is not None and typed_equal(current,self.previous['scope'])
            and json_digest(current)==self.previous['scopeSha256'] and [json_digest(row) for row in rows]==self.previous['rows'])

    def discard(self):
        self.pending=None;self.pending_sha=json_digest(None)

    def abort(self):
        # A late commit failure cannot leave a new warm admission usable.
        self.previous=None;self.sha=json_digest(None);self.discard();self.failed=True
