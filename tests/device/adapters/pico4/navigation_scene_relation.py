"""One admitted packed-memory relation; never a file or current-source proof.

Only the owning journal's successful CAS/readback or original validated load
constructs this object. There is no renewal or reseal method. Every use checks
both original graph identities and their complete type-exact local bytes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.chat_journey.remote_publication import _warm_signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need
from adapters.script_journey.history import same,unpack


class NavigationMemoryRelation:
    def __init__(self,disk,state):
        need(type(disk) is dict and type(state) is dict
            and same(unpack(disk['payload']),[state]))
        # Admission retains the original complete closed JSON boundary. The
        # signatures are process-local bytes, never persisted or unmarshaled.
        json_digest(disk);json_digest(state)
        self.seal=self.original_seal=(disk,state,_warm_signature(disk),_warm_signature(state))

    def require(self,disk,state):
        seal=self.seal
        need(seal is self.original_seal and type(seal) is tuple and len(seal)==4
            and disk is seal[0] and state is seal[1]
            and type(disk) is type(state) is dict
            and type(seal[2]) is type(seal[3]) is bytes
            and _warm_signature(disk)==seal[2] and _warm_signature(state)==seal[3])
