"""Connect exact paired Emote live ownership to process, SDK and host end.

This internal coordinator does not advertise an area capability. Each retry
continues durable owners; after a Stop is issued no live factory for that role
is opened. The original inactive fixture phase is acquired, never reconstructed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import unpack,same
from feature_journeys import terminal as contract
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_fence import _seal,inactive,inactive_prefixes
from ios.adapters.emote_rooted_inventory import IOSEmoteRootedInventory
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
from ios.adapters.emote_rooted_state import metadata_paths
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal


def existing_archive(primary,actor_lock):
    """Open only actual frozen metadata and original files under both locks."""
    primary.lock.assert_held();actor_lock.assert_held()
    store=PrivateFeatureState(primary.store.path.with_name('ios-emote-primary-'+primary.run+'-rooted-final.json'))
    value=store.read()
    if value is None:return None,None
    need(type(value) is dict and type(value.get('paths')) is list)
    paths=[PrivateFeatureState(Path(path)) for path in value['paths']]
    def qualify(copies):
        return IOSEmoteRootedOwnership(copies,run=primary.run,lock=primary.lock,actor_lock=actor_lock).read()
    archive=IOSEmoteRootedFinalArchive(store,primary.root,value['binding'],primary.run,'primary',primary.lock,primary.lock,
        paths,primary.clock,qualify)
    archive.freeze();need(archive.state['phase']=='validated')
    ownership=IOSEmoteRootedOwnership(archive.copies(),run=primary.run,lock=primary.lock,actor_lock=actor_lock)
    return archive,ownership


class IOSEmoteRootedFinish:
    def __init__(self,terminal,seal):
        from ios.adapters.emote_terminal import IOSEmoteTerminal
        need(type(terminal) is IOSEmoteTerminal);contract.sealed(seal)
        self.terminal,self.flow,self.actor=terminal,terminal.flow,terminal.actor
        self.seal=deepcopy(seal)
        need(seal['description']['runId']==self.flow.run and seal['description']['area']=='emotes')
    def freeze(self):
        flow,actor=self.flow,self.actor
        archive,ownership=existing_archive(flow,actor.lock)
        if archive is not None:
            proof=ownership.read();_seal(proof,self.seal,run=flow.run,role='primary',binding=archive.binding)
            return archive,ownership
        raw=PrivateFeatureState(flow.store.path.with_name('ios-emote-primary-'+flow.run+'-terminal.json')).read()
        if raw is None:raise EmoteObservationPending('A fully qualified original Emote seal is required before finish')
        rows=unpack(raw['payload']);need(len(rows)==1 and rows[0]['phase']=='sealed' and same(rows[0]['seal'],self.seal))
        with read_scope(fresh=True) as reads:
            window=self.terminal.window(retired=True);journal=IOSEmoteTerminalJournal(window,check=self.terminal.guard)
            need(journal.state['phase']=='sealed' and same(journal.state['seal'],self.seal))
            paths=metadata_paths(window,self.terminal.responsibilities)+[journal.store]
            copies={str(path.path):path.read() for path in paths}
            ownership=IOSEmoteRootedOwnership(copies,run=flow.run,lock=flow.lock,actor_lock=actor.lock)
            proof,floor,prefixes=ownership.read_with_retirement_context();_seal(proof,self.seal,run=flow.run,role='primary',binding=flow.state['binding'])
            current=flow.phase.status()
            inactive(current,run=flow.run,instance=flow.state['phaseInstance'],ticket=self.seal['description']['ticket'],after=floor)
            inactive_prefixes(current,prefixes,run=flow.run)
            census=IOSEmoteRootedInventory(journal,reads);census.guard();self.terminal.guard()
        # These exact current snapshots become immutable copies. Subsequent
        # destructive admission is owned by a new typed closed process cut.
        self.terminal.responsibilities=[];self.terminal.inventory=None
        def qualify(actual):
            need(same(actual,copies));return IOSEmoteRootedOwnership(actual,run=flow.run,lock=flow.lock,actor_lock=actor.lock).read()
        archive=IOSEmoteRootedFinalArchive(PrivateFeatureState(flow.store.path.with_name('ios-emote-primary-'+flow.run+'-rooted-final.json')),
            flow.root,flow.state['binding'],flow.run,'primary',flow.lock,flow.lock,paths,self.terminal.clock,qualify)
        archive.begin(current);archive.freeze();return archive,ownership
    def invoke(self):
        archive,ownership=self.freeze()
        end=IOSEmoteRootedEndArchive(archive,ownership,self.seal,self.terminal.clock)
        retirement=end if end.state is not None else None
        actor=IOSEmoteRootedProcessEnd(self.actor,ownership,archive,self.seal,retirement=retirement)
        primary=IOSEmoteRootedProcessEnd(self.flow,ownership,archive,self.seal,peer=actor,retirement=retirement)
        processes=dict(actor=actor,primary=primary)
        if end.state is None:
            for role in ('actor','primary'):
                process=processes[role];flow=process.flow
                if process.state is None:process.prepare()
                if process.state['phase']=='prepared':
                    # Only the still-running local role may construct live
                    # owners. Issued/uncertain paths go straight to OS reads.
                    phase=flow.phase.status()
                    inactive(phase,run=flow.run,instance=flow.state['phaseInstance'],ticket=self.seal['description']['ticket'],after=archive.state['phaseOriginal']['retiredEpochMs'])
                    parts=flow.components();process.stop(parts['scope'],flow.pointers(parts),flow.keys(parts))
                if not process.advance():raise EmoteObservationPending('Original '+role+' Emote OS quiet window is still pending')
        actor_sdk=IOSEmoteRootedSessionEnd(actor,processes)
        primary_sdk=IOSEmoteRootedSessionEnd(primary,processes,peer=actor_sdk)
        sessions=dict(actor=actor_sdk,primary=primary_sdk)
        if end.state is None:
            for role in ('actor','primary'):
                if not sessions[role].finish():raise EmoteObservationPending('Original '+role+' Emote SDK-end OS quiet window is still pending')
        end.attach(processes,sessions)
        if end.state is None:end.prepare()
        end.retire()
        from ios.adapters.emote_rooted_terminal_end import role_end
        result=dict(featureTerminalEndVersion=1,seal=deepcopy(self.seal),roles={role:role_end(processes[role],sessions[role],end) for role in ('primary','actor')})
        contract.ended(result,self.seal);return dict(stage='finish',end=result)
