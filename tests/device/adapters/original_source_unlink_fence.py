"""The existing bounded original-source unlink policy, shared by typed owners.

Feature-specific wrappers admit their actual original producer. This helper
never creates an observer or grants retirement from a supplied source verdict.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import uuid
from adapters.chat_journey.source_chunks import digest
from adapters.native_feature_observation import need,number
from adapters.script_journey.history import same

VERSION=1


class OriginalSourceUnlinkFence:
    """At most 16 unlinks/250 ms using the same original source acquisition.

    The 250-ms window begins when that acquisition completes; its original
    1.5-s host/native deadlines still include the complete acquisition. Every
    actual unlink has a NEW independent phase query after its final intent.
    Only prepare() before that intent may acquire a new source. Any failure
    retains the original pending token and makes this warm fence unusable.
    """
    def __init__(self,guard,*,now,clock_ms,source_sequence):
        need(callable(guard) and all(callable(value) for value in (now,clock_ms,source_sequence)))
        self.guard,self.now,self.clock_ms,self.source_sequence=guard,now,clock_ms,source_sequence
        self.proof=None;self.snapshot=None;self.started=self.epoch=None
        self.uses=0;self.pending=None;self.failed=False

    def clocks(self):
        measured=self.now();epoch=self.clock_ms();ended=self.now()
        need(number(ended,measured,measured+1.5));return measured,epoch,ended

    def window(self):
        measured,epoch,ended=self.clocks()
        need(number(measured,self.started,self.started+.250) and number(ended,measured,self.started+.250)
            and number(epoch,self.epoch,self.epoch+250) and epoch-self.epoch+math.ceil((ended-measured)*1000)<=250)

    def prepare(self):
        try:
            need(not self.failed and self.pending is None)
            now,epoch,ended=self.clocks()
            expired=self.proof is None or self.uses>=16 or now-self.started>=.250 or epoch-self.epoch>=250
            if expired:
                self.proof=deepcopy(self.guard());self.guard.final(self.proof)
                self.snapshot=self.guard.cursors();self.started,self.epoch,_ended=self.clocks();self.uses=0
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window()
            need(same(self.snapshot,self.guard.cursors()))
            token=dict(archiveUnlinkFenceVersion=1,requestId=uuid.uuid4().hex,sourceSha256=digest(self.proof),
                sourceSequence=self.source_sequence(self.proof),windowUse=self.uses+1)
            self.pending=deepcopy(token);result=deepcopy(token)
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window();return result
        except Exception:self.failed=True;raise

    def check(self,token):
        try:
            need(not self.failed and self.pending is not None and same(token,self.pending)
                and digest(self.proof)==token['sourceSha256'] and same(self.snapshot,self.guard.cursors()))
            self.window();self.guard.current_phase(self.proof)
            need(same(self.snapshot,self.guard.cursors()))
            self.window();self.guard.final(self.proof,expected_cursors=self.snapshot)
        except Exception:self.failed=True;raise

    def complete(self,token):
        try:
            need(not self.failed and self.pending is not None and same(token,self.pending) and digest(self.proof)==token['sourceSha256'])
            self.guard.final(self.proof,expected_cursors=self.snapshot);self.window()
            self.uses+=1;self.pending=None
        except Exception:self.failed=True;raise
