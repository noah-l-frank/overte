"""Ordinary host WDA app input, actual generated JS and passive DOM output.

All native Qt/UIKit/WK sources are explicit models. Original JS receives only
real file selection and actual modeled WDA input callbacks. Source rows describe
those deliveries; this fixture cannot qualify native/device execution.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import gc
import hashlib
import json
import re
import uuid
from urllib.parse import urlsplit
from feature_journeys.browser_fixture import BrowserResources
from adapters.normal_ui import W3C_ELEMENT
from ios.adapters import tablet_web_state as state
from ios.self_tests.tablet_web_normal_fixture import TabletNormalBoundary
from ios.self_tests.tablet_web_host_app import TabletHostApp
from ios.self_tests.tablet_web_dom_fixture import shown
from ios.self_tests.test_ios_tablet_web_documents import originals as document_originals
from ios.self_tests.test_ios_tablet_web_sources import stamp
from ios.self_tests.tablet_web_deferred_fixture import TabletDeferredModel


class Object:pass


class TabletPageBoundary(TabletNormalBoundary):
    def __init__(self,test,**options):
        super().__init__(test,**options);self.template['sources']['instance']=self.button_source.snapshot()['rootInstance']
        self.browser=BrowserResources(clock_ms=self.epoch);self.browser.open(self.source.run)
        self.native_objects={};self.native_targets={};self.host_app=None;self.nav_count=0;self.page_identity=None
        self.focused=None;self.responder=uuid.uuid4().hex;self.wk_view=None
        self.message_events=set();self.actual_calls=0;self.trace_entries={};self.emission_object=None;self.stack_instance=uuid.uuid4().hex
        self.stack_first=None
        self.ignore_wda=False;self.lose_wda_return=False
        self.page_requests=0;self.history=[];self.history_index=-1
        self.live_marker=False
        self.script_stopped=False;self.terminal_events=[];self.script_thread=None;self.ending_original=None
        self.document_serial=0;self.presentation_current=None
        self.deferred_model=TabletDeferredModel(self)
        controls=self.ui.controls
        def actual_controls():
            rows=controls()
            for row in rows:
                if 'tabletAppButton' in row:self.ensure_control(row['tabletAppButton'],row['token'])
            return rows
        self.ui.controls=actual_controls
        self.runtime.observer.browser=lambda:self.browser.snapshot(self.source.run)
        call=self.ui.call
        def input_call(method,path,body=None):
            if method=='POST' and path.endswith('/elements') and body['value'] in ('Close','Back','Reload'):
                if self.page_identity is None or not self.template['state']['presentations']:return []
                return [{W3C_ELEMENT:'wk-toolbar-'+body['value']}]
            if '/element/wk-toolbar-' in path:
                label=path.split('/element/wk-toolbar-')[1].split('/')[0]
                if method=='GET':
                    if path.endswith(('/displayed','/enabled')):return True
                    if path.endswith('/attribute/type'):return 'XCUIElementTypeButton'
                    if path.endswith('/attribute/label'):return label
                    if path.endswith('/rect'):return dict(x=0.,y=0.,width=80.,height=44.)
                if method=='POST' and path.endswith('/click'):
                    self.test.assertEqual('Close',label);self.close_native();return None
            if method=='POST' and path.endswith('/actions'):
                if self.ignore_wda:return None
                pointer=body['actions'][0];move=pointer['actions'][0];view=self.template['document']['source']['presentationAfter'];viewport=self.template['document']['source']['dom']['document']['visualViewport']
                scale=view['screenFrame'][2]/viewport['width'];x=(move['x']-view['screenFrame'][0])/scale+viewport['offsetLeft'];y=(move['y']-view['screenFrame'][1])/scale+viewport['offsetTop']
                self.press_wk();output=self.host_app.call('page-tap',x=x,y=y,epoch=self.epoch());self.focus(output);self.sync_messages(output);self.follow_requests(output)
                if self.lose_wda_return:self.lose_wda_return=False;raise OSError('Actual modeled WDA return lost after real host delivery')
                return None
            if method=='GET' and path.endswith('/element/active'):
                self.test.assertIn(self.focused,('text','foreign'));return {W3C_ELEMENT:'wk-field-'+self.focused}
            if '/element/wk-field-' in path:
                field=path.split('/element/wk-field-')[1].split('/')[0];self.test.assertEqual(self.focused,field)
                source=self.template['document']['source'];element=next(row for row in source['dom']['elements'] if row['id']==field)
                if method=='GET':
                    if path.endswith('/attribute/type'):return 'XCUIElementTypeTextField'
                    if path.endswith('/attribute/label'):return element['accessibilityLabel']
                    if path.endswith('/attribute/value'):return element['value']
                    if path.endswith(('/displayed','/enabled')):return True
                    if path.endswith('/rect'):
                        from ios.adapters.tablet_web_native_input import TabletWebNativeInput
                        return TabletWebNativeInput.screen_rect(source,element)
                if method=='POST' and path.endswith(('/clear','/value')):
                    output=self.host_app.call('page-text',id=field,text='' if path.endswith('/clear') else body['text'],epoch=self.epoch());self.focus(output);return None
            if '/element/' in path and method=='POST' and path.endswith('/click'):
                reference=path.split('/element/')[1].split('/')[0];name,token=self.ui.elements[reference]
                if name.startswith('tablet-web-app.'):
                    rows=[row for row in self.ui.controls() if row['id']==name];self.test.assertEqual(1,len(rows));self.test.assertEqual(token,rows[0]['token'])
                    metadata=rows[0]['tabletAppButton'];self.press_control(metadata,token)
                    self.button_source.click(metadata['button']);actual=self.host_app.call('click',semanticId=metadata['semanticId'])
                    for navigation in actual['navigations'][self.nav_count:]:self.open_http(navigation['source'])
                    self.nav_count=len(actual['navigations']);return None
            result=call(method,path,body)
            if self.manager is not None and not self.script_stopped and not any(row['url']==self.manager['url'] for row in self.ui.qt.rows):self.stop_app_worker()
            return result
        self.ui.call=input_call

    def focus(self,output):
        self.sleep(max(0,output['nativeEpoch']-self.epoch())/1000)
        self.focused=output['focusedElement']
        if self.page_identity is not None:
            responders=[self.responder] if self.focused in ('text','foreign') else []
            source=self.template['document']['source']
            for name in ('presentationBefore','presentationAfter'):source[name]['responders']=deepcopy(responders)
            self.template['state']['presentations'][0]['snapshot']['responders']=deepcopy(responders)
            for row in self.template['state']['targets']:
                if row['kind']=='wk' and row['source']['view']==self.wk_view:row['subtreeResponder']=bool(responders)

    def sync_messages(self,output):
        """Model native originals from actual executed callbacks, never verbs."""
        self.deferred_model.received(output)
        ledger=self.template['ledger'];emitter=self.template['emitter'];events=[]
        for index,row in enumerate(output['pageEvents']):
            key=('event',index)
            if key in self.message_events:continue
            self.message_events.add(key);kind=row['kind'];message=row['message'];epoch=row['epoch']
            if kind=='native-envelope':
                body=json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[message]))
                events.append((epoch,kind,dict(envelope=body,documentNonce=self.page_identity['nonce'],frame=self.page_identity['url'],mainFrame=True),('envelope',index)))
            elif kind=='script-delivery':events.append((epoch,kind,dict(message=message),('delivery',index)))
            else:
                origin='script-delivery' if kind=='script-delivery-return' else 'native-envelope'
                parent=max(number for number in range(index) if output['pageEvents'][number]['kind']==origin)
                events.append((epoch,'signal-return',None,('delivery' if origin=='script-delivery' else 'envelope',parent)))
        for ordinal,actual in enumerate(output['emissions'],1):
            if ordinal<=self.actual_calls:continue
            self.actual_calls=ordinal
            if self.emission_object is None:
                self.emission_object=uuid.uuid4().hex;emitter['objects'].append(dict(id=self.emission_object,born=stamp(actual['objectObserved']),expired=None,alive=True))
            if self.stack_first is None:self.stack_first=actual['contextObserved']
            frames=[];url=self.manager['url']
            for line,column in re.findall(re.escape(url)+r':([0-9]+):([0-9]+)',actual['stack']):
                frames.append(dict(scriptId=71,line=int(line),column=int(column),sourceUrlSha256=hashlib.sha256(url.encode()).hexdigest(),isEval=False,isConstructor=False,
                    compiled=dict(urlSha256=hashlib.sha256(url.encode()).hexdigest(),encoding=self.code['encoding'],codeUnits=self.code['codeUnits'],sha256=self.code['sha256'],firstObservedEpochMs=self.stack_first)))
            call_id=uuid.uuid4().hex;emitter['callSequence']+=1
            caller=dict(callerVersion=1,method='emitScriptEvent',sequence=len(self.button_source.rows)+ordinal,invokedEpochMs=actual['contextObserved'],manager=deepcopy(self.manager),code=deepcopy(self.code),
                emitStack=dict(emitStackVersion=1,instance=self.stack_instance,complete=True,frames=frames))
            emitter['calls'].append(dict(id=call_id,sequence=emitter['callSequence'],object=self.emission_object,surface='tablet',target='com.highfidelity.interface.tablet.system',message=actual['message'],
                caller=caller,entered=stamp(actual['entered']),returned=stamp(actual['returned']),**{'finally':stamp(actual['finally'])}))
            for prefix,kind in (('slot','script-event-slot'),('page','page-reply')):
                events.append((actual[prefix+'TraceEntered'],kind,dict(message=actual['message'],**({'active':True} if prefix=='slot' else {})),('sink',ordinal,prefix)))
                events.append((actual[prefix+'TraceReturn'],'signal-return',None,('sink',ordinal,prefix)))
                emitter['sinkSequence']+=1;emitter['sinks'].append(dict(id=uuid.uuid4().hex,sequence=emitter['sinkSequence'],kind=kind,call=call_id,
                    identity=deepcopy(self.page_identity),message=actual['message'],entered=stamp(actual[prefix+'Entered']),returned=stamp(actual[prefix+'Returned']),**{'finally':stamp(actual[prefix+'Finally'])}))
        for epoch,kind,detail,key in sorted(events,key=lambda item:item[0]):
            sequence=len(ledger['events'])+1
            if kind=='signal-return':detail=dict(entry=self.trace_entries[key])
            else:self.trace_entries[key]=sequence
            ledger['events'].append(dict(sequence=sequence,eventId=uuid.uuid4().hex,kind=kind,clock=stamp(epoch),identity=deepcopy(self.page_identity),detail=detail))
        ledger['eventSequence']=len(ledger['events'])

    def execute_app(self,path):
        self.host_app=TabletHostApp(self.test,path)
        return [row['properties'] for row in self.host_app.original['buttons']]

    def load(self,url):
        super().load(url);self.script_stopped=False;self.script_thread=uuid.uuid4().hex
        self.actual_calls=0;self.message_events=set();self.stack_first=None;self.stack_instance=uuid.uuid4().hex
        self.nav_count=0;self.page_requests=0;self.history=[];self.history_index=-1
        self.deferred_model.seen=0
        self.terminal_event('thread-bound')

    def terminal_event(self,kind):
        clock=self.tick()
        self.terminal_events.append(dict(eventSequence=len(self.terminal_events)+1,capturedEpochMs=clock['epochMs'],monotonicMs=clock['monotonicMs'],
            kind=kind,threadInstance=self.script_thread,manager=deepcopy(self.manager),code=None if kind=='thread-bound' else deepcopy(self.code),
            work=dict(signalCallbacks=0,timerCallbacks=0,evaluating=False,timers=0) if kind=='shutdown-drained' else None))

    def stop_app_worker(self):
        # A returned Qt Stop is insufficient. Run the actual generated Ending
        # handlers, observe their disconnect/remove output, then wait for the
        # actual host VM process to exit before this native-model exit event.
        actual=self.host_app.call('stop');self.test.assertTrue(actual['stopped']);self.test.assertEqual(0,actual['connections'])
        self.test.assertTrue(all(row['removed'] and row['connections']==0 for row in actual['buttons']))
        self.ending_original=deepcopy(actual)
        for row in self.button_source.rows:
            if row['caller']['manager']['instance']==self.manager['instance']:
                button=next(item for item in actual['buttons'] if item['properties']['semanticId']==row['semanticId'])
                self.test.assertTrue(button['removed']);self.button_source.remove(row['id'])
        self.controls={};self.sleep(max(0,self.button_source.now-self.epoch())/1000)
        self.terminal_event('shutdown-drained');self.host_app.close();self.test.assertIsNotNone(self.host_app.process.poll())
        self.terminal_event('thread-finished');self.script_stopped=True

    def tick(self):self.sleep(.001);return stamp(self.epoch())

    def object(self,kind):
        key=uuid.uuid4().hex;self.native_objects[key]=Object()
        self.template['touches']['objects'].append(dict(id=key,kind=kind,born=self.tick(),expired=None,alive=True));return key

    def press_control(self,metadata,token):
        touches=self.template['touches'];view=self.ensure_control(metadata,token)
        target=next(row for row in touches['targets'] if row['view']==view)
        window=self.object('window');touch=self.object('touch');event=self.object('event');contact=uuid.uuid4().hex
        association=dict(deepcopy(target),ancestry=[view]);begin=self.tick();end=self.tick()
        touches['contacts'].append(dict(id=contact,kind='touch',object=touch,target=view,window=window,source=association,
            began=begin,ended=end,phase=3,active=False))
        for phase,entered in ((0,begin),(3,end)):
            touches['dispatchSequence']+=1;returned=self.tick()
            touches['dispatches'].append(dict(sequence=touches['dispatchSequence'],event=event,entered=entered,returned=returned,
                **{'finally':deepcopy(returned)},phases=[dict(object=touch,contact=contact,kind='touch',phase=phase,target=view,window=window,source=deepcopy(association))]))
        self.project_targets()

    def ensure_control(self,metadata,token):
        touches=self.template['touches'];key=(metadata['control'],token)
        if key not in self.native_targets:
            view=self.object('view');self.native_targets[key]=view
            target=dict(view=view,qtControl=dict(deepcopy(metadata),sourceToken=token),bound=self.tick());touches['targets'].append(target)
        return self.native_targets[key]

    def press_wk(self):
        self.test.assertIsNotNone(self.wk_view);touches=self.template['touches'];target=next(row for row in touches['targets'] if row['view']==self.wk_view)
        view=self.wk_view;window=self.object('window');touch=self.object('touch');event=self.object('event');contact=uuid.uuid4().hex
        association=dict(deepcopy(target),ancestry=[view]);begin=self.tick();end=self.tick()
        touches['contacts'].append(dict(id=contact,kind='touch',object=touch,target=view,window=window,source=association,began=begin,ended=end,phase=3,active=False))
        for phase,entered in ((0,begin),(3,end)):
            touches['dispatchSequence']+=1;returned=self.tick()
            touches['dispatches'].append(dict(sequence=touches['dispatchSequence'],event=event,entered=entered,returned=returned,
                **{'finally':deepcopy(returned)},phases=[dict(object=touch,contact=contact,kind='touch',phase=phase,target=view,window=window,source=deepcopy(association))]))

    def project_targets(self):
        previous={row['source']['view']:row for row in self.template['state']['targets']};rows=[]
        for source in self.template['touches']['targets']:
            if 'qtControl' in source:
                attached=self.ui.qt.opened and self.ui.qt.page=='home' and any(item['control']==source['qtControl']['control'] for item in self.controls.values())
                row=dict(source=deepcopy(source),kind='qt-control',alive=True,windowAttached=attached,superviewPresent=attached,subtreeResponder=False)
            else:row=previous.get(source['view']) or dict(source=deepcopy(source),kind='wk',alive=True,windowAttached=True,superviewPresent=True,subtreeResponder=False)
            rows.append(row)
        self.template['state']['targets']=rows

    def follow_requests(self,output):
        for request in output['pageRequests'][self.page_requests:]:
            self.page_requests+=1
            self.sleep(max(0,request['epoch']-self.epoch())/1000)
            if request['kind']=='back':
                self.test.assertGreater(self.history_index,0);self.history_index-=1;url=self.history[self.history_index]
            else:url=request['source']
            self.open_http(url,transition=request['kind'])

    def open_http(self,url,*,transition=None):
        if url.startswith('data:'):return self.open_inline(url)
        actual=urlsplit(url);root=urlsplit(self.source.fixture)
        origins=self.runtime.observer.origins
        matches=[key for key,origin in origins.items() if (urlsplit(origin).scheme,urlsplit(origin).netloc)==(actual.scheme,actual.netloc)]
        self.test.assertEqual(1,len(matches));origin=matches[0]
        relative=actual.path.removeprefix(root.path);parts=relative.split('/');self.test.assertEqual('tickets',parts[0]);self.test.assertEqual(3,len(parts))
        ticket,resource=parts[1:];status,_headers,body,_mime=self.browser.resource(self.source.run,ticket,resource,origin=origin)
        if transition=='foreground':self.history=[url];self.history_index=0
        elif transition not in ('back','reload'):
            self.history=self.history[:self.history_index+1]+[url];self.history_index=len(self.history)-1
        return self.open_document(url,body,transition=transition,status=status,resource=resource,origin=origin)

    def open_inline(self,source):
        prefix='data:text/html;charset=utf-8;base64,';self.test.assertTrue(source.startswith(prefix))
        raw=base64.b64decode(source[len(prefix):],validate=True);self.test.assertEqual(source,prefix+base64.b64encode(raw).decode())
        token=uuid.uuid4().hex;url='http://'+token+'.overte-inline.invalid/index.html'
        return self.open_document(url,raw,inline=dict(input=source,token=token,carrier=uuid.uuid4().hex,binding=uuid.uuid4().hex),resource=None,status=0,origin='inline')

    def retire_inline(self):
        for carrier in self.template['sources']['carriers']:
            if 'retired' not in carrier:
                carrier['retired']=self.tick();carrier['retireReturned']=self.tick()
                for binding in carrier['bindings']:
                    binding.update(current=False,revoked=deepcopy(carrier['retired']))

    def open_document(self,url,body,*,transition=None,status=200,resource=None,origin='primary',inline=None):
        fresh=transition is None;recreated=transition=='foreground'
        previous_identity=deepcopy(self.page_identity)
        if fresh:
            if self.template['state']['presentations']:self.close_native()
            self.retire_inline();self.document_serial+=1
        elif recreated:
            self.test.assertIsNotNone(previous_identity);self.test.assertIsNone(inline)
            self.test.assertFalse(self.template['state']['presentations']);self.document_serial+=1
        epoch=self.epoch();self.host_app.call('page-create',url=url,html=body.decode(),inline=inline is not None,bridge=True,authorized=origin in ('primary','inline'),
            inlineToken='' if inline is None else inline['token'],liveMarker=self.live_marker,epoch=epoch+10);self.focused=None
        output=self.host_app.call('page-read',requestId='ios-'+uuid.uuid4().hex,epoch=epoch+30);dom=output['dom']
        self.sleep((dom['capturedEpochMs']-epoch+30)/1000)
        ledger,_sources,document,_browser=document_originals(dom,inline=inline is not None,status=status,resource=resource)
        new_source=fresh or self.page_identity is None;first=new_source or recreated
        reference=dict(root='3'*32,navigation=uuid.uuid4().hex,fixtureUrl=self.source.fixture,carrier=None if inline is None else inline['carrier'],binding=None if inline is None else inline['binding']) if new_source else deepcopy(self.page_identity['source'])
        identity=deepcopy(document['source']['nativeView']) if first else deepcopy(self.page_identity)
        identity.update(source=reference,url=url,nonce=str(uuid.uuid4()),page=1 if first else identity['page']+1)
        if first:identity.update(creation=self.document_serial,grant=self.document_serial,sourceUrl=url if new_source else previous_identity['sourceUrl'],
            sourceIdentity='tablet:'+('http:' if inline is None else 'inline:')+uuid.uuid4().hex if new_source else previous_identity['sourceIdentity'])
        self.page_identity=identity
        # Same modeled native return event, separate Source/Buttons timer
        # origins. Never copy a Buttons monotonic counter into Sources.
        root_clock=stamp(self.button_source.rows[0]['returned']['epochMs'])
        if new_source:
            self.template['sources']['roots']=[dict(id='3'*32,clock=root_clock,alive=True)]
            input_source=url if inline is None else inline['input']
            self.template['sources']['navigations'].append(dict(id=reference['navigation'],root='3'*32,fixtureUrl=self.source.fixture,
                tablet='com.highfidelity.interface.tablet.system',sourceUrl=input_source,sourceSha256=hashlib.sha256(input_source.encode()).hexdigest(),
                scriptUrl=self.manager['url'],kind='http' if inline is None else 'inline',body=None if inline is None else dict(base64=base64.b64encode(body).decode(),sha256=hashlib.sha256(body).hexdigest(),charset='utf-8'),
                clock=stamp(epoch),returned=dict(clock=stamp(epoch+1),invoked=True)))
            if inline is not None:
                self.template['sources']['carriers'].append(dict(id=inline['carrier'],navigation=reference['navigation'],root='3'*32,identity=identity['sourceIdentity'],clock=stamp(epoch+2),alive=True,
                    bindings=[dict(id=inline['binding'],clock=stamp(epoch+3),token=inline['token'],revision=1,transportUrl=url,sha256=hashlib.sha256(body).hexdigest(),charset='utf-8',returned=stamp(epoch+4),current=True,contextAlive=True,pageAlive=True)]))
        elif not first:ledger['events']=[row for row in ledger['events'] if row['kind']!='view-created']
        offset=len(self.template['ledger']['events'])
        for index,row in enumerate(ledger['events'],1):
            row.update(sequence=offset+index,eventId=uuid.uuid4().hex,identity=deepcopy(identity),clock=stamp(epoch+index+10))
            if row['kind'] in ('view-created','document-began'):row['identity']['url']=''
        self.template['ledger']['events'].extend(ledger['events']);self.template['ledger']['eventSequence']=len(self.template['ledger']['events'])
        document['source']['nativeView']=deepcopy(identity);document['source']['nativeFinishedEpochMs']=next(row['clock']['epochMs'] for row in ledger['events'] if row['kind']=='native-finished')
        shown_before=shown();shown_before['screenScale']=1.;shown_before['nativeScreenBounds']=[0.,0.,500.,800.]
        if first:
            if self.document_serial>1:
                for key in ('view','controller','presentation'):shown_before[key]=uuid.uuid4().hex
                shown_before['top']=shown_before['presentation'];shown_before['recognizers']=[dict(id=uuid.uuid4().hex,view=shown_before['view'],state=0,enabled=True)]
            self.presentation_current=deepcopy(shown_before)
        else:shown_before=deepcopy(self.presentation_current)
        document['source']['presentationBefore']=shown_before;document['source']['presentationAfter']=deepcopy(shown_before)
        self.template['document'].update(status='ready',source=document['source'])
        # UIKit associates the original native view-creation identity. Its
        # URL can still be empty; the later committed DOM identity stays apart.
        view=self.wk_view
        if first:
            view=self.object('view');target=dict(view=view,identity=deepcopy(ledger['events'][0]['identity']),bound=self.tick());self.template['touches']['targets'].append(target)
            self.wk_view=view
        flags=dict({key:False for key in state.FLAGS},generation=identity['grant'])
        for key in ('active','viewPresent','presentationPresent','presentationAttached','windowPresent','sourceCurrent'):flags[key]=True
        if new_source:
            owner=dict(id=uuid.uuid4().hex,handle=identity['handle'],source=deepcopy(reference),firstObserved=self.tick(),expired=None,alive=True,current=flags)
            self.template['state']['owners'].append(owner)
            for old in self.template['state']['owners'][:-1]:old['current']=dict(deepcopy(flags),sourceCurrent=False)
        else:
            owner=self.template['state']['owners'][-1];owner['current']=flags
        self.template['state']['presentations']=[dict(owner=owner['id'],handle=owner['handle'],source=deepcopy(reference),generation=identity['grant'],snapshot=shown_before,target=view)]
        # Source-owned Home delegates really disappear on the normal Loader
        # replacement; physical native UIButton contacts can remain cached.
        for metadata in self.controls.values():self.button_source.strong.pop(metadata['control'],None)
        self.controls={};gc.collect();self.ui.qt.page='web';self.project_targets()

    def suspend_native(self):
        """Model actual IOSWebView applicationStateChanged teardown, not Home."""
        if not self.template['state']['presentations']:return
        self.test.assertIsNone(self.page_identity['source']['carrier'])
        self.resume_url=self.page_identity['sourceUrl'];self.host_app.call('page-close',epoch=self.epoch())
        ledger=self.template['ledger'];sequence=len(ledger['events'])+1
        ledger['events'].append(dict(sequence=sequence,eventId=uuid.uuid4().hex,kind='view-teardown',clock=self.tick(),identity=deepcopy(self.page_identity),detail={}))
        ledger['eventSequence']=sequence;self.template['document'].update(status='unavailable',source={})
        for owner in self.template['state']['owners']:owner['current']=dict({key:False for key in state.FLAGS},generation=0)
        self.template['state']['presentations']=[];self.focused=None
        for row in self.template['state']['targets']:
            if row['kind']=='wk':row.update(windowAttached=False,superviewPresent=False,subtreeResponder=False)
        self.project_targets()

    def resume_native(self):
        """The same original policy URL opens a new real host page instance."""
        url=getattr(self,'resume_url',None)
        if url is not None:self.open_http(url,transition='foreground');self.resume_url=None

    def close_native(self):
        self.test.assertTrue(self.template['state']['presentations']);ledger=self.template['ledger'];sequence=len(ledger['events'])+1
        self.host_app.call('page-close',epoch=self.epoch())
        ledger['events'].append(dict(sequence=sequence,eventId=uuid.uuid4().hex,kind='view-teardown',clock=self.tick(),identity=deepcopy(self.page_identity),detail={}))
        ledger['eventSequence']=sequence;self.template['document'].update(status='unavailable',source={})
        for owner in self.template['state']['owners']:owner['current']=dict({key:False for key in state.FLAGS},generation=0)
        self.template['state']['presentations']=[];self.focused=None
        self.ui.qt.opened=True;self.ui.qt.page='home'
        for row in self.template['state']['targets']:
            if row['kind']=='wk':row.update(windowAttached=False,superviewPresent=False,subtreeResponder=False)
        for row in self.button_source.rows:
            if row['removed'] is None:
                metadata=self.button_source.bind(row['id']);match=row['semanticId'].split('.')
                metadata.update(featureRun=match[1],nonce=match[2],semanticId=row['semanticId'],fixtureUrl=row['fixtureUrl'])
                self.controls[match[3]]=metadata
        self.sleep(max(0,self.button_source.now-self.epoch())/1000+.001)
        self.project_targets()

    def produce(self,query):
        before=self.epoch()
        if query['action']=='feature-ios-tablet-web-defer':return query['action']+'.json',self.deferred_model.command(query)
        if query['action']=='feature-ios-tablet-web-deferred':self.deferred_model.sweep()
        if query['action']=='feature-ios-tablet-web-dom' and self.template['state']['presentations']:
            value=self.host_app.call('page-read',requestId=query['commandId'],epoch=self.epoch())
            self.sleep(max(0,value['dom']['capturedEpochMs']-self.epoch())/1000+.001)
            self.template['document']['source']['dom']=value['dom'];self.focus(value)
        self.project_targets()
        name,packet=super().produce(query)
        if query['action']=='feature-script-terminal-observe':
            packet['source'].update(events=deepcopy(self.terminal_events),eventSequence=len(self.terminal_events))
        if query['action']=='feature-script-observe' and self.script_stopped:
            packet['source'].update(engines=[],membership=dict(complete=True,revision=2*len({row['threadInstance'] for row in self.terminal_events}),managers=[]))
        elif query['action']=='feature-script-observe' and self.manager is not None:
            packet['source']['membership']['revision']=2*len({row['threadInstance'] for row in self.terminal_events})-1
        if query['action']=='feature-ios-tablet-web-dom' and self.template['state']['presentations']:
            packet['clockBefore']=stamp(before);packet['clockAfter']=stamp(self.epoch())
        if query['action']=='native-geometry-snapshot' and self.focused in ('text','foreign'):
            packet['observation']['nativeUi'].update(keyboardVisible=True,imeInsetBottom=300)
        return name,packet
