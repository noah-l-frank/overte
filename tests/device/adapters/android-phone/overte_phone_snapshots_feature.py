"""Ordinary Snapshot composition over the original independent owners.

This module is deliberately not registered as a public capability until the
complete common journey, independent actor and strict finalizer are verified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import time
import uuid

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier
from feature_journeys.evidence import rectangle
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.scenarios import VERSION
from fixture.messages_mixer import start_identity
from overte_phone_create_feature import PhoneCreateFeature
from overte_phone_graphics_surface import MODES
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshots_evidence import SnapshotsOriginals
from overte_phone_snapshot_handoff import bound as handoff_binding,control as handoff_control
from overte_phone_snapshot_upload_fixture import SnapshotUploadFixtureReader
from overte_phone_snapshot_foundation import PhoneSnapshotFoundation
from overte_phone_snapshot_cancel import validate as cancel_packet
from overte_phone_snapshot_upload_source import require_retired as upload_retired
from overte_phone_snapshot_capture_facts import capture_facts
from overte_phone_snapshots_measurements import SnapshotPending
from overte_phone_script_history import canonical
from adapters.native_script_work import scope as script_scope,validate as validate_work
from overte_phone_snapshot_measurements import validate as validate_group
from adapters.native_account_observation import accept as account_advance
from adapters.native_phone_touch_state import released as touch_released


def configuration(value):
    exact(value,{'snapshotsFeatureVersion','artifactRoot','imageExtent','markerRoi','imagePolicy','fileImagePolicy','domainId','receiverApkSha256'})
    need(type(value['snapshotsFeatureVersion']) is int and value['snapshotsFeatureVersion']==1)
    root=Path(value['artifactRoot']);PrivateFeatureState(root/'snapshots-evidence-boundary.json')._parent()
    extent=value['imageExtent'];need(type(extent) is list and len(extent)==2 and all(integer(item,240,4096) for item in extent))
    for key in ('imagePolicy','fileImagePolicy'):
        policy=value[key];exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
        rectangle(policy['marker'],extent);rectangle(policy['subject'],extent)
        marker,subject=policy['marker'],policy['subject']
        need(marker[2]-marker[0]>=128 and marker[3]-marker[1]>=32
            and not(max(marker[0],subject[0])<min(marker[2],subject[2]) and max(marker[1],subject[1])<min(marker[3],subject[3])))
    x0,y0,x1,y1=rectangle(value['markerRoi'],extent)
    need(x1-x0>=160 and y1-y0>=40 and (x1-x0)*(y1-y0)<=.1*extent[0]*extent[1]
        and value['imagePolicy']['marker']==[round(x0+(x1-x0)*4/160),round(y0+(y1-y0)*4/40),round(x0+(x1-x0)*132/160),round(y0+(y1-y0)*36/40)])
    need(str(uuid.UUID(value['domainId']))==value['domainId'] and uuid.UUID(value['domainId']).int!=0
        and type(value['receiverApkSha256']) is str and len(value['receiverApkSha256'])==64
        and all(char in '0123456789abcdef' for char in value['receiverApkSha256']))
    return deepcopy(value)


class PhoneSnapshotsFeature(PhoneCreateFeature):
    def __init__(self,adapter,selector,phase,config,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(phase,SnapshotUploadFixtureReader) and phase.area=='snapshots' and role in ('primary','actor'))
        self.adapter,self.selector,self.phase,self.config,self.role=adapter,selector,phase,configuration(config),role
        self.run,self.fixture_url=phase.run,phase.fixture_url;self.root=Path(config['artifactRoot']);self.policy=deepcopy(config['imagePolicy'])
        self.monotonic,self.sleep=monotonic,sleep;path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-snapshots-feature.json'));self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))
        self.previous,self.state=None,None;self._initial_header=self.store.read();self._initial_state=None
        self._runtime_guard=None;self._system_scope=None
        if self._initial_header is not None:
            header=self._initial_header;exact(header,{'snapshotsFeatureVersion','runId','fixtureUrl','binding','configuration','payload'})
            need(type(header['snapshotsFeatureVersion']) is int and header['snapshotsFeatureVersion']==1 and header['runId']==self.run
                and header['fixtureUrl']==self.fixture_url and same(header['configuration'],self.config))
            rows=unpack(header['payload']);need(len(rows)==1);self._initial_state=rows[0]
        self._scope_ready=False
        if self._initial_header is not None:
            # Construction can precede another role's normal OS transition.
            # Retain host ownership only; select measured authority from the
            # fresh exact header under the shared source lock in load().
            self.binding=deepcopy(context(self._initial_header['binding']));self.pid=int(self.binding['processIdentity'].split(':')[0])
            self.guard=self.header_authority
        else:
            _ui,_service,binding,self._runtime_guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
            self.binding=deepcopy(context(binding));self.pid=int(self.binding['processIdentity'].split(':')[0]);self.guard=self._runtime_guard
            self._scope_ready=True
        self.inputs=SnapshotsOriginals(self.root,self.binding,self.run,'primary',self.bound,self.storage_intent,kind='snapshots-input')

    def header_authority(self):
        if getattr(self,'_retirement_authority',None) is not None and self.previous is None:
            need(self.store.read() is None and self._retirement_authority() is True);return True
        expected=self.previous if self.previous is not None else self._initial_header
        need(expected is not None and same(self.store.read(),expected) and expected['runId']==self.run
            and expected['fixtureUrl']==self.fixture_url and same(expected['binding'],self.binding)
            and same(expected['configuration'],self.config));return True

    def public_configuration(self):return deepcopy(self.config)

    def bound(self):
        self.lock.assert_held();need(self._scope_ready and same(self.store.read(),self.previous))
        need(self.guard() is not False);return True

    def save(self):
        need(self.role=='primary');self.bound()
        value=dict(snapshotsFeatureVersion=1,runId=self.run,fixtureUrl=self.fixture_url,binding=self.binding,configuration=self.config,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def load(self):
        self.lock.assert_held();self.previous=self.store.read();self.state=None
        if self.previous is None:return
        value=self.previous;exact(value,{'snapshotsFeatureVersion','runId','fixtureUrl','binding','configuration','payload'})
        need(type(value['snapshotsFeatureVersion']) is int and value['snapshotsFeatureVersion']==1 and value['runId']==self.run
            and value['fixtureUrl']==self.fixture_url and same(value['binding'],self.binding) and same(value['configuration'],self.config))
        rows=unpack(value['payload']);need(len(rows)==1);self.state=rows[0]
        exact(self.state,{'phase','original','inputTicket','domainId','nativeSessionId','objects','current','actions','leases','hostProcess',
            'marker','markerSource','inputs','inputSequence','inputStorage','retained','settingsIndex','filesBinding','docArm','docBinding',
            'consumerArm','consumerBinding','cancelJobs','handoff','handoffs','captureTicket','restoreId','restoreSha256','quiet','cleanupStages','capturePath','settingsIntent','filesIndex','partial'})
        need(type(self.state['partial']) is bool and self.state['domainId']==self.config['domainId'])
        need(self.state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned','partial-cleaned','retiring')
            and self.state['objects']==[] and integer(self.state['inputSequence'],0,1024)
            and type(self.state['actions']) is list and len(self.state['actions'])<=32
            and type(self.state['handoffs']) is list and len(self.state['handoffs'])<=4
            and type(self.state['cancelJobs']) is list and len(self.state['cancelJobs'])<=2)
        # Replaying immutable host originals grants no native/UI authority.
        # It establishes the exact pending/handoff floor before any runtime or
        # system-context factory can be selected from this fresh locked state.
        self._scope_ready=False
        host=SnapshotsOriginals(self.root,self.binding,self.run,'primary',self.header_authority,lambda *_:need(False),kind='snapshots-input')
        originals=host.restore(self.state['inputs'],self.state['inputSequence'])
        if originals:
            first=originals[0]['snapshotsBaseline']
            need(same(self.state['original'],dict(avatar=dict(source=dict(cameraMode=first['avatar']['source']['cameraMode'])))))
            if self.state['settingsIndex'] is not None:
                settings=originals[self.state['settingsIndex']-1]['snapshotsSettingsCaptured']
                need(settings['runId']==self.run and settings['source']['openedEpochMs']>=self.state['settingsIntent']['requestedEpochMs'])
            if self.state['filesIndex'] is not None:
                need(same(self.state['filesBinding'],originals[self.state['filesIndex']-1]['snapshotsFilesPlanned']))
        else:need(self.state['phase'] in ('preparing','partial-cleaned') and self.state['partial'])
        if self.state['handoff'] is not None:self.check_handoff(self.state['handoff'],originals)
        self.check_pending(originals)
        pending=self.state['current']['pending'] if self.state['current'] is not None else None
        self._system_scope=None
        if pending is not None and pending['kind']=='background':
            self.guard=self.background_guard;self._scope_ready=True
        elif self.state['handoff'] is not None:
            handoff=self.state['handoff']
            self._system_scope=self.adapter._snapshot_system_context(self.selector,self.binding,handoff['resolution'],self.header_authority)
            self.guard=self._system_scope.guard;self._scope_ready=True
        else:self.foreground()
        self.bound()

    def check_pending(self,originals):
        from overte_phone_snapshot_handoff_input import plan as check_plan
        current=self.state['current']
        if current is None:return
        exact(current,{'call','pending','phase'});call=current['call']
        exact(call,{'contractVersion','runId','fixtureUrl','ticket','verb','inputs'})
        need(type(call['contractVersion']) is int and call['contractVersion']==VERSION and call['runId']==self.run
            and call['fixtureUrl']==self.fixture_url and type(call['inputs']) is dict)
        identifier(call['ticket']);pending=current['pending']
        if pending is None:return
        need(type(pending) is dict)
        if pending.get('kind')=='background':
            exact(pending,{'kind','stage','before','startedMonotonic'})
            need(call['verb']=='background-resume' and pending['stage'] in ('background-issued','resume-issued')
                and number(pending['startedMonotonic'],0,1e15) and self.state['handoff'] is None)
            from adapters.native_feature_observation import validate as native_packet
            before=pending['before'];native_packet(before,before['requestId'],self.pid,before['capturedEpochMs'])
            return
        if pending.get('kind')=='handoff-start':
            exact(pending,{'kind','id','mode','plan'});identifier(pending['id'])
            need(self.state['handoff'] is None and pending['mode'] in ('share','document')
                and call['verb']==('share-open' if pending['mode']=='share' else 'save-picker-open'))
        else:
            exact(pending,{'kind','plan','binding','issued'});handoff=self.state['handoff']
            need(pending['kind']=='handoff-input' and pending['issued'] is True and handoff is not None
                and same(pending['binding'],handoff['binding'])
                and same(pending['plan'],originals[handoff['sourceIndex']-1]['handoffPlan']))
        value=pending['plan'];check_plan(value,self.pid,value['original']['capturedEpochMs'])
        inputs=[row['snapshotInput'] for row in originals if row.get('snapshotInput',{}).get('request',{}).get('commandId')==value['request']['commandId']]
        need(len(inputs)==1 and same(inputs[0],value))

    def check_handoff(self,handoff,originals):
        exact(handoff,{'id','kind','resolution','binding','sourceIndex'})
        need(handoff['kind'] in ('share','document') and integer(handoff['sourceIndex'],1,len(originals)))
        original=originals[handoff['sourceIndex']-1]['handoffStart']
        request=dict(schemaVersion=1,commandId=original['requestId'],action='phone-snapshot-handoff',runId=self.run,handoffId=handoff['id'],operation='start')
        handoff_control(original,request,self.pid,original['capturedEpochMs'])
        need(same(handoff_binding(original),handoff['binding']))
        from overte_phone_snapshot_handoff_input import plan as check_plan
        planned=originals[handoff['sourceIndex']-1]['handoffPlan'];check_plan(planned,self.pid,planned['original']['capturedEpochMs'])
        need(planned['request']['controlId'].startswith('snapshot.'+('share' if handoff['kind']=='share' else 'save')+'.'))

    def input_originals(self):
        # Immutable host history never supplies a current product measurement.
        # Keep every file check and bracket the complete pass with current
        # target continuity rather than issuing a target RPC per old reference.
        self.bound()
        host=SnapshotsOriginals(self.root,self.binding,self.run,'primary',self.header_authority,lambda *_:need(False),kind='snapshots-input')
        frames=host.restore(self.state['inputs'],self.state['inputSequence'])
        self.bound();return frames

    def original(self):
        frames=self.input_originals();need(frames and 'snapshotsBaseline' in frames[0])
        baseline=deepcopy(frames[0]['snapshotsBaseline'])
        if self.state['settingsIndex'] is not None:baseline['settings']=deepcopy(frames[self.state['settingsIndex']-1]['snapshotsSettingsCaptured'])
        if self.state['filesIndex'] is not None:baseline['filesBinding']=deepcopy(frames[self.state['filesIndex']-1]['snapshotsFilesPlanned'])
        return baseline

    def archive_input(self,frame):
        need(self.role=='primary');return super().archive_input(frame)

    def input_intent(self,value):
        self.active();self.archive_input(dict(snapshotInput=deepcopy(value),provider=self.phase.status()));return True

    def login_intent(self,stage,original,control):
        self.active();self.archive_input(dict(accountInput=dict(stage=stage,original=deepcopy(original),control=control)));return True

    def controls(self):return self.adapter._snapshot_normal_controls(self.selector,self.input_intent,read_only=False)

    def files(self):
        return self.adapter._snapshot_capture_files(self.selector,self.root/'snapshots-primary-files',
            self.store.path.with_name('phone-snapshots-files-owner.json'),read_only=False)

    def observer_files(self,role,*,handoff_source=None):
        need(role in ('primary','actor'));root=self.root/('snapshots-'+role+'-files-observer');root.mkdir(mode=0o700,exist_ok=True)
        owner=self.store.path.with_name('phone-snapshots-'+role+'-files-observer.json')
        if handoff_source is None:result=self.adapter._snapshot_capture_files(self.selector,root,owner,read_only=True)
        else:
            handoff=self.state['handoff'];need(handoff is not None)
            result=self.adapter._snapshot_system_files(self.selector,root,owner,self.binding,handoff['resolution'],self.header_authority,handoff_source)
        result.attach(self.state['filesBinding']);return result

    def documents(self,*,read_only=True):
        need(self.state['docArm'] is not None)
        if read_only and self.state['handoff'] is not None:
            return self.adapter._snapshot_system_documents(self.selector,self.run,self.state['docArm'],self.config['receiverApkSha256'],
                self.binding,self.state['handoff']['resolution'],self.header_authority,binding=self.state['docBinding'])
        return self.adapter._snapshot_documents(self.selector,self.run,self.state['docArm'],self.config['receiverApkSha256'],self.binding,
            self.original()['documentResolution'],self.header_authority,read_only=read_only,binding=self.state['docBinding'])

    def consumer(self,*,read_only=True):
        need(self.state['consumerArm'] is not None)
        if self.state['handoff'] is None:
            return self.adapter._snapshot_consumer(self.selector,self.run,self.state['consumerArm'],self.config['receiverApkSha256'],
                read_only=read_only,binding=self.state['consumerBinding'])
        return self.adapter._snapshot_system_consumer(self.selector,self.run,self.state['consumerArm'],self.config['receiverApkSha256'],
            self.binding,self.state['handoff']['resolution'],self.header_authority,read_only=read_only,binding=self.state['consumerBinding'])

    def settings(self,*,read_only=True):
        result=self.adapter._snapshot_settings(self.selector,read_only=read_only)
        result.restore_source(self.original()['settings']);return result

    def initialize(self):
        need(self.role=='primary' and (self.state is None or self.state['phase']=='preparing'))
        phase=self.phase.read();need(phase['verb']=='baseline')
        if self.state is None:
            self.state=dict(phase='preparing',original=None,inputTicket=phase['ticket'],domainId=self.config['domainId'],nativeSessionId=None,objects=[],
                current=dict(call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,ticket=phase['ticket'],verb='baseline',inputs={}),pending=None,phase='issuing'),
                actions=[],leases=dict(tablet=False,menu=False,address=False,picker=False),hostProcess=dict(pid=os.getpid(),start=start_identity(os.getpid())),
                marker=None,markerSource=None,inputs=[],inputSequence=0,inputStorage=None,retained=[],settingsIndex=None,filesBinding=None,
                docArm=None,docBinding=None,consumerArm=None,consumerBinding=None,cancelJobs=[],handoff=None,handoffs=[],captureTicket=None,restoreId='',restoreSha256='',quiet=[],cleanupStages={},capturePath=None,settingsIntent=None,filesIndex=None,partial=True)
            self.save()
        self.recover_archive()
        if self.state['inputs']:
            self.prepare_owned_leases();self.state.update(phase='baseline',current=None,partial=False);self.save();return
        need(PrivateFeatureState(self.store.path.with_name('phone-snapshot-foundation.json')).read() is None)
        # Foundation owns a separate completed scope; no extended owner adopts
        # its files, settings lease or original capture history.
        group,_selected=self.adapter._snapshot_measurements(self.selector).read(self.run)
        source=group['snapshot']['source'];need(PhoneSnapshotFoundation.idle(group['snapshot']))
        entities=self.adapter._create_source(self.selector,read_only=True).read(self.run)
        need(entities['source']['connected'] and entities['source']['domainId']==self.config['domainId'] and entities['source']['canRez']
            and not entities['source']['entities'] and entities['source']['sessionId'] is not None)
        native=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
        need(not native['account']['loggedIn'] and native['account']['observation']['credentialActive']
            and native['account']['principalSha256']==hashlib.sha256(b'').hexdigest()
            and not any(native['account']['observation'][key] for key in ('loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent'))
            and native['account']['observation']['endpointSha256'] in {hashlib.sha256(value.encode()).hexdigest() for value in (self.phase.provider()['origin'],self.phase.provider()['origin']+'/')})
        avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read();need(avatar['source']['cameraMode'] in MODES)
        touch=self.adapter._touch_state_observer(self.selector,read_only=True).read();touch_released(touch)
        world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True)
        platform=self.adapter._snapshot_platform(self.selector).read();resolution=self.adapter._snapshot_share_resolution(self.selector).read()
        document_resolution=self.adapter._snapshot_document_resolution(self.selector).read() if platform['source']['saveBackend']=='document-picker' else None
        self.state.update(original=dict(avatar=dict(source=dict(cameraMode=avatar['source']['cameraMode']))),nativeSessionId=entities['source']['sessionId'])
        self.save()
        # All readonly preflight originals precede any own lease. A failed read
        # leaves no possibly adopted foreign UI or settings responsibility.
        original=dict(group=group,entities=entities,native=native,avatar=avatar,touch=touch,world=world,platform=platform,resolution=resolution,
            documentResolution=document_resolution)
        self.archive_input(dict(snapshotsBaseline=original));self.prepare_owned_leases()
        self.state.update(phase='baseline',current=None,partial=False);self.save()

    def prepare_owned_leases(self):
        need(self.state['phase'] in ('preparing','cleaning'))
        originals=self.input_originals()
        if self.state['settingsIndex'] is None:
            saved=[index for index,row in enumerate(originals,1) if 'snapshotsSettingsCaptured' in row];need(len(saved)<=1)
            if saved:self.state['settingsIndex']=saved[0];self.save()
            else:
                if self.state['settingsIntent'] is None:
                    self.state['settingsIntent']=dict(requestedEpochMs=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms(),issued=True);self.save()
                settings=self.adapter._snapshot_settings(self.selector,read_only=False).request(self.run,'capture')
                need(settings['source']['openedEpochMs']>=self.state['settingsIntent']['requestedEpochMs']
                    and settings['source']['currentSha256']==settings['source']['originalSha256'])
                self.state['settingsIndex']=self.archive_input(dict(snapshotsSettingsCaptured=settings));self.save()
        if self.state['filesIndex'] is None:
            saved=[index for index,row in enumerate(originals,1) if 'snapshotsFilesPlanned' in row];need(len(saved)<=1)
            if saved:
                self.state.update(filesIndex=saved[0],filesBinding=deepcopy(originals[saved[0]-1]['snapshotsFilesPlanned']));self.save()
            else:
                files=self.files();files.plan(self.run,'e2e-'+self.run);binding=files.binding();need(not files.inventory()['files'])
                index=self.archive_input(dict(snapshotsFilesPlanned=binding));self.state.update(filesIndex=index,filesBinding=binding);self.save()
        self.prepare_documents()

    def prepare_documents(self):
        if self.original()['documentResolution'] is None:return
        if self.state['docArm'] is None:self.state['docArm']=uuid.uuid4().hex;self.save()
        reader=self.documents(read_only=False)
        if self.state['docBinding'] is None:
            reader.control('arm');original=reader.observe();self.archive_input(dict(documentsArmed=original))
            self.state['docBinding']=reader.binding();self.save()
        else:reader.observe()

    def wait_original(self,read,predicate,*,seconds=5):
        started=previous=self.monotonic();need(number(started,0,1e15))
        for attempt in range(201):
            value=read();now=self.monotonic();need(number(now,previous,1e15) and now-started<seconds);previous=now
            if predicate(value):return value
            need(attempt<200);self.sleep(.1)
        need(False)

    def account(self,*,logged_in):
        packet=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
        value=packet['account'];observation=value['observation'];baseline=self.original()['native']['account']
        account_advance(baseline['observation'],value)
        need(value['loggedIn'] is logged_in and observation['endpointSha256']==baseline['observation']['endpointSha256']
            and not observation['loginPending'] and not observation['refreshPending'])
        if logged_in:
            need(value['principalSha256']==hashlib.sha256(('e2e-'+self.run).encode()).hexdigest() and observation['credentialActive'] and observation['tokenValid'])
        else:need(value['principalSha256']==baseline['principalSha256'] and observation['credentialActive'] and not any(observation[key] for key in ('tokenPresent','tokenValid','refreshPresent')))
        return packet

    def validate_account(self,account,verb,epoch):
        from adapters.native_account_observation import validate as account_packet
        account_packet(account,epoch)
        baseline=self.original()['native']['account'];source=account['observation']
        account_advance(baseline['observation'],account)
        need(source['credentialActive'] and source['endpointPresent']
            and source['endpointSha256']==baseline['observation']['endpointSha256']
            and not source['loginPending'] and not source['refreshPending'])
        logged_in=verb not in ('baseline','cleanup')
        principal=hashlib.sha256(('e2e-'+self.run).encode()).hexdigest() if logged_in else baseline['principalSha256']
        need(account['loggedIn'] is logged_in and account['principalSha256']==principal)
        if logged_in:need(source['tokenPresent'] and source['tokenValid'])
        else:need(not source['tokenPresent'] and not source['tokenValid'] and not source['refreshPresent'])
        return account

    def login(self):
        origin=self.phase.provider()['origin'];ui=self.adapter._login_controls(self.selector,self.login_intent,self.run,origin)
        ui.open();credentials=self.phase.client.request('/runs/'+self.run+'/snapshot-upload/credentials')
        try:ui.fill(credentials);ui.submit()
        finally:
            if type(credentials) is dict:credentials.clear()
            credentials=None
        def complete(packet):
            account=packet['account'];observation=account['observation']
            return account['loggedIn'] and account['principalSha256']==hashlib.sha256(('e2e-'+self.run).encode()).hexdigest() and observation['tokenValid'] and not observation['loginPending']
        native=self.wait_original(lambda:self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True),complete)
        baseline=self.original()['native']['account']['observation']
        need(any(row['kind']=='profile-reply' and row['sequence']>baseline['eventSequence'] and row['httpStatus']==200
            and row['networkError']==0 and not row['transportRejected'] and not row['timedOut'] for row in native['account']['observation']['events']))
        ui.cancel();self.archive_input(dict(snapshotLogin=native));self.account(logged_in=True)

    def normal_system_intent(self,value):
        self.active();self.archive_input(dict(snapshotSystemInput=deepcopy(value),provider=self.phase.status()));return True

    def handoff_ui(self):
        handoff=self.state['handoff'];need(handoff is not None)
        factory=self.adapter._snapshot_share_ui if handoff['kind']=='share' else self.adapter._snapshot_document_ui
        return factory(self.selector,self.binding,handoff['resolution'],self.normal_system_intent,self.header_authority)

    def begin_handoff(self,kind,path):
        need(kind in ('share','document') and self.state['handoff'] is None and len(self.state['handoffs'])<4)
        resolution=self.original()['resolution' if kind=='share' else 'documentResolution'];need(resolution is not None)
        controls=self.controls();plan=controls.plan_image_action('share' if kind=='share' else 'save',path)
        id=uuid.uuid4().hex
        # Native start does not deliver input. Its real original binding is
        # archived before the fixed ordinary command may leave the foreground.
        self.state['current']['pending']=dict(kind='handoff-start',id=id,mode=kind,plan=deepcopy(plan));self.save()
        original=self.adapter._snapshot_handoff_control(self.selector).request(self.run,'start',id)
        index=self.archive_input(dict(handoffStart=original,handoffPlan=deepcopy(plan)))
        self.state['handoff']=dict(id=id,kind=kind,resolution=deepcopy(resolution),binding=handoff_binding(original),sourceIndex=index)
        self.state['current']['pending']=None;self.save()
        self._system_scope=self.adapter._snapshot_system_context(self.selector,self.binding,resolution,self.header_authority)
        self.guard=self._system_scope.guard
        def admit(value,owner):
            need(self.state['current']['pending'] is None and same(owner,self.state['handoff']['binding']) and same(value,plan))
            self.state['current']['pending']=dict(kind='handoff-input',plan=deepcopy(value),binding=deepcopy(owner),issued=True);self.save();return True
        delivery=self.adapter._snapshot_handoff_input(self.selector,self.binding,resolution,self.header_authority,self.state['handoff']['binding'],admit)
        receipt=delivery.deliver(plan);self.archive_input(dict(snapshotHandoffInput=plan,receipt=receipt))
        self.state['current']['pending']=None;self.save()
        expected=resolution['component'];self.wait_original(self.handoff_ui().capture,lambda row:row['component']==expected)

    def finish_handoff(self):
        handoff=deepcopy(self.state['handoff']);need(handoff is not None)
        actual=self.handoff_ui().capture();need(actual['component'].split('/')[0]=='io.github.noah_be.overte.phone')
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.binding));self.guard=guard
        original=self.adapter._snapshot_handoff_control(self.selector).request(self.run,'retire',handoff['id'])
        need(original['source']['retired'] and not original['source']['timerActive'])
        self.archive_input(dict(handoffEnd=original,returnedSystem=actual));self.state['handoffs'].append(dict(handoff,retirementIndex=self.state['inputSequence']))
        self.state['handoff']=None;self.save();self._system_scope=None

    def capture_path(self):
        if self.state['handoff'] is not None:
            saved=self.state['capturePath'];need(saved is not None)
            originals=self.input_originals()
            actual=originals[saved['sourceIndex']-1]['snapshotCapturePath']
            need(any(row['runId']==self.run and row['path']==saved['path'] and row['closed'] and not row['absent'] for row in actual['rows']))
            return saved['path']
        inventory=self.files().inventory();rows=[row for row in inventory['rows'] if row['runId']==self.run and not row['absent']]
        need(len(rows)==1 and rows[0]['closed'] and rows[0]['captureId'])
        if self.state['capturePath'] is None:
            index=self.archive_input(dict(snapshotCapturePath=inventory));self.state['capturePath']=dict(path=rows[0]['path'],sourceIndex=index);self.save()
        else:need(rows[0]['path']==self.state['capturePath']['path'])
        return rows[0]['path']

    def cancel(self,*,cleanup=False):
        need(len(self.state['cancelJobs'])<2)
        controls=self.controls();controls.configure('animated','png');request=controls.plan_cancel()
        job=dict(id=request['commandId'],sourceIndex=None,retirementIndex=None)
        self.state['cancelJobs'].append(job);self.save()
        reader=self.adapter._snapshot_cancel(self.selector,read_only=False)
        packet=reader.request(self.run,job['id'],'start',request)
        packet=self.wait_original(lambda:reader.request(self.run,job['id'],'observe'),lambda value:value['source']['phase'] in ('complete','failed'))
        need(packet['source']['phase']=='complete' and packet['source']['request'])
        job['sourceIndex']=self.archive_input(dict(snapshotCancel=packet,cleanup=cleanup));self.save()
        return packet

    def close_cancels(self):
        originals=self.input_originals()
        for job in self.state['cancelJobs']:
            need(job['sourceIndex'] is not None)
            original=originals[job['sourceIndex']-1]['snapshotCancel'];caller=original['source']['cancelled']['native']['scriptHistory']['events'][-1]['caller']
            work=self.adapter._script_work(self.selector,read_only=True).read(caller['manager']['instance'])
            selected=script_scope(work,caller['compilation'])
            need(not selected['timers'] and not selected['unknownTimers'] and not selected['evaluating']
                and all(selected[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
            packet=self.adapter._snapshot_cancel(self.selector,read_only=False).request(self.run,job['id'],'retire',closed_read_work_request_id=work['requestId'])
            index=self.archive_input(dict(snapshotCancelRetired=packet));job['retirementIndex']=index;self.save()

    def arm_consumer(self):
        if self.state['consumerArm'] is None:self.state['consumerArm']=uuid.uuid4().hex;self.save()
        if self.state['consumerBinding'] is None:
            reader=self.consumer(read_only=False);reader.control('arm');original=reader.observe()
            self.archive_input(dict(consumerArmed=original));self.state['consumerBinding']=reader.binding();self.save()

    def act(self,value):
        call=deepcopy(arguments('feature.snapshots.act',value));need(self.role=='primary' and call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None and self.state['phase'] not in ('cleaning','cleaned','partial-cleaned','retiring'))
            found=[row for row in self.state['actions'] if row['ticket']==call['ticket']]
            if found:need(len(found)==1 and found[0]['phase']=='acknowledged' and same(found[0]['call'],call));return {'performed':True}
            need(self.state['current'] is None);self.state.update(phase='acting',current=dict(call=call,pending=None,phase='issuing'));self.save();self.active()
            verb=call['verb'];ui=None if self.state['handoff'] is not None else self.controls()
            if verb=='open':
                self.login();self.surface().select_camera('first person look at');self.state['leases']['tablet']=True;self.save();ui.open();ui.name('e2e-'+self.run)
            elif verb=='capture-cancel':self.cancel()
            elif verb=='capture':
                self.marker('prepare');ui.configure(call['inputs']['mode'],call['inputs']['format'])
                self.state['captureTicket']=call['ticket'];self.save();ui.input('snapshot.capture')
            elif verb=='save-picker-open':self.begin_handoff('document',self.capture_path())
            elif verb=='save-picker-cancel':self.handoff_ui().cancel();self.finish_handoff()
            elif verb=='save':
                if self.original()['platform']['source']['saveBackend']=='document-picker':
                    self.handoff_ui().select_root();self.handoff_ui().save(self.capture_path().rsplit('/',1)[-1]);self.finish_handoff()
                else:ui.image_action('save',self.capture_path())
            elif verb=='share-open':self.arm_consumer();self.begin_handoff('share',self.capture_path())
            elif verb=='share-cancel':self.handoff_ui().back();self.finish_handoff()
            elif verb=='share-select-owned':
                consumer=self.consumer(read_only=True);actual=consumer.observe();self.handoff_ui().select_receiver(consumer.binding()['installed'])
                self.wait_original(consumer.observe,lambda row:row['phase']=='complete' and row['originalClosed'])
                self.handoff_ui().back(receiver=True);self.finish_handoff()
            elif verb in ('upload-fail','upload'):ui.image_action('upload',self.capture_path())
            elif verb=='background-resume':self.marker('prepare');self.background()
            elif verb=='close':ui.close();self.state['leases']['tablet']=False;self.save()
            else:need(False) # Unsupported required backend actions remain red.
            self.active();self.state['actions'].append(dict(call=call,ticket=call['ticket'],phase='acknowledged'))
            self.state.update(phase='active',current=None);self.save();return {'performed':True}

    def observe(self,value):
        from overte_phone_snapshots_role import PhoneSnapshotsRole
        call=arguments('feature.snapshots.observe',value);need(call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None or self.state['phase']=='preparing':self.initialize()
            need(self.state['phase'] in ('baseline','active','cleaned'))
            for attempt in range(51):
                role=PhoneSnapshotsRole(self,self.role)
                if role.state['phase']=='reading':role.recover()
                try:return role.read(call['afterSequence'])
                except SnapshotPending:need(attempt<50);self.sleep(.1)
            need(False)
    def background_guard(self):
        self.header_authority()
        state=self.state if self.state is not None else self._initial_state
        pending=state['current']['pending'];need(pending['kind']=='background')
        status=self.adapter._graphics_lifecycle_status(self.selector,self.binding)
        exact(status,{'binding','foreground','running','appState'})
        need(same(status['binding'],self.binding) and status['running'] and status['appState'] in (2,3,4)
            and status['foreground']==(status['appState']==4))
        now=self.monotonic();need(number(now,pending['startedMonotonic'],1e15) and now-pending['startedMonotonic']<20)
        return True

    def foreground(self):
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.binding));self.guard=guard;self._scope_ready=True;self.bound()

    def background(self,*,cleanup=False):
        need(self.state['handoff'] is None);current=self.state['current'];pending=current['pending']
        if pending is None:
            need(not cleanup)
            before=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
            current['pending']=dict(kind='background',stage='background-issued',before=deepcopy(before),startedMonotonic=self.monotonic())
            self.save();self.guard=self.background_guard
            self.adapter.invoke(self.selector,'lifecycle.background',{})
        else:need(pending['kind']=='background');self.guard=self.background_guard
        pending=current['pending'];before=pending['before']
        if pending['stage']=='background-issued':
            status=self.adapter._graphics_lifecycle_status(self.selector,self.binding)
            if cleanup and status['foreground']:
                self.foreground()
                actual=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
                need(actual['instance']==before['instance'] and actual['processId']==before['processId']
                    and all(actual['lifecycle'][key]>=value for key,value in before['lifecycle'].items()))
                self.archive_input(dict(snapshotBackgroundUncertain=deepcopy(pending),actual=actual))
                current['pending']=None;self.save();return
            status=self.wait_original(lambda:self.adapter._graphics_lifecycle_status(self.selector,self.binding),lambda row:row['foreground'] is False)
            self.archive_input(dict(snapshotBackground=status,nativeBefore=before))
            pending['stage']='resume-issued';self.save()
            self.adapter.invoke(self.selector,'app.launch',{})
        need(pending['stage']=='resume-issued')
        self.wait_original(lambda:self.adapter._graphics_lifecycle_status(self.selector,self.binding),lambda row:row['foreground'] is True)
        self.foreground()
        after=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
        need(after['instance']==before['instance'] and after['processId']==before['processId']
            and after['lifecycle']['launches']==before['lifecycle']['launches']
            and after['lifecycle']['backgrounds']>before['lifecycle']['backgrounds']
            and after['lifecycle']['activations']>before['lifecycle']['activations'])
        self.archive_input(dict(snapshotResumed=after));current['pending']=None;self.save()

    def queued_idle(self,group,packet,*,previous=None):
        epoch=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms()
        selected=validate_group(group,run=self.run,pid=self.pid,epoch=epoch)
        initial=self.original()['group']
        baseline=validate_group(initial,run=self.run,pid=self.pid,epoch=initial['rootsAfter']['capturedEpochMs'])
        need(same(selected,baseline) and packet['instance']==group['script']['instance'])
        request=dict(schemaVersion=1,commandId=packet['requestId'],action='feature-script-work-observe',managerInstance=selected['manager']['instance'])
        validate_work(packet,request,self.pid,epoch,previous=previous)
        need(same(packet['source']['manager'],selected['manager']) and same(packet['source']['code'],selected['code']))
        selected_work=script_scope(packet,selected['compilation'])
        need(not selected_work['evaluating'] and not selected_work['timers'] and not selected_work['unknownTimers']
            and all(selected_work[key]==0 for key in ('signalCallbacks','timerCallbacks','unknownSignalCallbacks','unknownTimerCallbacks')))
        return packet

    def quiet_work_floor(self):
        if not self.state['quiet']:return None
        proof=self.state['quiet'][-1];need(proof['sources'])
        originals=self.input_originals()
        return originals[proof['sources'][-1]-1]['snapshotQuiet']['work']

    def quiet(self,label):
        need(label in ('before-restoration','after-restoration') and self.state['handoff'] is None)
        reader=self.adapter._snapshot_measurements(self.selector)
        started=previous=self.monotonic();need(number(started,0,1e15));first=last=None;digest=None;indices=[];previous_work=self.quiet_work_floor()
        for attempt in range(201):
            group,selected=reader.read(self.run);need(PhoneSnapshotFoundation.idle(group['snapshot']))
            manager=selected['manager']['instance'];work=self.adapter._script_work(self.selector,read_only=True).read(manager)
            self.queued_idle(group,work,previous=previous_work);previous_work=deepcopy(work)
            upload=self.adapter._snapshot_upload_source(self.selector).read(self.run);upload_retired(upload['source'])
            provider=self.phase.provider();need(provider['inflight']==0 and not provider['held'] and provider['stories']==0)
            source=group['snapshot']['source'];fingerprint=hashlib.sha256(canonical(dict(history=source['history'],script=source['scriptHistory'],
                exports=source['androidExport']['events'],uploadEvents=upload['source']['events'],providerRequests=provider['requests']))).hexdigest()
            now=self.monotonic();need(number(now,previous,1e15) and now-started<20);previous=now
            if digest is None:digest=fingerprint
            else:need(digest==fingerprint)
            epoch=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms()
            for packet in (group['rootsBefore'],group['rootsAfter'],group['script'],group['snapshot'],work,upload,provider):
                fresh(packet['capturedEpochMs'],epoch)
            index=self.archive_input(dict(snapshotQuiet=dict(label=label,group=group,work=work,upload=upload,provider=provider,
                measuredMonotonic=now,fingerprint=fingerprint)))
            indices.append(index)
            # Real monotone time, contiguous current samples. Slow sources may
            # restart the absence interval, never shorten its three seconds.
            if first is None or last is not None and now-last>1.5:first=now
            last=now
            if now-first>=3 and len(indices)>=2:
                return dict(label=label,startMonotonic=first,endMonotonic=now,sources=indices,fingerprint=digest)
            self.sleep(.1)
        raise NativeUIError('Original Snapshot work never reached a contiguous quiet window')

    def recover_handoff_input(self):
        from overte_phone_snapshot_handoff_input import plan as check_plan
        pending=self.state['current']['pending']
        if pending is None:return
        if pending['kind']=='background':self.background(cleanup=True);return
        if pending['kind']=='handoff-start':
            exact(pending,{'kind','id','mode','plan'});need(self.state['handoff'] is None and pending['mode'] in ('share','document'))
            check_plan(pending['plan'],self.pid,pending['plan']['original']['capturedEpochMs'])
            # Observe an already created original job. Never replay start or the
            # unadmitted Save/Share click after an uncertain start return.
            original=self.adapter._snapshot_handoff_control(self.selector,read_only=True).request(self.run,'observe',pending['id'])
            index=self.archive_input(dict(handoffStart=original,handoffPlan=pending['plan'],recoveredStart=True))
            resolution=self.original()['resolution' if pending['mode']=='share' else 'documentResolution']
            self.state['handoff']=dict(id=pending['id'],kind=pending['mode'],resolution=resolution,binding=handoff_binding(original),sourceIndex=index)
            self.state['current']['pending']=None;self.save();return
        exact(pending,{'kind','plan','binding','issued'})
        need(pending['kind']=='handoff-input' and self.state['handoff'] is not None and pending['issued'] is True)
        handoff=self.state['handoff'];need(same(pending['binding'],handoff['binding']))
        originals=self.input_originals()
        need(same(pending['plan'],originals[handoff['sourceIndex']-1]['handoffPlan']))
        check_plan(pending['plan'],self.pid,pending['plan']['original']['capturedEpochMs'])
        reader=self.adapter._snapshot_handoff_input(self.selector,self.binding,handoff['resolution'],self.header_authority,
            handoff['binding'],lambda *_:need(False),read_only=True)
        original=reader.observe(pending['plan']);self.archive_input(dict(snapshotHandoffRecovered=original,plan=pending['plan']))
        self.state['current']['pending']=None;self.save()

    def cleanup(self,value):
        call=arguments('feature.snapshots.cleanup',value);need(self.role=='primary' and call['runId']==self.run)
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load();need(self.state is not None);phase=self.phase.read();need(phase['verb']=='cleanup')
            self.recover_archive()
            if self.state['phase']=='partial-cleaned':self.partial_restored();return {'performed':True}
            if self.state['phase']=='cleaned':self.restored();return {'performed':True}
            if self.state['phase']=='preparing' and not self.state['inputs']:
                need(self.state['settingsIntent'] is None and self.state['filesBinding'] is None and self.state['docArm'] is None)
                self.state.update(phase='partial-cleaned',current=None);self.save();self.partial_restored();return {'performed':True}
            if self.state['current'] is not None:
                if self.state['current']['pending'] is not None:self.recover_handoff_input()
                self.state['retained'].append(deepcopy(self.state['current']))
            self.state.update(phase='cleaning',current=dict(call=dict(contractVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,
                ticket=phase['ticket'],verb='cleanup',inputs={}),pending=None,phase='issuing'));self.save()
            if self.state['partial']:self.prepare_owned_leases()
            stages=self.state['cleanupStages']
            if self.state['handoff'] is not None:
                system=self.handoff_ui().capture();primary=system['component'].split('/')[0]=='io.github.noah_be.overte.phone'
                if not primary:
                    if self.state['handoff']['kind']=='document':self.handoff_ui().cancel()
                    else:self.handoff_ui().back(receiver=system['component'].startswith('org.overte.e2e.snapshotreceiver/'))
                self.finish_handoff()
            ui=self.controls();source=self.adapter._snapshot_source(self.selector).read(self.run)
            review=source['source']['review']['review']
            if self.state['partial']:need(review is None and not self.state['actions'] and not self.state['cancelJobs'])
            if review is not None:
                for key,id in (('uploadPath','snapshot.cancel-upload'),('exportTicket','snapshot.cancel-export'),('capturing','snapshot.cancel-capture')):
                    if review[key]:ui.input(id)
            provider=self.phase.provider()
            if provider['stories']:
                # Normal takeSnapshot deletes this owned previous story before
                # its unchanged 350ms capture timer; normal Cancel prevents a
                # new allocation. The original DELETE must actually complete.
                if 'storyCancel' not in stages:
                    ui.open();self.state['leases']['tablet']=True;self.save()
                    packet=self.cancel(cleanup=True);stages['storyCancel']=packet['source']['job'];self.save()
                self.wait_original(self.phase.provider,lambda row:row['inflight']==0 and row['stories']==0)
            if 'closed' not in stages:
                if self.state['leases']['tablet']:ui.close()
                self.state['leases']['tablet']=False;stages['closed']=True;self.save()
            self.close_cancels()
            if not self.state['quiet']:
                self.state['quiet']=[self.quiet('before-restoration')];self.save()
            readbacks=self.adapter._snapshot_readbacks(self.selector,read_only=False)
            observed=readbacks.request(self.run)['source']['source']
            for job in observed.get('jobs',[]):
                if job['phase'] in ('queued','reading'):readbacks.request(self.run,'cancel',resource_id=job['id'])
            for row in observed.get('osDestinations',{}).get('rows',[]):
                key='destination-'+row['request']
                if key not in stages:stages[key]=uuid.uuid4().hex;self.save()
                if not row['deleteIssued']:readbacks.request(self.run,'remove-destination',row['request'],stages[key])
            for row in observed.get('shareGrants',{}).get('rows',[]):
                key='grant-'+row['request']
                if key not in stages:stages[key]=uuid.uuid4().hex;self.save()
                if not row['revokeIssued']:readbacks.request(self.run,'revoke-share',row['request'],stages[key])
            if observed.get('initialized') is False:
                from overte_phone_snapshots_measurements import no_owned_exports
                source=self.adapter._snapshot_source(self.selector).read(self.run)
                proof=no_owned_exports(source,self.original()['group']['snapshot'],observed)
                self.archive_input(dict(snapshotNoOwnedExports=proof))
            else:
                readbacks.request(self.run,'retire-copies');readbacks.require_os_retired(self.run);readbacks.require_share_retired(self.run)
            if self.state['consumerArm'] is not None:
                consumer=self.consumer(read_only=False);consumer.control('retire')
                self.wait_original(consumer.observe,lambda row:row['retired'] and row['workersTerminated']);consumer.require_retired()
            if self.state['docArm'] is not None:
                documents=self.documents(read_only=False);documents.control('retire')
                self.wait_original(documents.observe,lambda row:row['retired'] and row['workersTerminated']);documents.require_retired()
            self.files().retire()
            for role_name in ('primary','actor'):
                path=self.store.path.with_name('phone-snapshots-'+role_name+'-files-observer.json')
                if PrivateFeatureState(path).read() is not None:self.observer_files(role_name).retire()
            settings=self.settings(read_only=False)
            observed=settings.request(self.run,'observe')
            if not observed['source']['restored']:
                if not self.state['restoreId']:
                    self.state.update(restoreId=uuid.uuid4().hex,restoreSha256=observed['source']['currentSha256']);self.save()
                settings.request(self.run,'restore',restore_id=self.state['restoreId'],expected_sha256=self.state['restoreSha256'])
            settings.request(self.run,'retire')
            account=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)['account']
            if account['loggedIn']:
                self.account(logged_in=True)
                self.adapter._account_menu(self.selector,self.login_intent,self.run,self.phase.provider()['origin']).logout()
            self.account(logged_in=False)
            # Account menu inputs may have opened the tablet during logout.
            if self.state['actions']:
                ui.release()
                if ui.tablet.tablet_visible():ui.close()
            self.state['leases']['tablet']=False;self.save()
            if self.state['marker'] is not None and self.state['marker']['operation']=='prepare':self.marker('release')
            if self.state['actions']:self.surface().select_camera(self.state['original']['avatar']['source']['cameraMode'])
            if len(self.state['quiet'])<2:
                self.state['quiet'].append(self.quiet('after-restoration'));self.save()
            self.state.update(phase='partial-cleaned' if self.state['partial'] else 'cleaned',current=None);self.save()
            self.partial_restored() if self.state['partial'] else self.restored();return {'performed':True}

    def file_inventory(self,files,*,file_owners=None):
        owner=self.files()
        if owner.store.read() is not None:inventory=owner.inventory()
        else:
            need(file_owners is not None and file_owners.get('phone-snapshots-files-owner.json') is not None)
            archived=file_owners['phone-snapshots-files-owner.json'];need(archived['scope']==self.run and archived['retired'] and not archived['readOnly'])
            plans=[row for row in files['plans'] if row['runId']==self.run];need(plans and all(row['sealed'] for row in plans))
            all_files=[]
            for plan in plans:
                scan=owner.transport.scan(plan['prefix']);owner.root(plan,scan);all_files.extend(scan['files'].values())
            need(not all_files and not any(owner.transport.artifacts.glob('snapshot-owned-'+self.run+'-*')))
            inventory=dict(files=all_files,rows=[row for row in files['rows'] if row['runId']==self.run],capturedEpochMs=files['capturedEpochMs'])
        return inventory

    def restored(self,*,snapshot=None,file_owners=None):
        from overte_phone_snapshots_measurements import retired
        need(self.state['phase'] in ('cleaned','partial-cleaned','retiring') and self.state['current'] is None and self.state['inputStorage'] is None
            and self.state['handoff'] is None and not any(self.state['leases'].values()) and len(self.state['quiet'])==2)
        for proof in self.state['quiet']:
            need(proof['endMonotonic']-proof['startMonotonic']>=3 and len(proof['sources'])>=2)
        if snapshot is None:
            group,_=self.adapter._snapshot_measurements(self.selector).read(self.run)
            files=self.adapter._snapshot_capture_file_source(self.selector,read_only=True).request(self.run)['source']
            inventory=self.file_inventory(files,file_owners=file_owners)
            readbacks=self.adapter._snapshot_readbacks(self.selector,read_only=True)
            readback=readbacks.request(self.run)['source']['source']
            if readback.get('initialized') is not False:readback=readbacks.require_retired(self.run)['source']['source']
            upload=self.adapter._snapshot_upload_source(self.selector).read(self.run)['source'];settings=self.settings().request(self.run,'observe')
            consumer=self.consumer().observe() if self.state['consumerArm'] is not None else None
            documents=self.documents().observe() if self.state['docArm'] is not None else None
            avatar=self.adapter._avatar_render_observer(self.selector,read_only=True).read()
            touch=self.adapter._touch_state_observer(self.selector,read_only=True).read()
            world=self.adapter._graphics_subject_observer(self.selector,read_only=True).read(self.run,require_avatar=True)
            native=self.account(logged_in=False)
            selected=validate_group(group,run=self.run,pid=self.pid,epoch=group['rootsAfter']['capturedEpochMs'])
            script_work=self.adapter._script_work(self.selector,read_only=True).read(selected['manager']['instance'])
        else:
            frame=snapshot['measurement'];group=frame['group'];files=frame['captureFiles'];inventory=frame['inventory'];readback=frame['readbacks']
            upload,settings,consumer,documents=(frame[key] for key in ('upload','settings','consumer','documents'))
            avatar=snapshot['avatarAfter'];touch=snapshot['touch'];world=snapshot['world'];native=snapshot['nativeAfter']
            need(native is not None and native['account']['loggedIn'] is False)
            script_work=snapshot['scriptWork']
        epoch=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms()
        self.queued_idle(group,script_work,previous=self.quiet_work_floor())
        capture_facts(self.original()['group'],group,run=self.run,pid=self.pid,epoch=epoch)
        retired(group,files,inventory,readback,upload,settings,run=self.run,epoch=epoch,consumer=consumer,
            consumer_binding=self.state['consumerBinding'],documents=documents,documents_binding=self.state['docBinding'],baseline=self.original()['group'])
        touch_released(touch);need(avatar['source']['cameraMode']==self.original()['avatar']['source']['cameraMode'])
        a={row['id']:row['sha256'] for row in self.original()['world']['source']['scan']['unowned']}
        b={row['id']:row['sha256'] for row in world['source']['scan']['unowned']};need(same(a,b))
        need(not native['account']['loggedIn'] and native['account']['observation']['credentialActive']
            and native['account']['principalSha256']==hashlib.sha256(b'').hexdigest()
            and not any(native['account']['observation'][key] for key in ('loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
        need(all(row['retirementIndex'] for row in self.state['cancelJobs']))
        if self.state['marker'] is not None:
            marker=self.adapter._create_fixture_observer(self.selector,read_only=True).read(self.run) if snapshot is None else snapshot['marker']
            need(marker['source']['phase']=='drained' and not marker['source']['entities'] and marker['source']['retainedObjects']==0)
        return dict(group=group,captureFiles=files,inventory=inventory,readbacks=readback,upload=upload,settings=settings,
            consumer=consumer,documents=documents,avatar=avatar,touch=touch,world=world,native=native,scriptWork=script_work)

    def partial_leases_retired(self,*,file_owners=None):
        from overte_phone_snapshot_settings import validate as settings_packet
        from overte_phone_snapshots_measurements import export_requests,inventory as inventory_rows
        group,_=self.adapter._snapshot_measurements(self.selector).read(self.run)
        need(PhoneSnapshotFoundation.idle(group['snapshot']) and not export_requests(group['snapshot'],self.original()['group']['snapshot']))
        facts=capture_facts(self.original()['group'],group,run=self.run,pid=self.pid,epoch=group['rootsAfter']['capturedEpochMs'])
        need(facts['contexts']==[] and len(self.state['quiet'])==2)
        packet=self.adapter._snapshot_capture_file_source(self.selector,read_only=True).request(self.run);files=packet['source']
        actual=self.file_inventory(files,file_owners=file_owners)
        inventory_rows(actual,files,run=self.run,epoch=packet['capturedEpochMs'])
        need(not actual['files'] and all(row['closed'] and row['absent'] and row['retireId'] for row in actual['rows'])
            and all(plan['sealed'] for plan in files['plans'] if plan['runId']==self.run))
        settings=self.settings().request(self.run,'observe');need(settings['source']['retired'] and settings['source']['restored']
            and not settings['source']['scopePresent'] and settings['source']['closed']
            and settings['source']['currentSerializedBase64']==self.original()['settings']['source']['currentSerializedBase64'])
        documents=self.documents().observe() if self.state['docArm'] is not None else None
        if documents is not None:self.documents().require_retired()
        readbacks=self.adapter._snapshot_readbacks(self.selector,read_only=True).request(self.run)
        if readbacks['source']['source'].get('initialized') is not False:
            source=readbacks['source']['source'];need(source['copiesRetired'] and source['workersTerminated'] and not source['files'])
        current=self.adapter._native_feature_observer(self.selector,read_only=True).read(0,require_account=True)
        selected=validate_group(group,run=self.run,pid=self.pid,epoch=group['rootsAfter']['capturedEpochMs'])
        work=self.adapter._script_work(self.selector,read_only=True).read(selected['manager']['instance'])
        self.queued_idle(group,work,previous=self.quiet_work_floor())
        need(same(current['account']['principalSha256'],self.original()['native']['account']['principalSha256']) and not current['account']['loggedIn'])
        epoch=self.adapter._native_feature_observer(self.selector,read_only=True).clock_ms()
        for row in (group['rootsBefore'],group['rootsAfter'],group['script'],group['snapshot'],packet,settings,readbacks,current):fresh(row['capturedEpochMs'],epoch)
        return dict(group=group,captureFiles=packet,inventory=actual,settings=settings,documents=documents,readbacks=readbacks,native=current,scriptWork=work)

    def partial_restored(self,*,file_owners=None):
        need(self.state['partial'] and self.state['phase']=='partial-cleaned' and self.state['current'] is None
            and self.state['inputStorage'] is None and not self.state['actions'] and not self.state['cancelJobs']
            and self.state['handoff'] is None and self.state['marker'] is None and not any(self.state['leases'].values()))
        provider=self.phase.provider();need(provider['stories']==provider['inflight']==provider['uploads']==0 and not provider['held'] and provider['requests']==[])
        status=self.adapter._graphics_lifecycle_status(self.selector,self.binding)
        need(same(status['binding'],self.binding) and status['running'] and status['foreground'] and status['appState']==4)
        if self.state['inputs']:
            proof=self.partial_leases_retired(file_owners=file_owners);kind='retired-own-leases'
        else:
            need(self.state['settingsIntent'] is None and self.state['settingsIndex'] is None and self.state['filesBinding'] is None
                and self.state['filesIndex'] is None and self.state['docArm'] is None and self.state['consumerArm'] is None)
            names=('phone-snapshots-files-owner.json','phone-snapshots-primary-files-observer.json','phone-snapshots-actor-files-observer.json')
            need(all(PrivateFeatureState(self.store.path.with_name(name)).read() is None for name in names))
            proof=dict(absentOwnHostJournals=list(names));kind='no-issued-lease'
        return dict(snapshotPartialRetirementVersion=1,kind=kind,owner=deepcopy(self.previous),processStatus=status,provider=provider,proof=proof)

    def finalize(self):
        from overte_phone_snapshots_retirement import PhoneSnapshotsRetirement
        return PhoneSnapshotsRetirement(self).finalize()
