"""Preparation plus normal Avatar controls at explicit native/Qt seams.

The source owners, normal-input transport and operation recipes are unchanged.
Only original Qt/model/renderer producers are modeled; no feature verdict is
injected. The preparation still performs actual HTTPS and Node operations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import uuid
import weakref
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from ios.adapters import avatar_inputs,avatar_controls,avatar_renderers
from ios.adapters.avatar_input_reads import IOSAvatarInputReads
from ios.self_tests.avatar_prepare_fixture import PrepareDomain,RUN,TICKET,SESSIONS
from ios.self_tests.test_ios_avatar_actions import Widget
from ios.self_tests import test_ios_avatar_entities as entities_fixture
from ios.self_tests import test_ios_avatar_renderers as renderers_fixture


class QtRoot:
    def __init__(self,role):self.role=role;self.identity=str(uuid.uuid4())


class ActiveDomain(PrepareDomain):
    def __init__(self,test):
        super().__init__(test);outer=self;self.widgets={};self.input_packets={}
        for role,scene in self.scenes.items():
            f,d,n=scene.f,scene.domain,self.natives[role]
            class QtWidget(Widget):
                @property
                def clock(_self):return _self.fixture.clock
                @clock.setter
                def clock(_self,value):
                    if hasattr(_self,'fixture'):_self.fixture.clock=value
                @property
                def shown(_self):return _self.domain.io.qt.opened if hasattr(_self,'domain') else False
                @shown.setter
                def shown(_self,value):
                    if hasattr(_self,'domain'):_self.domain.io.qt.opened=value
                @property
                def screen(_self):
                    page=_self.domain.io.qt.page if hasattr(_self,'domain') else 'home'
                    return page if page in ('avatar','people') else 'home'
                @screen.setter
                def screen(_self,value):
                    if hasattr(_self,'domain'):
                        _self.domain.io.qt.page=value
                        if getattr(_self,'current_root',None) is not None and _self.current_root.role!=value:_self.current_root=None
                        if hasattr(_self,'current_root') and value in ('avatar','people'):_self.root()
                def root(_self):
                    if _self.screen not in ('avatar','people'):return _self.root_id
                    if _self.current_root is None or _self.current_root.role!=_self.screen:
                        _self.current_root=QtRoot(_self.screen);_self.roots.append(weakref.ref(_self.current_root))
                    return _self.current_root.identity
                def observed(_self):
                    if _self.current_root is not None and _self.current_root.role!=_self.screen:_self.current_root=None
                    value=super().observed();value['processId']=31
                    return value
            widget=QtWidget(f);widget.domain=d;widget.instance=n.instance;widget.screen='home';widget.target=n.target;widget.pid=31
            widget.current_root=None;widget.roots=[]
            f.prototypes['state']['iosAvatarStateVersion']=3;f.prototypes['state']['source']['sessionPresent']=True
            self.widgets[role]=widget;f.widget=widget;self.input_packets[role]=dict(sequence=0,events=[],current=None)
            old_widgets=d.widgets
            def widgets(old=old_widgets,w=widget,n=n,d=d):
                w.sequence=n.sequence
                # The Script manager controls are the original Domain producer;
                # both consumers see the same actual process input sequence.
                if d.io.qt.page=='scripts':
                    value=old();w.source_sequence+=1
                    value.update(instance=w.instance,lastSequence=n.sequence,avatarGeneration='33333333-3333-4333-8333-333333333333',
                        avatarSourceSequence=w.source_sequence)
                else:value=w.observed()
                roots=[]
                for weak in w.roots:
                    root=weak()
                    if root is None:continue
                    roots.append(dict(rootId=root.identity,qmlSource='file:///app.bundle/qml/hifi/'+('AvatarApp.qml' if root.role=='avatar' else 'Pal.qml'),
                        role=root.role,visible=w.shown and root is w.current_root,enabled=True,attached=root is w.current_root,windowPresent=root is w.current_root,
                        panels={name:w.dialog==('connection' if name=='connection' else name) for name in (('connection',) if root.role=='people' else ('popup','favorite','settings','wearables'))}))
                value['avatarInventory']=dict(iosAvatarUiInventoryVersion=1,complete=True,roots=roots)
                return value
            d.widgets=widgets;scene.widgets=widgets
            observed=n.observed
            def global_widgets(n=n,old=observed,widgets=widgets):
                actual=old()
                if n.login.dialog:
                    w=outer.widgets[n.scene.scope.role];w.source_sequence+=1
                    actual.update(avatarControlsVersion=1,avatarGeneration='33333333-3333-4333-8333-333333333333',
                        avatarSourceSequence=w.source_sequence,avatarInventory=dict(iosAvatarUiInventoryVersion=1,complete=True,roots=[]));return actual
                current=widgets()
                if n.menu=='file':
                    actual.update({key:value for key,value in current.items() if key.startswith('avatar')});return actual
                identifiers={row['id'] for row in current['controls']}
                current['controls'].extend(row for row in actual['controls'] if row['id'] not in identifiers)
                actual.update(current);return actual
            n.observed=global_widgets
            mutate=f.mutate
            def model(name,value,f=f,w=widget,old=mutate):
                old(name,value)
                if name=='state':
                    source=value['source'];source.update(requestedUrl=w.avatar_url,resourceUrl=w.avatar_url,targetScale=w.scale,modelScale=w.scale)
                    if w.avatar_url.endswith('/missing.fst'):source['resourceUrl']=source['defaultResourceUrl']
                    entries={} if not w.name else {w.name:deepcopy(w.saved)};source['bookmarks']['entries']=entries
                    raw=json.dumps(entries,sort_keys=True,separators=(',',':')).encode()
                    source['bookmarkFile'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())
                elif name=='renderers':
                    source=value['source'];row=next(row for row in source['avatars'] if row['self'])
                    row.update(requestedUrl=w.avatar_url,resourceUrl=w.avatar_url,targetScale=w.scale,modelScale=w.scale)
                    if w.avatar_url.endswith('/missing.fst'):row['resourceUrl']=f.prototypes['state']['source']['defaultResourceUrl']
                    if w.wearable_id:
                        renderers_fixture.attach(value);entity=source['avatarEntities'][-1]
                        entity.update(id=w.wearable_id,modelUrl=w.wearable_url,resourceUrl=w.wearable_url,
                            geometryLoaded=not w.failed_geometry,addedToScene=not w.failed_geometry,loadFailed=w.failed_geometry)
                        source['tree']['entities'][-1]['id']=w.wearable_id
                    source['tree'].update(revisionBefore=source['tree']['revisionBefore']+w.entity_revision,revisionAfter=source['tree']['revisionAfter']+w.entity_revision)
                elif name=='people':
                    value['source']['tabletShown']=w.shown
                    for root in value['source']['roots']:root.update(visible=w.screen=='people',active=w.shown and w.screen=='people')
            f.mutate=model
            post=n.post
            def transport(request,timeout,n=n,w=widget,f=f,old=post,role=role):
                command=json.loads(request.data)
                if command['action']=='normal-ui-input' and command['operation']=='edit' and command['input']['operation']!='clear-login-username' and any(row['token']==command['input']['fieldToken'] for row in w.rows()):
                    w.sequence=n.sequence;before=w.rows();control=next(row for row in before if row['token']==command['input']['fieldToken'])
                    # Original API ledger values are produced only by the
                    # native model call performed during this actual Qt input.
                    seeded=False
                    if control['id']=='avatar.popup.confirm' and w.popup_title=='Specify Wearable URL' and not f.prototypes['entities']['source']['events']:
                        f.prototypes['entities']['source']['events']=[deepcopy(entities_fixture.packet()[0]['source']['events'][0])];seeded=True
                    result=w.post(request,timeout);n.sequence=w.sequence
                    if seeded:
                        rows=f.prototypes['entities']['source']['events'];rows.pop(0);rows[0]['sequence']=1
                        caller=rows[0]['caller'];worker=f.prototypes['scripts']['source']['workers'][0]
                        caller.update(manager=deepcopy(worker['membership']),code=deepcopy(worker['code']),
                            avatarCode={key:deepcopy(worker['avatar'][key]) for key in ('avatarScriptVersion','instance','complete','code')})
                    w.receipt['status'].update(processId=31,sampleEpochMs=f.now());n.ui_receipt=deepcopy(w.receipt);n.echo=json.dumps(command).encode()
                    ledger=outer.input_packets[role];identity=str(uuid.uuid4());stamp=dict(epochMs=f.now(),monotonicMs=round(outer.clock[0]*1000))
                    root={key:control[key] for key in ('rootId','qmlSource')} if 'rootId' in control else None
                    if root is None and control['id']=='tablet.home':
                        page=next(row for row in before if row['id'] in ('avatar.page','people.page'));root={key:page[key] for key in ('rootId','qmlSource')}
                    for kind,detail in (('received',dict(outerCommandId=command['commandId'],command=deepcopy(command['input']),controlId=control['id'],root=root)),('returned',deepcopy(n.ui_receipt))):
                        ledger['events'].append(dict(sequence=len(ledger['events'])+1,eventId=str(uuid.uuid4()),inputId=identity,kind=kind,clock=deepcopy(stamp),details=detail))
                    return n
                return old(request,timeout)
            n.post=transport
        base_type=type(self.runtime)
        class Runtime(base_type):
            def _avatar_input_reads(_self,selector,sources):
                n=outer.natives[selector];ledger=outer.input_packets[selector]
                def send(query):
                    outer.clock[0]+=.001;ledger['sequence']+=1
                    ledger['current']=dict(iosNormalInputsVersion=1,profile='avatar',requestId=query['commandId'],runId=RUN,
                        instance='e'*32,sequence=ledger['sequence'],processId=31,clockDomain='native-process-normal-inputs',
                        clockBefore=dict(epochMs=n.epoch(),monotonicMs=round(outer.clock[0]*1000)),
                        clockAfter=dict(epochMs=n.epoch(),monotonicMs=round(outer.clock[0]*1000)),source=dict(complete=True,events=deepcopy(ledger['events'])))
                reader=avatar_inputs.IOSAvatarInputs(send,lambda:json.dumps(ledger['current']),n.epoch,lambda:True,31,
                    monotonic=lambda:outer.clock[0],sleep=outer.sleep)
                return IOSAvatarInputReads(PrivateFeatureState(_self.state_path(selector).with_name('ios-avatar-'+sources.role+'-input-reads.json')),
                    sources.root,sources.binding,RUN,sources.role,sources.lock,sources.guard,reader,monotonic=lambda:outer.clock[0])
            def _avatar_actions(_self,selector,sources,peer):
                result=super()._avatar_actions(selector,sources,peer)
                # NativeUI's scheduling clock is the same original modeled
                # event loop as all source producers, established at creation.
                original=result.sdk.check_continuity
                result.sdk.monotonic=lambda:outer.clock[0];result.sdk.sleep=outer.sleep
                return result
        self.runtime.__class__=Runtime
        # Actual Source UI input uses the same normal-input channel as recipes.
        for role,scene in self.scenes.items():
            old=scene.readers
            def readers(role=role,old=old):
                result=old();source=outer.runtime._sources(role);result['ui']=avatar_controls.IOSAvatarIO(source['native']);return result
            scene.readers=readers
