"""Closed-profile raw fenced images before marker setup and after retirement.

These frames contain no fabricated challenge/background and establish no active
feature facts. Each untouched PNG retains its own actual GPU lifetime owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import uuid
import hashlib
from adapters.graphics_subject_geometry import near
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels,command as frame_command
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_marker_scope import OriginalMarkerScope,_components
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner,owns_slot
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import avatar_renderers
from ios.adapters.emote_marker_measurements import orientation
from ios.adapters.emote_native_prefix import follow
from ios.adapters.graphics_history import restore_native
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1
FRAME={'worldBefore','renderersBefore','capture','retirement','renderersAfter','worldAfter','clockJoin'}


def frame_original(value,*,profile,root,binding,run,role,lock):
    exact(value,{'markerRestorationFrameVersion','profile','runId','role','binding','requestId','kind','phase','payload','owner'})
    need(type(value['markerRestorationFrameVersion']) is int and value['markerRestorationFrameVersion']==1 and value['profile']==profile
        and value['runId']==run and value['role']==role and same(value['binding'],binding) and value['phase']=='captured'
        and value['kind'] in ('initial','cleanup') and type(value['requestId']) is str and value['requestId'].startswith('ios-'))
    identifier(value['requestId'][4:]);context(binding);identifier(run)
    frames,owners=unpack(value['payload']),unpack(value['owner']);need(len(frames)==len(owners)==1)
    frame,owner=frames[0],owners[0];exact(frame,FRAME)
    need(owns_slot(owner) and same(owner['frame'],frame['capture']) and any(same(row['receipt'],frame['retirement']) for row in unpack(owner['transcript'])))
    raw=VulkanWorldFrameOwner.archive_original(owner,Path(root),binding,run,role,0,value['requestId'],lock)
    pid=int(binding['processIdentity']);join=validate_join(frame['clockJoin'],{key:frame[key] for key in FRAME-{'clockJoin'}})
    follow(join['nativeBefore'],join['nativeAfter']);need(join['nativeBefore']['processId']==pid)
    c=_components(profile);before,after=frame['worldBefore'],frame['worldAfter'];c.world_original(before)
    c.world_packet(after,dict(schemaVersion=1,commandId=after['requestId'],action=c.WORLD_ACTION,runId=run),pid,previous=before)
    need(before['runId']==run and before['processId']==pid and not before['source']['markers'] and not after['source']['markers'])
    need(same(c.actual_domain(before),c.actual_domain(after)) and same(before['source']['tree'],after['source']['tree']))
    c.body_preserved(before,after);c.view_preserved(before,after)
    left,right=frame['renderersBefore'],frame['renderersAfter'];avatar_renderers.original(left)
    avatar_renderers.validate(right,dict(schemaVersion=1,commandId=right['requestId'],action=avatar_renderers.ACTION,runId=run),pid,previous=left)
    need(left['runId']==run and left['processId']==pid and left['iosAvatarRenderersVersion']>=4)
    for packet,world in ((left,before),(right,after)):
        own=[row for row in packet['source']['avatars'] if row['self']];need(len(own)==1)
        need(hashlib.sha256(uuid.UUID(own[0]['sessionId']).bytes).hexdigest()==world['source']['domain']['selfSha256']
            and packet['source']['tree']['treeInstance']==world['source']['tree']['treeInstance'])
    capture,retired=frame['capture'],frame['retirement'];epoch=join['nativeAfter']['capturedEpochMs']
    query=dict(schemaVersion=1,commandId=capture['commandId'],requestId=value['requestId'],action='feature-vulkan-world-frame',operation='read')
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(retired,dict(query,operation=retired['operation'],commandId=retired['commandId']),pid,epoch)
    need(absent(retired) and retired['instance']==capture['instance'] and retired['sequence']>capture['sequence'])
    trace=capture['source']['renderTrace'];view=before['source']['view'];recorded=trace['recordedView']
    need(view['perspective'] and trace['forwardDrawCalls']>0 and near(view['position'],recorded['position'],.001)
        and orientation(view['rotation'],recorded['rotation']) and near(view['fieldOfViewDegrees'],recorded['fieldOfViewDegrees'],.001)
        and near(view['aspectRatio'],recorded['aspectRatio'],.0001)
        and abs(view['aspectRatio']-capture['source']['targetExtent'][0]/capture['source']['targetExtent'][1])<=.01)
    ordered=[join['nativeBefore']['capturedEpochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],
        left['clockBefore']['epochMs'],left['clockAfter']['epochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],
        capture['source']['submittedEpochMs'],capture['source']['fenceObservedEpochMs'],capture['source']['pixelsReadEpochMs'],capture['capturedEpochMs'],
        retired['requestedEpochMs'],retired['capturedEpochMs'],right['clockBefore']['epochMs'],right['clockAfter']['epochMs'],
        after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],epoch]
    need(all(integer(v,1) for v in ordered) and ordered==sorted(ordered))
    return deepcopy(frame),raw


class OriginalMarkerRestorationFrames:
    PROFILE=None
    @property
    def components(self):return _components(type(self).PROFILE)
    @classmethod
    def archive(cls,value,*,store,root,binding,run,role,lock):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result=object.__new__(cls);result.store,result.root,result.binding,result.run,result.role,result.lock=store,Path(root),deepcopy(context(binding)),identifier(run),role,lock
        need(type(result).PROFILE in ('emote','avatar'));result.previous=store.read();result.state=result.decode(value);return result
    def __init__(self,runtime,selector,scope,root,lock,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(runtime,IOSScriptRuntime) and isinstance(scope,OriginalMarkerScope) and isinstance(lock,ScriptSourceLock)
            and type(self).PROFILE in ('emote','avatar') and scope.PROFILE==type(self).PROFILE and all(callable(fn) for fn in (epoch_ms,monotonic,sleep)))
        self.runtime,self.selector,self.scope,self.lock=runtime,selector,scope,lock
        self.root,self.binding,self.run,self.role=Path(root),deepcopy(context(scope.binding)),scope.run,scope.role
        self.epoch_ms,self.monotonic,self.sleep=epoch_ms,monotonic,sleep
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir() and role_valid(self.role))
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-'+self.PROFILE+'-'+self.role+'-restoration-frames.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'));lock.assert_held()
        self.previous=self.store.read();self.state=dict(records=[],pending=None,cursors=dict(native=None,world=None,renderers=None))
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(markerRestorationFramesVersion=1,profile=self.PROFILE,runId=self.run,role=self.role,binding=self.binding,
        artifactRoot=str(self.root),payload=pack([state]))
    def file(self,index):
        need(integer(index,1,128));return PrivateFeatureState(self.root/(self.PROFILE+'-restoration-'+self.run+'-'+self.role+'-'+str(index)+'.json'))
    def original(self,ref):
        exact(ref,{'index','sha256'});value=self.file(ref['index']).read();need(value is not None and digest(value)==ref['sha256']);return value
    def frame(self,ref):return frame_original(self.original(ref),profile=self.PROFILE,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
    def partial(self,p):
        exact(p,{'requestId','kind','priorCursors','parts','candidate'});need(p['kind'] in ('initial','cleanup') and type(p['requestId']) is str and p['requestId'].startswith('ios-'))
        identifier(p['requestId'][4:]);exact(p['priorCursors'],{'native','world','renderers'});need(type(p['parts']) is dict)
        need(set(p['parts'])<=FRAME|{'nativeStart','nativeReads','owner','drains'})
        for key in ('worldBefore','worldAfter'):
            if key in p['parts']:self.components.world_original(p['parts'][key]);need(p['parts'][key]['runId']==self.run and p['parts'][key]['processId']==int(self.binding['processIdentity']))
        for key in ('renderersBefore','renderersAfter'):
            if key in p['parts']:avatar_renderers.original(p['parts'][key]);need(p['parts'][key]['runId']==self.run and p['parts'][key]['processId']==int(self.binding['processIdentity']))
        if p['candidate'] is not None:
            value=p['candidate'];need(type(value) is dict and value.get('profile')==self.PROFILE and value.get('runId')==self.run
                and value.get('role')==self.role and same(value.get('binding'),self.binding) and value.get('requestId')==p['requestId'] and value.get('kind')==p['kind'])
            if value.get('phase')=='captured':
                exact(value,{'markerRestorationFrameVersion','profile','runId','role','binding','requestId','kind','phase','payload','owner'})
                need(type(value['markerRestorationFrameVersion']) is int and value['markerRestorationFrameVersion']==1
                    and same(unpack(value['payload']),[{key:p['parts'][key] for key in FRAME}]) and same(unpack(value['owner']),[p['parts']['owner']]))
            else:
                need(value.get('phase')=='abandoned' and same(unpack(value['payload']),[dict(p,candidate=None)]));self.validate(value)
        return p
    def validate(self,value):
        need(type(value) is dict and value.get('profile')==self.PROFILE and value.get('runId')==self.run and value.get('role')==self.role
            and same(value.get('binding'),self.binding))
        if value.get('phase')=='captured':return self.frame_value(value)
        exact(value,{'markerRestorationAbandonedVersion','profile','runId','role','binding','requestId','kind','phase','payload','owner'})
        need(type(value['markerRestorationAbandonedVersion']) is int and value['markerRestorationAbandonedVersion']==1 and value['phase']=='abandoned')
        rows=unpack(value['payload']);need(len(rows)==1);p=rows[0];self.partial(dict(p,candidate=None))
        need(value['requestId']==p['requestId'] and value['kind']==p['kind'])
        parts=p['parts'];drains=parts['drains'];need(type(drains) is list and 1<=len(drains)<=16)
        released=[];commands=set();previous_owner=None
        for attempt in drains:
            self.drain_attempt(attempt,value['requestId'])
            if attempt['inspection'] is not None:
                q=attempt['inspection']['command'];need(q['commandId'] not in commands);commands.add(q['commandId'])
                if q['operation']=='release':released.append(q['commandId']);need(len(released)<=1)
            if attempt['owner'] is not None:
                if previous_owner is not None:
                    old=unpack(previous_owner['transcript']);new=unpack(attempt['owner']['transcript']);need(same(old,new[:len(old)]))
                previous_owner=attempt['owner']
        last=drains[-1];need(last['clockJoin'] is not None and same(unpack(value['owner']),[last['owner']]))
        return deepcopy(value)
    def drain_attempt(self,attempt,request):
        exact(attempt,{'nativeStart','inspection','owner','absence','partialFile','clockJoin'})
        start=attempt['nativeStart']
        if start is not None:
            exact(start,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(start['clockJoinVersion']) is int and start['clockJoinVersion']==1 and number(start['hostBeforeEpochMs'],1,1e15) and number(start['hostBeforeMonotonic'],0,1e15))
            packet=start['nativeBefore'];native_packet(packet,packet['requestId'],int(self.binding['processIdentity']),packet['capturedEpochMs'])
        if attempt['inspection'] is not None:
            inspection=attempt['inspection'];exact(inspection,{'command','receipt'});q=inspection['command'];frame_command(q)
            need(q['requestId']==request and q['operation'] in ('inspect','release'))
            if inspection['receipt'] is not None:storage(inspection['receipt'],q,int(self.binding['processIdentity']),inspection['receipt']['capturedEpochMs']);need(absent(inspection['receipt']))
        proof=attempt['absence']
        if proof is not None:
            need(start is not None and absent(proof) and proof['requestId']==request)
            from ios.adapters.emote_sample_recovery import retained_file
            if attempt['owner'] is not None:
                need(owns_slot(attempt['owner']))
                need(same(attempt['partialFile'],retained_file(attempt['owner'],self.root,self.binding,self.run,self.role,request,self.lock)))
                need(any(same(row['receipt'],proof) for row in unpack(attempt['owner']['transcript'])))
            else:
                need(attempt['partialFile'] is None and attempt['inspection'] is not None and same(proof,attempt['inspection']['receipt'])
                    and not (self.root/('vulkan-world-'+self.run+'-'+self.role+'-0-'+request[4:]+'.png')).exists())
        if attempt['clockJoin'] is not None:
            join=validate_join(attempt['clockJoin'],dict(absence=proof));need(all(same(start[key],join[key]) for key in start))
            follow(join['nativeBefore'],join['nativeAfter']);need(join['nativeBefore']['processId']==int(self.binding['processIdentity']))
        return attempt

    def frame_value(self,value):return frame_original(value,profile=self.PROFILE,root=self.root,binding=self.binding,run=self.run,role=self.role,lock=self.lock)
    def timeline(self,values,pending,expected):
        """Independently replay all completed and interrupted original floors."""
        cursors=dict(native=None,world=None,renderers=None)
        gpu=[None];accepted={}
        def original_owner(value,request=None):
            need(type(value) is dict)
            actual_request=value['requestId'] if request is None else request
            class Frozen(PrivateFeatureState):
                def read(self):return deepcopy(value)
                def write(self,*_args,**_kwargs):need(False)
                def discard(self,*_args,**_kwargs):need(False)
            path=self.lock.path.with_name('graphics-world-frame-'+self.role+'-0-'+actual_request[4:]+'.json')
            reader=VulkanWorldFrameOwner(Frozen(path),self.root,self.binding,self.run,self.role,0,actual_request,
                lambda *_:need(False),lambda:True,source_lock=self.lock)
            reader._load();return deepcopy(reader.events)
        def receipts(rows):
            for row in rows:
                receipt=row['receipt']
                if receipt is None:continue
                query=row['command'];key=query['commandId'];fingerprint=digest(receipt)
                if key in accepted:
                    need(accepted[key]==fingerprint);continue
                accepted[key]=fingerprint
                packet=receipt['packet'] if query['operation']=='read-bytes' else receipt
                if gpu[0] is not None:
                    need(packet['instance']==gpu[0]['instance'] and packet['sequence']>gpu[0]['sequence']
                        and packet['requestedEpochMs']>=gpu[0]['capturedEpochMs'])
                need(packet['processId']==int(self.binding['processIdentity']));gpu[0]=deepcopy(packet)
        def gpu_parts(parts,request=None):
            owner=parts.get('owner')
            if owner is not None:receipts(original_owner(owner,request))
            for attempt in parts.get('drains',[]):
                if attempt['owner'] is not None:receipts(original_owner(attempt['owner'],request))
                if attempt['inspection'] is not None:receipts([attempt['inspection']])
            if request is not None:
                # A process interruption may precede the enclosing frame's
                # owner/drain snapshot. The actual GPU journal is already
                # durable, including a return after the earlier saved copy.
                live=PrivateFeatureState(self.lock.path.with_name('graphics-world-frame-'+self.role+'-0-'+request[4:]+'.json')).read()
                if live is not None:receipts(original_owner(live,request))
        def advance(parts):
            for packet in parts.get('nativeReads',[]):
                native_packet(packet,packet['requestId'],int(self.binding['processIdentity']),packet['capturedEpochMs'])
                if cursors['native'] is not None:follow(cursors['native'],packet)
                cursors['native']=deepcopy(packet)
            for key in ('worldBefore','worldAfter'):
                if key not in parts:continue
                packet=parts[key];self.components.world_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=self.components.WORLD_ACTION,runId=self.run),
                    int(self.binding['processIdentity']),previous=cursors['world']);cursors['world']=deepcopy(packet)
            for key in ('renderersBefore','renderersAfter'):
                if key not in parts:continue
                packet=parts[key];avatar_renderers.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=avatar_renderers.ACTION,runId=self.run),
                    int(self.binding['processIdentity']),previous=cursors['renderers']);cursors['renderers']=deepcopy(packet)
        for item in values:
            self.validate(item)
            if item['phase']=='captured':
                frame=unpack(item['payload'])[0];parts=dict(frame,nativeReads=[frame['clockJoin']['nativeBefore'],frame['clockJoin']['nativeAfter']])
                parts['owner']=unpack(item['owner'])[0]
            else:
                original=unpack(item['payload'])[0];need(same(original['priorCursors'],cursors));parts=original['parts']
            advance(parts);gpu_parts(parts)
        if pending is not None:
            self.partial(pending);need(same(pending['priorCursors'],cursors));advance(pending['parts']);gpu_parts(pending['parts'],pending['requestId'])
        need(same(cursors,expected));return True
    def decode(self,value):
        exact(value,{'markerRestorationFramesVersion','profile','runId','role','binding','artifactRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0];exact(state,{'records','pending','cursors'});exact(state['cursors'],{'native','world','renderers'})
        need(type(state['records']) is list and len(state['records'])<=128);values=[]
        for index,ref in enumerate(state['records'],1):need(ref['index']==index);values.append(self.original(ref))
        self.timeline(values,state['pending'],state['cursors'])
        if state['pending'] is None:need(len(state['records'])==128 or self.file(len(state['records'])+1).read() is None)
        return deepcopy(state)
    def journal_native(self,native):
        read=native.read
        def observed(after):
            packet=read(after);parts=self.state['pending']['parts']
            if 'nativeReads' not in parts:parts['nativeReads']=[]
            parts['nativeReads'].append(deepcopy(packet));self.state['cursors']['native']=deepcopy(packet);self.save();return packet
        native.read=observed
        self._native_wrappers.append((native,read,observed))

    def journaled(self,operation,*args):
        self._native_wrappers=[]
        try:return operation(*args)
        finally:
            for native,read,observed in reversed(self._native_wrappers):
                # Restore only the wrapper this owner installed, including on
                # interrupted reads. Another owner never inherits our journal.
                need(native.read is observed);native.read=read
            self._native_wrappers=[]

    def bound(self):self.lock.assert_held();self.scope.bound();need(same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def remember(self,key,value):
        p=self.state['pending'];need(p is not None and key not in p['parts']);p['parts'][key]=deepcopy(value)
        field={'worldBefore':'world','worldAfter':'world','renderersBefore':'renderers','renderersAfter':'renderers'}.get(key)
        if field:self.state['cursors'][field]=deepcopy(value)
        if key=='nativeStart':self.state['cursors']['native']=deepcopy(value['nativeBefore'])
        if key=='clockJoin':self.state['cursors']['native']=deepcopy(value['nativeAfter'])
        self.save()
    def owner(self,request):
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding));observer=live['observer']
        store=PrivateFeatureState(self.store.path.with_name('graphics-world-frame-'+self.role+'-0-'+request[4:]+'.json'))
        return VulkanWorldFrameOwner(store,self.root,self.binding,self.run,self.role,0,request,lambda intent,receipt:observer.vulkan_world_frame(intent,receipt),
            live['check'],source_lock=self.lock,monotonic=self.monotonic,sleep=self.sleep)
    def resolve(self):
        self.bound();p=self.state['pending']
        if p is None:return True
        if p['candidate'] is None:return False
        value=p['candidate'];self.validate(value)
        self.timeline([self.original(ref) for ref in self.state['records']]+[value],None,self.state['cursors'])
        index=len(self.state['records'])+1;store=self.file(index);old=store.read()
        if old is None:store.write(value,None)
        else:need(same(old,value))
        ref=dict(index=index,sha256=digest(value));self.original(ref);self.state['records'].append(ref);self.state['pending']=None;self.save();return True
    def capture(self,kind):
        return self.journaled(self._capture,kind)

    def _capture(self,kind):
        self.bound();need(kind in ('initial','cleanup') and self.resolve() and len(self.state['records'])<128)
        if kind=='initial':need(self.scope.state['baseline'] is None and not self.scope.frames)
        else:need(self.scope.state['phase']=='released' and self.scope.state['pending'] is None)
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding));observer,clock=live['observer'],live['clock_source']
        native=observer.bound_native_observer(clock);restore_native(native,self.state['cursors']['native'])
        world=getattr(observer,self.components.world_factory)(clock);world.last=deepcopy(self.state['cursors']['world'])
        renderers=observer.avatar_renderers(clock);renderers.last=deepcopy(self.state['cursors']['renderers'])
        request='ios-'+uuid.uuid4().hex;self.state['pending']=dict(requestId=request,kind=kind,priorCursors=deepcopy(self.state['cursors']),parts={},candidate=None);self.save()
        owner=self.owner(request);need(owner.store.read() is None);self.journal_native(native);window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(self.epoch_ms());self.remember('nativeStart',window.started)
        self.remember('worldBefore',world.read(self.run));self.remember('renderersBefore',renderers.read(self.run))
        try:
            capture,_raw=owner.capture(self.scope.ticket);self.remember('capture',capture)
        finally:
            if owner.store.read() is not None and owns_slot(owner.store.read()):
                try:self.remember('retirement',owner.release())
                finally:
                    if 'owner' not in self.state['pending']['parts']:self.remember('owner',owner.store.read())
            elif owner.store.read() is not None:
                self.remember('owner',owner.store.read())
        self.remember('renderersAfter',renderers.read(self.run));self.remember('worldAfter',world.read(self.run))
        p=self.state['pending'];frame={key:p['parts'][key] for key in FRAME-{'clockJoin'}}
        fields=[(key,'capturedEpochMs') for key,value in frame.items() if 'capturedEpochMs' in value]
        self.remember('clockJoin',window.finish(frame,fields));frame['clockJoin']=p['parts']['clockJoin']
        p['candidate']=dict(markerRestorationFrameVersion=1,profile=self.PROFILE,runId=self.run,role=self.role,binding=self.binding,
            requestId=request,kind=kind,phase='captured',payload=pack([frame]),owner=pack([owner.store.read()]))
        self.save();need(self.resolve());return deepcopy(self.state['records'][-1])
    def abandon(self):
        """Only retire actual GPU ownership; never repeat an uncertain read."""
        return self.journaled(self._abandon)

    def _abandon(self):
        self.bound()
        try:
            if self.resolve():return True
        except NativeUIError:
            p=self.state['pending']
            # A fully returned but unqualified camera/body read remains raw
            # ownership. Before an immutable record exists, all its exact bytes
            # are already retained in parts; only its eligibility is discarded.
            need(p is not None and p['candidate'] is not None and p['candidate']['phase']=='captured'
                and self.file(len(self.state['records'])+1).read() is None)
            self.partial(p);p['candidate']=None;self.save()
        p=self.state['pending'];parts=p['parts']
        if 'drains' not in parts:parts['drains']=[];self.save()
        if not parts['drains'] or parts['drains'][-1]['clockJoin'] is None:
            need(len(parts['drains'])<16)
            attempt=dict(nativeStart=None,inspection=None,owner=None,absence=None,partialFile=None,clockJoin=None)
            parts['drains'].append(attempt);self.save()
            live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding))
            native=live['observer'].bound_native_observer(live['clock_source']);restore_native(native,self.state['cursors']['native'])
            owner=self.owner(p['requestId']);self.journal_native(native);window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
            window.begin(self.epoch_ms());attempt['nativeStart']=deepcopy(window.started);self.save()
            if owner.store.read() is None:
                need(not (self.root/owner.name).exists())
                def intent(query):
                    need(attempt['inspection'] is None and query['requestId']==p['requestId'] and query['operation'] in ('inspect','release'))
                    attempt['inspection']=dict(command=deepcopy(query),receipt=None);self.save()
                def receipt(query,value):
                    need(same(query,attempt['inspection']['command']) and attempt['inspection']['receipt'] is None and absent(value))
                    attempt['inspection']['receipt']=deepcopy(value);self.save()
                reader=live['observer'].vulkan_world_frame(intent,receipt)
                issued=any(row['inspection'] is not None and row['inspection']['command']['operation']=='release' for row in parts['drains'])
                proof=reader.perform(dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='inspect' if issued else 'release',
                    commandId='ios-'+uuid.uuid4().hex,requestId=p['requestId']))
            else:
                # An occupied/unknown original inspection is another owner's
                # resource, even when this request reserved a private PNG.
                need(owns_slot(owner.store.read()));proof=owner.release()
            need(absent(proof));attempt['absence']=deepcopy(proof);attempt['owner']=owner.store.read()
            if attempt['owner'] is not None:
                from ios.adapters.emote_sample_recovery import retained_file
                attempt['partialFile']=retained_file(attempt['owner'],self.root,self.binding,self.run,self.role,p['requestId'],self.lock)
            self.save();attempt['clockJoin']=window.finish(dict(absence=proof),[('absence','capturedEpochMs')])
            self.state['cursors']['native']=deepcopy(attempt['clockJoin']['nativeAfter']);self.save()
        attempt=parts['drains'][-1]
        p['candidate']=dict(markerRestorationAbandonedVersion=1,profile=self.PROFILE,runId=self.run,role=self.role,binding=self.binding,
            requestId=p['requestId'],kind=p['kind'],phase='abandoned',payload=pack([dict(p,candidate=None)]),owner=pack([attempt['owner']]))
        self.save();return self.resolve()


def role_valid(role):return role in ('primary','actor')
