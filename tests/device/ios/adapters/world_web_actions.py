"""The shared nineteen browser inputs through normal world touch/key/lifecycle."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import urlsplit,urlunsplit
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.contract import arguments
from ios.adapters.world_web_api_clock import check
from ios.adapters.world_web_input import WorldWebInput
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_background import WorldWebBackground
from ios.adapters.world_web_measurements import origin
from ios.adapters.world_web_resource_disposition import resource_admission,ResourceAdmissionPending


class WorldWebActions:
    def __init__(self,store,source,inputs,scope,background,origins,guard):
        need(isinstance(store,PrivateFeatureState) and isinstance(inputs,WorldWebInput) and inputs.source is source
            and isinstance(scope,IOSWorldWebScope) and isinstance(background,WorldWebBackground) and background.source is source
            and same(scope.binding,source.binding) and scope.run==source.run and scope.lock is source.lock and callable(guard))
        exact(origins,{'primary','foreign'});need(origin(origins['primary'])!=origin(origins['foreign']))
        self.store,self.source,self.inputs,self.scope,self.background,self.origins,self.guard=store,source,inputs,scope,background,deepcopy(origins),guard
        self.run,self.binding,self.lock=source.run,source.binding,source.lock;self.previous=store.read();self.state=dict(calls=[])
        if self.previous is not None:self.state=self.decode(self.previous)
    def envelope(self,state):return dict(iosWorldWebActionsVersion=1,binding=self.binding,runId=self.run,origins=self.origins,payload=pack([state]))
    def decode(self,value):
        with self.source.validation_round():return self._decode(value)

    def _decode(self,value):
        exact(value,{'iosWorldWebActionsVersion','binding','runId','origins','payload'});rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'calls'});need(type(state['calls']) is list and len(state['calls'])<=32);tickets=set()
        for row in state['calls']:
            exact(row,{'call','phase','before','after'});call=arguments('feature.world-web.act',row['call']);need(call['runId']==self.run and call['ticket'] not in tickets
                and row['phase'] in ('preparing','acting','returned'));tickets.add(call['ticket'])
            for name in ('before','after'):
                if row[name] is not None:self.source.retained(row[name])
            need(row['phase']=='preparing' or row['before'] is not None);need(row['phase']!='returned' or row['after'] is not None)
        return deepcopy(state)
    def save(self):
        check();self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous));value=self.envelope(self.state);self.decode(value)
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);check()
    def current(self,label):return self.source.frame(self.source.capture(label))
    def click(self,call,label,control):return self.inputs.perform(call['ticket'],label,'tap',control)
    def replace(self,call,label,control,text):return self.inputs.perform(call['ticket'],label,'replace',control,text=text)
    @staticmethod
    def field(frame,id):
        document=frame['originals']['document'];need(document is not None and document['source']['dom']['iosWorldWebDOMVersion']>=2)
        rows=[row for row in document['source']['dom']['elements'] if row['id']==id];need(len(rows)==1);return rows[0]
    def act(self,call):
        call=deepcopy(arguments('feature.world-web.act',call));need(call['runId']==self.run and call['fixtureUrl']==self.source.phase.fixture_url)
        status=self.source.phase.read();need(status['ticket']==call['ticket'] and status['verb']==call['verb'] and same(status['inputs'],call['inputs']))
        old=[row for row in self.state['calls'] if row['call']['ticket']==call['ticket']]
        if old:
            row=old[0];need(same(row['call'],call))
            if row['phase']=='returned':return {'performed':True}
        else:
            need(len(self.state['calls'])<32);row=dict(call=call,phase='preparing',before=None,after=None);self.state['calls'].append(row);self.save()
        if row['before'] is None:row['before']=self.source.capture('before-'+call['verb']);self.save()
        row['phase']='acting';self.save();verb=call['verb']
        if verb=='open':
            need(self.source.frame(row['before'])['originals']['ledgerAfter']['iosWorldWebVersion']>=3)
            self.scope.prepare();self.scope.admit_rendered()
        elif verb=='focus-type':
            self.click(call,'focus-text','text');self.replace(call,'type-text','text',call['inputs']['text'])
        elif verb=='clear-text':
            self.click(call,'focus-clear-text','text');self.replace(call,'clear-text','text','')
        elif verb in ('submit','foreign-origin-message'):self.click(call,'send-message','bridge')
        elif verb=='navigate':
            resource=call['inputs']['resource'];control={'page-b.html':'same-origin','recovery.html':'recovery','reference.html':'reference'}[resource]
            current=self.current('before-link');link=self.field(current,control);parsed=urlsplit(link['href']);actual=current['originals']['document']['source']['nativeView']
            need((parsed.scheme,parsed.netloc)==origin(self.origins['primary']) and parsed.path==urlsplit(actual['url']).path.rsplit('/',1)[0]+'/'+resource
                and not parsed.query and not parsed.fragment);self.click(call,'navigate-'+control,control)
        elif verb=='back':self.click(call,'back-document','back')
        elif verb=='reload':self.click(call,'reload-document','reload')
        elif verb=='navigate-foreign':
            current=self.current('before-foreign-navigation');actual=current['originals']['document']['source']['nativeView'];selected=urlsplit(self.origins['foreign'])
            url=urlunsplit((selected.scheme,selected.netloc,urlsplit(actual['url']).path.rsplit('/',1)[0]+'/'+call['inputs']['resource'],'',''))
            self.click(call,'focus-foreign-url','foreign');self.replace(call,'type-foreign-url','foreign',url)
            field=self.field(self.current('foreign-url-observed'),'foreign');need(field['focused'] and field['value']==url)
            self.click(call,'navigate-foreign-url','navigate')
        elif verb=='restore-resource':
            # Reader-owned activation has already changed only server recovery
            # availability. No second control and no product input is sent.
            before=self.source.frame(row['before']);need(before['originals']['browser']['ready'])
        elif verb=='background-resume':self.background.act(call)
        elif verb=='close':self.scope.cleanup()
        else:need(False)
        row['after']=self.source.capture('after-'+verb)
        if verb=='open' and self.source.version>=4:
            # Only passive observations repeat while the original rendered
            # path is not yet complete. The ordinary Script/UI recipe is not
            # replayed, and the enclosing operation retains its 25s ceiling.
            marker=self.scope.state['admission']['marker']
            for _attempt in range(41):
                check();frame=self.source.frame(row['after'])
                try:resource_admission(frame['originals']['closures'],marker['id'],marker['sourceUrl'])
                except ResourceAdmissionPending:
                    self.source.native.sleep(.1);row['after']=self.source.capture('rendered-path-pending')
                else:break
            else:raise ResourceAdmissionPending('Actual World Web rendered resource admission did not complete')
        row['phase']='returned';self.save();return {'performed':True}
