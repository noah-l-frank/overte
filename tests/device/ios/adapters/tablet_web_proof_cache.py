"""One runtime's unchanged complete historical proof, never fresh product data.

Only a successful full decoder and unchanged complete original inventories can
produce a hit. SDK/readiness/freshness/current-prefix checks remain outside
this cache. Its sole excluded path is this role's exact publisher CAS journal,
which the full original decoder must not read.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.native_clock_join import digest
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope,record
from feature_journeys.contract import identifier
from ios.adapters.emote_original_lease import EmoteOriginalLease


class TabletPublicationProofCache:
    def __init__(self,roots,binding,run,role):
        context(binding);identifier(run);need(role in ('primary','actor') and type(roots) is list and 1<=len(roots)<=2)
        paths=[Path(path) for path in roots]
        need(all(path.is_absolute() and path.resolve(strict=True)==path and path.is_dir() for path in paths))
        self.publisher=paths[0]/('phase-publication-tablet-web-'+run+'-'+role+'.json')
        # The second root is an independently configured original-image scope;
        # overlapping trees need only their actual outer inventory.
        self.roots=[path for index,path in enumerate(paths) if not any(path==prior or path.is_relative_to(prior) for prior in paths[:index])]
        self.context=None;self.leases=[];self.values={}

    def clear(self):self.leases=[];self.values={}

    def _unchanged(self):
        for lease in self.leases:lease.guard()

    def decode(self,value,seal,decoder):
        need(callable(decoder));current=digest(seal)
        if self.context!=current:self.clear();self.context=current
        if self.leases:
            try:self._unchanged()
            except (NativeUIError,ValueError,OSError):self.clear()
        key=digest(value)
        if key in self.values:
            answer,members=self.values[key]
            for path in members:record(path)
            return deepcopy(answer)
        leases=self.leases or [EmoteOriginalLease(root,[self.publisher]) for root in self.roots]
        with scope(fresh=True) as members:answer=decoder(value)
        for lease in leases:lease.guard()
        need(self.publisher not in members)
        # Unknown external reads are still fully decoded, but never reusable
        # without an independently captured inventory for their real scope.
        covered=all(any(path==root or path.is_relative_to(root) for root in self.roots) for path in members)
        for path in members:record(path)
        if covered:
            self.leases=leases
            if len(self.values)>=64:self.values={}
            self.values[key]=(deepcopy(answer),frozenset(members))
        return answer
