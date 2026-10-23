"""Warm pure transcript decoding; never acquire or qualify an observation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import re

from adapters.chat_journey.original_memory import plain
from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.native_feature_observation import integer,need
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW

VERSION=1


class ChatDecodedPrefix:
    """Only successful original transactions may commit decoded old prefixes."""
    def __init__(self,history):
        need(type(history) is ChatSourceChunks)
        self.path=str(history.root_path);self.scope=history.scope
        self.identity=(self.path,self.scope);self.records=self._records=();self.pending=None
        self.sha=digest(self.description())
        self.seal=self._seal=(self.records,self.identity,self.sha)

    def description(self):
        need(type(self.path) is str and type(self.scope) is str and (self.path,self.scope)==self.identity
            and type(self.records) is tuple and self.records is self._records and len(self.records)<=MAX_FRAMES)
        rows=[]
        for row in self.records:
            need(type(row) is tuple and len(row)==5)
            signature,expected,raw,sha,count=row
            need(type(signature) is tuple and len(signature)==8 and all(type(value) is int for value in signature)
                and all(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) for value in (expected,sha))
                and type(raw) is bytes and integer(count,2,MAX_RAW))
            rows.append([list(signature),expected,sha,count])
        return dict(version=VERSION,path=self.path,scopeSha256=self.scope,rows=rows)

    def control(self,*,deep=False):
        # All nested tuple/bytes/string/int types were checked at admission.
        # They cannot mutate in place; each used decoded byte string is still
        # fully SHA-checked in decode(), after the unchanged physical read.
        need(type(self.seal) is tuple and self.seal is self._seal and len(self.seal)==3
            and type(self.records) is tuple and self.records is self._records is self.seal[0]
            and type(self.identity) is tuple and self.identity is self.seal[1]
            and (self.path,self.scope)==self.identity and type(self.sha) is str and self.sha==self.seal[2])
        if deep:need(digest(self.description())==self.sha)
        return self.sha

    def begin(self,history,manifest):
        self.control(deep=True);need(type(history) is ChatSourceChunks and str(history.root_path)==self.path
            and history.scope==self.scope and type(manifest) is list and len(self.records)<=len(manifest)<=MAX_FRAMES
            and [row[1] for row in self.records]==manifest[:len(self.records)])
        self.pending=ChatDecodedCandidate(self,history,manifest)
        return self.pending

    def commit(self,candidate):
        self.control(deep=True);need(type(candidate) is ChatDecodedCandidate and candidate is self.pending and candidate.base is self
            and candidate.previous_sha==self.sha and candidate.complete)
        candidate.control();need(candidate.records is candidate.finished_records)
        self.records=self._records=candidate.records
        self.sha=digest(self.description());self.seal=self._seal=(self.records,self.identity,self.sha)
        self.pending=None;self.control()


class ChatDecodedCandidate:
    """Uncommitted computation is discarded; it contains no source verdict."""
    def __init__(self,base,history,manifest):
        need(type(base) is ChatDecodedPrefix and type(history) is ChatSourceChunks)
        self.base=base;self.history=history;self.previous_sha=base.sha
        self.previous_records=base.records;self.identity=(base.path,base.scope)
        self.manifest=tuple(manifest);self._manifest=self.manifest
        self.records=self._records=();self.complete=False;self.finished_records=None;self.finish_seal=None

    def identity_control(self):
        need(type(self.base) is ChatDecodedPrefix and self.base.pending is self and self.base.sha==self.previous_sha
            and self.base.records is self.previous_records and (self.base.path,self.base.scope)==self.identity
            and self.manifest is self._manifest and type(self.manifest) is tuple
            and type(self.records) is tuple and self.records is self._records
            and len(self.records)<=len(self.manifest)<=MAX_FRAMES and type(self.complete) is bool)
        need(str(self.history.root_path)==self.base.path and self.history.scope==self.base.scope)

    def control(self):
        self.base.control();self.identity_control()
        if self.complete:
            need(type(self.finish_seal) is tuple and len(self.finish_seal)==2
                and self.records is self.finished_records is self.finish_seal[0]
                and self.manifest is self.finish_seal[1])

    def bind(self,history,manifest):
        self.control();need(history is self.history and type(manifest) is list and tuple(manifest)==self.manifest
            and not self.complete and not self.records)

    def decode(self,index,expected,signature,value):
        self.identity_control();need(not self.complete and integer(index,0,len(self.manifest)-1) and index==len(self.records)
            and expected==self.manifest[index] and type(signature) is tuple)
        if index<len(self.base.records):
            record=self.base.records[index];old_signature,old_expected,raw,sha,count=record
            need(signature==old_signature and expected==old_expected and value['transcript']['bytes']==count
                and hashlib.sha256(raw).hexdigest()==sha)
            frames=json.loads(raw)
        else:
            frames=unpack(value['transcript']);plain(frames);raw=canonical(frames)
            record=(signature,expected,raw,hashlib.sha256(raw).hexdigest(),value['transcript']['bytes'])
        need(type(frames) is list and len(frames)==1)
        self.records=self._records=self.records+(record,)
        return frames

    def finish(self):
        self.control();need(len(self.records)==len(self.manifest))
        self.finished_records=self.records;self.finish_seal=(self.records,self.manifest)
        self.complete=True;self.control()
