"""Two normal People apps, actual JS consent and actual authenticated HTTPS.

All owners/decoders remain real. Qt rows, native HTTP events and model timers
are explicit host producers; neither a provider ACK nor a requested phase is
used as a feature observation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from urllib.error import HTTPError
from urllib.request import Request
import uuid
from ios.adapters.emote_world import actual_domain
from ios.self_tests.avatar_active_fixture import ActiveDomain,RUN,TICKET,SESSIONS
from ios.self_tests.avatar_connection_node import ConnectionNode
from ios.self_tests.avatar_prepare_fixture import peer_template
from ios.self_tests.test_ios_people_model import packet as people_packet


def wire(raw):return dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode())


class SocialDomain(ActiveDomain):
    node_type=ConnectionNode
    def __init__(self,test):
        super().__init__(test);self.views={};self.tables={role:[] for role in SESSIONS};self.rows={role:None for role in SESSIONS}
        self.http_events={role:[] for role in SESSIONS};self.timer_events={role:[] for role in SESSIONS};self.connected_events=[]
        self.node=self.node_type(test,self.identities(),lambda:self.natives['primary'].epoch(),lambda:self.clock[0]);self.update(self.node.latest)
        outer=self
        for role,w in self.widgets.items():
            other='actor' if role=='primary' else 'primary';w.tab='nearbyTab';w.selected=False;w.selected_connection=False
            original_type=type(w)
            class PeopleWidget(original_type):
                def rows(_self):
                    result=super().rows()
                    if _self.screen!='people':return result
                    role=_self.owner_role;other='actor' if role=='primary' else 'primary';state=outer.views[role]
                    page=next(row for row in result if row['id']=='people.page');page.update(activeTab=_self.tab,connectionState=deepcopy(state))
                    def add(identifier,**fields):
                        result.append(dict(id=identifier,token=str(uuid.uuid5(uuid.NAMESPACE_URL,identifier+str(_self.selected)+state['requestId']+state['phase'])),
                            enabled=True,focused=False,inputReady=True,rootId=_self.root(),qmlSource='file:///app.bundle/qml/hifi/Pal.qml',**fields))
                    def peer(identifier,selected):
                        add(identifier,peerSession=SESSIONS[other],username=outer.identities()[other]['account'],selected=selected,present=True,replicated=False)
                    if _self.dialog=='none':
                        add('people.nearby');add('people.connections')
                        if _self.tab=='nearbyTab':
                            peer('people.select.'+SESSIONS[other],_self.selected)
                            if _self.selected:peer('people.request.'+SESSIONS[other],True)
                        else:
                            for row in outer.tables[role]:
                                digest=hashlib.sha256(row['userName'].encode()).hexdigest()[:32]
                                peer('people.connection-select.'+digest,_self.selected_connection)
                                if _self.selected_connection:peer('people.remove.'+digest,True)
                    elif state['phase']=='incoming':add('people.accept');add('people.decline')
                    return result
                def post(_self,request,timeout):
                    value=json.loads(request.data);selected=None
                    if value['operation']=='edit':selected=next(row['id'] for row in _self.rows() if row['token']==value['input']['fieldToken'])
                    result=super().post(request,timeout);role=_self.owner_role
                    if selected and selected.startswith('people.select.'):_self.selected=True
                    elif selected and selected.startswith('people.request.'):outer.exchange('request',role=role,peer=SESSIONS['actor' if role=='primary' else 'primary'])
                    elif selected in ('people.accept','people.decline'):outer.exchange('respond',role=role,accept=selected=='people.accept')
                    elif selected=='people.cancel':outer.exchange('cancel',role=role)
                    elif selected=='people.nearby':_self.tab='nearbyTab'
                    elif selected=='people.connections':_self.tab='connectionsTab';outer.directory(role)
                    elif selected and selected.startswith('people.connection-select.'):_self.selected_connection=True
                    elif selected and selected.startswith('people.remove.'):
                        peer=outer.identities()['actor' if role=='primary' else 'primary']['account']
                        outer.remove_connection(role,peer)
                    if value['operation']=='edit':_self.receipt['status']['sampleEpochMs']=_self.fixture.now()
                    return result
            w.__class__=PeopleWidget;w.owner_role=role
            f=self.scenes[role].f;mutate=f.mutate
            def model(name,value,role=role,w=w,old=mutate):
                old(name,value)
                if name=='people':
                    roots=[]
                    for weak in w.roots:
                        root=weak()
                        if root is None or root.role!='people':continue
                        row=people_packet()['source']['roots'][0];row.update(rootId=root.identity,qmlSource='file:///app.bundle/qml/hifi/Pal.qml',
                            visible=w.screen=='people',active=w.shown and w.screen=='people',activeTab=w.tab,
                            connectionState=deepcopy(outer.views[role]),connectionRows=deepcopy(outer.tables[role]),myData=dict(userName=outer.identities()[role]['account']))
                        row['panels']['connectionPrompt']=w.dialog=='connection';row['pagination']['totalEntries']=len(outer.tables[role]);roots.append(row)
                    value['source']['roots']=sorted(roots,key=lambda row:row['rootId'])
                elif name=='http':value['events']=deepcopy(outer.http_events[role])
                elif name=='scripts':
                    value['source']['workers'][0]['avatar']['events']=[dict(sequence=index,**deepcopy(event)) for index,event in enumerate(outer.timer_events[role],1)]
            f.mutate=model
        base=type(self.runtime)
        class Runtime(base):
            def _avatar_consent(_self,selector,sources,peer,username):
                result=super()._avatar_consent(selector,sources,peer,username);result.sdk.monotonic=lambda:outer.clock[0];result.sdk.sleep=outer.sleep;return result
        self.runtime.__class__=Runtime
    def identities(self):
        domain=actual_domain(peer_template()['world'])['domainId'];result={}
        for role,n in self.natives.items():
            result[role]=dict(self=SESSIONS[role],domain=domain,endpoint=self.origin,loggedIn=n.account['loggedIn'],
                account=n.cache[2] if n.cache else '',accountGeneration=n.account['observation']['credentialGeneration'])
        return result
    def update(self,value):
        self.views=deepcopy(value['views']);self.timer_events=deepcopy(value['timers']);self.connected_events.extend(value['connected'])
        for role,view in self.views.items():
            w=self.widgets[role];w.phase=view['phase']
            if view['phase']=='incoming':w.screen='people';w.shown=True;w.dialog='connection'
            elif view['phase']!='idle':w.dialog='connection'
            else:w.dialog='none'
    def exchange(self,op,**fields):
        value=self.node.request(op,config=self.identities(),**fields)
        for _ in range(64):
            self.update(value);requests=value['requests']
            if not requests:return value
            for row in requests:
                response=self.response(row['role'],row['options']);value=self.node.request('reply',id=row['id'],raw=json.dumps(response),config=self.identities())
                self.update(value)
                # Callback-created requests are returned only after these real
                # responses; they retain their original Node callback IDs.
                if value['requests']:requests.extend(value['requests'])
            self.clock[0]+=.21;value=self.node.request('tick',config=self.identities())
        raise AssertionError('Original consent protocol did not settle its bounded HTTP callbacks')
    def remove_connection(self,role,peer):
        self.response(role,dict(uri=self.origin+'/api/v1/user/connections/'+peer,method='DELETE'));self.directory(role)

    def response(self,role,options):
        n=self.natives[role];url=options['uri'];method=options.get('method','GET');body=options.get('body')
        if method=='GET' and body:
            from urllib.parse import urlencode
            url+='?'+urlencode(body);body=None
        raw=json.dumps(body,separators=(',',':')).encode() if body is not None else b''
        headers={'Authorization':'Bearer '+n.token,'Content-Type':'application/json'}
        request=Request(url,data=raw if method in ('POST','DELETE') else None,headers=headers,method=method)
        worker=self.scenes[role].f.prototypes['scripts']['source']['workers'][0]
        from urllib.parse import urlsplit
        path=urlsplit(url).path;suffix='/system/libraries/peopleConnection.js' if path=='/api/v1/user/connection_request' else '/system/request-service.js' if path=='/api/v1/users/connections' else '/system/pal.js'
        original=dict(callerChain=['qrc:/scripts/modules/request.js','qrc:/scripts'+suffix],engine=deepcopy(worker['membership']),submitted=deepcopy(worker['code']),
            requestUrl=url,method=method,protocolSignature='cHBwcHBwcHBwcHBwcHBwcA==')
        events=self.http_events[role];xhr=uuid.uuid4().hex;reply=uuid.uuid4().hex
        def add(kind,details):
            events.append(dict(sequence=len(events)+1,eventId=uuid.uuid4().hex,xhrId=xhr,kind=kind,
                clock=dict(epochMs=n.epoch(),monotonicMs=round(self.clock[0]*1000)),details=details))
        add('created',original);add('sent',dict(replyId=reply,url=url,method=method,body=wire(raw),authorizationAttached=True,contentType='application/json'))
        try:response=self.opener.open(request,timeout=5)
        except HTTPError as error:response=error
        with response:status=response.code;data=response.read(65537);identity=response.headers.get('X-Overte-Fixture-Response')
        add('reply-finished',dict(replyId=reply,httpStatus=status,networkError=0,responseId=identity,body=wire(data)))
        add('callback-enter',dict(callback='readystatechange',readyState=4));add('text-read',dict(replyId=reply,scriptSource=original['callerChain'][0],sha256=wire(data)['sha256']))
        parsed=json.loads(data);add('callback-leave',dict(callback='readystatechange',readyState=4))
        add('callbacks-released',{});add('timer-destroyed',{});add('xhr-destroyed',{});add('reply-destroyed',dict(replyId=reply));return parsed
    def directory(self,role):
        value=self.response(role,dict(uri=self.origin+'/api/v1/users/connections?page=1&per_page=1000&sort=username%2CASC'))
        self.tables[role]=self.node.request('page',data=value['data'])['rows'];return self.tables[role]
