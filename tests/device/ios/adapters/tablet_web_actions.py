"""Whole Tablet ordinary inputs with durable once-only step responsibility.

The independent Source/Actor owners prove effects. This journal records only
actual input provenance and delivery; it never supplies requested feature facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,need,number,fresh
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import Locator,NativeUI
from adapters.operation_transport_guard import scope as transport_scope
from adapters.script_feature.history import same,pack,unpack
from feature_journeys.contract import arguments
from ios.adapters.tablet_web_app_owner import TabletWebAppOwner
from ios.adapters.tablet_web_inputs import TabletWebInputs
from ios.adapters.tablet_web_app_origin import admitted
from ios.adapters import tablet_web_buttons as buttons,tablet_web_presentation as presentation,tablet_web_state as native_state

VERSION=1


def ordinary_toolbar(runtime,label,send):
    """Normal UIKit toolbar input, including a genuinely loading own page.

    Ready DOM is neither required nor invented. Actual native SourceStamp,
    weak target, current presentation and ordinary WDA button authority are
    independently retained before the once-only request.
    """
    source=runtime.observer.source;source.bound();binding=source.binding
    need(source.role=='primary' and callable(send))
    need(label in ('Close','Back','Reload'));started=last=source.monotonic();failed=False
    def bounded():
        nonlocal last,failed
        now=source.monotonic()
        if failed or not number(now,last,started+1.5) or now-started>=1.5:failed=True;need(False)
        last=now
    with transport_scope(bounded):
        packets={};references={}
        for name in ('sources','trace','uikit','state'):
            child=source.children[name];packets[name]=child.capture(runtime.observer.readers[name])
            references[name]=deepcopy(child.state['records'][-1])
        native_state.join(packets['state'],packets['sources'],packets['trace'],packets['uikit'])
        need(packets['state']['iosTabletWebStateVersion']==2 and packets['state']['otherLiveTablets']==0)
        roots={}
        for app in source.app_sources():
            proof=admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],binding,after_epoch=app['afterEpochMs'])
            for control in proof['controls'].values():
                need(control['rootInstance']==packets['sources']['instance'])
                roots.setdefault(control['root'],set()).add(proof['profile']['assignedUrl'])
        choices=[]
        for candidate in packets['state']['presentations']:
            ref=candidate['source'];navigation=[item for item in packets['sources']['navigations'] if item['id']==ref['navigation']]
            if ref['root'] not in roots or len(navigation)!=1:continue
            need(navigation[0]['root']==ref['root'] and navigation[0]['scriptUrl'] in roots[ref['root']])
            choices.append(native_state.current_presentation(packets['state'],ref,handle=candidate['handle']))
        need(len(choices)==1);selected=choices[0];view=selected['snapshot'];presentation.current(view)
        ui=NativeUI(runtime.client,binding['sessionId'],lambda:runtime.process() is not None,
            monotonic=source.monotonic,sleep=runtime.transport.sleep)
        element=ui._resolve(Locator('accessibility id',label));rect=ui._request('GET',element+'/rect')
        kind=ui._request('GET',element+'/attribute/type');actual_label=ui._request('GET',element+'/attribute/label')
        exact(rect,{'x','y','width','height'});need(kind=='XCUIElementTypeButton' and actual_label==label
            and all(number(rect[key],-1e6,1e6) for key in rect) and rect['width']>0 and rect['height']>0)
        window=view['screenCoordinates'];wk=view['screenFrame'];x,y=rect['x']+rect['width']/2,rect['y']+rect['height']/2
        need(window[0]<=x<window[0]+window[2] and window[1]<=y<window[1]+window[3]
            and not (wk[0]<=x<wk[0]+wk[2] and wk[1]<=y<wk[1]+wk[3]))
        fresh(packets['state']['clockAfter']['epochMs'],runtime.native_clock());bounded()
        send('POST',element+'/click',{},dict(kind='native-toolbar',label=label,rect=rect,components=references,presentation=selected))


class TabletWebActions:
    def __init__(self,runtime):
        self.runtime=runtime;source=runtime.observer.source;source.bound();need(source.role=='primary')
        self.source,self.root,self.run,self.binding=source,source.root,source.run,source.binding
        self.apps=TabletWebAppOwner(runtime);self.store=PrivateFeatureState(self.root/('tabletweb-actions-'+self.run+'.json'))
        self.saved=self.store.read();self.state=dict(calls=[],pending=None) if self.saved is None else self.decode(self.saved)
        self.inputs=TabletWebInputs(runtime.client,source.children['dom'],runtime.observer.readers['dom'],source.lock,runtime.native_clock,
            monotonic=source.monotonic,epoch_ms=source.epoch_ms)
        if self.saved is None:self.save()
    def envelope(self):return dict(tabletWebActionsVersion=VERSION,binding=self.binding,runId=self.run,payload=pack([self.state]))
    def bound(self):self.source.bound();need(same(self.store.read(),self.saved))
    def decode(self,value):
        exact(value,{'tabletWebActionsVersion','binding','runId','payload'});need(type(value['tabletWebActionsVersion']) is int and value['tabletWebActionsVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0];exact(state,{'calls','pending'})
        need(type(state['calls']) is list and len(state['calls'])<=64);tickets=set()
        for row in state['calls']+([state['pending']] if state['pending'] else []):
            exact(row,{'call','phase','before','after','receipts','requests'})
            call=arguments('feature.tablet-web.act',row['call']);need(call['runId']==self.run and call['fixtureUrl']==self.source.fixture
                and call['ticket'] not in tickets and row['phase'] in ('preparing','issued','waiting','returned','failed')
                and type(row['receipts']) is list and type(row['requests']) is list);tickets.add(call['ticket'])
            # Receipts retain input provenance, never observed page facts.
            for reference in row['receipts']:need(type(reference) is dict)
            for request in row['requests']:
                exact(request,{'method','path','body','returned','ownership'})
                need(request['method'] in ('POST','DELETE') and type(request['path']) is str and type(request['ownership']) is dict)
        need(all(row['phase']=='returned' for row in state['calls']));return deepcopy(state)
    def save(self):
        self.bound();value=self.envelope();self.decode(value);self.store.write(value,self.saved);self.saved=deepcopy(value)
    def pending(self):need(self.state['pending'] is not None);return self.state['pending']
    def source_original(self):return self.runtime.observe()
    def document(self):return self.source.children['dom'].capture(self.runtime.observer.readers['dom'])
    def input(self,label,kind,control,text=None):
        row=self.pending();reference=self.inputs.perform(row['call']['ticket'],label,kind,control,text=text)
        row['receipts'].append(deepcopy(reference));self.save();return reference
    def current_generation(self):
        self.apps.decode();rows=[row for row in self.apps.state['generations'] if row['admission'] is not None];need(rows);return rows[-1]
    def app_button(self,verb):
        generation=self.current_generation();app=self.source.app_originals.read(self.source.app_originals.expand(generation['admission']))
        proof=admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],self.binding,after_epoch=app['afterEpochMs'])
        def home():
            manager=self.apps.manager(generation);snapshot=manager.ui.capture()
            if not snapshot['open']:manager.ui.open_tablet();snapshot=manager.ui.capture()
            if manager.ui.control(snapshot,'tablet.home') is not None:manager.ui.activate('tablet.home')
            else:
                expected=proof['controls'][verb]
                actual=[control for control in snapshot['controls'] if type(control.get('tabletAppButton')) is dict and control['enabled']
                    and all(same(control['tabletAppButton'].get(key),value) for key,value in expected.items() if key!='control')]
                need(len(actual)==1)
        self.apps.once(generation,'button-home-'+verb+'-'+self.pending()['call']['ticket'],home)
        def click():
            started=last=self.source.monotonic();failed=False
            def fresh_input():
                nonlocal last,failed
                now=self.source.monotonic()
                if failed or not number(now,last,started+1.5) or now-started>=1.5:failed=True;need(False)
                last=now
            with transport_scope(fresh_input):
                native=self.runtime.read_auxiliary('widgets')['observation'];actual=self.source.children['buttons'].capture(self.runtime.observer.readers['buttons'])
                selected=self.runtime.returned_controls(actual,self.apps.ownership(generation))[verb]
                need(all(same(selected[key],value) for key,value in proof['controls'][verb].items() if key!='control'))
                buttons.selected(actual,selected,proof['profile'])
                rows=[row for row in native['controls'] if row['id']=='tablet-web-app.'+verb and row['enabled']];need(len(rows)==1)
                need(same(rows[0]['tabletAppButton'],selected));fresh(native['sampleEpochMs'],self.runtime.native_clock())
                ui,_qt=self.apps.input_objects();ui.click_with_token(Locator('accessibility id','OverteNavigation.tablet-web-app.'+verb),rows[0]['token'])
        self.apps.once(generation,'app-'+verb+'-'+self.pending()['call']['ticket'],click)
    def sdk(self,method,path,body,ownership):
        row=self.pending();request=dict(method=method,path=path,body=deepcopy(body),returned=False,ownership=deepcopy(ownership))
        need(not any(not item['returned'] for item in row['requests']));row['requests'].append(request);self.save()
        self.runtime.process();result=self.runtime.client.call(method,'/session/'+self.binding['sessionId']+path,body)
        request['returned']=True;self.save();self.runtime.process();return result
    def toolbar(self,label):return ordinary_toolbar(self.runtime,label,self.sdk)

    def act(self,value):
        # The original operation budget begins before phase/process/source
        # preparation and remains active at every final transport boundary.
        started=last=self.source.monotonic();failed=False
        def deadline():
            nonlocal last,failed
            now=self.source.monotonic()
            if failed or not number(now,last,started+60) or now-started>=60:failed=True;need(False)
            last=now
        with transport_scope(deadline):return self._act(value,deadline)

    def _act(self,value,deadline):
        self.bound();call=deepcopy(arguments('feature.tablet-web.act',value));need(call['runId']==self.run and call['fixtureUrl']==self.source.fixture)
        status=self.runtime.observer.phase.read();need(status['ticket']==call['ticket'] and status['verb']==call['verb'] and same(status['inputs'],call['inputs']))
        found=[row for row in self.state['calls'] if row['call']['ticket']==call['ticket']]
        if found:need(same(found[0]['call'],call));return {'performed':True}
        if self.state['pending'] is not None:
            row=self.state['pending'];need(row['phase']=='waiting' and same(row['call'],call) and call['verb'] in ('open','open-inline-app'))
            return self.open_ready(row,deadline)
        need(self.state['pending'] is None and len(self.state['calls'])<64)
        row=dict(call=call,phase='preparing',before=None,after=None,receipts=[],requests=[]);self.state['pending']=row;self.save()
        try:
            with transport_scope(deadline):
                row['before']=self.source_original();row['phase']='issued';self.save();verb=call['verb']
                if verb=='open':
                    self.apps.prepare(call['ticket']);row['phase']='waiting';self.save();return self.open_ready(row,deadline)
                elif verb in ('focus-type','clear-text'):
                    self.input('focus-text','tap','text');self.input('replace-text','replace','text',call['inputs']['text'] if verb=='focus-type' else '')
                elif verb in ('submit','foreign-origin-message'):self.input('send-message','tap','bridge')
                elif verb=='navigate':
                    target={'page-b.html':'same-origin','reference.html':'reference','recovery.html':'recovery'}[call['inputs']['resource']]
                    document=self.document();links=[row for row in document['source']['dom']['elements'] if row['id']==target];need(len(links)==1)
                    href=urlsplit(links[0]['href']);current=urlsplit(document['source']['nativeView']['url'])
                    need((href.scheme,href.netloc)==(current.scheme,current.netloc) and href.path==current.path.rsplit('/',1)[0]+'/'+call['inputs']['resource'] and not href.query and not href.fragment)
                    self.input('navigate-'+target,'tap',target)
                elif verb in ('back','reload'):self.input(verb+'-document','tap',verb)
                elif verb=='navigate-foreign':
                    document=self.document();current=urlsplit(document['source']['nativeView']['url']);foreign=urlsplit(self.runtime.observer.origins['foreign'])
                    address=urlunsplit((foreign.scheme,foreign.netloc,current.path.rsplit('/',1)[0]+'/'+call['inputs']['resource'],'',''))
                    self.input('focus-foreign-url','tap','foreign');self.input('replace-foreign-url','replace','foreign',address);self.input('navigate-foreign','tap','navigate')
                elif verb=='restore-resource':need(self.runtime.observer.browser()['ready'])
                elif verb=='close':self.toolbar('Close')
                elif verb=='open-inline-app':
                    # A new genuine input generation binds the current inline
                    # ticket. The old VM and its controls are stopped normally;
                    # original native files and weak resources remain owned.
                    self.toolbar('Close');generation=self.current_generation();manager=self.apps.manager(generation)
                    app=self.source.app_originals.read(self.source.app_originals.expand(generation['admission']))
                    url=app['files']['source']['directory']+'/script.js'
                    from ios.adapters.tablet_web_owned_home import enter,leave
                    self.apps.once(generation,'inline-open-manager-'+call['ticket'],lambda:enter(manager,self.apps.state['operations']))
                    self.apps.once(generation,'inline-stop-old-'+call['ticket'],lambda:manager.stop_source(url))
                    self.apps.once(generation,'inline-close-manager-'+call['ticket'],lambda:leave(manager,self.apps.state['operations'],'inline-open-manager-'+call['ticket']))
                    self.apps.prepare(call['ticket']);row['phase']='waiting';self.save();return self.open_ready(row,deadline)
                elif verb=='return-from-inline':self.toolbar('Close');self.app_button('return')
                elif verb=='hold-inline-message':
                    receipt=self.runtime.defer('arm');row['receipts'].append(dict(defer=receipt));self.save();self.input('send-held-inline','tap','bridge')
                elif verb=='deliver-retired-inline-message':
                    packet=self.source.children['deferred'].capture(self.runtime.observer.readers['deferred'])
                    from ios.adapters.tablet_web_deferred import held
                    receipt=self.runtime.defer('deliver',held(packet)['id']);row['receipts'].append(dict(defer=receipt));self.save()
                else:need(False)  # Whole lifecycle/close setup is bound by its owning coordinator.
                row['after']=None  # Effects are acquired independently by observe/Actor.
                deadline();row['phase']='returned';self.state['calls'].append(deepcopy(row));self.state['pending']=None;self.save()
            return {'performed':True}
        except Exception:row['phase']='failed';self.save();raise

    def open_ready(self,row,deadline):
        """Independent Actor retains live Home controls before their destruction."""
        from ios.adapters.tablet_web_app_readiness import ready
        generation=self.current_generation()
        if not ready(self.runtime,[self.apps.ownership(generation)]):return None
        try:
            self.app_button('open' if row['call']['verb']=='open' else 'inline');deadline()
            row['phase']='returned';self.state['calls'].append(deepcopy(row));self.state['pending']=None;self.save()
            return {'performed':True}
        except Exception:row['phase']='failed';self.save();raise
