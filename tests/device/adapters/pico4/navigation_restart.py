"""Explicit v16 restart ownership between immutable Navigation generations.

The parent supplies its ordinary once-only SDK routes and original next-runtime
factory. Receipts cannot supply process absence, native birth or feature state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import NativeFeatureObservation,need,exact,number,integer,validate as native_packet
from adapters.native_location_bookmarks import validate as bookmark_packet
from adapters.native_process_presence import NativeProcessPresence
from adapters.navigation_bookmarks import NavigationBookmarks
from adapters.navigation_restart_proof import validate as restart_proof
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.navigation_bookmark_join import NavigationBookmarkJoin
from adapters.pico4.navigation_history import NavigationHistory
from adapters.pico4.navigation_prefix_source import NavigationPrefixSource,projection
from adapters.pico4.navigation_originals import capture as capture_originals,verify as verify_originals,read_original
from adapters.restart_inputs import RestartInputs
from adapters.script_journey.history import same,pack,unpack
from feature_journeys.contract import arguments,identifier
from feature_journeys.fixtures import context as fixture_context
from feature_journeys.phase_fixture import validate as phase_packet

VERSION=1


def session_record(value,binding):
    exact(value,{'schemaVersion','processIdentity','sessionNonce','nextSequence'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['processIdentity']==binding['processIdentity'] and integer(value['nextSequence'],1,0xffffffff)
        and type(value['sessionNonce']) is str and len(value['sessionNonce'])==64
        and all(letter in '0123456789abcdef' for letter in value['sessionNonce']))
    return value


class NavigationRestart:
    """One boundary owner; no replay of the initial eleven-action recipe."""
    def __init__(self,parent,store,native,*,outside_guard,stop,stopped,launch,rebind,successor):
        need(isinstance(store,PrivateFeatureState) and store.path==parent.lock.path.with_name('navigation-prefix-restart.json')
            and all(callable(callback) for callback in (outside_guard,stop,stopped,launch,rebind,successor)))
        self.parent,self.store,self.native=parent,store,native
        self.store_path=store.path
        self.outside_guard,self.stop,self.stopped,self.launch,self.rebind,self.successor=outside_guard,stop,stopped,launch,rebind,successor
        self.run,self.binding=parent.run,deepcopy(parent.binding);self.scope_sha=json_digest(parent.scope())
        self.inputs=RestartInputs(PrivateFeatureState(store.path.with_name('navigation-prefix-restart-inputs.json')),
            [parent.bookmarks.store,PrivateFeatureState(store.path.with_name('navigation-prefix-generation-1-bookmarks.json')),parent.store],monotonic=parent.monotonic)
        self.disk=self.store.read();self.state=None;self.anchor=None;self.runtime=None
        self.capture_anchor=self.capture_anchor_sha=None
        if self.disk is not None:self.load()

    def scope(self):
        p=self.parent;p.lock.assert_held();p.control()
        root=self.store_path.parent
        need(self.store.path==self.store_path and self.scope_sha==json_digest(p.scope()) and same(self.binding,p.binding)
            and p.store.path==root/'navigation-prefix-owner.json' and p.bookmarks.store.path==root/'navigation-prefix-bookmarks.json'
            and self.inputs.store.path==root/'navigation-prefix-restart-inputs.json'
            and [owner.path for owner in self.inputs.owners]==[root/'navigation-prefix-bookmarks.json',root/'navigation-prefix-generation-1-bookmarks.json',p.store.path]
            and self.inputs.owner_files==[str(owner.path) for owner in self.inputs.owners])
        if self.state is not None:
            need(same(self.store.read(),self.disk) and same(unpack(self.disk['payload']),[self.state]))
            verify_originals(self.state['files'],self.store.path.parent,self.run,self.state['normalUiPath'],p.lock)
        return dict(parent=deepcopy(p.disk),restart=deepcopy(self.disk),scopeSha256=self.scope_sha)

    def fence(self):
        # No dead original Qt/runtime guard is queried during Stop/Launch.
        # The route-specific candidate/process-or-stopped admission precedes
        # the exact independent HTTP phase; only clocks follow that phase.
        self.scope();p=self.parent;started=p.now();need(self.outside_guard(self.inputs.store.read()) is not False)
        current=p.phase.read();need(current['ticket']==self.state['arguments']['ticket'] and current['verb']=='restart-app'
            and same(current['inputs'],{}) and current['status']['instance']==self.state['fixture']['instance']
            and same(current['status']['activations'],self.state['fixture']['activations']))
        epoch=p.phase.epoch_ms();now=p.now();need(number(epoch,1,1e15)
            and max(epoch-current['status']['capturedEpochMs'],(now-started)*1000)<=1500)
        self.anchor=dict(hostMonotonic=now,nativeEpochMs=epoch,fixtureEpochMs=current['status']['capturedEpochMs'])
        self.anchor_sha=json_digest(self.anchor)
        return current

    def publish(self,operation):
        # Called while the original Session mutex is held: host/CAS/clock only.
        self.scope();need(operation in ('app.stop','app.launch') and self.anchor is not None
            and self.anchor_sha==json_digest(self.anchor))
        now=self.parent.now();a=self.anchor
        need(now>=a['hostMonotonic'] and max(a['nativeEpochMs']-a['fixtureEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)
        if operation=='app.stop':
            need(max(a['nativeEpochMs']-self.state['oldFrame']['before']['ui']['observedEpochMs'],0)+(now-a['hostMonotonic'])*1000<=1500)

    def bookmark_original(self):
        # A warm independent actor can predate the primary's normal Add/Rename
        # actions. Its object cache is not the original persistent owner. Read
        # and strictly validate that actual journal without UI/native input or
        # changing either role's cache or the old owner file.
        p=self.parent;value=NavigationBookmarks.archive(p.bookmarks.store.read())
        need(value['runId']==self.run and same(value['binding'],self.binding)
            and value['active'] is None and value['completed'] and value['completed'][-1]['verb']=='bookmark-rename')
        return value

    def validate(self,value):
        exact(value,{'arguments','fixture','phase','scope','prefix','normalUiPath','profile','session','stream','streamStatus',
            'oldFrame','oldNative','oldBookmark','proof','newSession','newFrame','files','sessionFile'})
        p=self.parent;call=arguments('feature.world-navigation.act',value['arguments'])
        need(call['runId']==self.run and call['fixtureUrl']==p.phase.fixture_url and call['verb']=='restart-app'
            and value['phase'] in ('prepared','observed') and same(value['scope'],p.scope())
            and value['prefix']['scopeSha256']==self.scope_sha and value['prefix']['binding']==self.binding
            and value['prefix']['phase']=='ready' and len(value['prefix']['completed'])==11)
        fixture=value['fixture'];phase_packet(fixture,run=self.run,area='world-navigation',request=fixture['requestId'],epoch=fixture['capturedEpochMs'])
        need(fixture['active'] and fixture['activations'][-1]['ticket']==call['ticket']
            and same(fixture['activations'][-1]['stimulus'],dict(verb='restart-app',inputs={})))
        old=value['oldNative'];native_packet(old,old['requestId'],int(self.binding['processIdentity'].split(':',1)[0]),old['capturedEpochMs'])
        book=value['oldBookmark'];bookmark_packet(book,dict(schemaVersion=1,commandId=book['commandId'],action='feature-location-bookmarks',runId=self.run),
            int(self.binding['processIdentity'].split(':',1)[0]),book['capturedEpochMs'])
        need(book['capturedEpochMs']<=old['capturedEpochMs'] and same(book['storage'],self.bookmark_original()['lastNative']['storage'])
            and same(value['oldFrame']['phase'],fixture))
        verify_originals(value['files'],self.store.path.parent,self.run,value['normalUiPath'],p.lock)
        session_record(value['session'],self.binding)
        exact(value['sessionFile'],{'path','present','signature','sha256'});need(value['sessionFile']['present'] is True)
        stream=value['stream'];need(stream['sessionNonce']==value['session']['sessionNonce']
            and stream['sequence']+1==value['session']['nextSequence']
            and NavigationBookmarkJoin.neutral(value['streamStatus'],stream))
        facts=p.source.project(value['oldFrame']);p.original_facts(value['oldFrame'])
        need(facts['location']=='A' and facts['bookmarkName']==fixture_context(self.run)['renamed']
            and not facts['panel'] and not facts['addressDialog'] and facts['error']=='none')
        if value['proof'] is None:
            need(value['phase']=='prepared' and value['newSession'] is None and value['newFrame'] is None)
        else:
            proof=restart_proof(value['proof'],self.run)
            need(value['phase']=='observed' and same(proof['input']['oldBinding'],self.binding)
                and same(proof['oldNative'],value['oldNative']) and same(proof['oldBookmark'],value['oldBookmark'])
                and proof['input']['ownerFiles']==self.inputs.owner_files)
            new=proof['input']['newBinding'];session_record(value['newSession'],new)
            need(value['newSession']['sessionNonce']!=value['session']['sessionNonce'] and value['newSession']['nextSequence']==1)
            frame=value['newFrame'];need(same(frame['binding'],new) and frame['phase']['instance']==fixture['instance']
                and same(frame['phase']['activations'],fixture['activations']))
            epoch=frame['after']['replies']['capturedEpochMs']
            fresh_facts=projection(frame,self.run,new,p.source.inputs,p.source.provider_instance,p.source.origin,p.source.profile,frame['receipt'],epoch)
            p.original_facts(frame);need(same(fresh_facts,facts))
            for key in ('bookmarks','panels','modals','environment','directory','replies'):
                need(frame['before'][key]['instance']!=value['oldFrame']['after'][key]['instance'])
            need(frame['before']['pose']['subject']['instance']!=value['oldFrame']['after']['pose']['subject']['instance'])

    def load(self):
        body=self.store.read();exact(body,{'navigationRestartVersion','runId','binding','parentScopeSha256','payload'})
        need(type(body['navigationRestartVersion']) is int and body['navigationRestartVersion']==VERSION
            and body['runId']==self.run and same(body['binding'],self.binding) and body['parentScopeSha256']==self.scope_sha)
        rows=unpack(body['payload']);need(len(rows)==1);self.validate(rows[0]);self.disk=deepcopy(body);self.state=rows[0]

    def save(self,value):
        self.validate(value)
        body=dict(navigationRestartVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),parentScopeSha256=self.scope_sha,payload=pack([value]))
        self.store.write(body,self.disk);self.disk=deepcopy(body);self.state=deepcopy(value)

    def prepare(self,call):
        p=self.parent;self.scope();need(self.state is None and isinstance(self.native,NativeFeatureObservation)
            and self.native.pid==int(self.binding['processIdentity'].split(':',1)[0]) and p.state['phase']=='ready'
            and len(p.state['completed'])==11 and p.state['completed'][-1]['verb']=='bookmark-visit'
            and re.fullmatch('[1-9][0-9]{0,9}:[0-9]{1,20}',self.binding['processIdentity']))
        current=p.phase.read();need(current['ticket']==call['ticket'] and current['verb']=='restart-app' and current['inputs']=={})
        closed=p.bookmark_visit();need(closed.state['phase']=='closed');stream=deepcopy(closed.transit_original().state['controllers']['close']['envelope'])
        with p.session._lock():
            session=deepcopy(p.session._load());session_file=read_original(p.session.state_path)
        status=p.session.observe_owned_status(self.binding['processIdentity'],stream)
        need(NavigationBookmarkJoin.neutral(status,stream))
        book=p.source.readers['bookmarks'].read(self.run)
        need(same(book['storage'],self.bookmark_original()['lastNative']['storage']))
        normal_path=str(p.source.normal.io.original.navigation.path)
        files=capture_originals(self.store.path.parent,self.run,normal_path,p.lock)
        NavigationHistory(p.scope(),p.disk,normal_path,p.session.profile,p.phase,p.lock,role=p.role,files=files)
        old=self.inputs.capture(self.binding,self.native)
        final_phase=p.phase.read();need(final_phase['ticket']==call['ticket'] and same(final_phase['status']['activations'],current['status']['activations']))
        current=final_phase
        started=p.now();frame=p.source.capture(p.state['receipt'],current['status'],lookup_receipt=p.state['lookupReceipt'])
        self.save(dict(arguments=deepcopy(call),fixture=deepcopy(current['status']),phase='prepared',scope=p.scope(),prefix=deepcopy(p.disk),
            normalUiPath=normal_path,files=files,profile=deepcopy(p.session.profile),session=session,sessionFile=session_file,stream=stream,streamStatus=status,
            oldFrame=frame,oldNative=old,oldBookmark=book,proof=None,newSession=None,newFrame=None))
        self.fence();epoch=p.phase.epoch_ms();need(max(epoch-frame['before']['ui']['observedEpochMs'],(p.now()-started)*1000)<=1500)

    def act(self,call):
        self.scope();need(self.parent.role=='primary')
        call=deepcopy(arguments('feature.world-navigation.act',call));need(call['verb']=='restart-app')
        if self.state is None:self.prepare(call)
        need(same(self.state['arguments'],call));self.fence()
        if self.state['phase']=='prepared':
            if self.inputs.read()['phase']=='prepared':self.inputs.stop(lambda:self.stop(self.fence))
            if self.inputs.read()['phase']=='stop-issued':self.inputs.launch(self.stopped,lambda:self.launch(self.fence))
            # The existing binding helper can establish only an unbound new
            # host Session after independent native birth/ESRCH observations.
            if self.inputs.read()['phase']=='launch-issued':self.rebind(self.inputs,self.scope)
            runtime=self.successor(self.inputs,self.state)
            exact(runtime,{'source','native','presence','session'})
            source,native,presence,session=runtime['source'],runtime['native'],runtime['presence'],runtime['session']
            need(isinstance(source,NavigationPrefixSource) and isinstance(native,NativeFeatureObservation)
                and isinstance(presence,NativeProcessPresence) and source.run==self.run)
            binding=context(source.binding);packet=self.inputs.observe(binding,native)
            exited=presence.require_absent(int(self.binding['processIdentity'].split(':',1)[0]));book=source.readers['bookmarks'].read(self.run)
            proof=dict(navigationBookmarkRestartProofVersion=1,input=self.inputs.read(),oldNative=deepcopy(self.state['oldNative']),
                native=packet,exit=exited,oldBookmark=deepcopy(self.state['oldBookmark']),bookmark=book)
            restart_proof(proof,self.run);self.fence()
            phase=self.fence();started=self.parent.now()
            self.capture_anchor=dict(hostMonotonic=started,nativeEpochMs=native.clock_ms())
            self.capture_anchor_sha=json_digest(self.capture_anchor)
            frame=source.capture(self.parent.state['receipt'],phase['status'],lookup_receipt=self.parent.state['lookupReceipt'])
            need(same(source.project(frame),self.parent.source.project(self.state['oldFrame'])))
            with session._lock():new_session=deepcopy(session._load())
            current=deepcopy(self.state);current.update(phase='observed',proof=proof,newSession=new_session,newFrame=frame)
            self.save(current);self.runtime=runtime;need(source.guard() is not False);self.fence()
            epoch=self.parent.phase.epoch_ms();need(max(epoch-frame['before']['ui']['observedEpochMs'],(self.parent.now()-started)*1000)<=1500)
        return dict(performed=True)
