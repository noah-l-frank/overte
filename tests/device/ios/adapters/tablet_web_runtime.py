"""Existing physical SDK composition for independent original Tablet observers.

No _sources(), installed-code verify/write, session creation, Stop, SDK deletion
or app staging occurs here. The run's preparation owner supplies its genuine
physical binding and original native setup packet. Full terminal retirement is
separate and this component does not advertise a feature capability.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import os
from pathlib import Path
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.phase_witness_publisher import PhaseWitnessPublisher,PublicationPending
from adapters.script_feature.history import same,canonical
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader,PhasePending
from feature_journeys.contract import identifier
from feature_journeys.witness import Client
from ios.adapters.feature_observation import FeatureObservation
from ios.adapters.graphics_history import follow_native,restore_native
from ios.adapters.script_runtime import IOSScriptRuntime
from ios.adapters.tablet_web_admission import admit_existing_tablet_observer,follows as admission_follows,installed_forward
from ios.adapters.tablet_web_context import TabletWebContext
from ios.adapters.tablet_web_native_reads import TabletNativeReads
from ios.adapters.tablet_web_app_files import OwnedTabletWebAppFiles
from ios.adapters.tablet_web_app_origin import Frozen,admitted
from ios.adapters import tablet_web_buttons as app_buttons
from ios.adapters.tablet_web_observer import TabletWebObserver,TabletWebDOMDisposition
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,TabletSourcePhaseChanged
from ios.adapters.tablet_web_native_semantics import TabletNativeSemantics,scope as native_semantics_scope

VERSION=1
FACTORIES=dict(sources='tablet_sources',trace='tablet_web',dom='tablet_web_dom',buttons='tablet_web_buttons',
    uikit='uikit_input',state='tablet_web_state',closures='tablet_web_closures',emissions='web_script_emissions',deferred='tablet_web_deferred')


class TabletObservationPending(RuntimeError):
    """A newly acquired typed native page is still loading, not a fact."""


def pending_document(source,original):
    """Classify only actual completed typed acquisition during page loading.

    The original stays in the same immutable source history. No normalized
    state is returned and no source clock or observation deadline restarts.
    All non-transient semantic mismatches remain fatal.
    """
    frames=source.history();need(not source.blocked and frames)
    frame=frames[-1];full=source.originals.expand(original['reference']);row=source.originals.read(full)
    need(full['index']==len(source.state['records']) and row['status']=='returned' and row['hostProcessId']==original['hostProcessId'])
    document=frame['document'];native=frame['state']
    if document['status']!='unavailable' or not native['complete'] or native['otherLiveTablets']!=0:return False
    # An actual pending page owns its existing native grant; a foreign view,
    # arbitrary missing DOM, detached cache or closed panel is not this case.
    from ios.adapters.tablet_web_state import join
    join(native,frame['sources'],frame['ledger'],frame['touches'])
    from ios.adapters.tablet_web_observer import resources
    resources(frame,row)  # Foreign active input remains a fatal admission error.
    for app in source.app_sources(row['apps']):
        admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],source.binding,after_epoch=app['afterEpochMs'])
    active=[owner for owner in native['owners'] if owner['alive'] and owner['current'] is not None
        and owner['current']['generation']>0 and owner['current']['sourceCurrent']
        and not owner['current']['cleanupFailed'] and any(owner['current'][key] for key in ('active','loading','openTimerActive','deadlineActive'))]
    return len(active)==1


def file_responsibilities(packets):
    """Actual stage/positive readback persists until same-scope absence.

    Release ACKs cannot discharge ownership, and observing another scope does
    not retire an earlier app generation. Callers provide fully decoded actual
    query prefixes; this is a responsibility projection, not a native fact.
    """
    outstanding=set()
    for packet in packets:
        scope=packet['runId'];operation=packet['operation'];source=packet['source']
        if operation=='stage':outstanding.add(scope)
        elif operation=='observe':
            if source['exists']:outstanding.add(scope)
            else:outstanding.discard(scope)
    return sorted(outstanding)


class TabletRuntimeObserver:
    def __init__(self,observer,bootstrap,*,primary_bootstrap=None,admission=None):
        self.observer,self.bootstrap,self.primary_bootstrap=observer,bootstrap,primary_bootstrap
        need(observer.source.role==bootstrap.role and same(observer.source.binding,bootstrap.binding)
            and observer.source.run==bootstrap.run and bootstrap.state['status']=='returned')
        self.admission=deepcopy(bootstrap.admission if admission is None else admission)
        admission_follows(bootstrap.admission,self.admission,bootstrap.binding)
        need(self.admission['hostProcessId']==os.getpid())
        if bootstrap.role=='actor':
            need(isinstance(primary_bootstrap,TabletWebContext) and primary_bootstrap.historical
                and primary_bootstrap.role=='primary' and primary_bootstrap.run==bootstrap.run
                and same(primary_bootstrap.binding,bootstrap.binding) and same(primary_bootstrap.setup,bootstrap.setup)
                and primary_bootstrap.admission['hostProcessId']!=os.getpid())
            primary_bootstrap.original()
        else:need(primary_bootstrap is None)
        self.publisher=None;self.auxiliaries={};self.proof_cache=None;self.proof_roots=[observer.source.root];self.native_semantics=TabletNativeSemantics()

    def auxiliary(self,kind):
        source=self.observer.source;source.bound()
        if kind not in self.auxiliaries:
            self.auxiliaries[kind]=TabletNativeReads(source.root,source.binding,source.run,source.role,kind,source.lock,source.guard,
                epoch_ms=source.epoch_ms,monotonic=source.monotonic)
        return self.auxiliaries[kind]

    def auxiliary_reader(self,kind,*,ownership=None,operation='observe',files=None):
        """Construct the unchanged source without issuing a command."""
        source=self.observer.source;owner=self.auxiliary(kind);old=owner.history()
        clock=self.native_clock_source
        if kind=='files':
            owned=OwnedTabletWebAppFiles(None,Frozen(ownership),source.binding).owned()
            need(owned['featureRun']==source.run and owned['fixtureUrl']==source.fixture)
            need(operation in ('observe','locate') or source.role=='primary')
            reader=self.transport.script_fixture_files()
            call=lambda reader:reader.request(operation,owned['runId'],owned['ownerToken'],files)
        elif kind=='diagnostic':
            from ios.adapters.tablet_web_widgets import TabletDiagnosticReader
            reader=TabletDiagnosticReader(self.transport,int(source.binding['processIdentity']),self.native_clock,source.monotonic,self.transport.sleep)
            call=lambda reader:reader.read(0 if not old else old[-1]['sampleSequence'])
        elif kind=='widgets':
            from ios.adapters.tablet_web_widgets import TabletWidgetsReader
            reader=TabletWidgetsReader(self.client,source.binding['sessionId'],self.target,self.process,self.native_clock,
                monotonic=source.monotonic,sleep=self.transport.sleep)
            call=lambda reader:reader.read()
        elif kind=='native':reader=self.observer.native;call=lambda reader:reader.read(reader.sequence)
        elif kind=='scripts':
            reader=self.transport.script_execution_observer()
            for packet in old:
                transition=reader._history_transition(packet,require_code_identity=True,require_membership=True)
                reader._commit_history(packet,transition)
            call=lambda reader:reader.read(reader.sequence,require_code_identity=True,require_membership=True)
        elif kind=='terminal':
            reader=self.transport.script_terminal(clock)
            if old:reader.restore(old[-1])
            call=lambda reader:reader.read(0 if reader.last is None else reader.last['sequence'])
        elif kind=='geometry':reader=self.transport.geometry();call=lambda reader:reader.capture()
        else:
            need(kind in ('keys','pointer','dialogs'))
            reader=getattr(self.transport,dict(keys='world_web_keys',pointer='pointer_state',dialogs='script_dialogs')[kind])(clock)
            call=lambda reader:reader.read(source.run)
        return owner,reader,call

    def read_auxiliary(self,kind,*,ownership=None,operation='observe',files=None):
        """Original-only setup/tail reads; only Primary may mutate its files."""
        owner,reader,call=self.auxiliary_reader(kind,ownership=ownership,operation=operation,files=files)
        return owner.capture(reader,call)

    def recover_inputs(self):
        """Primary-only administrative recovery; no query or input is sent."""
        source=self.observer.source;source.bound()
        if source.role!='primary':return None
        store=PrivateFeatureState(source.root/('tabletweb-inputs-'+source.run+'-'+source.role+'.json'))
        if store.read() is None:return None
        from ios.adapters.tablet_web_inputs import TabletWebInputs
        owner=TabletWebInputs(self.client,source.children['dom'],self.observer.readers['dom'],source.lock,self.native_clock,
            monotonic=source.monotonic,epoch_ms=source.epoch_ms)
        reference=None
        if owner.state['original'] is not None:reference=owner.recover_record()
        if owner.state['pending'] is not None:
            if owner.state['pending']['phase']=='returned':reference=owner.archive()
            else:reference=owner.abort_pending()
        return reference

    def recover_auxiliaries(self,ownerships):
        """Only original file/readback recovery; no query/input is repeated.

        A later ordinary observation must still acquire fresh bounded native
        data. Unsafe/rejected/incomplete originals remain blocking.
        """
        source=self.observer.source;self.recover_inputs();files_by_run={row['runId']:row for row in ownerships}
        for kind in self.auxiliary_kinds():
            store=PrivateFeatureState(source.root/('tabletweb-aux-'+kind+'-'+source.run+'-'+source.role+'.json'))
            if store.read() is None:continue
            owner=self.auxiliary(kind);owner.history()
            if owner.state['original'] is not None:owner.recover_record()
            pending=owner.state['pending']
            if pending is None:need(not owner.blocked);continue
            if kind=='defer':
                from types import SimpleNamespace
                actual=self.transport.tablet_web_defer(self.native_clock_source)
                reader=SimpleNamespace(original=actual.read,guard=actual.guard)
            else:
                ownership=None
                if kind=='files':
                    need(pending['query'] is not None and pending['query']['runId'] in files_by_run)
                    ownership=files_by_run[pending['query']['runId']]
                _owner,reader,_invoke=self.auxiliary_reader(kind,ownership=ownership)
            owner.reconcile(reader)

    @staticmethod
    def returned_controls(packet,ownership):
        """Construct metadata solely from actual returned Qt object originals."""
        app_buttons.original(packet);controls={}
        for button in packet['buttons']:
            match=app_buttons.SEMANTIC.fullmatch(button['semanticId'])
            if match[1]!=ownership['featureRun'] or match[2]!=ownership['nonce']:continue
            actual=[row for row in packet['controls'] if row['button']==button['id'] and row['alive']]
            need(len(actual)==1 and button['alive'] and button['removed'] is None and button['returned'] is not None)
            verb=match[3];need(verb not in controls)
            controls[verb]=dict(instance=packet['instance'],button=button['id'],control=actual[0]['id'],root=button['root'],rootInstance=packet['rootInstance'],
                semanticId=button['semanticId'],uuid=button['uuid'],featureRun=match[1],fixtureUrl=button['fixtureUrl'],nonce=match[2],verb=verb)
            app_buttons.metadata(controls[verb])
        need(set(controls)=={'open','inline','return'});return controls

    def defer(self,operation,record_id=None):
        """One genuine controlled native fault command with owned raw receipt."""
        import uuid
        from ios.adapters.tablet_web_deferred import IOSTabletWebDefer,FAULT,receipt
        source=self.observer.source;source.bound();need(source.role=='primary' and operation in ('arm','deliver','discard'))
        before=source.children['deferred'].capture(self.observer.readers['deferred'])
        query=dict(schemaVersion=1,action=FAULT,commandId='ios-'+uuid.uuid4().hex,runId=source.run,fixtureUrl=source.fixture,operation=operation)
        if operation!='arm':query['recordId']=record_id
        actual=self.transport.tablet_web_defer(self.native_clock_source)
        class OriginalFault(IOSTabletWebDefer):
            def __init__(self):
                self.original=actual.read
                super().__init__(actual.send,lambda:self.original(),actual.clock_ms,actual.guard,actual.pid,
                    monotonic=actual.monotonic,sleep=actual.sleep)
        owner=self.auxiliary('defer');packet=owner.capture(OriginalFault(),lambda reader:reader.issue(query,before),authority=dict(fixtureUrl=source.fixture,reference=deepcopy(source.children['deferred'].state['records'][-1])))
        receipt(packet,query,before['instance'],None)
        need(packet['status']=={'arm':'armed','deliver':'delivered','discard':'discarded'}[operation])
        return packet

    def remember_app(self,ownership):
        """The Actor reads genuine input ownership, then acquires its own facts.

        This never copies a Primary observation, writes native files, starts a
        Script or selects a button. Original readback may occur after real load.
        """
        source=self.observer.source;source.bound()
        actual=OwnedTabletWebAppFiles(None,Frozen(ownership),source.binding).owned()
        need(actual['featureRun']==source.run and actual['fixtureUrl']==source.fixture)
        prior=source.app_sources()
        for index,value in enumerate(prior):
            if same(value['owner'],actual):return deepcopy(source.state['apps'][index])
        native_files=self.read_auxiliary('files',ownership=actual)
        scripts=self.read_auxiliary('scripts')
        buttons=source.children['buttons'].capture(self.observer.readers['buttons'])
        controls=self.returned_controls(buttons,actual)
        app=dict(owner=actual,files=native_files,scripts=scripts,buttons=buttons,controls=controls,afterEpochMs=self.bootstrap.setup['capturedEpochMs'])
        # The full returned originals are saved by the parent before the final
        # cross-source admission. A mismatch remains owned and blocks capture.
        ref=source.remember_app(app)
        admitted(actual,native_files,scripts,buttons,controls,source.binding,after_epoch=app['afterEpochMs'])
        return ref

    def validate_original(self,original,*,require_current=False):
        need(type(require_current) is bool)
        if not require_current:
            return self.historical_proof('observation',original,self._validate_original)
        return self._validate_original(original,require_current=True)

    def _validate_original(self,original,*,require_current=False,_source_sink=None):
        need(_source_sink is None or callable(_source_sink))
        exact(original,{'tabletWebRuntimeObservationVersion','bootstrap','primaryBootstrap','observation','auxiliaries'})
        need(type(original['tabletWebRuntimeObservationVersion']) is int and original['tabletWebRuntimeObservationVersion']==VERSION)
        current=self.bootstrap
        historical=TabletWebContext(current.root,current.binding,current.run,current.role,current.lock,current.admission,current.setup,
            lambda:need(False),monotonic=current.monotonic,historical=True)
        need(same(original['bootstrap'],historical.state['original']))
        birth=historical.original()
        if current.role=='actor':
            primary=self.primary_bootstrap
            need(same(original['primaryBootstrap'],primary.state['original'])
                and primary.admission['hostProcessId']!=original['observation']['hostProcessId'])
            primary.original()
        else:need(original['primaryBootstrap'] is None)
        exact(original['auxiliaries'],set(self.auxiliary_kinds()))
        native_file_hold=False;readiness={}
        for kind,reference in original['auxiliaries'].items():
            if reference is None:continue
            source=self.observer.source
            history=TabletNativeReads(source.root,source.binding,source.run,source.role,kind,source.lock,lambda:need(False),
                epoch_ms=lambda:need(False),monotonic=source.monotonic,historical=True)
            actual=history.at(reference)
            if require_current:
                history.history();need(not history.blocked and history.state['pending'] is None and history.state['original'] is None
                    and history.state['records'][-1]==reference)
            if kind in ('keys','pointer','geometry','widgets'):
                full=history.frames.expand(reference);entry=history.frames.read(full);need(entry['status']=='returned')
                readiness[kind]=(actual,entry)
            if kind=='files':native_file_hold=bool(file_responsibilities(history.through(reference)))
        if require_current:
            source=self.observer.source
            for kind,reference in original['auxiliaries'].items():
                if reference is not None:continue
                path=source.root/('tabletweb-aux-'+kind+'-'+source.run+'-'+source.role+'.json')
                if os.path.lexists(path):
                    history=TabletNativeReads(source.root,source.binding,source.run,source.role,kind,source.lock,lambda:need(False),
                        epoch_ms=lambda:need(False),monotonic=source.monotonic,historical=True)
                    history.history();need(not history.blocked and not history.state['records'] and history.state['pending'] is None and history.state['original'] is None)
        observed,archived,record,frame=self.observer._decoded_original(original['observation'])
        need(set(readiness)=={'keys','pointer','geometry','widgets'})
        acquisition=observed['acquisition'];earliest=min((entry['before'] for _packet,entry in readiness.values()),key=lambda stamp:stamp['monotonic'])
        for packet,entry in readiness.values():
            need(entry['after'] is not None and entry['after']['epochMs']<=acquisition['hostBeforeEpochMs']
                and entry['after']['monotonic']<=acquisition['hostBeforeMonotonic'])
        need(0<=acquisition['hostAfterEpochMs']-earliest['epochMs']<1500
            and 0<=acquisition['hostAfterMonotonic']-earliest['monotonic']<1.5
            and abs(acquisition['hostAfterEpochMs']-earliest['epochMs']-(acquisition['hostAfterMonotonic']-earliest['monotonic'])*1000)<=250)
        acquisition.update(hostBeforeEpochMs=earliest['epochMs'],hostBeforeMonotonic=earliest['monotonic'])
        observed['public']['capturedEpochMs']=earliest['epochMs']
        if native_file_hold and 'file:tablet-app-inputs' not in observed['public']['resources']:
            observed['public']['resources'].append('file:tablet-app-inputs')
        source=self.observer.source
        follow_native(birth,record['nativeBefore'])
        if record['tabletWebAcquisitionVersion']>=2:
            admission_follows(current.admission,record['admission'],source.binding)
            need(record['admission']['hostProcessId']==original['observation']['hostProcessId'])
        else:need(current.admission['hostProcessId']==original['observation']['hostProcessId'])
        need(frame['state']['iosTabletWebStateVersion']==2)
        if require_current:
            # Recheck the exact mutable WALs after the pure readiness joins.
            # Every pending/unsafe/raw/query floor was fully decoded above;
            # none may change while reusing that successful interpretation.
            source.lock.assert_held();need(same(archived.store.read(),archived.state))
            for child in archived.children.values():need(same(child.store.read(),child.state))
            need(not archived.blocked and archived.state['pending'] is None and archived.state['records'][-1]==original['observation']['reference'])
        for kind,(packet,_entry) in readiness.items():
            end=packet['observation']['sampleEpochMs'] if kind in ('geometry','widgets') else packet['clockAfter']['epochMs']
            need(0<=record['nativeAfter']['capturedEpochMs']-end<1500)
        if not record['apps']:
            from ios.adapters import world_web_keys as keys
            keys.privacy_qualified(readiness['keys'][0]);keys.drained(readiness['keys'][0])
            pointer=readiness['pointer'][0]['source']
            need(pointer['complete'] and pointer['startup']['observed'] and pointer['pendingDispatches']==0
                and not pointer['contacts'] and pointer['qtMouseButtons']==0 and pointer['worldTapActive'] is False)
            widgets=readiness['widgets'][0]['observation'];inventory=widgets['scriptInventory'];geometry=readiness['geometry'][0]['observation']['nativeUi']
            need(inventory['inventoryVersion']==2 and inventory['complete'] and inventory['rootOwnership']['available']
                and inventory['rootOwnership']['complete'] and inventory['rootOwnership']['wholeTreeReady']
                and widgets['tabletShown'] is False and not any(control['focused'] for control in widgets['controls'])
                and not any(manager['rootVisible'] or manager['labelVisible'] for manager in inventory['managers'])
                and not any(picker['visible'] or picker['closing'] or picker['requestId'] for picker in inventory['pickers'])
                and geometry['keyboardVisible'] is False and geometry['imeInsetBottom']==0)
        if _source_sink is not None:_source_sink(archived)
        return observed

    @contextmanager
    def image_observation_context(self,original,artifact_root):
        """Carry one freshly decoded historical owner through this image only.

        No frame/result is memoized here. Every tail still executes frame_at /
        history and its original file reads. A proof-cache hit supplies no new
        owner and takes the ordinary existing tail path instead.
        """
        from ios.adapters.emote_original_lease import EmoteOriginalLease
        source=self.observer.source;lock=source.lock;monotonic=source.monotonic
        lock.assert_held();holders=[];active=True
        metadata=lambda item:(str(item.root),canonical(item.binding),item.run,item.role,item.fixture,item.pid)
        expected=metadata(source)
        roots=[source.root,*self.proof_roots,Path(artifact_root)]
        roots=[path for index,path in enumerate(roots) if not any(path==prior or path.is_relative_to(prior) for prior in roots[:index])]
        publisher=source.root/('phase-publication-tablet-web-'+source.run+'-'+source.role+'.json')
        leases=[EmoteOriginalLease(root,[publisher]) for root in roots]
        def unchanged():
            need(active and self.observer.source is source and source.lock is lock
                and source.monotonic is monotonic and metadata(source)==expected)
            lock.assert_held()
            for lease in leases:lease.guard()
        def decoded(value):return self._validate_original(value,_source_sink=holders.append)
        try:
            observed=self.historical_proof('observation',original,decoded);unchanged();need(len(holders)<=1)
            if not holders:
                yield observed,self.validate_tail_source
                return
            owner=holders[0]
            need(isinstance(owner,TabletWebSourceOwner) and owner.historical and owner.lock is lock and metadata(owner)==expected)
            store=owner.store;path=store.path;state=canonical(owner.state);saved=canonical(owner.saved)
            need(type(store) is PrivateFeatureState and path==source.root/('tabletweb-source-owner-'+source.run+'-'+source.role+'.json'))
            children={name:(child,child.store,child.store.path,canonical(child.state),canonical(child.saved),
                metadata(child),child.module,child.monotonic) for name,child in owner.children.items()}
            need(all(type(entry[1]) is PrivateFeatureState and entry[2]==source.root/('tabletweb-'+name+'-queries-'+source.run+'-'+source.role+'.json')
                and entry[5]==expected and entry[0].component==name for name,entry in children.items()))
            def current_owner():
                unchanged();need(getattr(self,'_image_tail',None) is capsule
                    and owner.historical and owner.lock is lock and owner.monotonic is monotonic and metadata(source)==metadata(owner)==expected
                    and owner.store is store and store.path==path and canonical(owner.state)==state
                    and canonical(owner.saved)==saved and canonical(store.read())==state and state==saved
                    and set(owner.children)==set(children))
                for name,(child,child_store,child_path,child_state,child_saved,child_metadata,module,child_monotonic) in children.items():
                    need(owner.children[name] is child and child.historical and metadata(child)==child_metadata
                        and child.module is module and child.monotonic is child_monotonic and child.store is child_store
                        and child_store.path==child_path and canonical(child.state)==child_state
                        and canonical(child.saved)==child_saved and canonical(child_store.read())==child_state
                        and child_state==child_saved)
                unchanged()
            def tail(value):
                current_owner()
                try:
                    return self.historical_proof('tail',value,lambda item:self._validate_tail_source(item,_history=owner))
                finally:current_owner()
            capsule=(self,tail,current_owner);previous=getattr(self,'_image_tail',None);self._image_tail=capsule
            try:current_owner();yield observed,tail
            finally:
                try:current_owner()
                finally:self._image_tail=previous
        finally:
            try:unchanged()
            finally:active=False

    def _image_tail_validator(self,callback):
        """No arbitrary callback can suppress original screen-tail validation."""
        from types import MethodType
        if (type(callback) is MethodType and callback.__self__ is self
                and callback.__func__ is TabletRuntimeObserver.validate_tail_source):return callback
        capsule=getattr(self,'_image_tail',None)
        need(type(capsule) is tuple and len(capsule)==3 and capsule[0] is self and callback is capsule[1])
        capsule[2]();return callback

    @staticmethod
    def auxiliary_kinds():
        from ios.adapters.tablet_web_native_reads import KINDS
        return KINDS

    def auxiliary_references(self):
        """Retain every existing own original across real caller reentry.

        Reconstruction reads original files only. It cannot send, reconcile an
        unknown query, promote a partial record or manufacture absent history.
        """
        source=self.observer.source;source.bound();references={kind:None for kind in self.auxiliary_kinds()}
        for kind in self.auxiliary_kinds():
            path=source.root/('tabletweb-aux-'+kind+'-'+source.run+'-'+source.role+'.json')
            if kind not in self.auxiliaries and not os.path.lexists(path):continue
            owner=self.auxiliary(kind);owner.history()
            need(not owner.blocked and owner.state['pending'] is None and owner.state['original'] is None)
            if owner.state['records']:references[kind]=deepcopy(owner.state['records'][-1])
        return references

    def observe(self,*,readiness=True):
        need(type(readiness) is bool)
        if readiness:
            for kind in ('keys','pointer','geometry','widgets'):self.read_auxiliary(kind)
        references=self.auxiliary_references()
        value=dict(tabletWebRuntimeObservationVersion=VERSION,bootstrap=deepcopy(self.bootstrap.state['original']),
            primaryBootstrap=None if self.primary_bootstrap is None else deepcopy(self.primary_bootstrap.state['original']),observation=self.capture_source(),auxiliaries=references)
        self.validate_original(value,require_current=True);return value

    def capture_source(self):
        source=self.observer.source
        parts,row=source.capture(self.observer.readers,self.observer.native,self.observer.phase,self.observer.browser)
        need(parts['state']['iosTabletWebStateVersion']==2)
        original=dict(tabletWebObservationOriginalVersion=1,binding=deepcopy(source.binding),runId=source.run,role=source.role,
            fixtureUrl=source.fixture,hostProcessId=row['hostProcessId'],reference=deepcopy(source.state['records'][-1]))
        try:self.observer.validate_original(original)
        except (RuntimeError,ValueError,TypeError,KeyError):
            if pending_document(source,original):raise TabletObservationPending('Actual native Tablet document is not ready') from None
            raise
        return original

    def tail_source(self):
        """Private typed disposal frame; no normalized page/feature result."""
        source=self.observer.source;source.bound()
        _parts,row=source.capture(self.observer.readers,self.observer.native,self.observer.phase,self.observer.browser)
        value=dict(tabletWebTailSourceVersion=1,bootstrap=deepcopy(self.bootstrap.state['original']),
            primaryBootstrap=None if self.primary_bootstrap is None else deepcopy(self.primary_bootstrap.state['original']),
            observation=dict(tabletWebObservationOriginalVersion=1,binding=deepcopy(source.binding),runId=source.run,role=source.role,
                fixtureUrl=source.fixture,hostProcessId=row['hostProcessId'],reference=deepcopy(source.state['records'][-1])))
        self.validate_tail_source(value);return value

    def validate_tail_source(self,value):
        """Full original prefix/birth validation without app/page fact inference."""
        return self.historical_proof('tail',value,self._validate_tail_source)

    def _validate_tail_source(self,value,*,_history=None):
        exact(value,{'tabletWebTailSourceVersion','bootstrap','primaryBootstrap','observation'})
        need(type(value['tabletWebTailSourceVersion']) is int and value['tabletWebTailSourceVersion']==1)
        source=self.observer.source;current=self.bootstrap
        original=TabletWebContext(current.root,current.binding,current.run,current.role,current.lock,current.admission,current.setup,
            lambda:need(False),monotonic=current.monotonic,historical=True)
        need(same(value['bootstrap'],original.state['original']));birth=original.original()
        observed=value['observation'];exact(observed,{'tabletWebObservationOriginalVersion','binding','runId','role','fixtureUrl','hostProcessId','reference'})
        need(type(observed['tabletWebObservationOriginalVersion']) is int and observed['tabletWebObservationOriginalVersion']==1
            and same(observed['binding'],source.binding) and observed['runId']==source.run and observed['role']==source.role and observed['fixtureUrl']==source.fixture)
        if source.role=='actor':
            primary=self.primary_bootstrap;need(same(value['primaryBootstrap'],primary.state['original'])
                and primary.admission['hostProcessId']!=observed['hostProcessId']);primary.original()
        else:need(value['primaryBootstrap'] is None)
        history=_history
        if history is None:
            history=TabletWebSourceOwner(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,
                lambda:need(False),epoch_ms=lambda:need(False),monotonic=source.monotonic,historical=True)
        else:
            need(isinstance(history,TabletWebSourceOwner) and history.historical and history.lock is source.lock
                and history.root==source.root and same(history.binding,source.binding)
                and (history.run,history.role,history.fixture,history.pid)==(source.run,source.role,source.fixture,source.pid))
        row,frame,_frames=history.frame_at(observed['reference']);need(observed['hostProcessId']==row['hostProcessId'])
        follow_native(birth,row['nativeBefore'])
        if row['tabletWebAcquisitionVersion']>=2:admission_follows(current.admission,row['admission'],source.binding)
        else:need(current.admission['hostProcessId']==row['hostProcessId'])
        need(frame['state']['iosTabletWebStateVersion']==2)
        return dict(row=row,frame=frame)

    def publication_original(self,value):
        # A retained cleanup publication is also a historical original. The
        # current cleanup_live path independently performs its full quiet
        # proof; publisher clocks/process/last-send checks remain outside this
        # immutable complete-graph reuse, exactly as for active publications.
        return self.historical_proof('publication',value,self._publication_original)

    def historical_proof(self,kind,value,decoder):
        """Reuse only one complete unchanged historical byte/inventory graph.

        This never wraps current validation, source acquisition, process/input
        guards, current cleanup proofs or publisher freshness/transport checks.
        """
        source=self.observer.source;source.lock.assert_held()
        from ios.adapters.tablet_web_proof_cache import TabletPublicationProofCache
        roots=list(self.proof_roots)
        seal=dict(kindContext=dict(binding=source.binding,run=source.run,role=source.role,pid=source.pid,fixture=source.fixture,
            bootstrap=self.bootstrap.state,primary=None if self.primary_bootstrap is None else self.primary_bootstrap.state,
            admission=self.admission,origins=self.observer.origins),roots=[str(path) for path in roots])
        if self.proof_cache is None or self.proof_cache_roots!=roots:
            self.proof_cache=TabletPublicationProofCache(roots,source.binding,source.run,source.role);self.proof_cache_roots=roots
        with native_semantics_scope(self.native_semantics):
            return self.proof_cache.decode(dict(kind=kind,original=value),seal,lambda item:decoder(item['original']))

    def _publication_original(self,value):
        if type(value) is dict and 'tabletWebImageObservationVersion' in value:
            from ios.adapters.tablet_web_image_observation import validate
            return validate(self,value)
        if type(value) is dict and 'tabletWebCleanupObservationVersion' in value:
            from ios.adapters.tablet_web_cleanup_observation import validate
            return validate(self,value)
        return self.validate_original(value)

    def observe_image(self,root,policy,ticket,*,readiness=True,before=None):
        """Original screen evidence and facts from its actual final source frame.

        Readiness is measured before the screenshot. No second feature capture
        replaces the source frame that actually brackets the returned PNG.
        """
        from ios.adapters.tablet_web_samples import TabletWebSamples
        need(type(readiness) is bool)
        if readiness:
            for kind in ('keys','pointer','geometry','widgets'):self.read_auxiliary(kind)
        source=self.observer.source;samples=TabletWebSamples(self,root,policy)
        reference=samples.capture(ticket,before=before);selected=samples.read(reference)['row']['after']['observation']
        references=self.auxiliary_references()
        observation=dict(tabletWebRuntimeObservationVersion=VERSION,bootstrap=deepcopy(self.bootstrap.state['original']),
            primaryBootstrap=None if self.primary_bootstrap is None else deepcopy(self.primary_bootstrap.state['original']),
            observation=selected,auxiliaries=references)
        self.validate_original(observation,require_current=True)
        original=dict(tabletWebImageObservationVersion=1,observation=observation,sample=reference,artifactRoot=str(root),policy=deepcopy(policy))
        self.publication_original(original);return original

    def actor_publisher(self):
        source=self.observer.source;need(source.role=='actor');source.bound()
        if self.publisher is None:
            phase=self.observer.phase
            if phase.previous is None:phase.status()
            self.publisher=PhaseWitnessPublisher(PrivateFeatureState(source.root/('phase-publication-tablet-web-'+source.run+'-actor.json')),
                source.binding,phase,source.lock,source.guard,self.publication_original,epoch_ms=source.epoch_ms,monotonic=source.monotonic)
        return self.publisher

    def publish(self):
        publisher=self.actor_publisher()
        if publisher.state['pending'] is not None:return publisher.resolve()
        return publisher.publish(self.observe())


class IOSTabletWebRuntime(IOSScriptRuntime):
    def _tablet_web_feature(self,selector,run,*,role,client,settings):
        from ios.adapters.tablet_web_configuration import settings as validate_settings
        from ios.adapters.tablet_web_feature import IOSTabletWebFeature
        need(role in ('primary','actor') and isinstance(client,Client));identifier(run)
        selected=validate_settings(settings,role=role,fixture_url=client.url)
        return IOSTabletWebFeature(self,selector,client,run,role,selected['physicalBinding'],selected['setupNative'],selected['origins'],
            screen=dict(artifactRoot=selected['artifactRoot'],policy=selected['imagePolicy']))

    def historical_observer(self,selector,run,role,binding,setup_native,origins,lock,*,fixture_url,monotonic=time.monotonic):
        """Reconstruct only this prepared role's actual immutable file graph.

        No SDK/process read, session creation or native query is available.
        This is used after the original live window; it supplies no freshness
        or terminal permission independently of the full original decoder.
        """
        root=self.state_path(selector).parent
        need(role in ('primary','actor') and isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock')
        def context_for(actual_role):
            value=PrivateFeatureState(root/('tabletweb-context-'+run+'-'+actual_role+'.json')).read()
            need(type(value) is dict and type(value.get('admission')) is dict)
            owner=TabletWebContext(root,binding,run,actual_role,lock,value['admission'],setup_native,lambda:need(False),
                monotonic=monotonic,historical=True)
            owner.original();return owner
        bootstrap=context_for(role);primary=context_for('primary') if role=='actor' else None
        source=TabletWebSourceOwner(root,binding,run,role,fixture_url,
            int(binding['processIdentity']),lock,lambda:need(False),epoch_ms=lambda:need(False),monotonic=monotonic,historical=True)
        observer=object.__new__(TabletWebObserver);observer.source=source;observer.origins=deepcopy(origins)
        observer.readers={};observer.native=observer.phase=None;observer.browser=lambda:need(False);observer.publisher=None
        result=object.__new__(TabletRuntimeObserver);result.observer=observer;result.bootstrap=bootstrap;result.primary_bootstrap=primary
        result.admission=deepcopy(bootstrap.admission);result.publisher=None;result.auxiliaries={}
        result.proof_cache=None;result.proof_roots=[root];result.native_semantics=TabletNativeSemantics()
        return result

    @contextmanager
    def observer_runtime(self,selector,run,role,fixture_client,origins,physical_binding,setup_native,*,
                         epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,sleep=time.sleep):
        """Hold the actual shared SDK source lock for one bounded caller operation.

        Actor and Primary use the same already-prepared selector/session. The
        Actor requires the Primary's actual persisted bootstrap and a different
        host process. Neither path creates product app input before baseline.
        """
        need(role in ('primary','actor') and isinstance(fixture_client,Client))
        root=self.state_path(selector).parent;lock=ScriptSourceLock(root/'script-feature-sources.lock');transient=None
        with lock.held():
            admission=admit_existing_tablet_observer(self,selector,physical_binding,epoch_ms=epoch_ms,monotonic=monotonic)
            client,session,state,target,scope=self._existing(selector)
            need(same(dict(scope,processIdentity=str(admission['processAfter']['pid'])),physical_binding))
            gate=self.adapter._binding(selector,client,session,state,target);expected=admission['installedAfter'];process=admission['processAfter']
            def check():
                nonlocal expected
                lock.assert_held();self.adapter._candidate_guard()
                need(same(self.adapter.read_session(selector),state) and same(self.adapter._scope(selector,session,state,target),scope))
                latest=gate.record();installed_forward(expected,latest);expected=deepcopy(latest)
                return True
            def actual_process():
                check();actual=gate.continuity();need(same(actual,process));return deepcopy(actual)
            bootstrap_transport=FeatureObservation(client,session,target,actual_process,epoch_ms=epoch_ms,monotonic=monotonic,sleep=sleep)
            prior=PrivateFeatureState(root/('tabletweb-context-'+run+'-'+role+'.json')).read()
            retained=admission
            if prior is not None:
                need(type(prior) is dict and type(prior.get('admission')) is dict)
                retained=prior['admission']
                admission_follows(retained,admission,physical_binding)
            context=TabletWebContext(root,physical_binding,run,role,lock,retained,setup_native,check,monotonic=monotonic)
            if context.state['status']=='prepared':context.bootstrap(bootstrap_transport.native_observer())
            else:context.original()  # Unknown/partial startup never issues another query.
            primary=None
            if role=='actor':
                original=PrivateFeatureState(root/('tabletweb-context-'+run+'-primary.json')).read()
                need(type(original) is dict and 'admission' in original)
                primary=TabletWebContext(root,physical_binding,run,'primary',lock,original['admission'],setup_native,
                    lambda:need(False),monotonic=monotonic,historical=True)
            clock=bootstrap_transport.native_observer()
            def native_epoch():return clock.read(clock.sequence)['capturedEpochMs']
            # Legacy Script/file/geometry factories also need actual native
            # clocks; the measured host clock is used only in acquisitions.
            transport=FeatureObservation(client,session,target,actual_process,epoch_ms=native_epoch,monotonic=monotonic,sleep=sleep)
            # The source factories keep their original independent native clock
            # behavior. Restoring this immutable floor does not mint freshness.
            native=transport.bound_native_observer(clock);restore_native(native,context.original())
            readers={name:getattr(transport,method)(clock) for name,method in FACTORIES.items()}
            readers['dom']=TabletWebDOMDisposition.from_reader(readers['dom'])
            phase=PhaseFixtureReader(fixture_client,run,'tablet-web',epoch_ms=epoch_ms,monotonic=monotonic)
            source=TabletWebSourceOwner(root,physical_binding,run,role,phase.fixture_url,int(physical_binding['processIdentity']),lock,check,
                epoch_ms=epoch_ms,monotonic=monotonic,admission=admission)
            observer=TabletWebObserver(source,readers,native,phase,lambda:fixture_client.request('/runs/'+run+'/browser'),origins)
            composed=TabletRuntimeObserver(observer,context,primary_bootstrap=primary,admission=admission)
            composed.transport,composed.native_clock,composed.native_clock_source,composed.client=transport,native_epoch,clock,client
            composed.check,composed.process,composed.target=check,actual_process,target
            # Keep the shared lock's ordinary final ownership/inode checks.
            # Its deliberately closed exception grammar must not erase the
            # specific actual phase/pending sentinels expected by this worker.
            # No source exception is interpreted from a message or cause chain.
            try:yield composed
            except (TabletSourcePhaseChanged,TabletObservationPending,PhasePending,PublicationPending) as observed:transient=observed
            check()
        if transient is not None:raise transient
