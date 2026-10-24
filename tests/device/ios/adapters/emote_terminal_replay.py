"""Read an original rooted Emote live seal without an SDK or native query.

Every fact is rederived from the actual retained role/peer/file/PNG/publication
originals. This historical read cannot discharge newer current-WAL owners or
establish process death, SDK deletion or a renewed observation clock.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_live import IOSEmoteRootedLive
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal


class IOSEmoteTerminalReplay:
    def __init__(self,store,lock,actor_lock):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock)
            and isinstance(actor_lock,ScriptSourceLock) and lock.path!=actor_lock.path)
        self.store,self.lock,self.actor_lock=store,lock,actor_lock
        lock.assert_held();actor_lock.assert_held();value=self.previous=store.read()
        exact(value,{'iosEmoteTerminalJournalVersion','runId','artifactRoot','bindings','locks','payload'})
        need(type(value['iosEmoteTerminalJournalVersion']) is int and value['iosEmoteTerminalJournalVersion']==1)
        self.run=identifier(value['runId']);exact(value['bindings'],{'primary','actor'});exact(value['locks'],{'primary','actor'})
        self.bindings={role:deepcopy(context(binding)) for role,binding in value['bindings'].items()}
        need(value['locks']==dict(primary=str(lock.path),actor=str(actor_lock.path))
            and store.path==lock.path.with_name('ios-emote-primary-'+self.run+'-terminal.json')
            and type(value['artifactRoot']) is str)
        self.root=Path(value['artifactRoot'])
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','description','references','seal','staged','record','pending'})
        need(state['phase']=='sealed' and state['staged'] is state['pending'] is None)
        self.state=deepcopy(state)
        self.frames=OriginalFrameStore(self.root,self.bindings['primary'],self.run,'primary',self.guard,self.forbidden,
            namespace='emote-terminal',schema_prefix='iosEmoteTerminalProof',kind='inputs')
        self.frames.expand(state['record']);need(state['record']['index']==1);self.guard()

    @staticmethod
    def forbidden(*_args,**_kwargs):need(False)

    def guard(self):
        self.lock.assert_held();self.actor_lock.assert_held();need(same(self.store.read(),self.previous));return True

    def read(self):
        self.guard();proof=self.frames.read(self.frames.expand(self.state['record']))
        exact(proof,{'seal','original'});original=proof['original']
        exact(original,{'iosEmoteTerminalWindowVersion','description','references','samples','journals','primary','actor','publisher'})
        exact(original['journals'],{'primary','actor'});lives={}
        for role,lock in (('primary',self.lock),('actor',self.actor_lock)):
            path=lock.path.with_name('ios-emote-'+role+'-'+self.run+'-terminal-live.json')
            live=IOSEmoteRootedLive.archive(original['journals'][role],store=Frozen(path,original['journals'][role]),
                lock=lock,primary_lock=self.lock)
            need(same(live.binding,self.bindings[role]) and live.run==self.run);lives[role]=live
        need(lives['primary'].root==self.root)
        window=IOSEmoteTerminalWindow(lives['primary'],lives['actor']);journal=IOSEmoteTerminalJournal(window)
        need(same(journal.previous,self.previous) and same(journal.state,self.state))
        journal.proof(proof,self.state)
        publisher=Frozen(self.actor_lock.path.with_name('phase-publication-emotes-'+self.run+'-actor.json'),original['publisher'])
        actual=window.qualify(self.state['description'],original['samples'],self.state['references'],publisher_store=publisher)
        need(same(actual,proof));journal.bound();self.guard();return deepcopy(actual)
