"""Explicit SourceTxn execution-policy/byte reservations; no observations.

NEW opt-in composition prerequisite, not wired into existing Policy/Cycle.
One original compound slot PER ENABLED ROLE remains charged for the entire profile lifetime,
including parser/unknown-return/failed-Native ownership. Raw tokens must use
side_bytes=0 ONLY under this typed original profile; the archive is unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass,field

from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import need
from adapters.pico4.emote_source_transaction_command import FILE_LIMIT,RECEIPT_LIMIT,COMMAND_LIMIT
from adapters.pico4.emote_source_transaction_wire import WIRE_LIMIT,EXISTING_SIDE_LIMIT
from adapters.chat_journey.source_chunks import json_digest

VERSION=1
PACKET_LIMIT=262144
METADATA=28*1024
# Existing Host lexical proof: W wire + W prior values + L raw + L text +
# 5L next canonical + L number token, L<=W/4. Physical receipt parsing finishes
# BEFORE native extents/source parsing; only <=4KiB frozen physical proof lives
# beside the old24KiB metadata peak. No second full Native-body slice exists.
HOST_SLOT=4*WIRE_LIMIT+METADATA
# For allowed complete packets: one reserved wire + _actual canonical<=5L +
# QJsonDocument serialized domain<=5L + literal<=L. During original writer
# readback, wire + prefix temporary + current byte read<=3W; old _expected is
# separately persistent below. Source callback failure keeps originals and
# never transfers the slot to a new owner. This is serialized bytes, NOT RSS.
NATIVE_BUILD_SLOT=WIRE_LIMIT+11*PACKET_LIMIT+METADATA
NATIVE_READBACK_SLOT=3*WIRE_LIMIT+METADATA
SLOT=max(HOST_SLOT,NATIVE_BUILD_SLOT,NATIVE_READBACK_SLOT)
# Actual old/current publisher expected bytes + native completed source +
# small closed receipts/proofs/commands/nonces. Successful widget observation
# must MOVE out its original map; failed maps remain within the charged slot.
PERSISTENT=WIRE_LIMIT+5*PACKET_LIMIT+6*RECEIPT_LIMIT+32768
CONTROL_FILE_LIMIT=16384


@dataclass(frozen=True,slots=True)
class PicoEmoteSourceProfile:
    roles:tuple=('primary',)
    host:str=''
    _roles:tuple=field(init=False,repr=False)
    _shape:tuple=field(init=False,repr=False)
    _host:str=field(init=False,repr=False)

    def __post_init__(self):
        need(type(self.roles) is tuple and self.roles and len(self.roles)<=2
            and len(set(self.roles))==len(self.roles) and all(type(role) is str and role in ('primary','actor') for role in self.roles)
            and self.host=='')
        object.__setattr__(self,'host',host_identity())
        object.__setattr__(self,'_host',self.host)
        object.__setattr__(self,'_roles',self.roles)
        object.__setattr__(self,'_shape',self.shape())
        need(SLOT<=EXISTING_SIDE_LIMIT and FILE_LIMIT+RECEIPT_LIMIT+1+4096==WIRE_LIMIT)

    def identity(self):
        self.resource_identity()
        need(type(self) is PicoEmoteSourceProfile and self.host==self._host and self.roles is self._roles
            and self.shape()==self._shape and type(self.roles) is tuple and self.roles
            and len(set(self.roles))==len(self.roles) and all(role in ('primary','actor') for role in self.roles)
            and SLOT==4*WIRE_LIMIT+METADATA and SLOT<=EXISTING_SIDE_LIMIT)

    def resource_identity(self):
        # Actual already-issued literals retain their original owner even if
        # a mutable public policy alias is substituted during SDK return.
        need(type(self) is PicoEmoteSourceProfile and host_identity()==self._host)

    @staticmethod
    def shape():
        return tuple((type(value),value) for value in (VERSION,WIRE_LIMIT,FILE_LIMIT,RECEIPT_LIMIT,COMMAND_LIMIT,
            PACKET_LIMIT,METADATA,HOST_SLOT,NATIVE_BUILD_SLOT,NATIVE_READBACK_SLOT,SLOT,PERSISTENT,
            CONTROL_FILE_LIMIT,EXISTING_SIDE_LIMIT))

    def limits(self,role):
        self.identity();need(role in ('primary','actor'))
        return dict(picoEmoteSourceProfileVersion=VERSION,sourceTransactionEnabled=int(role in self.roles),
            sourceWireFileBytes=FILE_LIMIT,sourceReceiptFileBytes=RECEIPT_LIMIT,sourceCommandFileBytes=COMMAND_LIMIT,
            sourcePersistentBytes=PERSISTENT,sourceReservedTransientBytes=SLOT)

    def extra_bill(self):
        self.identity();count=len(self.roles)
        # Fixed command channels for both original roles + source current,
        # actual receipt and uncertain command temporary per selected role.
        # Slot is logical reserved capacity, NOT an immutable history part.
        # Distinct Pico GUI builders and unknown SDK returns can coexist with
        # the other Host decoder. No cross-role exclusion is assumed.
        stored=2*CONTROL_FILE_LIMIT+count*(FILE_LIMIT+RECEIPT_LIMIT+COMMAND_LIMIT+SLOT)
        return dict(parts=2+3*count,storedBytes=stored,decodedBytes=stored+count*PERSISTENT)

    def scope(self):
        self.identity()
        return dict(picoEmoteSourceProfileVersion=VERSION,roles=list(self.roles),
            originalHost=self.host,limits={role:self.limits(role) for role in ('primary','actor')})

    @property
    def sha256(self):return json_digest(self.scope())

    def require_bootstrap(self):
        """Pure Host minimum before even cold runtime/kernel SDK setup."""
        from adapters.pico4.emote_stream_capacity import descriptor,PART
        from adapters.script_journey.history import MAX_RAW
        limits=descriptor();value=self.extra_bill()
        # Existing Capture capacity's unavoidable fixed native files/marker
        # for BOTH roles and its three fixed metadata/CAS allowances. Actual
        # roots, raw literals and future receipts/PNGs add to this lower bound.
        fixed=2*sum(limits[key] for key in ('worldFileBytes','modelFileBytes','inventoryFileBytes','pendingMarkerFileBytes'))+3*PART
        need(max(value['storedBytes'],value['decodedBytes'])+fixed<=MAX_RAW)
        return value
