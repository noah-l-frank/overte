"""Paired typed Emote end authority and ordered metadata-only retirement.

The frozen live archive is immutable. Exact final fence WALs come from retained
process originals. Only this journal's durable per-path deletion intent admits
their later absence; neither a missing file nor a namespace grants authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.emote_session_carriers import inventory


class IOSEmoteRootedEndArchive:
    def __init__(self,archive,ownership,seal,guard):
        need(type(archive) is IOSEmoteRootedFinalArchive and type(ownership) is IOSEmoteRootedOwnership and callable(guard))
        self.archive,self.ownership,self.seal,self.guard=archive,ownership,deepcopy(seal),guard
        self.run=ownership.roles.run;self.processes=self.sessions=None
        self.store=PrivateFeatureState(archive.store.path.with_name('ios-emote-primary-'+self.run+'-rooted-end.json'))
        need(self.store.path not in {path.path for path in archive.paths} and archive.role=='primary'
            and archive.lock is ownership.roles.locks['primary'])
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(iosEmoteRootedEndArchiveVersion=1,runId=self.run,archiveSha256=digest(self.archive.previous),
            seal=deepcopy(self.seal),payload=pack([state]))
    def decode(self,value):
        exact(value,{'iosEmoteRootedEndArchiveVersion','runId','archiveSha256','seal','payload'})
        rows=unpack(value['payload']);need(type(value['iosEmoteRootedEndArchiveVersion']) is int and len(rows)==1
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','processes','sessions','retired','pending'})
        need(state['phase'] in ('prepared','retiring','complete') and type(state['retired']) is int
            and 0<=state['retired']<=len(self.archive.paths))
        for key in ('processes','sessions'):
            exact(state[key],{'primary','actor'})
            need(all(type(sha) is str and len(sha)==64 and all(c in '0123456789abcdef' for c in sha) for sha in state[key].values()))
        if state['pending'] is not None:need(state['phase']=='retiring' and type(state['pending']) is int
            and state['pending']==state['retired'] and state['pending']<len(self.archive.paths))
        if state['phase']=='prepared':need(state['retired']==0 and state['pending'] is None)
        if state['phase']=='complete':need(state['retired']==len(self.archive.paths) and state['pending'] is None)
        return deepcopy(state)
    def bound(self,*,writing=False):
        need(self.guard() is not False)
        for lock in self.ownership.roles.locks.values():lock.assert_held()
        archive=self.archive;need(archive.state is not None and archive.state['phase']=='validated'
            and same(archive.store.read(),archive.previous) and same(archive.envelope(archive.state),archive.previous)
            and same(self.store.read(),self.previous))
        copies=deepcopy(self.ownership.roles.copies);copies[str(self.ownership.path)]=deepcopy(self.ownership.terminal)
        need(same(archive.copies(),copies))
        if not writing:need(self.previous is None and self.state is None or self.previous is not None and same(self.state,self.decode(self.previous)))
        return True
    def save(self):
        self.bound(writing=True);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def attach(self,processes,sessions):
        from ios.adapters.emote_rooted_process_end import IOSEmoteRootedProcessEnd
        from ios.adapters.emote_rooted_session_end import IOSEmoteRootedSessionEnd
        exact(processes,{'primary','actor'});exact(sessions,{'primary','actor'})
        for role in ('primary','actor'):
            process,session=processes[role],sessions[role]
            need(type(process) is IOSEmoteRootedProcessEnd and type(session) is IOSEmoteRootedSessionEnd
                and process.archive is self.archive and process.ownership is self.ownership and process.role==role
                and session.process is process and same(process.seal,self.seal))
            if self.state is not None:need(digest(process.previous)==self.state['processes'][role]
                and digest(session.previous)==self.state['sessions'][role])
        need(processes['primary'].peer is processes['actor'] and sessions['primary'].peer is sessions['actor'])
        self.processes,self.sessions=dict(processes),dict(sessions)
        for process in processes.values():process.retirement=self if self.state is not None else None
    def expected(self):
        need(self.processes is not None);copies=self.archive.copies()
        for role,process in self.processes.items():
            value=process.fence_original()
            for key,tail in (('scope','marker'),('keys','keys'),('pointers','pointers')):
                path=process.lock.path.with_name('ios-emote-'+role+'-'+tail+'.json')
                need(str(path) in copies);copies[str(path)]=deepcopy(value[key])
        return copies
    def metadata(self):
        self.bound();need(self.state is not None);copies=self.expected()
        for index,store in enumerate(self.archive.paths):
            current=store.read();expected=copies[str(store.path)]
            deleted=index<self.state['retired']
            pending=index==self.state['pending']
            if deleted:need(current is None)
            elif pending:need(current is None or same(current,expected))
            else:need(same(current,expected))
        return copies
    def store_for(self,path,value):
        """Only exact typed fence metadata gets its retained interpretation."""
        need(self.state is not None)
        features={lock.path.with_name('ios-emote-'+role+'-feature.json'):role
            for role,lock in self.ownership.roles.locks.items()}
        if path in features:
            # Bootstrap only this exact absent feature path before reopening
            # its typed process owner. The durable end index and both actual
            # end-journal digests must already bind its deletion responsibility.
            self.bound();copies=self.archive.copies();paths=[store.path for store in self.archive.paths]
            need(path in paths and str(path) in copies and same(value,copies[str(path)]))
            index=paths.index(path);current=PrivateFeatureState(path).read()
            if index<self.state['retired']:need(current is None)
            elif index==self.state['pending']:need(current is None or same(current,value))
            else:need(same(current,value))
            role=features[path]
            for kind,tail in (('processes','process'),('sessions','sdk')):
                store=PrivateFeatureState(path.with_name('ios-emote-'+role+'-'+self.run+'-rooted-'+tail+'-end.json'))
                raw=store.read();need(raw is not None and digest(raw)==self.state[kind][role])
            return Frozen(path,value)
        need(self.processes is not None)
        allowed={process.lock.path.with_name('ios-emote-'+role+'-'+tail+'.json')
            for role,process in self.processes.items() for tail in ('marker','keys','pointers')}
        need(path in allowed);copies=self.metadata();need(same(copies[str(path)],value))
        return Frozen(path,value)
    def roots(self):
        return {root for process in self.processes.values() for root in (process.root,process.lock.path.parent)}
    def verify(self):
        self.bound();need(self.state is not None and self.processes is not None and self.sessions is not None)
        leases=[EmoteOriginalLease(root,[]) for root in self.roots()]
        with read_scope(fresh=True) as reads:
            self.metadata();proof=self.ownership.read()
            from ios.adapters.emote_rooted_fence import _seal
            for role,process in self.processes.items():
                need(digest(process.previous)==self.state['processes'][role] and digest(self.sessions[role].previous)==self.state['sessions'][role])
                _seal(proof,self.seal,run=self.run,role=role,binding=process.binding)
                process.completed();self.sessions[role].completed()
            self.bound();need(inventory(self.roots())<=reads)
        for lease in leases:lease.guard()
        return True
    def prepare(self):
        self.bound();need(self.state is None and self.processes is not None and self.sessions is not None)
        for role in ('actor','primary'):self.processes[role].completed();self.sessions[role].completed()
        copies=self.expected()
        need(all(same(store.read(),copies[str(store.path)]) for store in self.archive.paths))
        self.state=dict(phase='prepared',processes={role:digest(owner.previous) for role,owner in self.processes.items()},
            sessions={role:digest(owner.previous) for role,owner in self.sessions.items()},retired=0,pending=None)
        self.save()
        for process in self.processes.values():process.retirement=self
        self.verify()
    def retire(self):
        mutable=[store.path for store in self.archive.paths]+[self.store.path]
        leases=[EmoteOriginalLease(root,mutable) for root in self.roots()]
        self.verify()
        for lease in leases:lease.guard()
        def unchanged():
            self.bound()
            for lease in leases:lease.guard()
        if self.state['phase']=='complete':self.metadata();return True
        self.state['phase']='retiring';self.save()
        while self.state['retired']<len(self.archive.paths):
            index=self.state['retired'];copies=self.metadata();store=self.archive.paths[index]
            if self.state['pending'] is None:self.state['pending']=index;self.save()
            unchanged();current=store.read();need(current is None or same(current,copies[str(store.path)]))
            if current is not None:store.discard(current)
            need(store.read() is None);unchanged()
            self.state.update(retired=index+1,pending=None);self.save()
        self.state['phase']='complete';self.save();unchanged();self.verify();return True
