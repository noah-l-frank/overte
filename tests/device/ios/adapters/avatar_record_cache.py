"""Operation-local reuse of already byte-validated immutable Avatar records.

This cache supplies no product facts, clocks or file qualification. A cold key
is decoded twice between actual file-signature inventories. Every reuse checks
all retained file identities/modes/link counts/lengths/mtime/ctime and restores
actual read membership. Changed originals fail closed rather than recaching.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import stat
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record,scope
from adapters.script_feature.history import canonical,same
from ios.adapters.emote_original_lease import EmoteOriginalLease


class AvatarRecordCache:
    def __init__(self):self.rows={}
    @staticmethod
    def signatures(paths):
        need(type(paths) is set and 1<=len(paths)<=2048);result={};parents={}
        for path in paths:
            need(isinstance(path,Path) and path.is_absolute())
            if path.parent not in parents:
                PrivateFeatureState(path)._parent()
                parents[path.parent]=EmoteOriginalLease.signature(path.parent.lstat())
            value=path.lstat();need(stat.S_ISREG(value.st_mode) and value.st_uid==os.geteuid() and value.st_nlink==1 and stat.S_IMODE(value.st_mode)==0o600)
            result[path]=EmoteOriginalLease.signature(value)
        # Canonical private parents are checked as a group; each leaf still
        # receives its own non-following stat. Recheck directory identity and
        # timestamps so a change during the census cannot qualify a result.
        for parent,signature in parents.items():
            PrivateFeatureState(parent/'original-cache-parent-boundary')._parent()
            need(EmoteOriginalLease.signature(parent.lstat())==signature)
        return result
    @staticmethod
    def absent(paths):
        need(type(paths) is set and len(paths)<=2048)
        for path in paths:
            need(isinstance(path,Path));PrivateFeatureState(path)._parent();need(not os.path.lexists(path))
    def read(self,key,validate,*,absent=lambda:set()):
        return self._read(key,validate,absent=absent,result=True)
    def check(self,key,validate,*,absent=lambda:set()):
        """Keep both original inventories and membership without a result copy."""
        self._read(key,validate,absent=absent,result=False)
    def _read(self,key,validate,*,absent,result):
        need(type(key) is dict and callable(validate) and callable(absent));key=canonical(key)
        if key not in self.rows:
            need(len(self.rows)<512)
            with scope(fresh=True) as first:value=validate()
            signatures=self.signatures(first);missing=set(absent());self.absent(missing)
            with scope(fresh=True) as second:confirmed=validate()
            need(first==second and set(absent())==missing and self.signatures(second)==signatures and same(value,confirmed));self.absent(missing)
            self.rows[key]=(deepcopy(confirmed),signatures,missing)
        value,signatures,missing=self.rows[key];need(self.signatures(set(signatures))==signatures);self.absent(missing)
        result=deepcopy(value) if result else None
        need(self.signatures(set(signatures))==signatures);self.absent(missing)
        for path in signatures:record(path)
        return result
