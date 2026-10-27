"""Same normal Pending/PNG file domain with an explicit combined manager."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from ios.self_tests.snapshot_combined_pending_domain import CombinedPendingDomain
from ios.self_tests.snapshot_journey_files_domain import SnapshotJourneyFilesDomain,RUN,REAL_TIME,REAL_MONOTONIC


class CombinedJourneyDomain(CombinedPendingDomain,SnapshotJourneyFilesDomain):
    """Reuse the existing actual file model and closed combined work sampler."""
    @contextmanager
    def capture_owner(self):
        with self.runtime.capture_owner('primary',RUN,self.client(),combined=True) as owner:
            owner.epoch_ms=lambda:int(REAL_TIME()*1000);owner.monotonic=REAL_MONOTONIC;owner.sleep=self.sleep
            owner.phase.epoch_ms=owner.epoch_ms;owner.phase.monotonic=REAL_MONOTONIC;yield owner

    def files_owner(self,*,combined=True):
        return self.runtime.journey_files_owner('primary',RUN,self.client(),combined=combined,
            epoch_ms=lambda:int(REAL_TIME()*1000),monotonic=REAL_MONOTONIC,sleep=self.sleep)
