"""Lossless terminal aliases for the actual decoded Tablet held-member set.

This is a pure projection of already qualified originals, never admission or
retirement authority. Complete member rows remain independently reconstructable
from the original native tail graph. A changed member changes its group digest.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from feature_journeys.terminal import KINDS,held


def terminal_aliases(members):
    need(type(members) is list and len(members)<=16384)
    names=[]
    for row in members:
        names.extend(held([row]))
    need(names==sorted(set(names)))
    # Preserve every existing small set literally, including alias/SHA bytes.
    if len(members)<=64:return deepcopy(members)
    groups=[]
    for kind in KINDS:
        actual=[deepcopy(row) for row in members if row['kind']==kind]
        if actual:
            sha=digest(dict(tabletHeldMembersVersion=1,kind=kind,members=actual))
            groups.append(dict(resource='panel:tablet-held-'+kind+'-'+sha[:32],kind=kind,originalSha256=sha))
    groups.sort(key=lambda row:row['resource']);held(groups);return groups
