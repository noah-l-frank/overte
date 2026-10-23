"""Version-three failed initial entry keeps actual uncertain ordinary inputs.

Only a preparing whole run, its complete untouched originals and its initial
Go To journals are admitted. No ordinary feature action or restart may borrow
this path. Unknown delivery is retained, never replayed or relabeled entered.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.script_feature.history import same
from navigation_observation import viewpoint_urls
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.navigation_address_inputs import NavigationAddressInputs
from ios.adapters.navigation_preparation_abort import NavigationPreparationAbort,INPUT_PREFIXES,OTHER_OWNERS
from ios.adapters.navigation_scene_inputs import NavigationSceneInputs
from ios.adapters.navigation_whole_feature import NavigationWholeFeature
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.adapters.normal_navigation import SCOPE

VERSION=3


def component(value,binding,proof):
    need(type(value) is dict and set(value)<={'iosNormalNavigation'})
    if value:
        row=value['iosNormalNavigation'];exact(row,{'context','addressOwned','tabletOwned'})
        need(type(row['addressOwned']) is bool and type(row['tabletOwned']) is bool
            and same(row['context'],dict(processId=int(binding['processIdentity']),
                inputInstance=proof['originals']['ui']['instance'],sceneUrl=proof['providerInputs']['sceneUrl'],scope=SCOPE)))


def entry_originals(flow,preparation):
    f=flow;images,admission=preparation.originals();proof=admission.archive();binding=preparation.state['binding']
    need(same(f.state['binding'],binding) and same(f.state['initialBinding'],binding)
        and f.state['stage']==0 and f.state['transferSha256'] is None and f.state['observerOffsets']==dict(primary=0,actor=0)
        and f.state['lastCall'] is None and f.state['phase'] in ('preparing','ready')
        and f.state['providerInstance']==proof['providerInstance'] and same(f.state['providerInputs'],proof['providerInputs']))
    need(f.state['admissionSha256'] in (None,digest(admission.previous)))
    need(f.state['entry']==('pending' if f.state['phase']=='preparing' else 'entered'))
    scene_store=PrivateFeatureState(f.store.path.with_name('ios-navigation-scene-inputs.json'))
    address_store=PrivateFeatureState(f.store.path.with_name('ios-navigation-address-'+binding['processIdentity']+'-inputs.json'))
    scene,address=scene_store.read(),address_store.read();scene_state=address_state=None
    if scene is None:need(address is None and f.state['phase']=='preparing' and f.state['entry']=='pending')
    else:
        need(f.state['admissionSha256']==digest(admission.previous))
        reader=object.__new__(NavigationSceneInputs);reader.store=scene_store;reader.admission=admission
        reader.binding,reader.run,reader.lock=binding,f.run,f.lock;scene_state=reader.decode(scene)
        need(scene_state['phase'] in ('enter-issued','entered'));component(scene_state['component'],binding,proof)
        if address is not None:
            need(scene_state['enterUi'] is not None)
            child=object.__new__(NavigationAddressInputs);child.binding,child.run=binding,f.run;address_state=child.decode(address)
            need(len(address_state['rows'])==1)
            for row in address_state['rows']:
                need(row['key']=='enter' and row['url']==viewpoint_urls(proof['providerInputs']['sceneUrl'])['A'])
                component(row['component'],binding,proof)
            if scene_state['phase']=='entered':
                need(address_state['rows'] and address_state['rows'][0]['phase']=='acknowledged'
                    and same(scene_state['enteredUi'],address_state['rows'][0]['closed']['original']))
        else:need(scene_state['phase']=='enter-issued')
        if f.state['phase']=='ready':need(scene_state['phase']=='entered' and f.state['entry']=='entered')
    need(same(scene_store.read(),scene) and same(address_store.read(),address))
    return dict(iosNavigationEntryPreparationReadsVersion=1,runId=f.run,binding=binding,
        featureSha256=digest(f.previous),preparationSha256=digest(preparation.previous),
        baselines={role:digest(image.previous) for role,image in images.items()},admissionSha256=digest(admission.previous),
        sceneInputsSha256=None if scene is None else digest(scene),addressInputsSha256=None if address is None else digest(address))


class NavigationEntryPreparationAbort(NavigationPreparationAbort):
    def parents(self):
        f=self.flow;f.lock.assert_held();need(f.role=='primary')
        leases=[EmoteOriginalLease(root,[]) for root in {f.root,f.store.path.parent}]
        f.load();whole=NavigationWholeFeature(f);whole.load();preparation=NavigationWholePreparation(f);preparation.load()
        need(f.state is not None and whole.state is not None and whole.state['phase']=='preparing' and whole.state['cleanup'] is None
            and preparation.state is not None and preparation.state['phase'] in ('preparing','entered'))
        allowed={'ios-navigation-scene-inputs.json','ios-navigation-address-'+f.state['binding']['processIdentity']+'-inputs.json'}
        for root in {f.root,f.store.path.parent}:
            for path in root.iterdir():need(not path.name.startswith(INPUT_PREFIXES) or path.parent==f.store.path.parent and path.name in allowed)
        for name in OTHER_OWNERS:need(PrivateFeatureState(f.store.path.with_name(name)).read() is None)
        reads=entry_originals(f,preparation)
        if preparation.state['phase']=='entered':need(f.state['phase']=='ready')
        for lease in leases:lease.guard()
        return dict(whole=whole.previous,preparation=preparation.previous,feature=f.previous,reads=reads),context(preparation.state['binding'])

    def envelope(self,state):
        value=super().envelope(state);value['iosNavigationPreparationAbortVersion']=VERSION;return value

    def result(self):
        value=super().result();value['iosNavigationPreparationAbortResultVersion']=VERSION;return value
