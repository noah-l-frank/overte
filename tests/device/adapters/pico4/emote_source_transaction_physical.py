"""Explicit PhysicalWire2 on the ORIGINAL Raw reply owner, no second writer.

NEW source composition, not yet selected by a BoundAdapter Source factory.
The six native schemas/Parent/phase/freshness joins remain the owning Source's
responsibility. A decoded declared transport DTO never grants input authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
import re

from adapters.native_feature_observation import need
from adapters.pico4.emote_source_transaction_command import envelope,SDKSourceExtent
from adapters.pico4.emote_source_transaction_profile import PicoEmoteSourceProfile
from adapters.pico4 import emote_source_transaction_wire as lexical
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical

VERSION=2


@dataclass(frozen=True,slots=True)
class PhysicalSourceExtents:
    sdk:SDKSourceExtent
    sources:lexical.SourceExtents


class PicoEmoteSourcePhysicalWire(lexical.PicoEmoteSourceTransactionWire):
    def __init__(self,archive,exchange,guard,clock,profile,*,role,identity):
        need(type(profile) is PicoEmoteSourceProfile and role in ('primary','actor')
            and type(identity) is str and re.fullmatch('[1-9][0-9]*:[0-9]+',identity))
        profile.identity();need(role in profile.roles)
        self.profile=self._profile=profile;self.role=self._role=role;self.native_identity=self._native_identity=identity
        self.profile_guard=self._profile_guard=profile.identity;self.profile_bill=self._profile_bill=profile.extra_bill
        self.profile_sha=profile.sha256;self.physical_parser=self._physical_parser=envelope
        super().__init__(archive,exchange,guard,clock)
        self.identity()

    def identity(self):
        super().identity()
        need(self.profile is self._profile and self.role==self._role and self.native_identity==self._native_identity
            and self.profile_guard is self._profile_guard and self.profile_bill is self._profile_bill
            and same_callable(self.profile.identity,self.profile_guard) and same_callable(self.profile.extra_bill,self.profile_bill)
            and self.physical_parser is self._physical_parser and type(self.profile) is PicoEmoteSourceProfile)
        self.profile_guard()
        need(self.profile.sha256==self.profile_sha and type(self.archive.scope.get('picoEmoteSourcePhysicalVersion')) is int
            and self.archive.scope['picoEmoteSourcePhysicalVersion']==VERSION
            and self.archive.scope.get('sourceProfileSha256')==self.profile_sha)

    def reserve_reply(self,value):
        self.identity()
        current=self.archive.other_bill();minimum=self.profile_bill()
        need(type(current) is dict and set(current)==set(minimum)
            and all(type(current[key]) is int and current[key]>=minimum[key] for key in minimum))
        # The SAME slot is already permanently charged by exact other_bill;
        # retaining this raw return must not release parser/failure capacity.
        return self.archive.reserve('emote-source-txn',value,lexical.WIRE_LIMIT,side_bytes=0)

    def parse_reply(self,wire,value):
        self.identity()
        physical=self.physical_parser(wire,value['commandId'],self.native_identity)
        # Receipt parse locals have died before Header/Extent/source objects
        # exist. Both protocols point into this SAME once-archived SDK literal.
        proof=lexical.extents(wire,value,start=physical.offset,end=physical.offset+physical.size)
        header=lexical.strict_json(proof.header.decode('utf-8'))
        need(len(proof.header)<=1024 and canonical(header)==proof.header)
        values=lexical.decode_sources(wire,proof)
        return PhysicalSourceExtents(physical,proof),values
