"""Durable marker-only normal Script/View setup and observed quiet cleanup.

This owner preserves the real Domain/AvatarMixer. Its local Web marker is a
controlled image challenge; neither file delivery nor Script execution proves
an Avatar or Emote effect, a replicated pose, or rendered pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from adapters.original_frame_store import MAX_FRAMES
from pathlib import Path
import re
import time
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_terminal import validate as terminal_packet
from adapters.native_script_work import validate as work_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.script_ui_inventory import validate as script_ui_inventory
from feature_journeys.contract import identifier
from ios.adapters.graphics_history import restore_native,follow_native
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.adapters.normal_input import observation as widgets_packet
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.web_closures import validate as web_packet,continuity as web_continuity,drained_owned_resources
from ios.adapters.script_dialogs import validate as dialogs_packet,completed as dialog_completed,ACTION as DIALOG_ACTION

VERSION=1
PHASES=('new','preparing','aborting-unused','ready','restoring-view','stopping-marker','quiet','releasing-files','released')



def _components(profile):
    need(profile in ('emote','avatar','worldweb'))
    if profile=='worldweb':
        from ios.adapters.world_web_scope_components import components
        return components()
    if profile=='emote':
        from ios.adapters import emote_world as world,emote_marker_files as files,emote_marker_measurements as measurements,emote_marker_partial as partial
        from ios.adapters.emote_originals import IOSEmoteOriginals as Originals
        from ios.adapters.emote_ui_inventory import absent as absent_chooser
        Files=files.OwnedEmoteMarkerFiles
    else:
        from ios.adapters import avatar_world as world,avatar_marker_files as files,avatar_marker_measurements as measurements,avatar_marker_partial as partial
        from ios.adapters.avatar_originals import IOSAvatarOriginals as Originals
        Files=files.OwnedAvatarMarkerFiles
        def absent_chooser(value):
            need(value.get('avatarControlsVersion')==1)
            return not any(row['id'].startswith(('avatar.','people.')) for row in value['controls'])
    return SimpleNamespace(profile=profile,scope_key='ios'+profile.title()+'MarkerScopeVersion',Files=Files,Originals=Originals,
        manifest_key=profile+'ManifestVersion',generation_key=profile+'Generation',source_sequence_key=profile+'SourceSequence',
        world_factory=profile+'_world',world_original=world.original,world_packet=world.validate,WORLD_ACTION=world.ACTION,
        actual_domain=world.actual_domain,owned_marker=world.owned_marker,admitted=measurements.admitted,restored=measurements.restored,
        body_preserved=measurements.body_preserved,view_preserved=measurements.view_preserved,
        image_body_preserved=measurements.body_preserved if profile=='emote' else measurements.image_body_preserved,
        partial_execution=partial.executed,finished_execution=partial.finished,partial_restored=partial.restored,
        drained_partial=partial.drained_partial,absent_chooser=absent_chooser)


class OriginalMarkerScope:
    PROFILE=None
    @property
    def components(self):
        # Object-only historical readers and the original v1 host fixtures did
        # not run __init__. Closed profiles still bind those readers precisely.
        if not hasattr(self,'_marker_components'):
            self._marker_components=_components(type(self).PROFILE)
        return self._marker_components

    @components.setter
    def components(self,value):
        need(value.profile==type(self).PROFILE);self._marker_components=value

    @classmethod
    def archive(cls,value,*,root,binding,run,role,lock,require_ready=False):
        """Read retained originals only; do not acquire a live SDK or guard."""
        need(isinstance(lock,ScriptSourceLock));lock.assert_held();context(binding);identifier(run)
        need(role in ('primary','actor') and type(require_ready) is bool and type(value) is dict)
        result=object.__new__(cls);result.components=_components(cls.PROFILE);result.root=Path(root);result.binding=deepcopy(binding);result.run=run;result.role=role
        result.pid=int(binding['processIdentity']);result.lock=lock;result.guard=lambda:True;result.failed=True;result.frames=[]
        need(result.root.is_absolute() and result.root.resolve()==result.root and result.root.is_dir())
        result.fixture_url=value.get('fixtureUrl');result.ticket=identifier(value.get('ticket'))
        result.files=result.components.Files(None,PrivateFeatureState(result.root/'archive-unused-marker-files.json'),binding)
        result.originals=result.components.Originals(root,binding,run,role,lambda:True,lambda *_:need(False),kind='inputs')
        result.state=result.decode(value)
        if require_ready:
            need(result.state['phase']=='ready' and result.state['cleanupMode']=='full'
                and result.state['webAdmission'] is not None and result.state['pending'] is None)
            rows=[row for row in result.frames if row['label']=='view-ready'];need(len(rows)==1)
            need(rows[0]['world']['source']['view']['mode']=='look at')
            result.ui_absent(rows[0])
            admission=result.frames[result.state['webAdmission']-1]['web'];url=result.state['admission']['marker']['sourceUrl']
            contexts=[r for r in admission['contexts'] if r['descriptor']['sourceUrl']==url]
            need(admission['iosWebClosureVersion']>=5 and len(contexts)==1 and contexts[0]['descriptor']['surface']=='world-entity'
                and any(c['created']>0 for c in contexts[0]['callbacks'].values()))
        return result

    def snapshot(self):self.bound();need(self.previous is not None);return deepcopy(self.previous)

    def bind_image_world(self,world):
        """Join original image geometry to the actual admitted Script entity."""
        need(self.state['phase']=='ready' and self.state['cleanupMode']=='full' and self.state['webAdmission'] is not None)
        baseline=self.frames[self.state['baseline']-1]['world'];self.components.image_body_preserved(baseline,world)
        marker=self.state['admission']['marker'];nonce=self.state['fileOwnership']['nonce']
        need(same(marker,self.components.owned_marker(world,nonce,marker['sourceUrl'])))
        return deepcopy(dict(nonce=nonce,url=marker['sourceUrl']))

    def __init__(self,runtime,selector,root,run,role,fixture_url,ticket,lock,*,
                 monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000,sleep=time.sleep):
        self.components=_components(type(self).PROFILE)
        need(isinstance(runtime,IOSScriptRuntime) and isinstance(lock,ScriptSourceLock) and role in ('primary','actor')
            and all(callable(fn) for fn in (monotonic,epoch_ms,sleep)))
        self.runtime,self.selector,self.root=runtime,selector,Path(root)
        self.run,self.role,self.fixture_url,self.ticket=identifier(run),role,fixture_url,identifier(ticket)
        self.lock,self.monotonic,self.epoch_ms,self.sleep=lock,monotonic,epoch_ms,sleep
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-'+self.components.profile+'-'+role+'-marker.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'));lock.assert_held()
        self.live=runtime._sources(selector);self.binding=deepcopy(context(self.live['binding']));self.pid=int(self.binding['processIdentity'])
        self.guard=self.live['check'];observer=self.live['observer'];clock=self.live['clock_source']
        self.native=observer.bound_native_observer(clock);self.world=getattr(observer,self.components.world_factory)(clock)
        self.terminals=observer.script_terminal(clock);self.work=observer.script_work(clock);self.web=observer.web_closures()
        self.dialogs=observer.script_dialogs(clock)
        self.files=self.components.Files(observer.script_fixture_files(),
            PrivateFeatureState(self.store.path.with_name('ios-'+self.components.profile+'-'+role+'-marker-files.json')),self.binding)
        self.originals=self.components.Originals(root,self.binding,run,role,self.guard,self.storage_intent,kind='inputs',monotonic=monotonic)
        self.frames=[];self.failed=False;self.previous=self.store.read()
        self.state=dict(phase='new',revision=0,manifests=[],pending=None,baseline=None,admission=None,admissionFrame=None,loadBarrier=None,
            stopBarrier=None,webAdmission=None,directory=None,fileOwnership=None,operations=[],leases=dict(tablet=False,address=False,menu=False),quiet=[],cleanupMode='full')
        if self.previous is not None:
            self.state=self.decode(self.previous)
            if self.frames:
                last=self.frames[-1];self.world.last=deepcopy(last['world']);self.terminals.restore(last['terminal'])
                self.web.last=deepcopy(last['web']);restore_native(self.native,last['clockJoin']['nativeAfter'])
                self.dialogs.last=deepcopy(last['dialogs'])
                work=[row['work'] for row in self.frames if row['work'] is not None]
                if work:self.work.restore(work)

    def envelope(self,state):
        return dict(**{self.components.scope_key:VERSION},runId=self.run,role=self.role,binding=self.binding,
            artifactRoot=str(self.root),fixtureUrl=self.fixture_url,ticket=self.ticket,payload=pack([state]))

    def decode(self,value):
        exact(value,{self.components.scope_key,'runId','role','binding','artifactRoot','fixtureUrl','ticket','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','revision','manifests','pending','baseline','admission','admissionFrame','loadBarrier','stopBarrier','webAdmission',
                     'directory','fileOwnership','operations','leases','quiet','cleanupMode'})
        need(state['cleanupMode'] in ('full','partial-execution','finished-execution','unloaded'))
        need(state['phase'] in PHASES and integer(state['revision'],0,MAX_FRAMES))
        frames=self.originals.restore(state['manifests'],state['revision']);previous=None
        for frame in frames:self.validate_frame(frame,previous);previous=frame
        self.frames=frames
        if state['fileOwnership'] is not None:
            # Validate retained input ownership even after native-file metadata
            # has legitimately retired. This does not reread or restage files.
            class Frozen:
                def read(_self):return deepcopy(state['fileOwnership'])
            owner=self.components.Files(self.files.native,Frozen(),self.binding);value=owner.owned()
            need(value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['ticket']==self.ticket)
        for key in ('baseline','webAdmission','admissionFrame'):
            need(state[key] is None or integer(state[key],1,len(frames)))
        need(type(state['operations']) is list and len(state['operations'])<=64 and type(state['quiet']) is list)
        labels=set()
        for row in state['operations']:
            exact(row,{'label','phase','result'});need(type(row['label']) is str and row['label'] not in labels
                and re.fullmatch('[a-z][a-z0-9-]{0,63}',row['label']) and row['phase'] in ('issued','returned'))
            labels.add(row['label']);need(row['phase']=='returned' or row['result'] is None)
        exact(state['leases'],{'tablet','address','menu'});need(all(type(v) is bool for v in state['leases'].values()))
        need(all(integer(v,1,len(frames)) for v in state['quiet']))
        if state['pending'] is not None:
            exact(state['pending'],{'label','original','manifest','partial'})
            need(type(state['pending']['label']) is str and type(state['pending']['partial']) is dict)
            if state['pending']['original'] is not None:self.originals.original(state['pending']['original'])
        if state['phase'] not in ('new','preparing'):
            need(state['baseline'] is not None and (state['admission'] is not None or state['cleanupMode']=='unloaded'))
        if state['admission'] is not None:
            need(state['admissionFrame'] is not None);loaded=frames[state['admissionFrame']-1]
            label='finished-marker-check' if state['cleanupMode']=='finished-execution' else 'partial-marker-check' if state['cleanupMode']=='partial-execution' else 'marker-loaded'
            barriers=[row for row in frames if row['label']=='before-marker-load']
            need(loaded['label']==label and len(barriers)==1 and state['fileOwnership'] is not None
                and state['loadBarrier']==barriers[0]['clockJoin']['nativeAfter']['capturedEpochMs'])
            if state['cleanupMode']=='finished-execution':
                expected=self.components.finished_execution(frames[state['baseline']-1]['world'],loaded['world'],state['fileOwnership'],state['directory'],loaded['terminal'],
                    after_sequence=barriers[0]['terminal']['source']['eventSequence'],after_epoch=state['loadBarrier'])
            else:
                admission=self.components.partial_execution if state['cleanupMode']=='partial-execution' else self.components.admitted
                expected=admission(frames[state['baseline']-1]['world'],loaded['world'],state['fileOwnership'],state['directory'],after_epoch=state['loadBarrier'])
            need(same(state['admission'],expected))
        if state['stopBarrier'] is not None:
            if state['cleanupMode']=='finished-execution':
                rows=[row for row in loaded['terminal']['source']['events'] if row['manager']==state['admission']['manager'] and row['kind']=='thread-bound']
                need(len(rows)==1 and state['stopBarrier']==dict(sequence=rows[0]['eventSequence'],epoch=rows[0]['capturedEpochMs']))
            else:
                barriers=[row for row in frames if row['label']=='before-marker-stop'];need(len(barriers)==1)
                need(state['stopBarrier']==dict(sequence=barriers[0]['terminal']['source']['eventSequence'],
                    epoch=barriers[0]['clockJoin']['nativeAfter']['capturedEpochMs']))
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(not self.failed and same(self.store.read(),self.previous) and self.guard() is not False)

    def save(self):
        self.bound();value=self.envelope(self.state)
        try:self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
        except Exception:self.failed=True;raise

    def storage_intent(self,kind,value):
        self.bound();pending=self.state['pending'];need(pending is not None and kind in ('original','manifest'))
        old=pending[kind]
        if kind=='original':
            self.originals.original(value);need(value['index']==len(self.frames)+1)
            need(value['phase']=='planned' if old is None else value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
                and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
                and (old['phase']=='planned' or same(old['file'],value['file'])))
        else:
            exact(value,{self.components.manifest_key,'reference','phase'});need(value[self.components.manifest_key]==1
                and pending['original'] is not None and pending['original']['phase']=='saved')
            self.originals.manifest_reference(value['reference'])
            need(value['phase']=='planned' if old is None else old['phase']=='planned' and value['phase']=='saved'
                and same(old['reference'],value['reference']))
        pending[kind]=deepcopy(value);self.save()

    def validate_frame(self,frame,previous=None):
        exact(frame,{'label','world','terminal','dialogs','web','widgets','work','clockJoin'})
        need(type(frame['label']) is str);originals={k:frame[k] for k in ('world','terminal','dialogs','web','widgets','work')}
        join=validate_join(frame['clockJoin'],originals);epoch=join['nativeAfter']['capturedEpochMs']
        world=self.components.world_original(frame['world']);need(world['processId']==self.pid and world['runId']==self.run)
        need(join['nativeBefore']['capturedEpochMs']<=world['clockBefore']['epochMs']<=world['clockAfter']['epochMs']<=epoch)
        widgets_packet(frame['widgets'],self.pid,epoch)
        d=frame['dialogs'];dialogs_packet(d,dict(schemaVersion=1,commandId=d['requestId'],action=DIALOG_ACTION,runId=self.run),self.pid,epoch,
            None if previous is None else previous['dialogs'])
        need(join['nativeBefore']['capturedEpochMs']<=d['clockBefore']['epochMs']<=d['clockAfter']['epochMs']<=epoch)
        t=frame['terminal'];terminal_packet(t,dict(schemaVersion=1,commandId=t['commandId'],action='feature-script-terminal-observe'),self.pid,epoch,
            previous=None if previous is None else previous['terminal'])
        w=frame['web'];web_packet(w,dict(schemaVersion=1,commandId=w['commandId'],action='feature-ios-web-closures',
            runId=self.run,fixtureUrl=self.fixture_url),self.pid,epoch)
        if frame['work'] is not None:
            item=frame['work'];query=dict(schemaVersion=1,commandId=item['requestId'],action='feature-script-work-observe',managerInstance=item['source']['manager']['instance'])
            work_packet(item,query,self.pid,epoch)
        if previous:
            follow_native(previous['clockJoin']['nativeAfter'],join['nativeBefore']);web_continuity(previous['web'],w,self.pid)
            self.components.world_packet(world,dict(schemaVersion=1,commandId=world['requestId'],action=self.components.WORLD_ACTION,runId=self.run),
                self.pid,epoch,previous['world'])
            left,right=previous['widgets'],frame['widgets']
            need(left['instance']==right['instance'] and left[self.components.generation_key]==right[self.components.generation_key]
                and right[self.components.source_sequence_key]>left[self.components.source_sequence_key] and right['lastSequence']>=left['lastSequence']
                and right['elapsedMs']>=left['elapsedMs'] and right['sampleEpochMs']>=left['sampleEpochMs'])
            need(join['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic'])
        return frame

    def capture(self,label,manager=None):
        from adapters.original_marker_recovery import OriginalMarkerRecovery
        self.bound();recovery=OriginalMarkerRecovery(self);recovery.recover();need(self.state['pending'] is None and len(self.frames)<MAX_FRAMES)
        self.state['pending']=dict(label=label,original=None,manifest=None,partial={});self.save()
        def remember(name,value):
            need(name not in self.state['pending']['partial']);self.state['pending']['partial'][name]=deepcopy(value);self.save();return value
        clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(self.epoch_ms())
        remember('nativeStart',clock.started);originals={}
        originals['world']=remember('world',self.world.read(self.run))
        originals['terminal']=remember('terminal',self.terminals.read(0 if self.terminals.last is None else self.terminals.last['sequence']))
        originals['dialogs']=remember('dialogs',self.dialogs.read(self.run))
        originals['web']=remember('web',self.web.read(self.run,self.fixture_url))
        originals['widgets']=remember('widgets',self.live['native'].capture())
        if manager is None and self.state['admission'] is not None:
            candidate=self.state['admission']['manager'];engines=originals['world']['source']['scriptOriginal']['source']['engines']
            if any(row['required']['instance']==candidate['instance'] and row['running'] and not row['stopping'] and not row['finished'] for row in engines):manager=candidate
        originals['work']=remember('work',None if manager is None else self.work.read(manager['instance'],0 if self.work.last is None else self.work.last['sequence']))
        fields=[(name,field) for name,row in originals.items() if type(row) is dict
                for field in ('capturedEpochMs','sampleEpochMs') if field in row]
        frame=dict(label=label,**originals,clockJoin=clock.finish(originals,fields))
        remember('clockJoin',frame['clockJoin']);self.validate_frame(frame,self.frames[-1] if self.frames else None);recovery.follow(frame)
        item=self.originals.write(len(self.frames)+1,frame);manifests=self.originals.append(self.state['manifests'],item)
        self.frames.append(deepcopy(frame));self.state.update(revision=len(self.frames),manifests=manifests,pending=None);self.save()
        return deepcopy(frame)

    def once(self,label,function):
        self.bound();rows=[r for r in self.state['operations'] if r['label']==label]
        if rows:need(rows[0]['phase']=='returned');return deepcopy(rows[0]['result'])
        need(len(self.state['operations'])<64);row=dict(label=label,phase='issued',result=None)
        self.state['operations'].append(row);self.save();result=function()
        self.bound();row.update(phase='returned',result=deepcopy(result));self.save();return result

    def manager(self):
        ui,observe,binding,_check,_installed=self.runtime.normal_feature_runtime(self.selector)
        need(same(binding,self.binding));picker=TokenScriptFilePicker(ui.io,self.state['directory'])
        return NormalScriptManager(ui,observe,PrivateFeatureState(self.store.path.with_name('ios-'+self.components.profile+'-'+self.role+'-marker-script.json')),
            binding,source_kind='script-file-bundle',file_owner=self.files,file_picker=picker)

    def surface(self):
        def intent(stage,subject,graphics,control):
            # The surface obtains independently validated originals before each
            # ordinary pointer. This compact journal owns delivery, not effects.
            self.bound();need(self.state['phase'] in ('preparing','restoring-view'))
            label='view-'+str(len(self.state['operations']))
            need(len(self.state['operations'])<64)
            self.state['operations'].append(dict(label=label,phase='returned',result=dict(stage=stage,control=control,
                subject=deepcopy(subject),controls=deepcopy(graphics))));self.save()
        def owns(field):return self.state['leases'][field]
        def lease(field,value):self.state['leases'][field]=value;self.save()
        return IOSGraphicsRuntime._graphics_surface(self.runtime,self.selector,self.run,intent,owns,lease,lambda _:False,lock=self.lock)

    def prepare(self):
        self.bound()
        if self.state['phase']=='ready':return deepcopy(self.state['admission'])
        need(self.state['phase']=='new' and self.files.store.read() is None)
        before=self.capture('baseline');self.components.actual_domain(before['world']);need(not before['widgets']['tabletShown'] and self.components.absent_chooser(before['widgets'])
            and before['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
        self.ui_absent(before)
        self.state.update(phase='preparing',baseline=len(self.frames));self.save()
        self.files.reserve_marker(self.run,self.fixture_url,self.ticket)
        self.state['fileOwnership']=deepcopy(self.files.owned());self.save()
        self.state['directory']=self.once('stage-marker-files',self.files.stage_reserved);self.save()
        manager=self.manager();self.once('open-marker-manager',manager.open);self.once('open-marker-picker',manager.file_picker_open)
        barrier=self.capture('before-marker-load');self.state['loadBarrier']=barrier['clockJoin']['nativeAfter']['capturedEpochMs'];self.save()
        self.once('load-marker-script',lambda:manager.file_picker_choose('script-bundle/main.js'))
        self.once('close-marker-manager',manager.close_tablet)
        after=self.capture('marker-loaded');owned=self.components.admitted(before['world'],after['world'],self.files.owned(),self.state['directory'],after_epoch=self.state['loadBarrier'])
        self.state.update(admission=owned,admissionFrame=len(self.frames));self.save()
        self.once('select-marker-view',lambda:self.surface().select_camera('look at'))
        current=self.capture('view-ready',owned['manager']);self.components.body_preserved(before['world'],current['world'])
        need(current['world']['source']['view']['mode']=='look at' and not current['widgets']['tabletShown'])
        self.state['phase']='ready';self.save();return deepcopy(owned)

    def admit_rendered(self):
        self.bound();need(self.state['phase']=='ready');frame=self.capture('rendered-marker')
        rows=[r for r in frame['web']['contexts'] if r['descriptor']['sourceUrl']==self.state['admission']['marker']['sourceUrl']]
        need(frame['web']['iosWebClosureVersion']>=5 and len(rows)==1 and rows[0]['descriptor']['surface']=='world-entity'
            and any(c['created']>0 for c in rows[0]['callbacks'].values()))
        self.state['webAdmission']=len(self.frames);self.save();return frame

    def cleanup(self):
        self.bound()
        if self.state['phase']=='released':return {'performed':True}
        if self.state['phase'] in ('new','preparing'):
            if self.state['baseline'] is None:
                current=self.capture('unused-baseline');self.ui_absent(current)
                need(current['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
                self.state['baseline']=len(self.frames);self.save()
            loaded=any(row['label']=='load-marker-script' for row in self.state['operations'])
            if loaded:
                # Cancel an owned unfinished picker before deciding whether its
                # asynchronous Application callback actually created a worker.
                self.close_owned_manager('partial')
                baseline=self.frames[self.state['baseline']-1];current=self.capture('partial-marker-check')
                url=self.state['directory']+'/script-bundle/main.js'
                engines=current['world']['source']['scriptOriginal']['source']['engines']
                if any(row['url']==url for row in engines):
                    owned=self.components.partial_execution(baseline['world'],current['world'],self.state['fileOwnership'],self.state['directory'],after_epoch=self.state['loadBarrier'])
                    self.state.update(admission=owned,admissionFrame=len(self.frames),cleanupMode='partial-execution',webAdmission=len(self.frames),phase='ready');self.save()
                else:
                    if any(row['manager']['url']==url for row in current['terminal']['source']['events']):
                        self.adopt_finished();self.state['phase']='ready';self.save()
                    else:self.unexecuted(current);self.state.update(cleanupMode='unloaded',phase='aborting-unused');self.save()
            else:self.state.update(cleanupMode='unloaded',phase='aborting-unused');self.save()
        if self.state['phase']=='aborting-unused':self.abort_unused()
        if self.state['phase']=='releasing-files' and self.state['cleanupMode']=='unloaded':return self.release_files()
        if self.state['phase']=='ready' and self.state['webAdmission'] is None:
            baseline=self.frames[self.state['baseline']-1];current=self.capture('partial-marker-check')
            if any(row['url']==self.state['directory']+'/script-bundle/main.js' for row in current['world']['source']['scriptOriginal']['source']['engines']):
                owned=self.components.partial_execution(baseline['world'],current['world'],self.state['fileOwnership'],self.state['directory'],after_epoch=self.state['loadBarrier'])
                self.state.update(admission=owned,admissionFrame=len(self.frames),cleanupMode='partial-execution',webAdmission=len(self.frames));self.save()
            else:self.adopt_finished()
        need(self.state['phase'] in ('ready','restoring-view','stopping-marker','quiet','releasing-files') and self.state['webAdmission'] is not None)
        baseline=self.frames[self.state['baseline']-1];owned=self.state['admission']
        if self.state['phase']=='ready':
            before=self.capture('before-view-restoration')
            need(not before['widgets']['tabletShown'] and self.components.absent_chooser(before['widgets'])
                and before['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
            if before['work'] is None and self.state['cleanupMode']!='finished-execution':
                self.adopt_finished();owned=self.state['admission']
            self.state['phase']='restoring-view';self.save()
        if self.state['phase']=='restoring-view':
            rows=[r for r in self.state['operations'] if r['label']=='restore-marker-view']
            if rows and rows[0]['phase']=='issued':
                current=self.capture('uncertain-view-restoration');self.components.view_preserved(baseline['world'],current['world'])
                if current['widgets']['tabletShown']:
                    need(self.state['leases']['tablet']);self.once('finish-owned-view-close',lambda:self.surface().close_tablet())
                    current=self.capture('uncertain-view-ui-closed')
                need(not current['widgets']['tabletShown']);self.components.view_preserved(baseline['world'],current['world'])
                inventory=script_ui_inventory(current['widgets']['scriptInventory'])
                need(inventory['complete'] and not any(r['rootVisible'] for r in inventory['managers'])
                    and not any(r['visible'] or r['closing'] or r['requestId'] for r in inventory['pickers']))
                for field in self.state['leases']:self.state['leases'][field]=False
                rows[0].update(phase='returned',result={'performed':True});self.save()
            self.once('restore-marker-view',lambda:self.surface().select_camera(baseline['world']['source']['view']['mode']))
            if self.state['cleanupMode']=='finished-execution':
                self.close_owned_manager('ended');current=self.capture('ended-marker-ui-closed')
                self.restored_marker(baseline,current,owned,self.state['stopBarrier']);self.retire_manager_metadata(current)
                self.state['phase']='quiet';self.save()
            else:
                barrier=self.capture('before-marker-stop',owned['manager']);work=barrier['work']['source']['work']
                need(work['signalCallbacks']==work['timerCallbacks']==0 and work['evaluating'] is False and work['timers']==[]
                    and barrier['work']['source']['manager']==owned['manager'] and barrier['work']['source']['code']==owned['code'])
                self.state.update(phase='stopping-marker',stopBarrier=dict(sequence=barrier['terminal']['source']['eventSequence'],
                    epoch=barrier['clockJoin']['nativeAfter']['capturedEpochMs']));self.save()
                manager=self.manager();self.once('reopen-marker-manager',manager.open)
                self.once('stop-marker-script',lambda:manager.stop_source(owned['sourceUrl']))
                self.close_owned_manager('retire-marker-manager')
        if self.state['phase']=='stopping-marker':
            current=self.capture('marker-stop-observed');barrier=self.state['stopBarrier']
            self.restored_marker(baseline,current,owned,barrier)
            if current['widgets']['tabletShown']:
                manager=self.manager();need(manager.state['tabletOwned'] and manager.state['source']==owned['sourceUrl'])
                # Independent terminal/source proof resolves a lost stop return;
                # the stop pointer itself is never delivered a second time.
                manager.mark(loadAttempted=False)
                self.close_owned_manager('retire-marker-manager')
                current=self.capture('marker-manager-closed')
            self.retire_manager_metadata(current)
            self.state['phase']='quiet';self.save()
        if self.state['phase']=='quiet':
            # Reconstructed quiet windows start with new original reads; old
            # saved observations never count as current quiet duration.
            self.state['quiet']=[];self.save();started=self.monotonic()
            for attempt in range(41):
                current=self.capture('cleanup-quiet');barrier=self.state['stopBarrier']
                try:
                    self.restored_marker(baseline,current,owned,barrier);self.ui_absent(current);self.dialog_drained(current)
                    need(current['clockJoin']['nativeAfter']['animation']['overrideActive'] is False)
                    drain=self.components.drained_partial if self.state['cleanupMode'] in ('partial-execution','finished-execution') else drained_owned_resources
                    drain(current['web'],self.frames[self.state['webAdmission']-1]['web'])
                except NativeUIError:self.state['quiet']=[]
                else:self.state['quiet'].append(len(self.frames))
                self.save()
                if len(self.state['quiet'])>=3:
                    if self.quiet_interval(self.frames[self.state['quiet'][0]-1],current):
                        self.state['phase']='releasing-files';self.save();break
                need(self.monotonic()-started<10)
                if attempt<40:self.sleep(.1)
            need(self.state['phase']=='releasing-files')
        if self.state['phase']=='releasing-files':return self.release_files()
        return {'performed':True}

    @classmethod
    def ui_absent(cls,frame):
        inventory=script_ui_inventory(frame['widgets']['scriptInventory'])
        need(inventory['complete'] and not inventory['tabletShown'] and not inventory['managers'] and not inventory['pickers']
            and not frame['widgets']['tabletShown'] and _components(cls.PROFILE).absent_chooser(frame['widgets']))

    def restored_marker(self,baseline,current,owned,barrier):
        restore=self.components.partial_restored if self.state['cleanupMode'] in ('partial-execution','finished-execution') else self.components.restored
        return restore(baseline['world'],current['world'],owned,current['terminal'],after_sequence=barrier['sequence'],after_epoch=barrier['epoch'])

    def adopt_finished(self):
        current=self.capture('finished-marker-check');baseline=self.frames[self.state['baseline']-1]
        barriers=[row for row in self.frames if row['label']=='before-marker-load'];need(len(barriers)==1)
        owned=self.components.finished_execution(baseline['world'],current['world'],self.state['fileOwnership'],self.state['directory'],current['terminal'],
            after_sequence=barriers[0]['terminal']['source']['eventSequence'],after_epoch=self.state['loadBarrier'])
        rows=[row for row in current['terminal']['source']['events'] if row['manager']==owned['manager'] and row['kind']=='thread-bound'];need(len(rows)==1)
        self.state.update(admission=owned,admissionFrame=len(self.frames),cleanupMode='finished-execution',
            stopBarrier=dict(sequence=rows[0]['eventSequence'],epoch=rows[0]['capturedEpochMs']))
        if self.state['webAdmission'] is None:self.state['webAdmission']=len(self.frames)
        self.save();return owned

    def release_files(self):
        self.bound();need(self.state['phase']=='releasing-files')
        if self.state['fileOwnership'] is None:
            need(self.files.store.read() is None and not any(row['label']=='stage-marker-files' for row in self.state['operations']))
        else:
            rows=[r for r in self.state['operations'] if r['label']=='release-marker-files']
            if rows and rows[0]['phase']=='issued':
                owned_files=self.state['fileOwnership'];source=self.files.native.request('observe',self.run,owned_files['ownerToken'])
                need(source==dict(exists=False,files=[]))
                if self.files.store.read() is not None:
                    need(same(self.files.owned(),owned_files));self.files.store.discard(self.files.store.read())
                rows[0].update(phase='returned',result={'performed':True});self.save()
            else:self.once('release-marker-files',self.files.release)
        need(self.files.store.read() is None and not any(self.state['leases'].values()))
        self.state['phase']='released';self.save()
        return {'performed':True}

    def resolve_closed_ui(self,frame,manager):
        inventory=script_ui_inventory(frame['widgets']['scriptInventory']);need(inventory['complete'])
        picker_absent=not inventory['pickers'];manager_absent=not inventory['managers'];tablet_absent=not frame['widgets']['tabletShown']
        changes={}
        if picker_absent:changes.update(pickerOwned=False,dialogOwned=False)
        if manager_absent:changes['managerOwned']=False
        if tablet_absent:changes['tabletOwned']=False
        if changes:manager.mark(**changes)
        for row in self.state['operations']:
            observed=(row['label'].endswith('-cancel-picker') and picker_absent
                or row['label'].endswith('-home') and manager_absent and picker_absent
                or row['label'].endswith('-reopen-owned-tablet') and not tablet_absent
                or row['label'].endswith('-close-tablet') and tablet_absent and picker_absent)
            if row['phase']=='issued' and observed:row.update(phase='returned',result=None)
        self.save();return inventory

    def close_owned_manager(self,prefix):
        store=PrivateFeatureState(self.store.path.with_name('ios-'+self.components.profile+'-'+self.role+'-marker-script.json'))
        if store.read() is None:
            frame=self.capture(prefix+'-ui-absent');self.ui_absent(frame);return
        manager=self.manager();frame=self.capture(prefix+'-ui-before-close');inventory=self.resolve_closed_ui(frame,manager)
        if inventory['managers'] and not frame['widgets']['tabletShown']:
            need(any(row['label']=='open-marker-manager' for row in self.state['operations']))
            manager.mark(tabletOwned=True)
            self.once(prefix+'-reopen-owned-tablet',manager.ui.open_tablet)
        if manager.state['pickerOwned']:self.once(prefix+'-cancel-picker',manager.close_dialog)
        current=manager.ui.capture()
        if current['open']:
            need(manager.state['tabletOwned'])
            if manager.ui.control(current,'tablet.home') is not None:self.once(prefix+'-home',lambda:manager.ui.activate('tablet.home'))
            self.once(prefix+'-close-tablet',manager.close_tablet)
        frame=self.capture(prefix+'-ui-closed');self.ui_absent(frame);self.resolve_closed_ui(frame,manager)

    def abort_unused(self):
        """Cancel only owned setup UI when no Script selection was delivered."""
        self.bound();need(self.state['phase']=='aborting-unused' and self.state['cleanupMode']=='unloaded')
        if self.state['fileOwnership'] is None and self.files.store.read() is not None:
            value=self.files.owned();need(value['runId']==self.run and value['fixtureUrl']==self.fixture_url and value['ticket']==self.ticket)
            self.state['fileOwnership']=value;self.save()
        child=PrivateFeatureState(self.store.path.with_name('ios-'+self.components.profile+'-'+self.role+'-marker-script.json'))
        if child.read() is not None:
            need(self.state['directory'] is not None);manager=self.manager()
            need(manager.state['source'] in (None,self.state['directory']+'/script-bundle/main.js'))
        self.close_owned_manager('abort')
        baseline=self.frames[self.state['baseline']-1];self.state['quiet']=[];self.save();started=self.monotonic()
        for attempt in range(41):
            current=self.capture('unused-cleanup-quiet')
            try:
                self.ui_absent(current);self.components.body_preserved(baseline['world'],current['world']);self.components.view_preserved(baseline['world'],current['world'])
                need(current['world']['source']['tree']['entities']==baseline['world']['source']['tree']['entities']
                    and not current['world']['source']['markers'] and current['clockJoin']['nativeAfter']['animation']['overrideActive'] is False
                    and same(current['clockJoin']['nativeAfter']['graphics'],baseline['clockJoin']['nativeAfter']['graphics']))
                self.components.drained_partial(current['web'],baseline['web'])
                if self.state['directory'] is not None:
                    url=self.state['directory']+'/script-bundle/main.js';source=current['world']['source']['scriptOriginal']['source']
                    need(source.get('membershipSourceVersion')==1 and source['membership']['complete']
                        and not any(row['url']==url for row in source['membership']['managers'])
                        and not any(row['url']==url for row in source['engines']))
                self.unexecuted(current);self.dialog_drained(current)
            except NativeUIError:self.state['quiet']=[]
            else:self.state['quiet'].append(len(self.frames))
            self.save()
            if len(self.state['quiet'])>=3 and self.quiet_interval(self.frames[self.state['quiet'][0]-1],current):
                if child.read() is not None:
                    manager=self.manager();manager.mark(tabletOwned=False,managerOwned=False,pickerOwned=False,dialogOwned=False,loadAttempted=False)
                    self.once('abort-release-input',manager.ui.release);manager.store.discard(manager.previous)
                self.state['phase']='releasing-files';self.save();return
            need(self.monotonic()-started<10)
            if attempt<40:self.sleep(.1)
        need(False)

    def unexecuted(self,current):
        """Actual returned dialog callback plus no assigned/started worker.

        QObject destruction alone is insufficient: its response can still be
        queued to Application. The original returned callback and complete
        native membership must both be present before ownership can retire.
        """
        if not any(row['label']=='open-marker-picker' for row in self.state['operations']):return True
        baseline=self.frames[self.state['baseline']-1];self.ui_absent(current)
        proof=self.dialog_drained(current)
        url=self.state['directory']+'/script-bundle/main.js';entered=proof['entered'];returned=proof['returned']
        need(entered['response']['text'] in ('',url) and returned['manager'] is None)
        source=current['world']['source']['scriptOriginal']['source'];membership=source.get('membership')
        need(source.get('membershipSourceVersion')==1 and membership['complete']
            and not any(row['url']==url for row in membership['managers'])
            and not any(row['url']==url for row in source['engines'])
            and not any(row['manager']['url']==url for row in current['terminal']['source']['events']))
        return proof

    def dialog_drained(self,current):
        """Both actual response return and original owned listener death."""
        if not any(row['label']=='open-marker-picker' for row in self.state['operations']):return True
        baseline=self.frames[self.state['baseline']-1]
        proof=dialog_completed(current['dialogs'],baseline['dialogs'],after_epoch=baseline['clockJoin']['nativeAfter']['capturedEpochMs'])
        rows=[row for row in current['dialogs']['source']['events']
              if row['dialogInstance']==proof['dialog'] and row['kind']=='listener-destroyed']
        need(len(rows)==1 and rows[0]['capturedEpochMs']>=baseline['clockJoin']['nativeAfter']['capturedEpochMs'])
        admission=self.state['admission']
        if admission is not None:
            need(proof['returned']['manager']==admission['manager'] and proof['entered']['fileExists'] is True
                and proof['entered']['response']['text']==admission['sourceUrl'])
        return proof

    @staticmethod
    def quiet_interval(first,last):
        """Exclude both acquisitions; require independent native elapsed time."""
        a,b=first['clockJoin'],last['clockJoin'];x,y=first['world'],last['world']
        need(x['processId']==y['processId'] and x['instance']==y['instance'])
        return (b['hostBeforeMonotonic']-a['hostAfterMonotonic']>=3
            and y['clockBefore']['monotonicMs']-x['clockAfter']['monotonicMs']>=3000
            and y['clockBefore']['epochMs']-x['clockAfter']['epochMs']>=3000)

    def retire_manager_metadata(self,frame):
        """Only retire uncertain child ownership after original GUI absence."""
        self.ui_absent(frame)
        store=PrivateFeatureState(self.store.path.with_name('ios-'+self.components.profile+'-'+self.role+'-marker-script.json'))
        if store.read() is not None:
            manager=self.manager();need(manager.state['source']==self.state['admission']['sourceUrl'])
            manager.mark(tabletOwned=False,managerOwned=False,dialogOwned=False,pickerOwned=False,loadAttempted=False)
            self.once('retire-marker-input-release',manager.ui.release)
            manager.store.discard(manager.previous)
        for row in self.state['operations']:
            if row['label'] in ('stop-marker-script','retire-marker-manager','retire-marker-manager-home') and row['phase']=='issued':
                row.update(phase='returned',result=None)
        self.save()
