"""Cleanup an actual interrupted preparation without completing preparation.

This coordinator retains the original failed whole owner. Successful Scene,
Complete and terminal-window contracts are deliberately not used by aborts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.avatar_abort import IOSAvatarAbort
from ios.adapters.avatar_abort_credentials import AvatarAbortCredentials
from ios.adapters.avatar_login_owner import IOSAvatarLoginOwner
from ios.adapters.avatar_runtime import IOSAvatarLoginRuntime
from ios.adapters.private_login_transport import IOSPrivateLoginTransport
from ios.adapters.account_preferences import validate_basis,require_owned,EMPTY

VERSION=1


class FailedPreparationPending(NativeUIError):pass


class AvatarFailedPreparation:
    """An abort-only account handoff followed by actual process retirement.

    Resource classes which cannot yet be retired stay owned. A partial result
    never enters a successful feature or terminal qualification path.
    """
    @classmethod
    def archive(cls,feature,value):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(isinstance(feature,IOSAvatarFeature));feature.lock.assert_held();feature.load()
        need(feature.state is not None and feature.state['phase'] in ('preparing','ready'))
        result=object.__new__(cls);result.feature,result.lock,result.runtime=feature,feature.lock,feature.runtime
        result.run,result.role,result.selector=feature.run,feature.role,feature.selector
        result.binding=deepcopy(feature.state['bindings'][feature.role]);result.failure=deepcopy(feature.previous)
        result.store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+feature.role+'-'+feature.run+'-failed-preparation.json'))
        result.login_store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+feature.role+'-login.json'))
        need(same(result.store.read(),value));rows=unpack(value['payload']);need(len(rows)==1)
        result.child_runtime=IOSAvatarLoginRuntime(feature.runtime.adapter,feature.authority.client,feature.run,feature.role,rows[0]['childRunId'])
        result.previous=deepcopy(value);result.state=None;result.state=result.decode(value)
        need(result.state['phase']=='failed-ended');result.abort=IOSAvatarAbort.archive(feature,result.state['process'])
        return result

    def __init__(self,feature):
        from ios.adapters.avatar_feature import IOSAvatarFeature
        need(isinstance(feature,IOSAvatarFeature));feature.lock.assert_held();feature.load()
        need(feature.state is not None and feature.state['phase'] in ('preparing','ready'))
        self.feature,self.lock,self.runtime=feature,feature.lock,feature.runtime
        self.run,self.role,self.selector=feature.run,feature.role,feature.selector
        self.binding=deepcopy(feature.state['bindings'][self.role]);self.failure=deepcopy(feature.previous)
        self.store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-failed-preparation.json'))
        self.login_store=PrivateFeatureState(feature.store.path.with_name('ios-avatar-'+self.role+'-login.json'))
        paired=None
        path=feature.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort.json')
        if feature.state['phase']=='ready' and PrivateFeatureState(path).read() is None:
            from ios.adapters.avatar_paired_failure import prepare
            paired=prepare(feature);need(paired is not None)
        self.abort=IOSAvatarAbort(feature,epoch_ms=feature.epoch_ms,monotonic=feature.monotonic,paired_failure=paired)
        self.previous=self.store.read();self.state=None
        if self.previous is None:
            authority=feature.authority.read();child=authority['accounts'][self.role]['runId']
            self.state=dict(childRunId=child,authority=authority,loginBefore=self.login_store.read(),loginAfter=None,
                credentials=None,leases={},account=None,preferences=None,scene=None,process=None,provider=None,phase='owned')
            self.child_runtime=IOSAvatarLoginRuntime(self.runtime.adapter,feature.authority.client,self.run,self.role,child)
            self.validate_login(self.state['loginBefore']);self.save()
        else:
            rows=unpack(self.previous['payload']);need(len(rows)==1)
            self.child_runtime=IOSAvatarLoginRuntime(self.runtime.adapter,feature.authority.client,self.run,self.role,rows[0]['childRunId'])
            self.state=self.decode(self.previous)
        self.bound()

    def envelope(self,state):
        return dict(iosAvatarFailedPreparationVersion=VERSION,runId=self.run,role=self.role,binding=self.binding,
            failedOriginal=self.failure,failedOriginalSha256=digest(self.failure),payload=pack([state]))

    def validate_login(self,value):
        if value is None:return None
        def forbidden(*_args,**_kwargs):need(False)
        owner=IOSAvatarLoginOwner(self.child_runtime,self.selector,self.feature.authority,self.lock,
            epoch_ms=getattr(self.feature,'epoch_ms',forbidden),monotonic=getattr(self.feature,'monotonic',forbidden),
            sleep=getattr(self.feature,'sleep',forbidden))
        state=owner.decode(value);need(same(state['binding'],self.binding));return state

    @staticmethod
    def login_prefix(before,after):
        need(same(after['binding'],before['binding']) and same(after['preferences'],before['preferences'])
            and same(after['samples'][:len(before['samples'])],before['samples']) and same(after['protected'],before['protected'])
            and len(after['actions'])>=len(before['actions']))
        for old,new in zip(before['actions'],after['actions']):
            if old['complete']:need(same(old,new))
            else:need(all(same(old[key],new[key]) for key in ('verb','ticket','before','intents')))

    def decode(self,value):
        exact(value,{'iosAvatarFailedPreparationVersion','runId','role','binding','failedOriginal','failedOriginalSha256','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and type(value['iosAvatarFailedPreparationVersion']) is int
            and value['iosAvatarFailedPreparationVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'childRunId','authority','loginBefore','loginAfter','credentials','leases','account','preferences','scene','process','provider','phase'})
        abort=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort.json')).read()
        need(abort is not None);IOSAvatarAbort.history(self.feature,abort)
        need(state['childRunId']==self.child_runtime.run and state['phase'] in ('owned','accounts-restored','native-retired','process-ended','failed-ended'))
        authority=state['authority'];epoch=max(row['capturedEpochMs'] for row in authority['accounts'].values())
        self.feature.authority.validate(authority,epoch)
        need(authority['accounts'][self.role]['runId']==state['childRunId'])
        before=self.validate_login(state['loginBefore']);after=self.validate_login(state['loginAfter'])
        if after is not None:
            need(before is not None);self.login_prefix(before,after)
        if state['credentials'] is not None:
            original=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort-credentials.json'))
            AvatarAbortCredentials.archive(state['credentials'],store=original,private_store=self.child_runtime.private_login_input_store(self.selector),
                binding=self.binding,run=self.run,child_run=state['childRunId'],role=self.role,lock=self.lock)
        exact(state['leases'],set(state['leases']))
        need(set(state['leases'])<={'probe','origin'})
        for kind,row in state['leases'].items():self.lease_original(kind,row,child=state['childRunId'])
        if state['account'] is not None:
            self.anonymous(state['account'])
        if state['preferences'] is not None:
            need(before is not None);basis=validate_basis(state['preferences'],self.child_runtime.origin)
            need(same(basis['binding'],self.binding) and same(basis['preferences'],before['preferences']['preferences']))
        if state['phase'] in ('accounts-restored','process-ended','failed-ended'):
            need(state['account'] is not None and all(row['complete'] for row in state['leases'].values())
                and (state['loginBefore'] is None or state['preferences'] is not None))
        if state['scene'] is not None:self.scene_original(state['scene'])
        if state['phase']!='owned':need(state['scene'] is not None)
        if state['process'] is not None:
            original=IOSAvatarAbort.archive(self.feature,state['process']);need(original.original_result()['status']=='failed')
        if state['phase'] in ('process-ended','failed-ended'):need(state['process'] is not None)
        if state['provider'] is not None:
            row=state['provider'];exact(row,{'issued','before','after','acquisition'})
            need(type(row['issued']) is bool and (not row['issued'] or self.role=='primary'))
            for key in ('before','after'):
                if row[key] is not None:
                    epoch=max(packet['capturedEpochMs'] for packet in row[key]['accounts'].values())
                    self.feature.authority.validate(row[key],epoch,authority)
                    need(all(row[key]['accounts'][role]['runId']==state['authority']['accounts'][role]['runId'] for role in ('primary','actor')))
            if row['after'] is not None:
                self.provider_retired(row['after']);IOSAvatarAbort.acquisition(row['acquisition'])
            else:need(row['acquisition'] is None)
        if state['phase']=='failed-ended':need(state['provider'] is not None and state['provider']['after'] is not None)
        return deepcopy(state)

    def bound(self):
        self.lock.assert_held();need(same(self.feature.store.read(),self.failure) and same(self.store.read(),self.previous))
        self.abort.bound()

    def guard(self):
        self.bound();self.abort.input_guard();return True

    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def anonymous(self,packet):
        native_packet(packet,packet.get('requestId'),int(self.binding['processIdentity']),packet.get('capturedEpochMs'),require_account=True)
        account=packet['account'];observed=account['observation']
        need(not account['loggedIn'] and account['principalSha256']==EMPTY and observed['credentialActive']
            and observed['endpointPresent'] and observed['endpointSha256'] in {self._sha(self.child_runtime.origin),self._sha(self.child_runtime.origin+'/')}
            and not any(observed[key] for key in ('loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
        return packet

    @staticmethod
    def _sha(value):
        import hashlib
        return hashlib.sha256(value.encode()).hexdigest()

    def credentials(self):
        self.guard();private=self.child_runtime.private_login_input_store(self.selector)
        if self.state['credentials'] is not None:
            self.decode(self.previous);return
        if private.read() is None:return
        actual=self.runtime._sources(self.selector);need(same(actual['binding'],self.binding))
        owner=AvatarAbortCredentials(PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+self.run+'-abort-credentials.json')),
            private,IOSPrivateLoginTransport(actual['observer']),self.binding,self.run,self.state['childRunId'],self.role,self.lock,self.guard,
            epoch_ms=self.feature.epoch_ms,monotonic=self.feature.monotonic)
        owner.cleanup();self.state['credentials']=deepcopy(owner.previous);self.save()

    def lease_original(self,kind,row,*,child=None):
        from adapters.native_account_probe import command as probe_command,validate as probe_packet
        from adapters.native_account_origin import command as origin_command,validate as origin_packet
        exact(row,{'ownership','queries','original','acquisition','complete'});need(type(row['complete']) is bool and type(row['queries']) is list and len(row['queries'])<=32)
        need(same(row['ownership']['binding'],self.binding));nonces=set();releases=0
        owned=row['ownership']
        need(type(owned['ownershipVersion']) is int and owned['ownershipVersion']==1)
        if kind=='probe':
            exact(owned,{'ownershipVersion','binding','probe'});probe_command(owned['probe'],ios=True)
            need(owned['probe']['operation']=='read' and owned['probe']['runId']==self.child_runtime.run)
        else:
            from adapters.native_account_origin import original_document
            exact(owned,{'ownershipVersion','binding','instance','data'});exact(owned['data'],{'runId','ownerToken','origin'})
            original_document(owned['data']['runId'],owned['data']['origin'])
            need(owned['data']['runId']==self.child_runtime.run and owned['data']['origin']==self.child_runtime.origin)
        for query in row['queries']:
            (probe_command if kind=='probe' else origin_command)(query,ios=True)
            need(query['runId']==(self.state['childRunId'] if child is None else child) and query['commandId'] not in nonces);nonces.add(query['commandId'])
            releases+=query['operation']=='release'
            need(query['operation'] in (('release','inspect') if kind=='probe' else ('release','observe')))
            if kind=='probe':
                need(same({key:item for key,item in query.items() if key not in ('commandId','operation')},
                    {key:item for key,item in owned['probe'].items() if key not in ('commandId','operation')}))
            else:need(query['instance']==owned['instance'] and query['ownerToken']==owned['data']['ownerToken'])
        need(releases==1)
        packet=row['original']
        if packet is not None:
            IOSAvatarAbort.acquisition(row['acquisition'])
            matches=[query for query in row['queries'] if query['commandId']==packet['commandId']];need(len(matches)==1)
            (probe_packet if kind=='probe' else origin_packet)(packet,matches[0],int(self.binding['processIdentity']),packet['capturedEpochMs'])
            need(matches[0]['operation']==('inspect' if kind=='probe' else 'observe'))
        else:need(row['acquisition'] is None)
        if row['complete']:
            need(packet is not None)
            if kind=='probe':need(packet['source']==dict(inflight=False,responseBytes=0,credentialBytes=0,released=True))
            else:
                source=packet['source'];need(source['retired'] and not source['originExists'] and not source['ownerExists']
                    and source['originBytes']==source['ownerBytes']==0)

    def release_lease(self,kind):
        """Durably retain the actual source-generated Release nonce, then inspect.

        The wrapper changes only this newly constructed host transport's send
        callback. It never changes a product source or replays an unknown send.
        """
        self.guard();runtime=self.child_runtime
        store=runtime.account_probe_store(self.selector,role=self.role) if kind=='probe' else runtime.account_origin_store(self.selector)
        owned=store.read();old=self.state['leases'].get(kind)
        if old is None and owned is None:return
        if old is not None and old['complete']:
            need(owned is None or same(owned,old['ownership']))
            if owned is not None:store.discard(owned)
            return
        actual=runtime._account_probe(self.selector,role=self.role) if kind=='probe' else runtime._account_origin(self.selector)
        source=actual.probe if kind=='probe' else actual.source
        if old is None:
            expected=actual.owner.owned() if kind=='probe' else actual.owned();need(same(expected,owned))
        else:need(same(owned,old['ownership']))
        send=source.send
        def retained(query):
            self.guard()
            if kind not in self.state['leases']:
                self.state['leases'][kind]=dict(ownership=deepcopy(owned),queries=[],original=None,acquisition=None,complete=False)
            row=self.state['leases'][kind];row['queries'].append(deepcopy(query));self.save();self.guard();send(query)
        source.send=retained
        before,started=self.feature.epoch_ms(),self.feature.monotonic()
        try:
            if old is None:
                if kind=='origin':
                    source.request(owned['data'],'release');packet=source.request(owned['data'],'observe')
                else:
                    query=deepcopy(owned['probe']);query.update(operation='release',commandId='ios-'+uuid.uuid4().hex);source._perform(query)
                    query=deepcopy(owned['probe']);query.update(operation='inspect',commandId='ios-'+uuid.uuid4().hex);packet=source._perform(query)
            elif kind=='probe':
                query=deepcopy(owned['probe']);query.update(operation='inspect',commandId='ios-'+uuid.uuid4().hex);packet=source._perform(query)
            else:packet=source.request(owned['data'],'observe')
        finally:source.send=send
        row=self.state['leases'][kind];row['original']=deepcopy(packet);row['complete']=True
        row['acquisition']=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.feature.epoch_ms(),
            hostBeforeMonotonic=started,hostAfterMonotonic=self.feature.monotonic())
        self.lease_original(kind,row)
        self.save()
        current=store.read();need(current is None or same(current,owned))
        if current is not None:store.discard(current)
        IOSAvatarAbort.acquisition(dict(row['acquisition'],hostAfterEpochMs=self.feature.epoch_ms(),hostAfterMonotonic=self.feature.monotonic()))

    def restore_account(self):
        if self.state['phase']=='owned':self.retire_native_inputs()
        if self.state['phase']!='native-retired':self.decode(self.previous);return True
        self.guard()
        owner=IOSAvatarLoginOwner(self.child_runtime,self.selector,self.feature.authority,self.lock,
            epoch_ms=self.feature.epoch_ms,monotonic=self.feature.monotonic,sleep=self.feature.sleep)
        state=owner.load();original=self.state['loginBefore']
        if original is None:
            need(state is None and all(store.read() is None for store in (self.child_runtime.private_login_input_store(self.selector),
                self.child_runtime.account_probe_store(self.selector,role=self.role),self.child_runtime.account_origin_store(self.selector))))
        else:
            need(state is not None);before=self.validate_login(original)
            self.login_prefix(before,state)
            if state['phase'] in ('login-issued','logout-issued'):
                action=state['actions'][-1];owner.terminal(action['verb'],action['ticket']);state=owner.state
            ticket=self.feature.authority.read()['ticket']
            with transport_scope(self.guard):
                if state['phase']=='logged-in':owner.logout(ticket);state=owner.state
                if state['phase']=='logged-out':owner.restore_preferences(ticket);state=owner.state
            if state['phase']=='restore-issued':
                # An uncertain preference input is never repeated. Adopt only
                # an actual already-restored preference original and account.
                source=self.child_runtime._sources(self.selector)
                require_owned(source['preferences'],self.child_runtime.origin,baseline=before['preferences']['preferences'])
                owner.sample();self.anonymous(owner.state['samples'][-1])
                basis=dict(binding=deepcopy(source['binding']),receipt=deepcopy(source['preferenceReceipt']),preferences=deepcopy(source['preferences']))
                validate_basis(basis,self.child_runtime.origin)
                owner.state['restoration']=basis;owner.state['actions'][-1].update(complete=True,after=len(owner.state['samples'])-1)
                owner.state['phase']='restored';owner.save();state=owner.state
            need(state['phase'] in ('prepared','restored'))
            source=self.child_runtime._sources(self.selector)
            require_owned(source['preferences'],self.child_runtime.origin,baseline=before['preferences']['preferences'])
            self.state['preferences']=dict(binding=deepcopy(source['binding']),receipt=deepcopy(source['preferenceReceipt']),preferences=deepcopy(source['preferences']))
            self.state['loginAfter']=deepcopy(owner.previous)
        reader=self.child_runtime._native_feature_observer(self.selector,read_only=True)
        packet=reader.read(reader.sequence,require_account=True);self.anonymous(packet)
        self.state.update(account=deepcopy(packet),phase='accounts-restored');self.save();self.guard();return True

    def scene_original(self,value):
        exact(value,{'scope','fileOwnerAbsent','samples','restoration'})
        need(type(value['fileOwnerAbsent']) is bool and value['fileOwnerAbsent'])
        if value['scope'] is not None:
            from ios.adapters.avatar_marker_history import archive as marker_archive
            original=marker_archive(value['scope'],root=self.feature.root,binding=self.binding,
                run=self.run,role=self.role,lock=self.lock)
            need(original.state['phase']=='released' and original.ticket==self.feature.state['initialTicket']
                and original.fixture_url==self.feature.phase.fixture_url)
        if value['samples'] is not None:
            from ios.adapters.avatar_held_samples import history as samples_history
            store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-samples.json'))
            original=samples_history(value['samples'],store=store,root=self.feature.root,binding=self.binding,
                run=self.run,role=self.role,policy=self.feature.policy,lock=self.lock)
            need(original.state['pending'] is None)
        if value['restoration'] is not None:
            from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
            store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-restoration-frames.json'))
            original=IOSAvatarRestorationFrames.archive(value['restoration'],store=store,root=self.feature.root,binding=self.binding,
                run=self.run,role=self.role,lock=self.lock)
            need(original.state['pending'] is None)
        return value

    def retire_native_inputs(self):
        """Retire an admitted partial marker; remaining Qt/GPU holds need OS end."""
        if self.state['phase']!='owned':self.decode(self.previous);return True
        self.guard();self.credentials()
        for kind in ('probe','origin'):self.release_lease(kind)
        path=self.feature.store.path.with_name('ios-avatar-'+self.role+'-marker.json');marker=PrivateFeatureState(path).read()
        files=PrivateFeatureState(path.with_name('ios-avatar-'+self.role+'-marker-files.json'))
        samples=PrivateFeatureState(path.with_name('ios-avatar-'+self.role+'-samples.json'))
        restoration=PrivateFeatureState(path.with_name('ios-avatar-'+self.role+'-restoration-frames.json'))
        sample_original=restoration_original=None;scope=None
        if marker is not None or restoration.read() is not None:
            scope=self.runtime._avatar_marker_scope(self.selector,self.feature.client,self.run,self.role,self.feature.root,
                self.feature.state['initialTicket'],self.lock)
        if restoration.read() is not None:
            from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
            owner=IOSAvatarRestorationFrames(self.runtime,self.selector,scope,self.feature.root,self.lock,
                epoch_ms=self.feature.epoch_ms,monotonic=self.feature.monotonic,sleep=self.feature.sleep)
            with transport_scope(self.abort.input_guard):owner.abandon()
            need(owner.state['pending'] is None);restoration_original=deepcopy(owner.previous)
        if marker is None:
            # Reservation is durable before native staging and normal Script
            # input. A missing marker owner cannot discharge other ownership.
            need(files.read() is None and samples.read() is None)
            original=None
        else:
            if samples.read() is not None:
                owner=self.runtime._avatar_samples(self.selector,scope,self.feature.client,self.feature.root,self.feature.policy,self.lock)
                with transport_scope(self.abort.input_guard):owner.drain()
                need(owner.state['pending'] is None);sample_original=deepcopy(owner.previous)
            with transport_scope(self.guard),self.runtime.existing_input_session(self.selector):scope.cleanup()
            need(scope.state['phase']=='released' and files.read() is None);original=deepcopy(scope.previous)
        self.state.update(scene=dict(scope=original,fileOwnerAbsent=True,samples=sample_original,restoration=restoration_original),phase='native-retired');self.save();return True

    def process_round(self):
        self.bound();need(self.state['phase'] in ('accounts-restored','process-ended','failed-ended'))
        if self.state['phase'] in ('process-ended','failed-ended'):self.decode(self.previous);return True
        self.scene_original(self.state['scene'])
        peer=self.peer_original()
        if peer.state['phase'] not in ('accounts-restored','process-ended','failed-ended'):
            raise FailedPreparationPending('The independent original account cleanup must precede either Stop')
        if self.abort.state['phase']=='failed':self.abort.stop()
        if self.abort.state['phase']=='stop-issued' and not self.abort.process_round():return False
        if self.abort.state['phase'] in ('os-quiet','delete-issued') and not self.abort.delete():return False
        result=self.abort.result();need(result['status']=='failed' and result['processEnded'] and result['sdkAbsent'])
        self.state.update(process=deepcopy(self.abort.previous),phase='process-ended');self.save();return True

    def peer_original(self):
        """Read the other actual failed owner; never create its abort lifecycle."""
        from ios.adapters.avatar_feature import IOSAvatarFeature
        other='actor' if self.role=='primary' else 'primary';lock=self.feature.locks[other];lock.assert_held()
        path=self.runtime.state_path(self.feature.selectors[other]).with_name('ios-avatar-'+other+'-'+self.run+'-failed-preparation.json')
        value=PrivateFeatureState(path).read()
        if value is None:raise FailedPreparationPending('Independent failed-preparation owner has not yet retired its process')
        original=value['failedOriginal'];flow=IOSAvatarFeature.archive(self.runtime,original,self.feature.authority.client,self.feature.locks)
        need(flow.run==self.run and flow.role==other and same(flow.state['bindings'],self.feature.state['bindings'])
            and flow.state['phase'] in ('preparing','ready'))
        need(same(PrivateFeatureState(flow.store.path).read(),original))
        owner=object.__new__(type(self));owner.feature,owner.runtime,owner.lock=flow,self.runtime,lock
        owner.run,owner.role,owner.selector=self.run,other,flow.selector;owner.binding=deepcopy(self.binding if other==self.role else flow.state['bindings'][other])
        owner.failure=deepcopy(original);owner.store=PrivateFeatureState(path);owner.previous=deepcopy(value);owner.state=None
        rows=unpack(value['payload']);need(len(rows)==1)
        owner.child_runtime=IOSAvatarLoginRuntime(self.runtime.adapter,self.feature.authority.client,self.run,other,rows[0]['childRunId'])
        owner.state=owner.decode(value)
        need(same(PrivateFeatureState(path).read(),value));return owner

    @staticmethod
    def provider_retired(status):
        need(status['phase']=='revoking' and all(not row['grantsEnabled'] and not row['armedHold'] and all(row[key]==0
            for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens')) for row in status['accounts'].values()))

    def retire_provider(self):
        self.bound();need(self.state['phase'] in ('process-ended','failed-ended'))
        if self.state['phase']=='failed-ended':self.decode(self.previous);return True
        peer=self.peer_original()
        if peer.state['phase'] not in ('process-ended','failed-ended'):
            raise FailedPreparationPending('Both original processes must end before controlled authority retirement')
        if self.state['provider'] is None:
            self.state['provider']=dict(issued=self.role=='primary',before=self.feature.authority.read(),after=None,acquisition=None);self.save()
            if self.role=='primary':
                with transport_scope(self.abort.input_guard):
                    self.abort.input_guard();self.feature.client.request('/runs/'+self.run+'/avatar/control',dict(operation='revoke'),method='POST')
        before,started=self.feature.epoch_ms(),self.feature.monotonic();status=self.feature.authority.read()
        if status['phase']!='revoking':raise FailedPreparationPending('Original failed-preparation authority revoke remains unresolved')
        self.provider_retired(status)
        acquisition=dict(hostBeforeEpochMs=before,hostAfterEpochMs=self.feature.epoch_ms(),hostBeforeMonotonic=started,hostAfterMonotonic=self.feature.monotonic())
        IOSAvatarAbort.acquisition(acquisition);self.state['provider'].update(after=deepcopy(status),acquisition=acquisition)
        self.state['phase']='failed-ended';self.save();return True

    def result(self):
        """Failed status with genuine resource retirement, never Scene success."""
        self.bound();return self.original_result()

    def original_result(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous) and same(self.feature.store.read(),self.failure))
        self.decode(self.previous);need(self.state['phase']=='failed-ended')
        peer=self.peer_original()
        if peer.state['phase']!='failed-ended':raise FailedPreparationPending('The independent original failed-run end is not yet retained')
        need(same(self.login_store.read(),self.state['loginAfter']))
        scene=self.state['scene']
        for suffix,key in (('marker','scope'),('samples','samples'),('restoration-frames','restoration')):
            store=PrivateFeatureState(self.store.path.with_name('ios-avatar-'+self.role+'-'+suffix+'.json'))
            need(same(store.read(),scene[key]))
        for store in (self.child_runtime.private_login_input_store(self.selector),self.child_runtime.account_probe_store(self.selector,role=self.role),
            self.child_runtime.account_origin_store(self.selector),self.store.__class__(self.store.path.with_name('ios-avatar-'+self.role+'-marker-files.json'))):
            need(store.read() is None)
        return dict(performed=True,status='failed',originalSha256=digest(self.failure),
            processEnded=True,sdkAbsent=True,preferencesRestored=True,providerRetired=True)
