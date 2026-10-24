"""Join the frozen whole role WAL to its actual original terminal live seal.

This is a pure pre-process-end checkpoint. All copied metadata is explicit;
real source/peer/PNG/publication/proof files remain independently decoded.
No current SDK metadata, native query, renewed clock or process operation exists.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.native_feature_observation import need
from adapters.pure_original_validation import inherited_scope as pure_scope,PROFILE
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_rooted_state import IOSEmoteRootedState
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal


class IOSEmoteRootedOwnership:
    def __init__(self,copies,*,run,lock,actor_lock):
        need(type(copies) is dict)
        self.path=lock.path.with_name('ios-emote-primary-'+run+'-terminal.json')
        need(str(self.path) in copies and type(copies[str(self.path)]) is dict)
        self.terminal=deepcopy(copies[str(self.path)])
        self.roles=IOSEmoteRootedState({path:value for path,value in copies.items() if path!=str(self.path)},
            run=run,lock=lock,actor_lock=actor_lock)

    def read(self):
        roles=self.roles;roots={lock.path.parent for lock in roles.locks.values()}
        for role,lock in roles.locks.items():
            value=roles.copies.get(str(lock.path.with_name('ios-emote-'+role+'-feature.json')))
            need(type(value) is dict and type(value.get('artifactRoot')) is str);roots.add(Path(value['artifactRoot']))
        leases=[EmoteOriginalLease(root,[]) for root in roots]
        def unchanged():
            for lock in roles.locks.values():lock.assert_held()
            for lease in leases:lease.guard()
            return True
        with pure_scope(PROFILE,unchanged):
            window=roles.read();journal=IOSEmoteTerminalJournal.archive(window,self.terminal,check=unchanged)
            need(journal.state is not None and journal.state['phase']=='sealed')
            proof=journal.originals.read(journal.originals.expand(journal.state['record']));journal.proof(proof,journal.state)
            original=proof['original']
            need(same(original['journals'],{role:live.previous for role,live in window.roles.items()}))
            publisher=roles.store(roles.locks['actor'].path.with_name('phase-publication-emotes-'+roles.run+'-actor.json'))
            need(same(original['publisher'],publisher.read()))
            actual=window.qualify(journal.state['description'],original['samples'],journal.state['references'],
                publisher_store=publisher,record_store_for=roles.store)
            need(same(actual,proof));journal.bound()
        return deepcopy(actual)
