"""Selected Audio PID originals in the existing actual raw archive and bill.

This source owns acquisition only. The original Android PID parser, candidate,
once-only input owner and native ESRCH proofs still decide their own results.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib

from adapters.bounded_process_original import BoundedProcessOriginal
from adapters.native_feature_observation import need
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from adapters.script_journey.history import canonical


class AudioCleanupProcessOriginals:
    def __init__(self,budget):
        need(type(budget) is AudioCleanupBudget1 and budget.process_source is self
             and budget.actor is not None)
        self.budget=budget;self.actor=budget.actor;self.bank=self.actor.raws
        self.original=(budget,self.actor,self.bank)
        self.rows=[];self.original_rows=self.rows
        self.failed=False;self.failure=None
        self.resource_identity()

    def resource_identity(self):
        budget,actor,bank=self.original
        need(self.budget is budget and self.actor is actor and self.bank is bank
             and type(budget) is AudioCleanupBudget1 and budget.process_source is self
             and budget.actor is actor and actor.raws is bank
             and self.rows is self.original_rows and type(self.rows) is list and len(self.rows)<=8)
        budget.guard()

    def acquire(self,argv,*,timeout):
        self.resource_identity()
        need(not self.failed and not self.budget.failed and len(self.rows)<8)
        # Strong registration and conservative retained SUM precede argument
        # validation/encoding, raw reservation, process creation and every read.
        capture=BoundedProcessOriginal()
        row=dict(capture=capture,token=None,body=None,reference=None,argvSha256=None)
        self.rows.append(row)
        try:
            self.budget.admit_process_capture(self)
            need(type(argv) is list and 0<len(argv)<=32
                 and all(type(arg) is str and 0<len(arg)<=8192 and '\x00' not in arg for arg in argv)
                 and sum(len(arg.encode('utf-8')) for arg in argv)<=capture.ARGUMENT_BYTES)
            digest=hashlib.sha256(b'utf8-length-prefix1\x00'+len(argv).to_bytes(4,'big'))
            for arg in argv:
                encoded=arg.encode('utf-8')
                digest.update(len(encoded).to_bytes(4,'big'));digest.update(encoded)
                del encoded
            row['argvSha256']=digest.hexdigest()
            command=dict(audioCleanupProcessOriginalVersion=1,runId=self.budget.value['runId'],
                ordinal=len(self.rows)-1,argvSha256=row['argvSha256'],argvDigestEncoding='utf8-length-prefix1',stdoutLimit=128,stderrLimit=128)
            row['token']=self.bank.reserve('audio-cleanup-process-query',command,4096)

            def retain(original):
                # Resource-only custody remains usable following a business
                # failure. Never drop acquired bytes because a new guard failed.
                self.resource_identity();need(original is capture and self.rows[-1] is row)
                body=dict(audioCleanupProcessOriginalVersion=1,argvSha256=row['argvSha256'],argvDigestEncoding='utf8-length-prefix1',
                    stdoutHex=bytes(original.buffers['stdout']).hex(),
                    stderrHex=bytes(original.buffers['stderr']).hex(),eof=dict(original.eof),
                    overflow=original.overflow,nativeReturnCode=original.returncode,
                    knownHostClose=original.closed,
                    acquisitionErrorAtRetention=None if original.failure is None else type(original.failure[0]).__name__)
                row['body']=canonical(body)
                need(len(row['body'])<=4096)
                row['reference']=self.bank.retain(row['token'],row['body'])

            result=capture.capture(argv,timeout=timeout,retain=retain)
            self.resource_identity();need(row['reference'] is not None)
            self.budget.check_global(self)
            return result
        except BaseException as error:
            self.failed=True;self.budget.failed=True
            if self.failure is None:self.failure=(error,error.__traceback__)
            raise
