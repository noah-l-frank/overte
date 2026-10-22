"""Closed cleanup recipes using the same durable ordinary input owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from feature_journeys.contract import arguments,identifier
from feature_journeys.navigation_scene import resource_root
from ios.adapters.avatar_controls import nonce
from ios.adapters.avatar_input_owner import AvatarInputOwner
from ios.adapters.avatar_state import text

VERSION=2
READS=(1,2)
LEGACY_STEPS={'dismiss-avatar','dismiss-people','connections','remove-connection','remove-wearable','restore-model','restore-scale','delete-bookmark'}
STEPS=LEGACY_STEPS|{'close-page'}


def call(value):
    exact(value,{'avatarCleanupInputCallVersion','contractVersion','runId','fixtureUrl','ticket','index','step','inputs'})
    version=value['avatarCleanupInputCallVersion']
    need(type(version) is int and version in READS and integer(value['index'],1,64)
        and value['step'] in (LEGACY_STEPS if version==1 else STEPS))
    arguments('feature.avatar-people.cleanup',{key:value[key] for key in ('contractVersion','runId')})
    identifier(value['ticket']);resource_root(value['fixtureUrl'],value['runId']);step,inputs=value['step'],value['inputs']
    if step=='connections':exact(inputs,set())
    elif step=='close-page':exact(inputs,{'rootId','page'});need(nonce(inputs['rootId']) and inputs['page'] in ('avatar','people'))
    elif step=='dismiss-avatar':
        exact(inputs,{'rootId','dialog'});need(nonce(inputs['rootId']) and inputs['dialog'] in ('popup','favorite','settings','wearables'))
    elif step=='dismiss-people':
        exact(inputs,{'rootId','peer','requestId','phase'})
        need(all(nonce(inputs[key]) for key in ('rootId','peer','requestId'))
            and inputs['phase'] in ('incoming','outgoing','accepted','submitting','polling','success','cancelled','declined','error'))
    elif step=='restore-scale':exact(inputs,{'value'});need(number(inputs['value'],.1,4) and abs(inputs['value']*10-round(inputs['value']*10))<.0001)
    elif step=='remove-wearable':exact(inputs,{'entityId'});need(nonce(inputs['entityId']))
    elif step=='restore-model':exact(inputs,{'url'});text(inputs['url'],2048);need(bool(inputs['url']))
    elif step=='remove-connection':exact(inputs,{'username'});text(inputs['username'],256);need(inputs['username'].startswith('e2e-'));identifier(inputs['username'][4:])
    else:exact(inputs,{'name'});need(inputs['name']=='e2e-'+value['runId'])
    return value


class AvatarCleanupInputOwner(AvatarInputOwner):
    VERSION_KEY='iosAvatarCleanupInputOwnerVersion'
    STORE_SUFFIX='cleanup-inputs'
    WRITER_VERSION=VERSION
    READ_VERSIONS=READS

    def call_arguments(self,value):return call(value)
    def call_key(self,value):return value['ticket'],value['index']

    def authorize(self,original):
        current=self.state['calls'][-1]['arguments'];call(current)
        step,inputs,control=current['step'],current['inputs'],original['controlId'];reference=original['reference']
        if step=='close-page':
            page=next((row for row in reference['controls'] if row['id']==inputs['page']+'.page'),None)
            need(control=='tablet.home' and page is not None and page['rootId']==inputs['rootId'] and page['dialog']=='none');return
        # Navigation remains normal original UI input. It cannot grant a
        # different product operation or remove an unowned row.
        navigation={'tablet.home','avatar.entry','people.entry'}
        if control in navigation or control.startswith('tablet.page.'):return
        allowed=set()
        if step=='connections':allowed={'people.nearby','people.connections'}
        elif step=='dismiss-avatar':
            page=next((row for row in reference['controls'] if row['id']=='avatar.page'),None)
            need(page is not None and page['rootId']==inputs['rootId'] and page['dialog']==inputs['dialog'])
            allowed={'avatar.'+inputs['dialog']+'.cancel'}
        elif step=='dismiss-people':
            page=next((row for row in reference['controls'] if row['id']=='people.page'),None)
            need(page is not None and page['rootId']==inputs['rootId'] and page['dialog']=='connection')
            state=page['connectionState'];need(all(state.get(key)==inputs[key] for key in ('peer','requestId','phase')))
            allowed={'people.decline' if inputs['phase']=='incoming' else 'people.cancel'}
        elif step=='restore-model':
            allowed={'avatar.url-open','avatar.url','avatar.popup.confirm'}
            if control in ('avatar.url','avatar.popup.confirm'):
                page=next(row for row in reference['controls'] if row['id']=='avatar.page')
                need(page['dialog']=='popup' and page['popupTitle']=='Specify Avatar URL')
            if original['action']=='replace':need(control=='avatar.url' and same(original['value'],inputs['url']))
        elif step=='restore-scale':
            allowed={'avatar.settings-open','avatar.scale','avatar.settings.confirm'}
            if control=='avatar.scale':need(original['action']=='set-value' and same(original['value'],inputs['value']))
        elif step=='remove-wearable':
            allowed={'avatar.wearables-open','avatar.wearable-choice','avatar.wearable-remove','avatar.wearables.confirm'}
            if control=='avatar.wearable-choice' and original['action']=='select-index':
                row=next(row for row in reference['controls'] if row['id']==control);need(row['choices'][original['value']]==inputs['entityId'])
            if control=='avatar.wearable-remove':
                row=next(row for row in reference['controls'] if row['id']==control);need(row['selectedId']==inputs['entityId'])
        elif step=='remove-connection':
            suffix=hashlib.sha256(inputs['username'].encode()).hexdigest()[:32]
            allowed={'people.connections','people.connection-select.'+suffix,'people.remove.'+suffix}
        elif step=='delete-bookmark':
            suffix=hashlib.sha256(inputs['name'].encode()).hexdigest()[:32]
            allowed={'avatar.manage','avatar.favorite.'+suffix,'avatar.popup.confirm'}
            if control=='avatar.favorite.'+suffix:
                row=next(row for row in reference['controls'] if row['id']==control)
                page=next(row for row in reference['controls'] if row['id']=='avatar.page')
                need(row['name']==inputs['name'] and page['manage'])
            if control=='avatar.popup.confirm':
                page=next(row for row in reference['controls'] if row['id']=='avatar.page')
                need(page['popupTitle']=='Delete Favorite: '+inputs['name'])
        need(control in allowed)

    def intent(self,original):
        self.bound();self.authorize(original);return super().intent(original)

    def decode(self,value):
        state=super().decode(value);old=self.state
        try:
            self.state={'calls':[]}
            for index,item in enumerate(state['calls'],1):
                need(item['arguments']['avatarCleanupInputCallVersion']<=value[self.VERSION_KEY])
                need(item['arguments']['index']==index and item['arguments']['ticket']==state['calls'][0]['arguments']['ticket'])
                self.state['calls'].append(item)
                for event in item['events']:self.authorize(event['intent'])
        finally:self.state=old
        return state
