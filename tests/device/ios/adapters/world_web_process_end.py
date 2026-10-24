"""Role-owned one-send normal Stop and independent original OS retirement.

The scene seal retains real cache roots, image copies and GPU holders. Only
this separate existing-SDK numeric-PID/DVT quiet window retires those process
resources. Lost Stop delivery is never replayed by this coordinator.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as original_reads
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.installed_code import source as installed_source
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent
from ios.adapters.world_web_api_clock import check
from ios.adapters import world_web_fence as fence
from ios.adapters.emote_original_lease import EmoteOriginalLease


class WorldWebProcessEnd:
    def __init__(self,flow):
        from ios.adapters.world_web_feature import IOSWorldWebFeature
        need(isinstance(flow,IOSWorldWebFeature));self.flow,self.lock=flow,flow.lock
        self.lock.assert_held();flow.primary_lock.assert_held();need(flow.state is not None)
        self.binding,self.run,self.role=deepcopy(flow.state['binding']),flow.run,flow.role
        self.store=flow.runtime._world_web_store(flow.selector,'ios-world-web-'+self.role+'-'+self.run+'-process-final.json')
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
    def envelope(self,state):
        return dict(iosWorldWebProcessFinalVersion=1,binding=self.binding,runId=self.run,role=self.role,payload=pack([state]))
    def bound(self,*,writing=False):
        if not writing:need(self.previous is None and self.state is None or self.previous is not None and same(self.state,self.decode(self.previous)))
        check();self.lock.assert_held();need(same(self.store.read(),self.previous) and same(self.flow.state['binding'],self.binding))
    def process_store(self):
        return PrivateFeatureState(self.store.path.with_name(filename('worldweb',self.role,0)))
    def decode(self,value):
        exact(value,{'iosWorldWebProcessFinalVersion','binding','runId','role','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosWorldWebProcessFinalVersion']) is int and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','source','bundleId','fence','sceneSha256','processSha256','peer'})
        need(state['phase'] in ('fencing','stop-issued','stopped','complete'));installed_source(state['source'])
        if self.role=='actor':need(state['peer'] is None)
        else:self.peer_original(state['peer'])
        need(state['bundleId']==self.flow.runtime.adapter.target(self.flow.selector)['appId'])
        if state['fence'] is None:need(state['phase']=='fencing')
        else:need(state['fence']['binding']==self.binding and state['fence']['runId']==self.run and state['fence']['role']==self.role
            and state['fence']['sceneSha256']==state['sceneSha256'])
        if state['processSha256'] is not None:
            process=self.process_store().read();need(process is not None and digest(process)==state['processSha256'])
            decoded=IOSProcessRetirement.archive(process,path=self.process_store().path,binding=self.binding,source=state['source'],
                bundle=state['bundleId'],run=self.run,role=self.role,stage=0,profile='worldweb')
            if state['phase']=='complete':need(decoded['windows'] and decoded['windows'][-1]['complete'] and decoded['pending'] is None)
        else:need(state['phase'] in ('fencing','stop-issued'))
        return deepcopy(state)
    def save(self):
        self.bound(writing=True);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def prepare(self,source,scene_sha,peer=None):
        self.bound();need(self.state is None);installed_source(source)
        need(type(scene_sha) is str and len(scene_sha)==64)
        self.state=dict(phase='fencing',source=deepcopy(source),bundleId=self.flow.runtime.adapter.target(self.flow.selector)['appId'],
            fence=None,sceneSha256=scene_sha,processSha256=None,peer=deepcopy(peer))
        self.save()
    def stop(self,parts,*,census):
        from contextlib import ExitStack
        from ios.adapters.world_web_stop_inventory import WorldWebStopInventory
        self.bound();need(self.state['phase']=='fencing')
        bridge=WorldWebStopInventory(census,self,parts)
        need(same(self.flow.runtime._graphics_final_source(self.flow.selector,self.binding),self.state['source']))
        # Full historical graphs are decoded before fresh acquisition. Only
        # declared append carriers can join this round; every later native/SDK
        # send and its return rechecks actual original file/inode continuity.
        with ExitStack() as stack:
            for source in (parts['source'],parts['peer']):
                if source is not None:
                    stack.enter_context(source.input_round(PrivateFeatureState(source.store.path.with_name('ios-world-web-inputs.json'))))
            with original_reads(fresh=True) as reads:
                fresh=fence.acquire(self.flow,parts);need(fresh['sceneSha256']==self.state['sceneSha256'])
                measured=fence.validate(fresh,self.flow,parts)
                bridge.freeze(fresh,reads)
            # The typed graph/append rounds validated the bytes before these
            # original identities were pinned; their exits guard this bridge.
            pins={}
            for source in (parts['source'],parts['peer']):
                if source is not None:pins.update(source.original_pins(source.previous))
            base=self.flow.runtime.adapter
            mutable=[self.store.path,base._binding_store(self.flow.selector).path,self.flow.runtime.state_path(self.flow.selector)]
            scope=parts['retirement'].scope if parts['lease'] is None else parts['lease'].scope
            roots={parts['source'].store.path.parent,scope.root}
            if self.role=='primary':
                actor_selector=self.flow.settings['actorTarget'];roots.add(self.flow.runtime.state_path(actor_selector).parent)
                mutable.extend([base._binding_store(actor_selector).path,self.flow.runtime.state_path(actor_selector)])
            if parts['peer'] is not None:roots.add(parts['peer'].store.path.parent)
            leases=[EmoteOriginalLease(root,mutable) for root in roots]
        self.state.update(phase='stop-issued',fence=fresh);self.save()
        def final_guard():
            self.bound()
            bridge.guard()
            for original_clock in measured['acquisitions']:fence.current_clocks(original_clock,self.flow)
            for path,signature in pins.items():need(parts['source'].original_signature(path)==signature)
            for lease in leases:lease.guard()
        with transport_scope(final_guard):
            final_guard();self.flow.runtime._world_web_final_stop(self.flow.selector,self,self.lock)
    def advance(self):
        """One new OS original; never invokes Stop or a foreground getter."""
        self.bound();need(self.state['phase'] in ('stop-issued','stopped','complete'))
        reader=self.flow.runtime._retired_process_observer(self.flow.selector,self.binding,self.state['source'])
        owner=IOSProcessRetirement(self.process_store(),reader,self.binding,self.run,self.role,0,self.lock,profile='worldweb')
        complete=owner.advance();current=owner.current();start=self.state['fence']['phaseAfter']['capturedEpochMs']
        need(current['acquisition']['hostBeforeEpochMs']>=start)
        if absent(current['original']):
            self.flow.runtime._graphics_final_stopped(self.flow.selector,self.binding,self.state['source']);self.state['phase']='stopped'
        self.state['processSha256']=digest(owner.previous)
        if complete:self.state['phase']='complete'
        self.save();owner.current();return complete
    def verify(self,parts):
        """Historical originals only; cannot assert a newly current OS sample."""
        self.bound();self.state=self.decode(self.previous);need(self.state['phase']=='complete')
        measured=fence.validate(self.state['fence'],self.flow,parts)
        need(measured['native']['processId']==int(self.binding['processIdentity']))
        return deepcopy(self.previous)

    def actor_ready(self,*,actor=None):
        """Actor completion is acquired outside any polling loop/actor lock."""
        from ios.adapters.peer_admission import validate as admitted
        need(self.role=='primary')
        peer=admitted(self.flow.state['actorAdmission'],self.binding);selector=self.flow.settings['actorTarget']
        original=PrivateFeatureState(self.flow.runtime.state_path(selector).with_name('ios-world-web-actor-feature.json')).read()
        if original is None:return None
        rows=unpack(original['payload']);need(len(rows)==1)
        if rows[0]['phase']!='retired':return None
        if actor is None:
            other=self.flow.runtime._world_web_feature(selector,self.run,role='actor',client=self.flow.client,
                settings={key:self.flow.settings[key] for key in ('artifactRoot','imagePolicy','origins')}|dict(primaryTarget=self.flow.selector))
        else:
            from ios.adapters.world_web_feature import IOSWorldWebFeature
            need(type(actor) is IOSWorldWebFeature and actor.runtime is self.flow.runtime and actor.selector==selector
                and actor.run==self.run and actor.role=='actor' and actor.primary_selector==self.flow.selector
                and actor.root==self.flow.root and same(actor.policy,self.flow.policy) and same(actor.origins,self.flow.origins))
            actor.lock.assert_held();need(actor.primary_lock is self.flow.lock)
            other=actor
        other.primary_lock=self.flow.lock
        with other.held():
            other.load();need(other.state['binding']==peer and other.state['primaryBinding']==self.binding and other.state['phase']=='retired'
                and other.state['phaseInstance']==self.flow.state['phaseInstance'])
            from ios.adapters.world_web_archived import rebuild
            from ios.adapters.world_web_final_archive import WorldWebFinalArchive
            from ios.adapters.world_web_session_end import WorldWebSessionEnd
            sdk=WorldWebSessionEnd(other)
            if sdk.state is None or sdk.state['phase']!='complete':return None
            sdk.historical()
            own=WorldWebProcessEnd(other);decoded=rebuild(other)
            own.verify(dict(source=decoded.source,peer=decoded.peer,retirement=decoded,lease=decoded.observer.lease))
            scene=WorldWebFinalArchive(other.runtime._world_web_store(selector,'ios-world-web-actor-'+self.run+'-final.json'),
                other.root,peer,self.run,'actor',other.lock);scene.verify()
            result=dict(binding=deepcopy(peer),process=deepcopy(own.previous),scene=deepcopy(scene.previous),coordinator=deepcopy(other.previous),sdk=deepcopy(sdk.previous))
        self.peer_original(result);return result
    def peer_original(self,value):
        from ios.adapters.peer_admission import validate as admitted
        exact(value,{'binding','process','scene','coordinator','sdk'})
        peer=admitted(self.flow.state['actorAdmission'],self.binding);need(value['binding']==peer)
        parent=self.flow.runtime.state_path(self.flow.settings['actorTarget']).parent
        for name,key in (('ios-world-web-actor-'+self.run+'-process-final.json','process'),
                ('ios-world-web-actor-'+self.run+'-final.json','scene'),('ios-world-web-actor-feature.json','coordinator'),('ios-world-web-actor-'+self.run+'-sdk-final.json','sdk')):
            need(same(PrivateFeatureState(parent/name).read(),value[key]))
        from ios.adapters.world_web_session_end import WorldWebSessionEnd
        sdk=WorldWebSessionEnd.archive(value['sdk'],root=self.flow.root,binding=peer,run=self.run,role='actor')
        need(sdk['phase']=='complete' and sdk['processSha256']==digest(value['process']) and sdk['sceneSha256']==digest(value['scene']))
        process=value['process'];exact(process,{'iosWorldWebProcessFinalVersion','binding','runId','role','payload'})
        need(type(process['iosWorldWebProcessFinalVersion']) is int and process['iosWorldWebProcessFinalVersion']==1
            and process['binding']==peer and process['runId']==self.run and process['role']=='actor')
        rows=unpack(process['payload']);need(len(rows)==1 and rows[0]['phase']=='complete');state=rows[0]
        raw=PrivateFeatureState(parent/filename('worldweb','actor',0)).read();need(raw is not None and digest(raw)==state['processSha256'])
        os_state=IOSProcessRetirement.archive(raw,path=parent/filename('worldweb','actor',0),binding=peer,source=state['source'],bundle=state['bundleId'],
            run=self.run,role='actor',stage=0,profile='worldweb')
        need(os_state['pending'] is None and os_state['windows'] and os_state['windows'][-1]['complete'])
        return deepcopy(value)
