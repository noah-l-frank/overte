"""Separate, durably owned originals for incomplete World Web setup.

Every returned component is saved before another native query. Unknown carrier
birth is retained without input/query replay; no fabricated rendered lease is
needed to decode a real null Entity return or an unexecuted Script selection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
import time
import uuid
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import identifier,result
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.world_web_file_receipts import WorldWebFileReceipts
from ios.adapters.world_web_setup_measurements import original as setup_original
from ios.adapters.world_web_setup_held import original as held_original
from ios.adapters.world_web_held_resources import public as held_public
from ios.adapters.world_web_setup_pixels import restored
from ios.adapters.world_web_retired import quiet,quiet_summary,activity
from ios.adapters.world_web_scene import scene
from ios.adapters.world_web_api_clock import check


def _readonly(function):
    """Keep existing immutable original scopes through one pure method only."""
    @wraps(function)
    def wrapped(self,*args,**kwargs):
        from ios.adapters.world_web_scope_archive import original_round
        with original_round(),self.observer.validation_round():return function(self,*args,**kwargs)
    return wrapped


class WorldWebSetupRetirement:
    def __init__(self,store,scope,observer,baseline,*,baseline_image=None,files=None,sample_factory=None,sample_requests=(),sleep=time.sleep):
        need(type(store) is PrivateFeatureState and type(scope) is IOSWorldWebScope and type(observer) is WorldWebObserver
            and observer.lease is None and same(scope.binding,observer.source.binding) and scope.run==observer.run
            and scope.lock is observer.source.lock and callable(sleep))
        self.store,self.scope,self.observer,self.sleep=store,scope,observer,sleep
        self.lease=None
        self.source,self.peer,self.binding,self.run,self.role,self.lock=observer.source,observer.peer,deepcopy(observer.binding),observer.run,observer.role,observer.lock
        self.baseline=deepcopy(baseline);self.source.frame(baseline)
        self.baseline_image,self.files,self.sample_factory=baseline_image,files,sample_factory
        if self.role=='primary':need(type(baseline_image) is WorldWebSample and baseline_image.source is self.source
            and type(files) is WorldWebFileReceipts and files.binding==self.binding and callable(sample_factory))
        else:need(baseline_image is files is sample_factory is None)
        self.required_images=list(dict.fromkeys(([] if baseline_image is None else [baseline_image.request])+list(sample_requests)))
        self.previous=store.read();self.state=dict(phase='new',ticket=None,baseline=deepcopy(baseline),records=[],pending=None,barrier=None,quiet=[],restoration=None,
            images=deepcopy(self.required_images))
        self.lock.assert_held();self.source.lock.assert_held()
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosWorldWebSetupRetirementVersion=1,binding=self.binding,primaryBinding=self.source.binding,runId=self.run,role=self.role,payload=pack([state]))

    def guard(self):
        check();self.lock.assert_held();self.source.lock.assert_held();need(same(self.store.read(),self.previous))
        for source in (self.source,self.peer):
            if source is None:continue
            if source.historical:need(source.readers is None);source.guard_originals()
            else:source.bound()

    def save(self):
        self.guard();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);check()

    def parts(self,row):
        def intent(kind,value):
            need(kind=='original' and row is self.state['pending'] and row['writing'] is not None
                and value['index']==len(row['parts'])+1)
            row['carrier']=deepcopy(value);self.save()
        return OriginalFrameStore(self.scope.root,self.binding,self.run,self.role,self.guard,intent,
            namespace='wwsu-'+row['acquisition'][:26],schema_prefix='worldWebSetup',monotonic=self.source.monotonic)

    def values(self,row):
        need(type(row['parts']) is list and len(row['parts'])<=256);store=self.parts(row);values={}
        for index,reference in enumerate(row['parts'],1):
            need(reference['index']==index);body=store.read(store.expand(reference));exact(body,{'name','value'})
            need(type(body['name']) is str and body['name'] not in values);values[body['name']]=body['value']
        return values

    def put(self,row,name,value):
        need(row is self.state['pending'] and row['writing'] is row['carrier'] is None)
        row['writing']=name;self.save();reference=self.parts(row).write(len(row['parts'])+1,dict(name=name,value=deepcopy(value)))
        row['parts'].append(reference);row.update(writing=None,carrier=None);self.save()

    def recover(self):
        if self.state['pending'] is None:return
        row=self.state['pending'];self.values(row)
        if row['writing'] is None:need(row['carrier'] is None);return
        carrier=row['carrier'];need(carrier is not None);store=self.parts(row);store.original(carrier)
        # Only an actually observed opened inode plus full immutable bytes can
        # finish private evidence storage. Planned/no-inode remains owned.
        need(carrier['phase'] in ('opened','saved'));body=store.read(carrier)
        exact(body,{'name','value'});need(body['name']==row['writing'])
        row['parts'].append(store.compact(dict(carrier,phase='saved')));row.update(writing=None,carrier=None);self.save()

    def sample(self,request):
        need(self.role=='primary');owner=self.baseline_image if request==self.baseline_image.request else self.sample_factory(request)
        need(type(owner) is WorldWebSample and owner.source is self.source and owner.request==request and owner.binding==self.binding)
        return owner

    @_readonly
    def measure(self,row):
        values=self.values(row);need('before' in values and 'observation' in values)
        names={'before','observation'}
        if self.role=='primary':
            names.add('files')
            names.update(prefix+request for request in row['images'] for prefix in ('gpu-owner:','gpu-before:','gpu-after:'))
        need(set(values)==names)
        measured=self.observer.validate_original(values['observation']);entry=self.observer.entries()[values['observation']['reference']['index']-1]
        native=setup_original(self.scope,self.source,self.baseline,entry['source'])
        first,last=self.source.frame(values['before']),self.source.frame(entry['source'])
        need(first['index']<last['index'] and first['ticket']==last['ticket']==self.state['ticket']
            and first['phaseBefore']['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        if self.role=='primary':
            owned=self.scope.state['fileOwnership']
            if owned is None:need(self.scope.files.store.read() is None and values.get('files') is None)
            else:
                file=self.files.original(values['files']);need(file['kind']=='absent' and same(file['ownership'],owned)
                    and first['clockJoin']['nativeAfter']['capturedEpochMs']<=file['clockJoin']['nativeBefore']['capturedEpochMs']
                    <=file['clockJoin']['nativeAfter']['capturedEpochMs']<=last['clockJoin']['nativeBefore']['capturedEpochMs'])
            from ios.adapters.world_web_retirement import WorldWebRetirement
            for request in row['images']:
                # Reuse the closed actual GPU byte/clock decoder, not its full
                # rendered-lease constructor or an invented native ownership.
                WorldWebRetirement.gpu_original(self,request,values['gpu-owner:'+request],values['gpu-before:'+request],values['gpu-after:'+request],first,last)
        else:
            peer=self.peer.frame(entry['peer']);initial=self.peer.frame(self.observer.entries()[0]['peer'])
            self.peer_original(initial,peer)
        public=deepcopy(measured['public']);public['sequence']=last['index']+len(self.state['records'])
        holders=[] if self.role=='actor' else held_original(native);public['resources']=[row['resource'] for row in held_public(holders)]
        public['artifacts']=[];result('feature.world-web.observe',public)
        return dict(ticket=self.state['ticket'],public=public,acquisition=deepcopy(measured['acquisition']),native=native,held=holders,
            before=deepcopy(values['before']),after=deepcopy(entry['source']),peer=None if self.role=='primary' else deepcopy(entry['peer']))

    def peer_original(self,initial,peer):
        from ios.adapters.emote_marker_measurements import body_preserved,view_preserved
        from ios.adapters import pointer_state,world_web_keys,world_web_source
        from ios.adapters.world_web_trace import current_view
        from ios.adapters.world_web_resource_disposition import disposition
        from adapters.script_ui_root_ownership import membership,validate as roots_validate
        a,b=initial['originals'],peer['originals'];body_preserved(a['world'],b['world']);view_preserved(a['world'],b['world'])
        need(same(a['world']['source']['tree']['entities'],b['world']['source']['tree']['entities'])
            and b['document'] is None and current_view(b['ledgerAfter']) is None and not world_web_source.pending(b['ledgerAfter']))
        world_web_keys.drained(b['keys']);pointer_state.drained(a['pointer'],b['pointer'],after_epoch=initial['clockJoin']['nativeAfter']['capturedEpochMs'])
        ui=b['uikit']['observation']['nativeUi'];need(ui['valid'] and not ui['keyboardVisible'] and ui['imeInsetBottom']==0 and not b['widgets']['tabletShown'])
        before=membership(a['widgets']['scriptInventory'],pid=self.peer.pid);after=membership(b['widgets']['scriptInventory'],pid=self.peer.pid)
        roots_validate(after,pid=self.peer.pid,previous=before)
        # This actor owns no marker or Script UI recipe. Its own native
        # inventories must preserve all original unowned resources.
        need(same(before['roots'],after['roots']))
        return disposition(b['closures'],a['closures'],partial=True)

    def native_frames(self,primary,peer):
        need(self.role=='actor')
        reference=self.source.state['records'][primary['index']-1]
        need(same(primary,self.source.frame(reference))
            and same(peer,self.peer.frame(self.peer.state['records'][peer['index']-1])))
        proof=setup_original(self.scope,self.source,self.baseline,reference)
        initial=self.peer.frame(self.observer.entries()[0]['peer']);self.peer_original(initial,peer)
        return proof

    def frame(self,index):
        need(integer(index,1,len(self.state['records'])))
        row=self.state['records'][index-1];measured=self.measure(row);values=self.values(row)
        return dict(before=measured['before'],after=measured['after'],files=values.get('files'))

    def entry(self,index):
        need(integer(index,1,len(self.state['records'])))
        row=self.state['records'][index-1];self.measure(row);value=self.values(row)['observation']
        return deepcopy(self.observer.entries()[value['reference']['index']-1])

    def capture(self):
        self.guard();self.recover()
        if self.state['pending'] is None:
            need(len(self.state['records'])<64);self.state['pending']=dict(index=len(self.state['records'])+1,acquisition=uuid.uuid4().hex,
                images=deepcopy(self.state['images']),parts=[],writing=None,carrier=None);self.save()
        row=self.state['pending'];values=self.values(row)
        if 'before' not in values:self.put(row,'before',self.source.capture('setup-cleanup-before'))
        if self.role=='primary':
            if 'files' not in values:self.put(row,'files',None if self.scope.state['fileOwnership'] is None else self.files.capture('absent',self.scope.state['fileOwnership']))
            for request in row['images']:
                values=self.values(row);owner=self.sample(request)
                if 'gpu-before:'+request not in values:self.put(row,'gpu-before:'+request,owner.clocks.snapshot())
                if 'gpu-owner:'+request not in values:
                    owner.retire_runtime();self.put(row,'gpu-owner:'+request,owner.frame_owner.store.read())
                if 'gpu-after:'+request not in values:self.put(row,'gpu-after:'+request,owner.clocks.snapshot())
        if 'observation' not in self.values(row):original,_measured=self.observer.capture();self.put(row,'observation',original)
        self.measure(row);self.state['records'].append(deepcopy(row));self.state['pending']=None;self.save();return row['index']

    def cleanup(self,ticket):
        self.guard();identifier(ticket)
        if self.state['ticket'] is None:self.state.update(ticket=ticket,phase='cleaning');self.save()
        need(self.state['ticket']==ticket)
        if self.role=='primary':self.scope.cleanup()
        else:need(self.scope.state['phase']=='released')
        self.recover()
        if self.state['barrier'] is None:
            self.state['barrier']=self.capture();self.save()
        proof=self.measure(self.state['records'][self.state['barrier']-1])
        if self.role=='primary' and self.state['restoration'] is None:
            request='ios-'+uuid.uuid4().hex;self.state['images'].append(request);self.save()
            image=self.sample(request);image.capture(ticket);restored(self.baseline_image,image,after_native=proof['native']['afterNativeEpochMs'])
            self.state['restoration']=request;self.save()
        self.state['phase']='quiet';self.save();started=self.source.monotonic()
        for _attempt in range(61):
            index=self.capture()
            if self.state['quiet']:
                before=self.measure(self.state['records'][self.state['quiet'][-1]-1]);after=self.measure(self.state['records'][index-1])
                if (not same(before['native']['scriptRoots'],after['native']['scriptRoots'])
                    or not same(activity(self.source.frame(before['after'])),activity(self.source.frame(after['before'])))):
                    self.state['quiet']=[]
            self.state['quiet'].append(index);self.save()
            if len(self.state['quiet'])>=3:
                try:self.qualification(self.state)
                except Exception as error:
                    from adapters.normal_ui import NativeUIError
                    if not isinstance(error,NativeUIError):raise
                else:self.state['phase']='retired';self.save();return self.original()
            need(self.source.monotonic()-started<15);self.sleep(.1)
        need(False)

    @_readonly
    def qualification(self,state):
        need(len(state['quiet'])>=3);previous=self.state;self.state=state
        try:
            rows=[self.measure(state['records'][index-1]) for index in state['quiet']]
            first,last=self.source.frame(rows[0]['after']),self.source.frame(rows[-1]['before']);quiet(first,last)
            need(same(rows[0]['native']['scriptRoots'],rows[-1]['native']['scriptRoots']))
            summary=quiet_summary(first,last)
            if self.role=='actor':
                # The Actor's native quiet metadata belongs to its own SDK.
                # Complete that real interval before the separately acquired
                # final dual-SDK original whose host bracket is published.
                need(self.peer is not None and len(rows)>=4)
                own_first=self.peer.frame(rows[0]['peer']);own_end=self.peer.frame(rows[-2]['peer'])
                quiet(first,self.source.frame(rows[-2]['after']));quiet(own_first,own_end)
                own_last=self.peer.frame(rows[-1]['peer']);quiet(own_first,own_last)
                before=self.source.frame(rows[-1]['before'])['clockJoin'];after=own_end['clockJoin']
                need(after['hostAfterEpochMs']<=before['hostBeforeEpochMs'] and after['hostAfterMonotonic']<=before['hostBeforeMonotonic'])
                summary=quiet_summary(own_first,own_end)
            else:need(self.peer is None)
            pixels=None
            if self.role=='primary':
                need(state['restoration'] is not None and integer(state['barrier'],1,state['quiet'][0]-1))
                need(all(state['records'][index-1]['images']==state['images'] for index in state['quiet']))
                barrier=self.measure(state['records'][state['barrier']-1]);image=self.sample(state['restoration'])
                pixels=restored(self.baseline_image,image,after_native=barrier['native']['afterNativeEpochMs'])
                need(image.state['after']['index']<first['index'])
            return dict(rows[-1],quiet=summary,pixels=pixels)
        finally:self.state=previous

    @_readonly
    def decode(self,value,*,with_measurement=False):
        exact(value,{'iosWorldWebSetupRetirementVersion','binding','primaryBinding','runId','role','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'phase','ticket','baseline','records','pending','barrier','quiet','restoration','images'})
        need(state['phase'] in ('new','cleaning','quiet','retired') and same(state['baseline'],self.baseline)
            and type(state['records']) is list and len(state['records'])<=64 and type(state['quiet']) is list
            and all(integer(index,1,len(state['records'])) for index in state['quiet'])
            and state['quiet']==sorted(set(state['quiet'])) and type(state['images']) is list and len(state['images'])<=64
            and len(set(state['images']))==len(state['images']) and state['images'][:len(self.required_images)]==self.required_images)
        for request in state['images']:
            need(type(request) is str and request.startswith('ios-'));identifier(request[4:])
        if self.role=='actor':need(state['images']==[] and state['restoration'] is None)
        if state['ticket'] is not None:identifier(state['ticket'])
        if state['phase']=='new':need(state['ticket'] is state['pending'] is state['barrier'] is state['restoration'] is None and not state['records'] and not state['quiet'])
        else:need(state['ticket'] is not None)
        need(state['barrier'] is None or integer(state['barrier'],1,len(state['records'])))
        if state['restoration'] is not None:
            need(self.role=='primary' and state['barrier'] is not None and state['restoration'] in state['images'])
        if state['phase'] in ('quiet','retired'):need(state['barrier'] is not None)
        previous=self.state;self.state=state;measured=None
        try:
            prior_images=deepcopy(self.required_images);prior=None
            for index,row in enumerate(state['records'],1):
                exact(row,{'index','acquisition','images','parts','writing','carrier'});need(row['index']==index and row['writing'] is row['carrier'] is None)
                identifier(row['acquisition']);need(type(row['images']) is list and row['images'][:len(prior_images)]==prior_images
                    and state['images'][:len(row['images'])]==row['images']);prior_images=deepcopy(row['images'])
                measured=self.measure(row)
                if prior is not None:
                    need(prior['after']['index']<measured['before']['index'])
                    if self.peer is not None:
                        need(self.peer.frame(prior['peer'])['clockJoin']['hostAfterMonotonic']
                            <=self.source.frame(measured['before'])['clockJoin']['hostBeforeMonotonic'])
                prior=measured
            if state['pending'] is not None:
                row=state['pending'];exact(row,{'index','acquisition','images','parts','writing','carrier'});need(row['index']==len(state['records'])+1)
                identifier(row['acquisition']);need(row['images']==state['images']);self.values(row)
                need(row['writing'] is None and row['carrier'] is None or type(row['writing']) is str)
                if row['carrier'] is not None:
                    self.parts(row).original(row['carrier']);need(row['carrier']['index']==len(row['parts'])+1)
            if state['phase']=='retired':measured=self.qualification(state)
        finally:self.state=previous
        return (deepcopy(state),deepcopy(measured)) if with_measurement else deepcopy(state)

    @contextmanager
    def original_round(self):yield

    @contextmanager
    def publication_round(self,publisher):
        from ios.adapters.world_web_publication_round import WorldWebPublicationRound
        with WorldWebPublicationRound(self,publisher).held():yield

    def original(self):
        self.guard();state=self.decode(self.previous);need(state['phase']=='retired')
        return dict(iosWorldWebSetupRetirementOriginalVersion=1,owner=deepcopy(self.previous))

    @_readonly
    def validate_original(self,value):return self.qualified_original(value)[2]

    @_readonly
    def qualified_original(self,value):
        # Share only this exact readonly traversal's already checked result.
        # No verdict survives the current original/file/inode guarded round.
        value=deepcopy(value)
        exact(value,{'iosWorldWebSetupRetirementOriginalVersion','owner'});need(type(value['iosWorldWebSetupRetirementOriginalVersion']) is int and value['iosWorldWebSetupRetirementOriginalVersion']==1)
        state,measured=self.decode(value['owner'],with_measurement=True);need(state['phase']=='retired' and measured is not None);sha=digest(value)
        verdict=dict(ticket=measured['ticket'],scene=scene(measured['public']),acquisition=deepcopy(measured['acquisition']),retirement=dict(originalSha256=sha,quiet=deepcopy(measured['quiet']),
            provenance=dict(version=1,namespace='ios-world-web-setup-retirement',reference=dict(index=state['records'][-1]['index'],sha256=sha),originalSha256=sha)))
        return state,measured,verdict
