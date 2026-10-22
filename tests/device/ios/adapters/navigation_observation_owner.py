"""One durable whole-state acquisition, with original image ownership retained.

This read-only owner cannot send normal input, publish an actor observation or
retire a run. Reconstruction resolves an old return without repeating a read.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextvars import ContextVar
import time

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,need,number,validate as native_packet
from adapters.native_navigation_replies import NativeNavigationReplies
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.navigation_fixture import configuration,validate_status
from feature_journeys.navigation_scene import validate_status as scene_status
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters import navigation_product_state as product
from ios.adapters import location_bookmarks,places_model,places_http,navigation_dialogs
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_fixture import NavigationFixtureReader,NavigationPhasePending
from ios.adapters.navigation_sample import NavigationMarkerPending
from ios.adapters.navigation_samples import NavigationSamples
from ios.adapters.navigation_state import IOSNavigationState
from ios.adapters.normal_input import NativeInput
from ios.adapters import navigation_source_prefix as source_prefix

VERSION=1
_ARCHIVE_ROUND=ContextVar('ios_navigation_original_archive_round',default=None)
SOURCES=dict(bookmarks=location_bookmarks.IOSLocationBookmarks,model=places_model.IOSPlacesModel,
    http=places_http.IOSPlacesHttp,dialogs=navigation_dialogs.IOSNavigationDialogs,replies=NativeNavigationReplies,ui=NativeInput)


def fixture_original(value,run,inputs,instance):
    """Recheck retained input originals; these never supply product facts."""
    exact(value,{'navigationFixtureReaderVersion','runId','ticket','verb','inputs','providerReadEpochMs',
        'hostBeforeMonotonic','hostAfterMonotonic','originals','originalsSha256'})
    need(type(value['navigationFixtureReaderVersion']) is int and value['navigationFixtureReaderVersion']==1
         and value['runId']==run and value['originalsSha256']==digest(value['originals']))
    rows=value['originals'];exact(rows,{'phaseBefore','navigation','scene','phaseAfter'})
    first,last=rows['phaseBefore'],rows['phaseAfter']
    for packet in (first,last):
        phase_packet(packet,run=run,area='world-navigation',request=packet['requestId'],epoch=packet['capturedEpochMs'])
    phase_packet(last,run=run,area='world-navigation',request=last['requestId'],epoch=last['capturedEpochMs'],previous=first)
    validate_status(rows['navigation'],instance=instance,run=run,inputs=inputs)
    scene_status(rows['scene'],instance=instance,run=run,scene_url=inputs['sceneUrl'])
    need(first['active'] and last['active'] and first['activations'] and same(first['activations'],last['activations'])
         and all(rows[name]['active'] and rows[name]['ticket']==value['ticket'] for name in ('navigation','scene')))
    current=last['activations'][-1]
    need(current['ticket']==value['ticket'] and same(current['stimulus'],dict(verb=value['verb'],inputs=value['inputs']))
         and value['providerReadEpochMs']==last['capturedEpochMs']
         and first['capturedEpochMs']-1<=rows['navigation']['capturedEpochMs']<=rows['scene']['capturedEpochMs']<=last['capturedEpochMs']+1
         and number(value['hostBeforeMonotonic'],0,1e15)
         and number(value['hostAfterMonotonic'],value['hostBeforeMonotonic'],value['hostBeforeMonotonic']+1.5)
         and value['hostAfterMonotonic']-value['hostBeforeMonotonic']<1.5)
    return value


class NavigationObservationOwner:
    def __init__(self,store,images,binding,run,role,stage,request,lock,guard,*,native=None,navigation=None,
                 sources=None,fixture=None,previous=None,historical=False,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(images,NavigationSamples) and isinstance(lock,ScriptSourceLock)
             and role in ('primary','actor') and type(stage) is int and stage in (0,1) and type(historical) is bool
             and callable(guard) and callable(epoch_ms) and callable(monotonic))
        identifier(run);identifier(request);context(binding)
        self.store,self.images,self.binding,self.run,self.role,self.stage,self.request=store,images,deepcopy(binding),run,role,stage,request
        self.lock,self.guard,self.historical=lock,(lambda:True) if historical else guard,historical
        self.native,self.navigation,self.sources,self.fixture=native,navigation,sources,fixture
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.previous_owner=previous
        need(store.path.name=='ios-navigation-'+role+'-'+str(stage)+'-'+request+'-observation.json'
             and store.path.parent==images.store.path.parent and lock.path==images.lock.path
             and same(binding,images.binding) and (run,role,stage)==(images.run,images.role,images.stage))
        self.pid=int(binding['processIdentity']);need(self.pid>0 and str(self.pid)==binding['processIdentity'])
        if historical:need(native is navigation is sources is fixture is None)
        else:
            need(isinstance(native,NativeFeatureObservation) and native.ios and native.pid==self.pid
                 and isinstance(navigation,IOSNavigationState) and navigation.pid==self.pid
                 and isinstance(fixture,NavigationFixtureReader) and fixture.run==run and fixture.instance is not None)
            exact(sources,SOURCES)
            for name,kind in SOURCES.items():
                need(isinstance(sources[name],kind))
                if name!='ui':need(sources[name].pid==self.pid)
            need(sources['replies'].ios)
        if previous is not None:
            need(isinstance(previous,NavigationObservationOwner) and previous.store.path!=store.path
                 and previous.store.path.parent==store.path.parent and same(previous.binding,binding)
                 and (previous.run,previous.role,previous.stage)==(run,role,stage))
            previous.archive()
        lock.assert_held();self.previous=store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosNavigationObservationOwnerVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
                    stage=self.stage,requestId=self.request,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationObservationOwnerVersion','binding','runId','role','stage','requestId','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationObservationOwnerVersion']) is int
            and value['iosNavigationObservationOwnerVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','ticket','url','label','hostBarrier','options','indexBefore','previous',
            'phaseBefore','phaseAfter','nativeStart','nativeEnd','imageRow','imageArchive','originals','clockJoin','result'})
        identifier(state['ticket']);need(state['phase'] in ('reading','observed','marker-pending','failed')
            and type(state['originals']) is dict and set(state['originals'])<=product.ORIGINALS
            and type(state['indexBefore']) is list and len(state['indexBefore'])<=512)
        if self.previous_owner is None:need(state['previous'] is None)
        else:need(same(state['previous'],dict(file=self.previous_owner.store.path.name,sha256=digest(self.previous_owner.store.read()))))
        return state

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))
        if self.previous_owner is not None and self.state is not None:
            need(digest(self.previous_owner.store.read())==self.state['previous']['sha256'])

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def remember(self,key,value):
        need(self.state['phase']=='reading' and self.state[key] is None);self.state[key]=deepcopy(value);self.save()

    def source(self,name,packet):
        need(self.state['phase']=='reading' and name not in self.state['originals'])
        self.state['originals'][name]=deepcopy(packet);self.save()

    def image(self):
        row,archive=self.state['imageRow'],self.state['imageArchive'];need(row is not None and archive is not None)
        need(same(self.images.original(row)[1],archive))
        values=unpack(archive['payload']);need(len(values)==1 and same(archive,self.images.archive_envelope(row,values[0]))
            and digest(archive)==row['archiveSha256'])
        child=self.images.frozen_child(row,values[0]);sample,result=child.archive()
        need(row['ticket']==self.state['ticket'] and row['status']==child.state['phase']
             and row['frameId']==sample['frame']['capture']['source']['renderTrace']['frameId'])
        return sample,result

    def validate(self):
        state=self.state;need(state is not None);sample,_=self.image()
        options=state['options'];exact(options,{'baseline','provider_inputs','fixture_url','provider_instance','directory','missing'})
        inputs,_urls=configuration(options['provider_inputs']);instance=options['provider_instance']
        first=fixture_original(state['phaseBefore'],self.run,inputs,instance)
        last=fixture_original(state['phaseAfter'],self.run,inputs,instance)
        phase_packet(last['originals']['phaseBefore'],run=self.run,area='world-navigation',
            request=last['originals']['phaseBefore']['requestId'],epoch=last['originals']['phaseBefore']['capturedEpochMs'],
            previous=first['originals']['phaseAfter'])
        need(first['ticket']==last['ticket']==state['ticket'] and same(first['originals']['phaseAfter']['activations'],
            last['originals']['phaseAfter']['activations']))
        originals=state['originals'];exact(originals,product.ORIGINALS);clock=validate_join(state['clockJoin'],originals)
        need(same(state['nativeStart'],{name:clock[name] for name in ('clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore')})
             and same(state['nativeEnd'],{name:clock[name] for name in ('nativeAfter','hostAfterEpochMs','hostAfterMonotonic')})
             and clock['hostBeforeEpochMs']>=state['hostBarrier'] and sample['url']==state['url'] and sample['label']==state['label'])
        self.continue_previous()
        # Marker-pending originals are retained, never converted into public
        # success. Every accepted source remains owned for the next validator.
        try:return product.compose(self.run,self.binding,originals,clock,sample,**options)
        except MarkerNotReady:return None

    def continue_previous(self):
        """A partial predecessor cannot erase earlier accepted source floors."""
        previous=self.previous_owner;first=self.state['nativeStart']
        while previous is not None:
            previous.archive();old=previous.state;sample,_result=previous.image()
            floor=sample['frame']['clockJoin']['nativeAfter']
            host_floor=sample['frame']['clockJoin']['hostAfterMonotonic']
            if old['nativeEnd'] is not None:
                floor=old['nativeEnd']['nativeAfter'];host_floor=old['nativeEnd']['hostAfterMonotonic']
            follow_native(floor,first['nativeBefore'])
            need(host_floor<=first['hostBeforeMonotonic'])
            for row in old['originals'].values():
                epoch=row['clockAfter']['epochMs'] if 'clockAfter' in row else row.get('capturedEpochMs',row.get('sampleEpochMs'))
                need(epoch<=first['nativeBefore']['capturedEpochMs'])
            source_prefix.follow(old['originals'],self.state['originals'],self.run,self.pid)
            # A complete predecessor already carries every channel's floor.
            if old['phase'] in ('observed','marker-pending'):break
            previous=previous.previous_owner

    def interrupted(self):
        """Check a retained partial source group, without a fresh/public result.

        An incomplete GPU attempt remains the image owner's responsibility.
        This path only admits an already sealed image and its accepted field
        prefix. Overlong original windows remain overlong and historical.
        """
        state=self.state;need(state is not None and state['phase'] in ('reading','failed') and state['result'] is None)
        sample,_result=self.image();originals=state['originals']
        need(product.IMAGE<=set(originals)
            and same({name:originals[name] for name in product.IMAGE},
                     {name:sample['frame'][name] for name in product.IMAGE}))
        fields=[name for name in source_prefix.ORDER if name in originals]
        need(fields==list(source_prefix.ORDER[:len(fields)]))
        source_prefix.validate(originals,self.run,self.pid)
        options=state['options'];exact(options,{'baseline','provider_inputs','fixture_url','provider_instance','directory','missing'})
        inputs,_urls=configuration(options['provider_inputs'])
        phase=fixture_original(state['phaseBefore'],self.run,inputs,options['provider_instance'])
        need(phase['ticket']==sample['ticket']==state['ticket'] and sample['url']==state['url'] and sample['label']==state['label']
            and sample['providerInstance']==options['provider_instance'] and sample['fixtureUrl']==options['fixture_url'])
        first=state['nativeStart'];exact(first,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
        need(type(first['clockJoinVersion']) is int and first['clockJoinVersion']==1
            and number(first['hostBeforeEpochMs'],state['hostBarrier'],1e15) and number(first['hostBeforeMonotonic'],0,1e15))
        packet=first['nativeBefore'];native_packet(packet,packet['requestId'],self.pid,packet['capturedEpochMs'])
        inner=sample['frame']['clockJoin'];follow_native(packet,inner['nativeBefore'])
        need(first['hostBeforeEpochMs']<=inner['hostBeforeEpochMs'] and first['hostBeforeMonotonic']<=inner['hostBeforeMonotonic'])
        floor=inner['nativeAfter']['capturedEpochMs']
        for name in fields:
            row=originals[name]
            if 'clockBefore' in row:begin,end=row['clockBefore']['epochMs'],row['clockAfter']['epochMs']
            else:begin=end=row.get('capturedEpochMs',row.get('sampleEpochMs'))
            need(number(begin,floor,1e15) and number(end,begin,1e15));floor=end
        ending=state['nativeEnd']
        if ending is not None:
            exact(ending,{'nativeAfter','hostAfterEpochMs','hostAfterMonotonic'})
            follow_native(inner['nativeAfter'],ending['nativeAfter'])
            need(ending['nativeAfter']['capturedEpochMs']>=floor
                and number(ending['hostAfterEpochMs'],inner['hostAfterEpochMs'],1e15)
                and number(ending['hostAfterMonotonic'],inner['hostAfterMonotonic'],1e15))
        if state['clockJoin'] is not None:
            need(ending is not None)
            times=[dict(source=name,field=field,epochMs=row[field]) for name,row in originals.items()
                for field in ('capturedEpochMs','sampleEpochMs') if field in row]
            clock=state['clockJoin'];exact(clock,set(first)|set(ending)|{'sourceTimes','originalsSha256'})
            need(same({key:item for key,item in clock.items() if key!='sourceTimes'},
                      dict(first,**ending,originalsSha256=digest(originals))) and type(clock['sourceTimes']) is list)
            need(same(sorted(clock['sourceTimes'],key=lambda row:(row['source'],row['field'])),
                      sorted(times,key=lambda row:(row['source'],row['field']))))
        if state['phaseAfter'] is not None:
            later=fixture_original(state['phaseAfter'],self.run,inputs,options['provider_instance'])
            phase_packet(later['originals']['phaseBefore'],run=self.run,area='world-navigation',
                request=later['originals']['phaseBefore']['requestId'],epoch=later['originals']['phaseBefore']['capturedEpochMs'],
                previous=phase['originals']['phaseAfter'])
        self.continue_previous();return None

    def abandon_sources(self):
        """Explicit local retirement of a failed read, preserving all originals.

        This performs no source read, capture, input, GPU release or deletion.
        A later observation has a new identity and must extend every prefix.
        """
        need(not self.historical);self.bound()
        need(self.state is not None and self.state['phase']=='reading');self.interrupted()
        self.state['phase']='failed';self.save();return None

    def acquire(self,ticket,url,label,host_barrier,*,baseline,provider_inputs,directory=None,missing=None):
        need(not self.historical);self.bound();need(self.state is None);identifier(ticket);self.images.bound()
        if self.previous_owner is None:need(not self.images.state['rows'])
        else:
            self.previous_owner.archive();need(self.images.state['rows'] and self.images.state['rows'][-1]['requestId']==
                self.previous_owner.state['imageRow']['requestId'])
        options=dict(baseline=baseline,provider_inputs=provider_inputs,fixture_url=self.fixture.fixture_url,
            provider_instance=self.fixture.instance,directory=directory,missing=missing)
        need(same(provider_inputs,self.fixture.inputs))
        self.state=dict(phase='reading',ticket=ticket,url=url,label=label,hostBarrier=host_barrier,options=deepcopy(options),
            indexBefore=[row['requestId'] for row in self.images.state['rows']],
            previous=None if self.previous_owner is None else dict(file=self.previous_owner.store.path.name,sha256=digest(self.previous_owner.store.read())),
            phaseBefore=None,phaseAfter=None,nativeStart=None,nativeEnd=None,imageRow=None,imageArchive=None,originals={},clockJoin=None,result=None)
        self.save();phase=self.fixture.read();self.remember('phaseBefore',phase)
        if phase['ticket']!=ticket:raise NavigationPhasePending('Original navigation phase does not match this acquisition')
        window=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic)
        window.begin(host_barrier);self.remember('nativeStart',window.started)
        try:self.images.read(ticket,url,label,host_barrier)
        except NavigationMarkerPending:pass
        rows=self.images.state['rows'];need(len(rows)==len(self.state['indexBefore'])+1
            and [row['requestId'] for row in rows[:-1]]==self.state['indexBefore'])
        row=rows[-1];need(row['status'] in ('observed','marker-pending'));self.remember('imageRow',row)
        self.remember('imageArchive',self.images.archive_store(row).read());sample,_=self.image()
        for name in product.IMAGE:self.source(name,sample['frame'][name])
        for name in ('bookmarks','model','http','dialogs','replies','ui'):
            reader=self.sources[name];packet=reader.capture() if name=='ui' else reader.read(self.run);self.source(name,packet)
        self.source('currentNavigation',self.navigation.read(self.run))
        originals=self.state['originals'];fields=[(name,field) for name,packet in originals.items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in packet]
        ending=dict(nativeAfter=self.native.read(self.native.sequence),hostAfterEpochMs=self.epoch_ms(),hostAfterMonotonic=self.monotonic())
        self.remember('nativeEnd',ending)
        clock=dict(window.started,**ending,sourceTimes=[dict(source=name,field=field,epochMs=originals[name][field]) for name,field in fields],
                   originalsSha256=digest(originals))
        self.remember('clockJoin',clock);validate_join(clock,originals)
        self.remember('phaseAfter',self.fixture.read())
        result=self.validate();self.state.update(phase='marker-pending' if result is None else 'observed',result=result);self.save()
        clock=self.state['clockJoin'];ended,epoch=self.monotonic(),self.epoch_ms()
        need(number(ended,clock['hostBeforeMonotonic'],clock['hostBeforeMonotonic']+1.5) and ended-clock['hostBeforeMonotonic']<1.5
             and number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
             and abs(epoch-clock['hostBeforeEpochMs']-(ended-clock['hostBeforeMonotonic'])*1000)<=250)
        self.bound()
        if result is None:raise NavigationMarkerPending('Whole original observation retains a pending navigation marker')
        return deepcopy(result)

    def archive(self):
        # A whole source chain checks its predecessor both before and during
        # composition. Share repeated historical validation only within this
        # synchronous round; otherwise a long journey grows exponentially.
        # Every participating carrier/state/PNG is rechecked before returning.
        cache=_ARCHIVE_ROUND.get()
        if cache is None:
            token=_ARCHIVE_ROUND.set({})
            try:
                result=self.archive()
                for owner,carrier,_result in _ARCHIVE_ROUND.get().values():
                    owner.bound();need(same(owner.previous,carrier) and same(owner.envelope(owner.state),carrier))
                    owner.image()
                return result
            finally:_ARCHIVE_ROUND.reset(token)
        self.bound();need(self.state is not None and self.state['phase'] in ('observed','marker-pending','failed'))
        need(same(self.envelope(self.state),self.previous));key=(str(self.store.path),digest(self.previous))
        if key in cache:return deepcopy(cache[key][2])
        if self.state['phase']=='failed':result=self.interrupted()
        else:
            result=self.validate();need(same(result,self.state['result']) and (result is None)==(self.state['phase']=='marker-pending'))
        self.bound();cache[key]=(self,deepcopy(self.previous),deepcopy(result));return deepcopy(result)

    def recover(self,*,directory=None):
        """Resolve retained originals; never perform source reads or input.

        First-open directory ownership may be joined after the complete raw
        group was retained. Its proof must use these exact HTTP/model/provider
        originals; it cannot import another sample or supply requested state.
        The enclosing normal-input owner remains responsible for its original
        admission barriers. This method yields no fresh measurement.
        """
        need(not self.historical);self.bound();need(self.state is not None and self.state['phase']=='reading')
        old=deepcopy(self.state['options']['directory'])
        if directory is not None:
            from ios.adapters.navigation_places_state import validate_directory_proof
            validate_directory_proof(directory,self.binding,self.run)
            originals=self.state['originals'];phase=self.state['phaseAfter']
            need(phase is not None and directory['admission']['ticket']==self.state['ticket']
                and same(directory['admission']['inputs'],self.state['options']['provider_inputs'])
                and same(directory['originals'],dict(http=originals['http'],model=originals['model'],
                    provider=phase['originals']['navigation'])) and (old is None or same(old,directory)))
            self.state['options']['directory']=deepcopy(directory)
        try:result=self.validate()
        except BaseException:
            self.state['options']['directory']=old;raise
        self.state.update(phase='marker-pending' if result is None else 'observed',result=result);self.save()

