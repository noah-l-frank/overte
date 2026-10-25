"""Avatar's explicit live-held seal and once-only process/SDK retirement.

Cached Login operands remain resources in every live observation. Only genuine
OS absence ends them. This owner never publishes a Complete retirement row.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope
from adapters.phase_witness_publisher import PhaseWitnessPublisher
from adapters.script_feature.history import pack,unpack,same
from feature_journeys import terminal
from feature_journeys.retirement_receipts import binding_from_context
from ios.adapters import appium_adapter as backend,avatar_operation_clock as operation_clock
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.installed_code import source as process_source
from ios.adapters.avatar_final import checked as final_checked
from ios.adapters.process_retirement import IOSProcessRetirement,filename

ROLES=('primary','actor')


def terminal_clock_begin(epoch,monotonic):
    need(number(epoch,1,1e15) and number(monotonic,0,1e15))
    return dict(avatarTerminalClockVersion=1,hostStartedEpochMs=epoch,hostStartedMonotonic=monotonic,
        deadlineEpochMs=epoch+30000,deadlineMonotonic=monotonic+30)


def terminal_clock_validate(value):
    # Existing private 25-second intents keep their original grammar/bound.
    need(type(value) is dict)
    if 'avatarOperationClockVersion' in value:return operation_clock.validate(value)
    exact(value,{'avatarTerminalClockVersion','hostStartedEpochMs','hostStartedMonotonic','deadlineEpochMs','deadlineMonotonic'})
    need(type(value['avatarTerminalClockVersion']) is int and value['avatarTerminalClockVersion']==1
        and number(value['hostStartedEpochMs'],1,1e15) and number(value['hostStartedMonotonic'],0,1e15)
        and value['deadlineEpochMs']==value['hostStartedEpochMs']+30000 and value['deadlineMonotonic']==value['hostStartedMonotonic']+30)
    return value


def terminal_clock_check(value,epoch,monotonic):
    terminal_clock_validate(value)
    if 'avatarOperationClockVersion' in value:return operation_clock.check(value,epoch,monotonic)
    if not (number(epoch,value['hostStartedEpochMs'],value['deadlineEpochMs'])
            and number(monotonic,value['hostStartedMonotonic'],value['deadlineMonotonic'])
            and epoch<value['deadlineEpochMs'] and monotonic<value['deadlineMonotonic']
            and abs(epoch-value['hostStartedEpochMs']-(monotonic-value['hostStartedMonotonic'])*1000)<=250):
        raise NativeUIError('Original Avatar terminal deadline has elapsed or changed')
    return monotonic


class AvatarTerminal:
    def __init__(self,flow):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(type(flow) is IOSAvatarFeature and flow.role=='primary')
        self.flow=flow;self.store=PrivateFeatureState(flow.store.path.with_name('ios-avatar-primary-'+flow.run+'-terminal.json'))
        flow.lock.assert_held();self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)

    @classmethod
    def archive(cls,flow,value):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(type(flow) is IOSAvatarFeature and flow.role=='primary');result=object.__new__(cls);result.flow=flow
        result.store=PrivateFeatureState(flow.store.path.with_name('ios-avatar-primary-'+flow.run+'-terminal.json'))
        need(same(result.store.read(),value));result.previous=deepcopy(value);result.state=result.decode(value);return result

    def envelope(self,state):return dict(iosAvatarTerminalVersion=1,runId=self.flow.run,bindings=self.flow.state['bindings'],payload=pack([state]))
    def decode(self,value):
        exact(value,{'iosAvatarTerminalVersion','runId','bindings','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosAvatarTerminalVersion']) is int and value['iosAvatarTerminalVersion']==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'description','roles','samples','seal','sealedRoles','actorPublisher','finish','archive','end'})
        terminal.description(state['description'],area='avatar-people',run=self.flow.run);exact(state['roles'],set(ROLES))
        if state['seal'] is None:need(all(state[key] is None for key in ('samples','sealedRoles','actorPublisher','finish','archive','end')))
        else:
            exact(state['sealedRoles'],set(ROLES));terminal.sealed(state['seal'],state['description'],self.flow.kept(state['samples'])['samples'])
        if state['end'] is not None:
            need(state['finish'] is not None and state['archive'] is not None);terminal.ended(state['end'],state['seal'])
        if state['archive'] is not None:
            need(state['finish'] is not None);exact(state['archive'],{'index','sha256'})
            archive=self.flow.kept(state['archive']);need(type(archive.get('iosAvatarTerminalArchiveVersion')) is int and archive['iosAvatarTerminalArchiveVersion']==1)
        if state['finish'] is not None:
            exact(state['finish'],{'phase','operationClock'});terminal_clock_validate(state['finish']['operationClock'])
            from feature_journeys.phase_fixture import validate
            phase=self.flow.kept(state['finish']['phase']);validate(phase,run=self.flow.run,area='avatar-people',request=phase['requestId'],epoch=phase['capturedEpochMs'])
            need(not phase['active'] and phase['instance']==self.flow.state['phaseInstance'])
        return deepcopy(state)
    def guard(self):
        f=self.flow;f.lock.assert_held();f.clock();need(same(self.store.read(),self.previous))
        f.runtime.adapter._candidate_guard(complete=True)
        for role in ROLES:
            target=f.runtime.adapter._target(f.selectors[role]);saved=f.runtime.adapter.read_session(f.selectors[role]);binding=f.state['bindings'][role]
            need(type(saved) is dict and saved.get('sessionId')==binding['sessionId'] and same(
                f.runtime.adapter._scope(f.selectors[role],binding['sessionId'],saved,target),{key:value for key,value in binding.items() if key!='processIdentity'}))
        return True
    def save(self):
        self.guard();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def roles(self,references=None):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        f=self.flow;result={}
        for role in ROLES:
            f.locks[role].assert_held()
            raw=f.kept(references[role]) if references is not None else PrivateFeatureState(f.runtime.state_path(f.selectors[role]).with_name('ios-avatar-'+role+'-feature.json')).read()
            need(raw is not None);owner=IOSAvatarFeature.archive(f.runtime,raw,f.client,f.locks)
            need(owner.role==role and owner.run==f.run and owner.state['phase']=='terminal-ready' and same(owner.state['bindings'],f.state['bindings'])
                and owner.state['phaseInstance']==f.state['phaseInstance'] and owner.state['cleanup'][0]['ticket']==f.state['cleanup'][0]['ticket'])
            result[role]=(owner,raw)
        return result
    @staticmethod
    def ready(owner):return next(row for row in owner.state['cleanup'] if row['kind']=='final-ready')
    def role_description(self,owner,event):
        proof=owner.terminal_live_proof(event)
        return dict(binding=binding_from_context(owner.state['bindings'][owner.role]),heldResources=deepcopy(proof['heldResources'][owner.role]),
            originalSha256=proof['originalSha256'])
    def inspect(self):
        self.guard();f=self.flow
        if self.state is None:
            owners=self.roles();rows={};refs={}
            for role,(owner,raw) in owners.items():
                rows[role]=self.role_description(owner,self.ready(owner));refs[role]=f.keep(raw)
            description=dict(featureTerminalVersion=1,profile=terminal.PROFILE,area='avatar-people',runId=f.run,ticket=f.state['cleanup'][0]['ticket'],roles=rows)
            terminal.description(description);self.state=dict(description=description,roles=refs,samples=None,seal=None,sealedRoles=None,actorPublisher=None,finish=None,archive=None,end=None);self.save()
        self.verify_description();return deepcopy(self.state['description'])
    def verify_description(self):
        need(self.state is not None)
        for role,(owner,_raw) in self.roles(self.state['roles']).items():
            need(same(self.role_description(owner,self.ready(owner)),self.state['description']['roles'][role]))
        return self.state['description']
    @final_checked
    def verify_window(self,owners,samples,publisher):
        descriptor=self.verify_description();terminal.window(samples,descriptor);f=self.flow
        actor=owners['actor'][0];path=actor.store.path.with_name('phase-publication-avatar-people-'+f.run+'-actor.json')
        journal=PhaseWitnessPublisher.archive(publisher,store=PrivateFeatureState(path),binding=f.state['bindings']['actor'],run=f.run,area='avatar-people',
            fixture_url=f.client.url,phase_instance=f.state['phaseInstance'],validate_original=actor.terminal_witness_original)
        need(journal['pending'] is None);reader=object.__new__(PhaseWitnessPublisher)
        reader.store,reader.binding,reader.run,reader.area=PrivateFeatureState(path),f.state['bindings']['actor'],f.run,'avatar-people'
        reader.url,reader.instance,reader.validate_original=f.client.url,f.state['phaseInstance'],actor.terminal_witness_original
        receipts=[reader.load(ref) for ref in journal['records']];last={}
        for pair in samples:
            primary=owners['primary'][0];matches=[]
            for event in primary.state['cleanup']:
                if event['kind']=='final-observation':
                    proof=primary.terminal_live_proof(event)
                    if proof['public']['sequence']==pair['primary']['sequence']:matches.append(proof)
            need(len(matches)==1 and same(matches[0]['public'],pair['primary']));last['primary']=matches[0]
            matched=[row for row in receipts if row['mode']=='published' and same(row['entry'],pair['actor'])]
            need(len(matched)==1);original=matched[0]['intent']['original']
            need(type(original.get('iosAvatarTerminalObservationReferenceVersion')) is int and original['iosAvatarTerminalObservationReferenceVersion']==1)
            event=actor.kept(original['reference']);last['actor']=actor.terminal_live_proof(event)
            for role in ROLES:need(same(last[role]['heldResources'][role],descriptor['roles'][role]['heldResources']))
        return last
    def seal(self,description,samples):
        self.guard();need(self.state is not None and same(description,self.verify_description()))
        if self.state['seal'] is not None:
            need(same(samples,self.flow.kept(self.state['samples'])['samples']));self.verify_seal();return deepcopy(self.state['seal'])
        f=self.flow;owners=self.roles();publisher=PrivateFeatureState(owners['actor'][0].store.path.with_name('phase-publication-avatar-people-'+f.run+'-actor.json')).read()
        need(publisher is not None);last=self.verify_window(owners,samples,publisher)
        seal=dict(featureTerminalSealVersion=1,description=deepcopy(description),windowSha256=digest(samples),
            liveOriginalSha256=digest({role:last[role]['originalSha256'] for role in ROLES}))
        terminal.sealed(seal,description,samples)
        self.state.update(samples=f.keep(dict(samples=deepcopy(samples))),sealedRoles={role:f.keep(raw) for role,(_owner,raw) in owners.items()},
            actorPublisher=f.keep(publisher),seal=seal);self.save();self.verify_seal();self.fresh(last)
        return deepcopy(seal)
    @final_checked
    def verify_seal(self):
        need(self.state is not None and self.state['seal'] is not None)
        samples=self.flow.kept(self.state['samples'])['samples']
        last=self.verify_window(self.roles(self.state['sealedRoles']),samples,self.flow.kept(self.state['actorPublisher']))
        terminal.sealed(self.state['seal'],self.state['description'],samples)
        need(self.state['seal']['liveOriginalSha256']==digest({role:last[role]['originalSha256'] for role in ROLES}));return last
    def fresh(self,last):
        f=self.flow;now,mono=f.epoch_ms(),f.monotonic()
        for proof in last.values():
            a=proof['acquisition'];need(a['hostAfterEpochMs']<=now<a['hostBeforeEpochMs']+1500
                and a['hostAfterMonotonic']<=mono<a['hostBeforeMonotonic']+1.5
                and abs(now-a['hostBeforeEpochMs']-(mono-a['hostBeforeMonotonic'])*1000)<=250)

    def finish_guard(self):
        self.guard();need(self.state['finish'] is not None)
        terminal_clock_check(self.state['finish']['operationClock'],self.flow.epoch_ms(),self.flow.monotonic());return True

    @final_checked
    def original_graph(self,processes):
        """Recompute actual typed owners and every historical publication."""
        self.verify_seal();f=self.flow;self.verify_description()
        for owner,_raw in self.roles(self.state['sealedRoles']).values():
            for event in owner.state['cleanup']:
                if event['kind'] in ('final-ready','final-observation'):owner.terminal_live_proof(event)
                elif event['kind'] in ('scene','scene-publication'):
                    owner.scoped_scene(event).derive(owner.kept(event['scoped']))
            if owner.role=='actor':
                event=next(row for row in owner.state['cleanup'] if row['kind']=='scene-publication');need(event['published'])
                from adapters.phase_retirement_publisher import PhaseRetirementPublisher
                PhaseRetirementPublisher.archive(owner.kept(event['publisher']),store=PrivateFeatureState(owner.store.path.with_name(
                    'phase-retirement-avatar-people-'+f.run+'-actor.json')),binding=owner.state['bindings']['actor'],run=f.run,area='avatar-people',
                    fixture_url=f.client.url,phase_instance=f.state['phaseInstance'],validate_original=owner.retirement_original)
        for process in processes.values():
            need(same(process.store.read(),process.previous));process.decode(process.previous)
            need(process.state['phase']=='ended');process.process_original(process.state['process'])

    def archive_originals(self,processes):
        """Immutable typed-graph membership, retaining all files after SDK end."""
        import os
        from pathlib import Path
        from adapters.original_file_reads import scope as original_reads
        from adapters.script_feature.history import canonical
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        f=self.flow;roots={f.root}|{owner.root for owner,_raw in self.roles(self.state['sealedRoles']).values()}
        roots|={process.store.path.parent for process in processes.values()}
        # Only these two genuine CAS parents may advance while the immutable
        # proof file is admitted. Every process/SDK end record remains fixed.
        leases=[EmoteOriginalLease(root,[f.store.path,self.store.path]) for root in sorted(roots)]
        with original_reads(fresh=True) as reads:self.original_graph(processes)
        files=[]
        for path in sorted(reads-{f.store.path,self.store.path}):
            path=Path(path);before=path.lstat()
            with path.open('rb') as stream:raw=stream.read();need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(os.fstat(stream.fileno())))
            need(EmoteOriginalLease.signature(before)==EmoteOriginalLease.signature(path.lstat()))
            files.append(dict(path=str(path),sha256=__import__('hashlib').sha256(raw).hexdigest(),signature=list(EmoteOriginalLease.signature(before))))
        value=dict(iosAvatarTerminalArchiveVersion=1,runId=f.run,bindings=deepcopy(f.state['bindings']),sealSha256=digest(self.state['seal']),
            originalFiles=files,processes={role:deepcopy(process.previous) for role,process in processes.items()})
        for lease in leases:lease.guard()
        if self.state['archive'] is None:
            ledger=f.snapshot_ledger();index=len(f.state['snapshots'])+1;store=ledger.originals
            body={store.key('FrameVersion'):1,'kind':store.kind,'binding':store.binding,'runId':store.run,'role':store.role,'index':index,'frame':value}
            raw=canonical(body);descriptor={store.key('OriginalVersion'):1,'kind':store.kind,'binding':store.binding,'runId':store.run,
                'role':store.role,'index':index,'sha256':__import__('hashlib').sha256(raw).hexdigest(),'bytes':len(raw),'phase':'planned','file':None}
            reserved=store.path(descriptor);need(not os.path.lexists(reserved))
            for lease in leases:lease.mutable.add(reserved)
            reference=f.keep(value);need(same(f.kept(reference),value));self.state['archive']=reference;self.save()
        else:need(same(f.kept(self.state['archive']),value))
        for lease in leases:lease.guard()
        return self.state['archive']['sha256']

    @final_checked
    def verify_end(self,*,membership=None):
        import hashlib
        from pathlib import Path
        from adapters.original_file_reads import scope as original_reads
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        need((membership is None or type(membership) is set) and self.state['end'] is not None and self.state['archive'] is not None)
        processes={}
        for role in ROLES:
            path=self.flow.runtime.state_path(self.flow.selectors[role]).with_name('ios-avatar-'+role+'-'+self.flow.run+'-terminal-process.json')
            need(PrivateFeatureState(path).read() is not None);processes[role]=AvatarTerminalProcess(self,role)
        roots={self.flow.root}|{owner.root for owner,_raw in self.roles(self.state['sealedRoles']).values()}|{p.store.path.parent for p in processes.values()}
        leases=[EmoteOriginalLease(root,[self.flow.store.path,self.store.path]) for root in sorted(roots)]
        with original_reads(fresh=True) as reads:self.original_graph(processes)
        value=self.flow.kept(self.state['archive'])
        exact(value,{'iosAvatarTerminalArchiveVersion','runId','bindings','sealSha256','originalFiles','processes'})
        need(type(value['iosAvatarTerminalArchiveVersion']) is int and value['iosAvatarTerminalArchiveVersion']==1 and value['runId']==self.flow.run
            and same(value['bindings'],self.flow.state['bindings']) and value['sealSha256']==digest(self.state['seal'])
            and same(value['processes'],{role:process.previous for role,process in processes.items()}))
        need(type(value['originalFiles']) is list and len(value['originalFiles'])<=50000);names=[]
        for row in value['originalFiles']:
            exact(row,{'path','sha256','signature'});need(type(row['path']) is str);names.append(row['path'])
        # Reject an unowned path before opening it. The independent complete
        # typed decoder, rather than archive-supplied names, defines membership.
        need(names==sorted(set(names)) and set(names)=={str(path) for path in reads-{self.flow.store.path,self.store.path}})
        for row in value['originalFiles']:
            path=Path(row['path']);before=path.lstat()
            need(list(EmoteOriginalLease.signature(before))==row['signature'] and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
                and list(EmoteOriginalLease.signature(path.lstat()))==row['signature'])
        end=dict(featureTerminalEndVersion=1,seal=self.state['seal'],roles={role:process.role_end(self.state['archive']['sha256']) for role,process in processes.items()})
        terminal.ended(end,self.state['seal']);need(same(end,self.state['end']))
        for lease in leases:lease.guard()
        if membership is not None:membership.update(reads)
        return deepcopy(end)

    def finish(self,seal):
        need(self.state is not None and same(seal,self.state['seal']));f=self.flow
        if self.state['end'] is not None:
            # Already-ended originals stay usable after the canonical caller
            # retires SDK/Installed metadata. No live guard or source factory.
            for lock in f.locks.values():lock.assert_held()
            need(same(self.store.read(),self.previous) and same(f.store.read(),f.previous))
            from ios.adapters.avatar_ended_archive import verify
            binding=verify(f.runtime.adapter,f.selector,f.previous,self.previous,held_locks=f.locks)
            need(same(binding,f.state['bindings']['primary']));return deepcopy(self.state['end'])
        self.guard();self.verify_seal()
        if self.state['finish'] is None:
            before=terminal_clock_begin(f.epoch_ms(),f.monotonic());phase=f.phase.status()
            need(not phase['active'] and phase['instance']==f.state['phaseInstance'])
            self.state['finish']=dict(phase=f.keep(phase),operationClock=before);self.save()
        processes={role:AvatarTerminalProcess(self,role) for role in ROLES}
        with transport_scope(self.finish_guard):
            for process in processes.values():
                self.finish_guard()
                if process.state['phase']=='sealed':process.stop()
            for _ in range(128):
                self.finish_guard()
                for process in processes.values():
                    if process.state['phase']=='stop-issued':process.process_round()
                if all(process.state['phase'] in ('os-quiet','delete-issued','ended') for process in processes.values()):break
                f.sleep(.15)
            else:need(False)
            for process in processes.values():
                if process.state['phase'] in ('os-quiet','delete-issued'):need(process.delete())
            archive_sha=self.archive_originals(processes)
            result=dict(featureTerminalEndVersion=1,seal=deepcopy(seal),roles={role:process.role_end(archive_sha) for role,process in processes.items()})
            terminal.ended(result,seal);self.state['end']=result;self.save();self.finish_guard();return deepcopy(result)


class AvatarTerminalProcess:
    """Exactly one Stop and DELETE for one sealed, actually admitted SDK."""
    def __init__(self,owner,role):
        need(type(owner) is AvatarTerminal and role in ROLES);owner.verify_seal();self.terminal,self.flow=owner,owner.flow
        self.role=role;f=self.flow;self.selector=f.selectors[role];self.binding=context(f.state['bindings'][role]);self.lock=f.locks[role]
        self.lock.assert_held();self.store=PrivateFeatureState(f.runtime.state_path(self.selector).with_name('ios-avatar-'+role+'-'+f.run+'-terminal-process.json'))
        need(PrivateFeatureState(self.store.path.with_name('ios-avatar-'+role+'-'+f.run+'-abort.json')).read() is None)
        self.previous=self.store.read()
        if self.previous is None:
            self.source=IOSGraphicsRuntime._graphics_final_source(f.runtime,self.selector,self.binding)
            self.bundle=f.runtime.adapter._target(self.selector)['appId'];self.state=dict(phase='sealed',stopReturned=False,process=None,sdkQueries=[],sdkPending=None)
            self.save()
        else:
            self.source=process_source(self.previous['source']);self.bundle=self.previous['bundleId'];self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosAvatarTerminalProcessVersion=1,runId=self.flow.run,role=self.role,binding=self.binding,
        sealSha256=digest(self.terminal.state['seal']),source=self.source,bundleId=self.bundle,payload=pack([state]))
    def decode(self,value):
        exact(value,{'iosAvatarTerminalProcessVersion','runId','role','binding','sealSha256','source','bundleId','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosAvatarTerminalProcessVersion']) is int and value['iosAvatarTerminalProcessVersion']==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','stopReturned','process','sdkQueries','sdkPending'})
        need(state['phase'] in ('sealed','stop-issued','os-quiet','delete-issued','ended') and type(state['stopReturned']) is bool
            and (not state['stopReturned'] or state['phase']!='sealed') and type(state['sdkQueries']) is list and len(state['sdkQueries'])<=64)
        need((state['process'] is not None)==(state['phase'] in ('os-quiet','delete-issued','ended')))
        if state['process'] is not None:self.process_original(state['process'])
        from ios.adapters.avatar_abort import IOSAvatarAbort
        for index,row in enumerate(state['sdkQueries'],1):
            exact(row,{'index','status','acquisition'});need(type(row['index']) is int and row['index']==index and row['status'] in ('present','absent','abandoned'))
            if row['status']=='abandoned':need(row['acquisition'] is None)
            else:IOSAvatarAbort.acquisition(row['acquisition'])
        need(state['sdkPending'] is None or type(state['sdkPending']) is int and state['sdkPending']==len(state['sdkQueries'])+1)
        need(not state['sdkQueries'] or state['phase'] in ('delete-issued','ended'))
        if state['phase']=='ended':need(state['sdkPending'] is None and state['sdkQueries'] and state['sdkQueries'][-1]['status']=='absent')
        return deepcopy(state)
    def guard(self):self.lock.assert_held();self.terminal.guard();need(same(self.store.read(),self.previous));return True
    def save(self):
        self.guard();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def process_store(self):return PrivateFeatureState(self.store.path.with_name(filename('avatar',self.role,0)))
    def process_original(self,reference):
        exact(reference,{'originalSha256'});store=self.process_store();value=store.read();need(value is not None and digest(value)==reference['originalSha256'])
        state=IOSProcessRetirement.archive(value,path=store.path,binding=self.binding,source=self.source,bundle=self.bundle,run=self.flow.run,
            role=self.role,stage=0,profile='avatar');need(state['pending'] is None and state['windows'] and state['windows'][-1]['complete']);return state
    def stop(self):
        self.guard();need(self.state['phase']=='sealed');f=self.flow;base=f.runtime.adapter;outer=base._operation
        need(outer in (None,'feature.avatar-people.terminal'))
        need(same(IOSGraphicsRuntime._graphics_final_source(f.runtime,self.selector,self.binding),self.source));self.state['phase']='stop-issued';self.save()
        need(base._operation==outer);old=base._session_recreation_forbidden;base._session_recreation_forbidden=True;base._operation=None
        try:
            with transport_scope(self.guard):base.invoke(self.selector,'app.stop',{})
        finally:base._session_recreation_forbidden=old;base._operation=outer
        self.state['stopReturned']=True;self.save()
    def process_round(self):
        self.guard();need(self.state['phase']=='stop-issued');f=self.flow
        reader=IOSGraphicsRuntime._retired_process_observer(f.runtime,self.selector,self.binding,self.source)
        owner=IOSProcessRetirement(self.process_store(),reader,self.binding,f.run,self.role,0,self.lock,profile='avatar')
        if not owner.advance():return False
        owner.current();IOSGraphicsRuntime._graphics_final_stopped(f.runtime,self.selector,self.binding,self.source)
        self.state.update(phase='os-quiet',process=dict(originalSha256=digest(owner.previous)));self.save();return True
    def delete(self):
        self.guard();need(self.state['phase'] in ('os-quiet','delete-issued'));f=self.flow
        if self.state['phase']=='os-quiet':
            from ios.adapters.retired_process import absent
            reader=IOSGraphicsRuntime._retired_process_observer(f.runtime,self.selector,self.binding,self.source)
            need(absent(reader.read()));self.process_original(self.state['process']);self.state['phase']='delete-issued';self.save()
            client=backend.WebDriver(f.runtime.adapter._target(self.selector)['serverUrl'])
            try:
                with transport_scope(self.guard):client.call('DELETE','/session/'+self.binding['sessionId'])
            except backend.WebDriverRequestError as error:need(error.status==404)
        return self.sdk_absence()
    def sdk_absence(self):
        self.guard();need(self.state['phase']=='delete-issued');f=self.flow
        if self.state['sdkPending'] is not None:
            self.state['sdkQueries'].append(dict(index=self.state['sdkPending'],status='abandoned',acquisition=None));self.state['sdkPending']=None;self.save()
        need(len(self.state['sdkQueries'])<64);self.state['sdkPending']=len(self.state['sdkQueries'])+1;self.save()
        before,started=f.epoch_ms(),f.monotonic();status='present';client=backend.WebDriver(f.runtime.adapter._target(self.selector)['serverUrl'])
        try:
            with transport_scope(self.guard):client.call('GET','/session/'+self.binding['sessionId'])
        except backend.WebDriverRequestError as error:need(error.status==404);status='absent'
        a=dict(hostBeforeEpochMs=before,hostAfterEpochMs=f.epoch_ms(),hostBeforeMonotonic=started,hostAfterMonotonic=f.monotonic())
        from ios.adapters.avatar_abort import IOSAvatarAbort
        IOSAvatarAbort.acquisition(a);self.state['sdkQueries'].append(dict(index=self.state['sdkPending'],status=status,acquisition=a));self.state['sdkPending']=None
        if status=='absent':self.state['phase']='ended'
        self.save();return status=='absent'

    def role_end(self,archive_sha):
        self.decode(self.previous);need(self.state['phase']=='ended');state=self.process_original(self.state['process']);store=self.process_store()
        reader=object.__new__(IOSProcessRetirement);reader.profile='avatar';reader.store=store;reader.binding=self.binding;reader.source=self.source
        reader.bundle,reader.run,reader.role,reader.stage=self.bundle,self.flow.run,self.role,0;reader.pid=int(self.binding['processIdentity'])
        window=state['windows'][-1];rows=[reader.load(state['records'][index-1]) for index in window['samples'][window['start']:]]
        need(len(rows)>=3 and all(row['mode']=='observed' for row in rows));a,b=rows[0],rows[-1]
        quiet=dict(source='dvt-owned-pid-and-bundle-state',clockDomain='appium-node-host',instance=self.source['instance'],processId=int(self.binding['processIdentity']),
            samples=len(rows),originalSha256=digest(dict(owner=store.read(),records=rows)),
            hostAfterFirstEpochMs=a['acquisition']['hostAfterEpochMs'],hostBeforeLastEpochMs=b['acquisition']['hostBeforeEpochMs'],
            hostAfterFirstMonotonic=a['acquisition']['hostAfterMonotonic'],hostBeforeLastMonotonic=b['acquisition']['hostBeforeMonotonic'],
            osAfterFirstEpochMs=a['original']['clockAfter']['epochMs'],osBeforeLastEpochMs=b['original']['clockBefore']['epochMs'],
            osAfterFirstMonotonicMs=a['original']['clockAfter']['monotonicMs'],osBeforeLastMonotonicMs=b['original']['clockBefore']['monotonicMs'])
        terminal.os_quiet(quiet,self.binding['processIdentity'])
        return dict(binding=binding_from_context(self.binding),heldOriginalSha256=self.terminal.state['description']['roles'][self.role]['originalSha256'],
            stopOriginalSha256=digest(self.previous),osAbsence=quiet,sdkDeletionOriginalSha256=digest(self.previous),archiveSha256=archive_sha)
