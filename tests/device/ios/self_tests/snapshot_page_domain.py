"""Explicit native launcher and UIKit boundaries; real CAS, files and lock.

Only actual normal W3C click delivery changes this modeled Qt route. Observation
requests, ACKs and file pulls cannot open a page or change SwipeView selection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import uuid
from adapters.native_feature_observation import need
from adapters.normal_ui import W3C_ELEMENT,NativeUIError
from ios.adapters.snapshot_page_runtime import IOSSnapshotPageRuntime
from ios.self_tests.snapshot_capture_domain import SnapshotCaptureDomain,ClockedOwner,RUN
from ios.self_tests.test_ios_snapshot_work import packet as work_packet,timer


class SnapshotPageDomain:
    def __init__(self,case,*,count=3,index=2,snapshot_page=1,route='launcher',capture=None):
        self.capture=SnapshotCaptureDomain(case) if capture is None else capture;self.ctx=self.capture.ctx;self.f=self.capture.f
        self.shown=False;self.route=route;self.count=count;self.index=index;self.snapshot_page=snapshot_page
        self.root=str(uuid.uuid4());self.generation=0;self.tokens={};self.elements={};self.clicks=[];self.requests=[]
        self.ignore=set();self.lose=set();self.swap_token=None;self.swap_root=None;self.held_work=False;self.work_cursor=1;self.call=0
        self.work_original=work_packet();row=self.work_original['source']['workers'][0]
        for state in (row['state'],row['events'][0]['state'],row['latest']['state']):state['open']=route=='snapshot'
        original_observed=self.f.input_native.observed
        def observed():
            value=original_observed();value.update(tabletShown=self.shown,tabletLauncherControlsVersion=1)
            snapshot_controls=deepcopy(value['controls']);rows=[]
            if self.shown:
                rows.append(self.row('tablet.close'))
                if self.route=='launcher':
                    if self.count>1:rows.extend(self.row('tablet.page.'+str(page+1),page) for page in range(self.count))
                    if self.index==self.snapshot_page:rows.append(self.row('snapshot.entry',-1))
                elif self.route=='snapshot':
                    rows.append(self.row('tablet.home'))
                    for control in snapshot_controls:
                        if control['id']=='snapshot.capture':control['token']=self.token('snapshot.capture')
                    rows.extend(snapshot_controls)
                else:rows.append(self.row('address.field'))
            else:rows.append(self.row('hud.tablet'))
            value['controls']=rows;return value
        self.f.input_native.observed=observed
        self.capture.work_packet=self.work_packet
        capture_effect=self.capture.capture_effect
        def captured():
            # Keep the existing actual input/file/native capture model intact.
            # Extend this launcher's same Script event history with its real
            # modeled takeSnapshot/completion callback originals.
            capture_effect();_before,after=self.f.work();source=after['source']['workers'][0]
            current=self.work_original['source']['workers'][0];revision=current['state']['revision'];call=self.call
            for entry in source['events'][1:]:
                event=deepcopy(entry);self.work_cursor+=1;event.update(sequence=self.work_cursor,callerSequence=self.work_cursor,call=call+entry['call'])
                event['state']['revision']+=revision;current['events'].append(event)
            self.call=call+2;current['state']=deepcopy(event['state']);current['latest']=deepcopy(event)
            self.work_original['source']['timerSources']=deepcopy(after['source']['timerSources'])
        self.capture.capture_effect=captured
        domain=self
        class Client:
            def call(self,method,path,body=None):return domain.http(method,path,body)
        client=Client()
        class Runtime(IOSSnapshotPageRuntime):
            def _sources(self,selector):
                native=domain.f.clock().native;normal=domain.f.input_native.input()
                normal.native_epoch_ms=lambda:native.read(native.sequence)['capturedEpochMs']
                return dict(binding=domain.ctx.binding,check=lambda:domain.capture.good,observer=domain.ctx.feature,
                    clock_source=native,native=normal,client=client,session='normal-page-session')
            def existing_input_session(self,selector):return nullcontext()
        self.runtime=Runtime(SimpleNamespace(state_path=lambda _selector:self.ctx.root/'session.json',_candidate_guard=lambda:True,_binding=lambda:None))

    def token(self,identifier):
        key=(identifier,self.generation,self.root,self.index,self.route,self.shown)
        if key not in self.tokens:self.tokens[key]=str(uuid.uuid4())
        return self.tokens[key]

    def row(self,identifier,page=None):
        value=dict(id=identifier,token=self.token(identifier),enabled=True,focused=False,frame=dict(x=10,y=10,width=30,height=20))
        if page is not None:
            value.update(tabletLauncherControlVersion=1,launcherRootId=self.root,launcherQmlSource='qrc:/qml/hifi/tablet/TabletHome.qml',
                launcherCurrentIndex=self.index,launcherPageCount=self.count,launcherControlIndex=page,inputReady=True)
        return value

    def transition(self,opened):
        row=self.work_original['source']['workers'][0];before=deepcopy(row['state']);after=deepcopy(before);after.update(open=opened,revision=before['revision']+1)
        self.call+=1
        for kind,state in (('entry',before),('returned',after),('finally',after)):
            self.work_cursor+=1
            event=dict(sequence=self.work_cursor,callerSequence=self.work_cursor,capturedEpochMs=self.f.now,invokedEpochMs=self.f.now,
                event=kind,closure='onMessage' if opened else 'onClosingWindow',call=self.call,state=deepcopy(state))
            row['events'].append(event)
        row['state']=after;row['latest']=deepcopy(event)

    def work_packet(self,query):
        self.capture.work_sequence+=1;self.work_cursor+=1;value=deepcopy(self.work_original);row=value['source']['workers'][0]
        row['latest']=dict(sequence=self.work_cursor,callerSequence=self.work_cursor,capturedEpochMs=self.f.now,invokedEpochMs=self.f.now,
            event='snapshot',closure='',call=0,state=deepcopy(row['state']))
        value.update(requestId=query['commandId'],sequence=self.capture.work_sequence,clockBefore=self.capture.clock(),clockAfter=self.capture.clock())
        value['source']['eventSequence']=self.work_cursor
        if self.held_work:
            # The native timer's QObject is gone but its actual timerFired
            # dispatch has not returned. The Script state can already be idle.
            value['source']['timerSources']['workers'][0]['timerWork']['timers']=[timer()]
        return value

    def http(self,method,path,body):
        self.requests.append((method,path,deepcopy(body)))
        need(path.startswith('/session/normal-page-session/'));suffix=path.split('/session/normal-page-session',1)[1]
        if suffix=='/elements':
            identifier=body['value'];control={'OverteTabletOpen':'hud.tablet','OverteTabletClose':'tablet.close'}.get(identifier)
            if control is None:
                need(identifier.startswith('OverteNavigation.'));control=identifier[len('OverteNavigation.'):]
            rows=[row for row in self.f.input_native.observed()['controls'] if row['id']==control]
            if not rows:return []
            # UIKit proxy identity is genuinely distinct for each source token.
            key='element-'+rows[0]['token'];self.elements[key]=(control,rows[0]['token'])
            return [{W3C_ELEMENT:key}]
        parts=suffix.split('/');need(len(parts)>=4 and parts[1]=='element');element=parts[2];control,token=self.elements[element]
        current=[row for row in self.f.input_native.observed()['controls'] if row['id']==control and row['token']==token]
        if suffix.endswith('/displayed') or suffix.endswith('/enabled'):return bool(current)
        if suffix.endswith('/attribute/value'):
            if self.swap_token==control:self.generation+=1;self.swap_token=None;return str(uuid.uuid4())
            if self.swap_root==control:self.root=str(uuid.uuid4());self.generation+=1;self.swap_root=None
            return token
        need(method=='POST' and suffix.endswith('/click'));self.clicks.append(control)
        if control not in self.ignore and current:
            if control=='hud.tablet':self.shown=True
            elif control=='tablet.close':self.shown=False
            elif control=='snapshot.entry':self.route='snapshot';self.transition(True)
            elif control=='tablet.home':
                self.route='launcher';self.root=str(uuid.uuid4());self.index=0;self.transition(False)
            else:need(control.startswith('tablet.page.'));self.index=int(control.rsplit('.',1)[1])-1
            self.generation+=1
        if control in self.lose:raise NativeUIError('Explicit lost ordinary UIKit return after delivery')
        return None

    def owner(self):
        return ClockedOwner(self.runtime.page_owner('primary',RUN,self.capture.client()),self.capture)
