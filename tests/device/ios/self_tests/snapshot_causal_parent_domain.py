"""Explicit fresh Upload4 boundary; old Upload3 fixture defaults stay literal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.normal_ui import NativeUIError
from ios.adapters import snapshot_causal_dispatch as source
from ios.adapters.snapshot_upload_backend_owner import backend_context
from ios.self_tests.snapshot_causal_dispatch_domain import CausalDispatchDomain
from ios.self_tests.snapshot_pending_domain import REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_upload_flow_domain import RUN


class CausalParentDomain(CausalDispatchDomain):
    def __init__(self,case):
        super().__init__(case);self.lose_causal=None;self.mutate_causal=None;self.delay_association=False;self.pending_dispatch=None
        previous=self.ctx.files.execute
        def original_file(session,operation,values):
            if values['remotePath'].endswith('/'+source.FILE) and source.FILE not in self.raws:
                raise NativeUIError('Declared causal original not produced')
            return previous(session,operation,values)
        self.ctx.files.execute=original_file
    def post(self,request,timeout):
        query=json.loads(request.data)
        if query['action']!=source.ACTION:return super().post(request,timeout)
        self.commands.append(deepcopy(query));lost=self.lose_causal;self.lose_causal=None
        if lost=='before':raise OSError('Declared causal source send lost before original')
        packet=self.causal_packet(query)
        if self.pending_dispatch is not None:
            upload=self.pending_dispatch;self.pending_dispatch=None;super().complete_dispatch(upload)
        if self.mutate_causal:self.mutate_causal(packet)
        self.raws[source.FILE]=json.dumps(packet,indent=1)+'\n';self.ctx.files.echo=json.dumps(query).encode()
        if lost=='after':raise OSError('Declared causal source original saved but dispatch return lost')
        return self.ctx.files
    def complete_dispatch(self,upload):
        if self.delay_association:self.pending_dispatch=upload
        else:super().complete_dispatch(upload)
    def upload_owner(self,*,combined=True,frontend_http=True,frontend_caller=True):
        return self.runtime.upload_owner('primary',RUN,self.client(),combined=combined,frontend_http=frontend_http,frontend_caller=frontend_caller,
            epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
    def backend_owner(self,*,combined=True,frontend_http=True,frontend_caller=True):
        return backend_context(self.runtime,'primary',RUN,self.reader,self.ctx.binding,epoch_ms=lambda:int(REAL_TIME()*1000),
            monotonic=REAL_MONOTONIC,sleep=self.sleep,domain_policy=self.domain_policy,combined=combined,frontend_http=frontend_http,frontend_caller=frontend_caller)
