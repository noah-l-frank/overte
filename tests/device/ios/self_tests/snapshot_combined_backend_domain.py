"""Same normal Combined capture/upload plus actual protected backend originals.

The existing Script/request.js and HTTP serializer execute. Qt/V8/SDK remain
declared boundaries; no HTTP consumer source or whole feature is fabricated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters.snapshot_upload_backend_owner import backend_context
from ios.self_tests.snapshot_combined_upload_domain import CombinedUploadDomain
from ios.self_tests.snapshot_preflight_original_domain import SnapshotPreflightOriginalDomain,RUN,REAL_TIME,REAL_MONOTONIC


class CombinedBackendDomain(CombinedUploadDomain,SnapshotPreflightOriginalDomain):
    def backend_owner(self,*,combined=True):
        return backend_context(self.runtime,'primary',RUN,self.reader,self.ctx.binding,epoch_ms=lambda:int(REAL_TIME()*1000),
            monotonic=REAL_MONOTONIC,sleep=self.sleep,domain_policy=self.domain_policy,combined=combined)
