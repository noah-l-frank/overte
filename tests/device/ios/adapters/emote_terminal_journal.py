"""Durable rooted Emote inspect/seal originals, without process discharge.

The paired window reader supplies the facts. This owner persists its exact
proof through the existing private original-file intent protocol. Recovery
never sends input, publishes or guesses an unobserved original-file birth.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal
from ios.adapters.emote_terminal_window import IOSEmoteTerminalWindow
from ios.adapters.emote_retirement import Frozen

VERSION=1


class IOSEmoteTerminalJournal:
    Window=IOSEmoteTerminalWindow
    FORMAT_VERSION=VERSION
    WINDOW_VERSION=1

    def __init__(self,window,*,check=lambda:True):
        self.initialize(window,check,historical=False,value=None)

    @classmethod
    def archive(cls,window,value,*,check=lambda:True):
        need(type(value) is dict)
        result=object.__new__(cls);result.initialize(window,check,historical=True,value=value);return result

    def initialize(self,window,check,*,historical,value):
        need(type(window) is self.Window and callable(check));need(check() is not False);window.guard()
        self.check,self.historical=check,historical
        self.window=window;primary=window.roles['primary']
        self.root,self.binding,self.run=primary.root,deepcopy(primary.binding),primary.run
        path=primary.store.path.with_name('ios-emote-primary-'+self.run+'-terminal.json')
        self.store=Frozen(path,value) if historical else PrivateFeatureState(path)
        self.failed=False;self.previous=self.store.read();self.state=None
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,'primary',self.bound,self.intent,
            namespace='emote-terminal',schema_prefix='iosEmoteTerminalProof',kind='inputs')
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosEmoteTerminalJournalVersion=self.FORMAT_VERSION,runId=self.run,artifactRoot=str(self.root),
            bindings={role:deepcopy(live.binding) for role,live in self.window.roles.items()},
            locks={role:str(live.lock.path) for role,live in self.window.roles.items()},payload=pack([state]))

    def proof(self,value,state):
        exact(value,{'seal','original'});original=value['original']
        exact(original,{'iosEmoteTerminalWindowVersion','description','references','samples','journals','primary','actor','publisher'})
        need(type(original['iosEmoteTerminalWindowVersion']) is int and original['iosEmoteTerminalWindowVersion']==self.WINDOW_VERSION
            and same(original['description'],state['description']) and same(original['references'],state['references'])
            and same(value['seal'],state['seal']) and digest(original)==value['seal']['liveOriginalSha256'])
        terminal.sealed(value['seal'],state['description'],original['samples'])
        return value

    def decode(self,value):
        exact(value,set(self.envelope(None)));rows=unpack(value['payload'])
        need(type(value['iosEmoteTerminalJournalVersion']) is int and value['iosEmoteTerminalJournalVersion']==self.FORMAT_VERSION
            and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','description','references','seal','staged','record','pending'})
        need(state['phase'] in ('inspected','sealing','sealed'))
        terminal.description(state['description'],area='emotes',run=self.run);exact(state['references'],terminal.ROLES)
        for role,reference in state['references'].items():self.window.roles[role].originals.expand(reference)
        if state['phase']=='inspected':
            need(all(state[key] is None for key in ('seal','staged','record','pending')))
        else:
            terminal.sealed(state['seal'],state['description'])
            if state['phase']=='sealing':
                need(state['record'] is None);self.proof(state['staged'],state)
                if state['pending'] is not None:
                    self.originals.original(state['pending']);need(state['pending']['index']==1)
            else:
                need(state['staged'] is state['pending'] is None)
                self.originals.expand(state['record']);need(state['record']['index']==1)
        return deepcopy(state)

    def bound(self):
        need(not self.failed and self.check() is not False);self.window.guard();need(same(self.store.read(),self.previous))
        expected=set()
        if self.state is not None:
            record,pending=self.state['record'],self.state['pending']
            if record is not None:expected.add(self.originals.path(self.originals.expand(record)))
            if pending is not None:
                path=self.originals.path(pending)
                if path.exists():expected.add(path)
        need(set(self.root.glob('emote-terminal-frame-inputs-'+self.run+'-primary-*.json'))==expected)
        return True

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        try:
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except BaseException:self.failed=True;raise

    def inspect(self,references):
        need(not self.historical);self.bound();description=self.window.describe(references)
        if self.state is None:
            self.state=dict(phase='inspected',description=deepcopy(description),references=deepcopy(references),
                seal=None,staged=None,record=None,pending=None);self.save()
        else:need(same(description,self.state['description']) and same(references,self.state['references']))
        return dict(stage='inspect',description=deepcopy(description))

    def intent(self,kind,value):
        need(not self.historical);self.bound();need(kind=='original' and self.state is not None and self.state['phase']=='sealing')
        self.originals.original(value);need(value['index']==1)
        pending=self.state['pending']
        if pending is None:need(value['phase']=='planned')
        else:
            need(all(same(value[key],pending[key]) for key in value if key not in ('phase','file'))
                and (pending['phase'],value['phase']) in (('planned','opened'),('opened','saved')))
            if pending['file'] is not None:need(same(value['file'],pending['file']))
        self.state['pending']=deepcopy(value);self.save()

    def recover(self):
        """File-only adoption; a public seal still requires full qualification."""
        need(not self.historical);self.bound();need(self.state is not None)
        if self.state['phase']!='sealing':return
        pending=self.state['pending']
        if pending is None:
            # No file intent was committed. The exact original proof was
            # staged before any file creation; O_EXCL still refuses an orphan.
            reference=self.originals.write(1,self.state['staged'])
        else:
            need(pending['phase'] in ('opened','saved'))
            need(same(self.originals.read(pending),self.state['staged']))
            reference=self.originals.compact(dict(pending,phase='saved'))
        need(same(self.originals.read(self.originals.expand(reference)),self.state['staged']))
        self.state.update(phase='sealed',record=reference,staged=None,pending=None);self.save()

    def seal(self,description,samples,*,publisher_store):
        need(not self.historical);self.bound();need(self.state is not None and same(description,self.state['description']))
        terminal.window(samples,description)
        actual=self.window.qualify(description,samples,self.state['references'],publisher_store=publisher_store)
        if self.state['phase']=='inspected':
            self.state.update(phase='sealing',seal=deepcopy(actual['seal']),staged=deepcopy(actual));self.save()
        else:
            retained=self.state['staged'] if self.state['phase']=='sealing' else self.originals.read(self.originals.expand(self.state['record']))
            self.proof(retained,self.state);need(same(actual,retained))
        self.recover();need(self.state['phase']=='sealed');self.bound()
        return dict(stage='seal',seal=deepcopy(actual['seal']))
