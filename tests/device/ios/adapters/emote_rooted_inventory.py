"""Paired unknown-carrier barrier over actually decoded original membership.

Only the typed terminal journal's exact current outputs may change. Names
alone grant no exemption and no native/process/SDK retirement authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_session_carriers import inventory
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal


class IOSEmoteRootedInventory:
    def __init__(self,journal,reads):
        need(type(journal) is IOSEmoteTerminalJournal and type(reads) is set)
        self.journal=journal;self.roots=set()
        for live in journal.window.roles.values():
            live.lock.assert_held();live.primary_lock.assert_held()
            self.roots.update((live.root,live.store.path.parent))
        found=inventory(self.roots);owned=self.owned()
        need(found<=reads|owned)
        self.paths=found-owned;self.signatures={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.guard()

    def owned(self):
        journal=self.journal;result={journal.store.path}
        state=journal.state
        if state is not None:
            if state['record'] is not None:result.add(journal.originals.path(journal.originals.expand(state['record'])))
            if state['pending'] is not None:result.add(journal.originals.path(state['pending']))
        return result

    def guard(self):
        for live in self.journal.window.roles.values():live.lock.assert_held();live.primary_lock.assert_held()
        # Structural journal validation binds every exact mutable output to
        # its original namespace, run, role, candidate and observed file birth.
        if self.journal.state is not None:self.journal.decode(self.journal.envelope(self.journal.state))
        need(inventory(self.roots)-self.owned()==self.paths)
        for path,signature in self.signatures.items():
            PrivateFeatureState(path)._parent();need(EmoteOriginalLease.signature(path.lstat())==signature);record(path)
        return True
