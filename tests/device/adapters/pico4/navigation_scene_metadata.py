"""Exact warm Navigation metadata; never a current-source or file verdict.

Reuse the selected Chat version-2 local signature, including its strict JSON
fallback for canonical Unicode aliases. Signatures are never loaded, persisted
or used to admit another scope. Every actual file and native guard stays fresh.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.chat_journey.remote_publication import _warm_signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import need


class NavigationMetadataSeal:
    def __init__(self,value):
        self.digest=json_digest(value)
        self.seal=self.original_seal=(self.digest,_warm_signature(value))

    def require(self,value,expected):
        seal=self.seal
        need(seal is self.original_seal and type(seal) is tuple and len(seal)==2
            and type(expected) is type(self.digest) is str and expected==self.digest==seal[0]
            and type(seal[1]) is bytes)
        if _warm_signature(value)!=seal[1]:
            # Preserve the old complete closed-JSON validator and canonical
            # digest on a mismatch. This never reseals or changes authority.
            need(json_digest(value)==seal[0])
