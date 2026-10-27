"""Avatar-only immutable Final-prefix reuse during literal witness decoding.

The shared publisher still validates every intent, receipt, original clock,
phase, sequence and current live guard. Each readonly decode ends its own
historical round before a publisher CAS write or HTTP request can proceed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.native_feature_observation import need
from ios.adapters.avatar_final import immutable_prefix_round


class AvatarWitnessPublisher(PhaseWitnessPublisher):
    def decode(self,value):
        need(self.area=='avatar-people')
        with immutable_prefix_round():return super().decode(value)

    def publication_original(self,original):
        need(self.area=='avatar-people')
        with immutable_prefix_round():return super().publication_original(original)

    def publication_pending(self,original):
        need(self.area=='avatar-people')
        with immutable_prefix_round():return super().publication_pending(original)
