"""Actual Script/HTTP bytes through the existing private original reader."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import urlsplit
from feature_journeys.snapshot_concurrency import SnapshotConcurrency
from feature_journeys.snapshot_domain_client import SnapshotDomainClient
from ios.adapters.snapshot_upload_backend_owner import backend_context
from ios.self_tests.snapshot_upload_backend_owner_domain import SnapshotBackendOriginalDomain,RUN,REAL_TIME,REAL_MONOTONIC
from ios.self_tests.snapshot_upload_script_domain import SnapshotUploadScriptFlow,OriginalUploadScript
from self_tests.snapshot_domain_fixture import PolicyFixture


class SnapshotPreflightOriginalDomain(SnapshotBackendOriginalDomain):
    dispatch_upload=SnapshotUploadScriptFlow.dispatch_upload
    def __init__(self,case):
        super().__init__(case);self.policy=PolicyFixture(case);epoch_ms=lambda:int(REAL_TIME()*1000)
        self.policy.reader.epoch_ms=epoch_ms;self.policy.reader.monotonic=REAL_MONOTONIC
        domain=SnapshotDomainClient(self.policy.config,epoch_ms=epoch_ms,monotonic=REAL_MONOTONIC)
        self.domain_policy=domain.public();self.backend.provider.concurrency=SnapshotConcurrency(self.backend.provider,domain)
        self.script=OriginalUploadScript(case,self.backend);self.script_results=[];self.native_birth_preflight=[];self.lost_preflight=False
    def private_open(self,request,timeout):
        result=super().private_open(request,timeout)
        if self.lost_preflight and urlsplit(request.full_url).path.endswith('/snapshots/preflight/original'):
            self.lost_preflight=False;raise OSError('Declared lost actual original preflight GET return')
        return result
    def backend_owner(self):
        return backend_context(self.runtime,'primary',RUN,self.reader,self.ctx.binding,epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep,domain_policy=self.domain_policy)
