"""Current-process restored Worlds images, input quiet and retained Qt roots.

This owner preserves the original live state before terminal process retirement.
It cannot claim root destruction, stop an app or retire another role's SDK.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import result as public_result
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.adapters.navigation_feature import IOSNavigationFeature,NavigationFeaturePending
from ios.adapters.navigation_quiet_image import NavigationQuietImage
from ios.adapters.navigation_quiet_period import compose as quiet_period
from ios.adapters.navigation_static_comparison import compare
from ios.adapters.navigation_admission_owner import SOURCES
from ios.adapters import navigation_product_state as product,navigation_places_state as places,navigation_error_state as errors

VERSION=1


class NavigationRestoration:
    def __init__(self,flow,baseline):
        need(type(flow) is IOSNavigationFeature and type(baseline) is NavigationBaselineImage
            and baseline.lock is flow.lock and baseline.root==flow.root and baseline.run==flow.run and baseline.role==flow.role)
        self.flow,self.baseline=flow,baseline;self.lock=flow.lock
        self.store=PrivateFeatureState(flow.store.path.with_name('ios-navigation-restoration-'+flow.role+'.json'))
        self.previous=self.state=None;self.historical=False

    def scope(self):
        f=self.flow;self.lock.assert_held();f.load();need(f.state is not None and f.state['stage']==1)
        phase=f.fixture.read();need(phase['verb']=='cleanup' and phase['inputs']=={})
        source=f.current();admission=f.initial_owner();transfer=f.transferred_owner();self.baseline.archive()
        need(same(admission.binding,self.baseline.binding))
        observer=f.observer();owners=observer.owners();need(owners and observer.state['rows'][-1]['status']=='observed')
        prior=owners[-1];prior.archive();current=f.admission();directory=f.directory(observer,current)
        self.binding=deepcopy(source['binding']);self.admission,self.transfer,self.observer,self.prior=admission,transfer,observer,prior
        self.process_context=transfer.archive();self.owner_files=transfer.owner_files;self.directory=directory
        self.context=dict(binding=self.binding,cleanupTicket=phase['ticket'],baselineSha256=digest(self.baseline.previous),
            admissionSha256=digest(admission.previous),transferSha256=digest(transfer.previous),
            previousOwnerSha256=digest(prior.previous),directorySha256=digest(directory))

    def phase_store(self):
        return PrivateFeatureState(self.store.path.with_name('ios-navigation-restoration-phase-'+self.flow.role+'-'+self.context['cleanupTicket']+'.json'))

    def phase_original(self):
        from ios.adapters.navigation_observation_owner import fixture_original
        value=self.phase_store().read();exact(value,{'iosNavigationRestorationPhaseVersion','binding','runId','role','original'})
        need(type(value['iosNavigationRestorationPhaseVersion']) is int and value['iosNavigationRestorationPhaseVersion']==1
            and same(value['binding'],self.binding) and value['runId']==self.flow.run and value['role']==self.flow.role)
        initial=self.admission.archive();phase=value['original']
        fixture_original(phase,self.flow.run,initial['providerInputs'],initial['providerInstance'])
        need(phase['verb']=='cleanup' and phase['inputs']=={} and phase['ticket']==self.context['cleanupTicket'])
        return deepcopy(phase)

    @classmethod
    def from_history(cls,flow,*,baseline=None):
        """Reopen actual source graphs without SDK/native/fixture requests."""
        from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
        from ios.adapters.navigation_restart import NavigationRestart
        from ios.adapters.navigation_before_restart import NavigationBeforeRestart
        from ios.adapters.navigation_process_owner import NavigationProcessOwner
        from ios.adapters.navigation_samples import NavigationSamples
        from ios.adapters.navigation_observer import NavigationObserver
        from ios.adapters.navigation_restart_proof import OWNERS
        flow.lock.assert_held();flow.load();need(flow.state is not None and flow.state['stage']==1)
        if baseline is None:
            preparation=NavigationWholePreparation(flow);preparation.load();images,initial=preparation.originals()
            baseline=images[flow.role]
        else:
            need(type(baseline) is NavigationBaselineImage and baseline.historical and baseline.lock is flow.lock
                and baseline.root==flow.root and baseline.run==flow.run and baseline.role==flow.role)
            initial=flow.initial_owner()
        actual=initial.archive();need(same(flow.state['initialBinding'],actual['binding'])
            and flow.state['providerInstance']==actual['providerInstance'] and same(flow.state['providerInputs'],actual['providerInputs'])
            and flow.state['admissionSha256']==digest(initial.previous))
        # These are validated authority metadata, not new provider observations.
        flow.fixture.instance=actual['providerInstance'];flow.fixture.inputs=deepcopy(actual['providerInputs'])
        previous=flow.prior_observers()
        restart=NavigationRestart(flow.runtime,flow.selector,actual,{role:owner.images for role,owner in previous.items()},flow.lock,flow.fixture)
        need(restart.state is not None and restart.state['status']=='observed')
        before=NavigationBeforeRestart.archive(restart.state['before'],actual)
        transfer=NavigationProcessOwner(PrivateFeatureState(flow.store.path.with_name('ios-navigation-process-context.json')),
            actual,before,restart.state['receipt'],[str(flow.store.path.with_name(name)) for name in OWNERS],flow.lock,lambda:True,historical=True)
        process=transfer.archive();need(digest(transfer.previous)==flow.state['transferSha256'] and same(transfer.binding,flow.state['binding']))
        samples=NavigationSamples(PrivateFeatureState(flow.store.path.with_name('ios-navigation-'+flow.role+'-1-samples.json')),
            flow.root,flow.state['binding'],flow.run,flow.role,1,flow.lock,lambda:True,historical=True)
        observer=NavigationObserver(PrivateFeatureState(flow.store.path.with_name('ios-navigation-'+flow.role+'-1-observer.json')),samples,historical=True)
        owners=observer.owners();need(owners and observer.state['rows'][-1]['status']=='observed');prior=owners[-1]
        directories=[owner.state['options']['directory'] for owner in owners if owner.state['options']['directory'] is not None]
        need(directories and all(same(row,directories[0]) for row in directories));directory=directories[0]
        result=cls(flow,baseline);result.historical=True
        result.binding=deepcopy(flow.state['binding']);result.admission,result.transfer,result.observer,result.prior=initial,transfer,observer,prior
        result.process_context=process;result.owner_files=transfer.owner_files;result.directory=deepcopy(directory)
        result.previous=result.store.read();need(result.previous is not None)
        context=result.previous['context'];result.context=dict(binding=result.binding,cleanupTicket=context['cleanupTicket'],
            baselineSha256=digest(result.baseline.previous),admissionSha256=digest(initial.previous),transferSha256=digest(transfer.previous),
            previousOwnerSha256=digest(prior.previous),directorySha256=digest(directory))
        result.state=result.decode(result.previous);result.phase_original();result.bound();return result

    def envelope(self,state):
        return dict(iosNavigationRestorationVersion=VERSION,runId=self.flow.run,role=self.flow.role,
            artifactRoot=str(self.flow.root),context=deepcopy(self.context),payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosNavigationRestorationVersion','runId','role','artifactRoot','context','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosNavigationRestorationVersion']) is int
            and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'rows','pending'});need(type(state['rows']) is list and len(state['rows'])<=32)
        requests=set()
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','requestId','ownerSha256','comparisonSha256'});self.request(row['requestId'])
            need(type(row['index']) is int and row['index']==index and row['requestId'] not in requests
                and all(type(row[k]) is str and len(row[k])==64 for k in ('ownerSha256','comparisonSha256')))
            requests.add(row['requestId'])
        if state['pending'] is not None:
            row=state['pending'];exact(row,{'index','requestId'});self.request(row['requestId'])
            need(type(row['index']) is int and row['index']==len(state['rows'])+1 and row['requestId'] not in requests)
        return deepcopy(state)

    @staticmethod
    def request(value):
        from feature_journeys.contract import identifier
        need(type(value) is str and value.startswith('ios-'));identifier(value[4:])

    def load(self):
        need(not self.historical);self.scope();self.previous=self.store.read()
        self.state=dict(rows=[],pending=None) if self.previous is None else self.decode(self.previous)
        store=self.phase_store()
        if store.read() is None:
            phase=self.flow.fixture.read();need(phase['verb']=='cleanup' and phase['ticket']==self.context['cleanupTicket'] and phase['inputs']=={})
            store.write(dict(iosNavigationRestorationPhaseVersion=1,binding=self.binding,runId=self.flow.run,role=self.flow.role,original=phase),None)
        self.phase_original()

    def bound(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        if self.historical:need(same(self.flow.store.read(),self.flow.previous)
            and same(self.flow.envelope(self.flow.state),self.flow.previous))
        else:
            self.flow.clock();phase=self.flow.fixture.read();need(phase['verb']=='cleanup' and phase['inputs']=={}
                and phase['ticket']==self.context['cleanupTicket'])
            self.flow.current()
        need(same(self.prior.store.read(),self.prior.previous)
            and same(self.baseline.store.read(),self.baseline.previous)
            and same(self.admission.store.read(),self.admission.previous) and same(self.transfer.store.read(),self.transfer.previous))

    def save(self):
        need(not self.historical);self.bound();value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def image(self,request,*,historical):
        f=self.flow;self.request(request)
        path=self.store.path.with_name('ios-navigation-quiet-'+f.role+'-'+request[4:]+'.json')
        if historical:
            return NavigationQuietImage(PrivateFeatureState(path),f.root,self.binding,f.run,f.role,request,self.lock,lambda:True,
                historical=True,process_context=self.process_context,owner_files=self.owner_files,directory=self.directory,previous=self.prior,
                epoch_ms=f.epoch_ms,monotonic=f.monotonic)
        owner=f.runtime._navigation_restored_image(f.selector,f.client,f.run,f.role,request,f.root,self.lock,
            process_context=self.process_context,owner_files=self.owner_files,directory_proof=self.directory,previous=self.prior,quiet=True)
        need(type(owner) is NavigationQuietImage and owner.store.path==path and owner.lock is self.lock
            and same(owner.binding,self.binding) and owner.role==f.role and owner.run==f.run)
        return owner

    def adopt(self,owner):
        owner.archive();comparison=compare(self.baseline,owner,self.admission,self.transfer)
        row=self.state['pending'];need(row is not None and row['requestId']==owner.request)
        self.state['rows'].append(dict(**row,ownerSha256=digest(owner.store.read()),comparisonSha256=digest(comparison)))
        self.state['pending']=None;self.save()

    def advance(self):
        """One new original image or one retained lost return; never a resend."""
        f=self.flow;need(not self.historical)
        with f.held():
            self.load();need(len(self.state['rows'])<32)
            if self.state['pending'] is not None:
                owner=self.image(self.state['pending']['requestId'],historical=False)
                if owner.state is None:raise NavigationFeaturePending('Restored Worlds image delivery remains unresolved')
                if owner.state['phase']=='reading':owner.recover()
            else:
                request='ios-'+uuid.uuid4().hex;owner=self.image(request,historical=False)
                need(owner.state is None);self.state['pending']=dict(index=len(self.state['rows'])+1,requestId=request);self.save()
                owner.acquire(f.epoch_ms())
            self.adopt(owner);self.bound();owner.fresh();return self.public(owner)

    def images(self):
        self.bound();need(self.state['pending'] is None and self.state['rows']);result=[]
        for row in self.state['rows']:
            owner=self.image(row['requestId'],historical=True);owner.archive()
            need(digest(owner.previous)==row['ownerSha256']
                and digest(compare(self.baseline,owner,self.admission,self.transfer))==row['comparisonSha256'])
            result.append(owner)
        return result

    @staticmethod
    def resources(owner):
        _result,proof,_raw=owner.archive();values=[]
        for root in proof['placesRoots']['roots']:
            need(root['status']=='retained' and root['drained'] is False)
            values.append('panel:navigation-places-'+digest(dict(rootId=root['rootId'],qmlSource=root['qmlSource']))[:20])
        root=proof['addressRoot']['root']
        need(root['status'] in ('retained','absent'))
        if not root['drained']:
            actual=root['original']['navigationInventory']['roots'];need(len(actual)==1)
            values.append('panel:navigation-address-'+digest({key:actual[0][key] for key in ('rootId','qmlSource')})[:20])
        need(values and len(values)==len(set(values)));return sorted(values)

    def derived(self,owner,index):
        """Actual validated static sources, with all retained roots explicit."""
        f=self.flow;measured,proof,_raw=owner.archive();parts=owner.originals();native=parts['nativeEnd']['nativeAfter']
        # Static-state qualification independently read scene/pose, the actual
        # bookmark file, all model/HTTP/reply/dialog/UI sources and input quiet.
        # The initial static viewpoint's actual pose has the public A label.
        originals={key:parts[key] for key in SOURCES};clock=owner.join(parts,originals)
        subset,view=product.validation_view(clock,originals,places.ORIGINALS)
        place=places.compose(f.run,self.binding,subset,view,baseline=self.process_context['initialAdmission']['bookmarkBaseline'],
            provider_inputs=self.process_context['initialAdmission']['providerInputs'],directory=self.directory)
        subset,view=product.validation_view(clock,originals,errors.ORIGINALS)
        error=errors.compose(f.run,self.binding,subset,view)
        fields=dict(place['fields'],location=measured['rendered']['location'],error=error['fields']['error'])
        need(fields['addressDialog']==error['fields']['addressDialog'])
        need(type(index) is int and 1<=index<=len(self.state['rows']))
        sequence=f.state['observerOffsets'][f.role]+self.observer.state['sequence']+index
        value=dict(schemaVersion=1,contractVersion=16,runId=f.run,sequence=sequence,capturedEpochMs=native['capturedEpochMs'],
            state=fields,artifacts=[],resources=self.resources(owner),lifecycle=deepcopy(native['lifecycle']))
        return public_result('feature.world-navigation.observe',value)

    def public(self,owner):
        value=self.derived(owner,len(self.state['rows']));self.bound();owner.fresh();return value

    def reference(self):
        self.bound();need(self.state['pending'] is None and self.state['rows'])
        return dict(iosNavigationRestorationReferenceVersion=VERSION,**deepcopy(self.state['rows'][-1]))

    def validate_original(self,reference):
        """Immutable publication decoding without a live source or freshness claim."""
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        state=self.decode(self.previous);exact(reference,{'iosNavigationRestorationReferenceVersion','index','requestId','ownerSha256','comparisonSha256'})
        need(type(reference['iosNavigationRestorationReferenceVersion']) is int
            and reference['iosNavigationRestorationReferenceVersion']==VERSION
            and type(reference['index']) is int and 1<=reference['index']<=len(state['rows']))
        row=state['rows'][reference['index']-1]
        need(same({key:reference[key] for key in row},row))
        owner=self.image(row['requestId'],historical=True);owner.archive()
        need(digest(owner.previous)==row['ownerSha256']
            and digest(compare(self.baseline,owner,self.admission,self.transfer))==row['comparisonSha256'])
        parts=owner.originals();clock=owner.join(parts,{key:parts[key] for key in SOURCES})
        phase=self.phase_original();need(phase['providerReadEpochMs']<=parts['baseRead']['before']['epochMs'])
        return dict(ticket=self.context['cleanupTicket'],public=self.derived(owner,row['index']),
            acquisition={key:clock[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')})

    def quiet(self):
        """Historical native/input/pixel quiet; root lifetime still needs OS end."""
        images=self.images();need(len(images)>=3)
        return quiet_period(images,self.baseline,self.admission,self.transfer)
