"""Route exact failed preparation without reentering image or scene setup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from feature_journeys.contract import arguments
from feature_journeys.graphics_resources import fixture_url
from feature_journeys.witness import Client
from ios.adapters.navigation_partial_preparation_abort import owner
from ios.adapters.navigation_whole_feature import NavigationWholeFeature


def verify(whole,call,result):
    """Return whether cleanup ended a failed setup; never query the dead SDK."""
    need(type(whole) is NavigationWholeFeature)
    f=whole.flow;call=arguments('feature.world-navigation.cleanup',call)
    need(f.role=='primary' and call['runId']==f.run and same(result,{'performed':True}))
    with f.held():
        value=PrivateFeatureState(f.store.path.with_name('ios-navigation-preparation-abort.json')).read()
        if value is None:return False
        original=owner(f).result();need(original['status']=='failed' and original['processEnded'] and original['sdkAbsent'])
        return True


def retire_existing(runtime,selector,config):
    """A persisted failed owner has priority over ordinary generic cleanup."""
    directory=runtime.state_path(selector).parent
    if PrivateFeatureState(directory/'ios-navigation-feature.json').read() is not None:return None
    store=PrivateFeatureState(directory/'ios-navigation-whole-feature.json');value=store.read()
    previous=PrivateFeatureState(directory/'ios-navigation-preparation-abort.json').read()
    if value is None:
        need(previous is None);return None
    exact(value,{'iosNavigationWholeFeatureVersion','runId','artifactRoot','payload'})
    need(type(value['iosNavigationWholeFeatureVersion']) is int and value['iosNavigationWholeFeatureVersion']==1)
    from ios.adapters.navigation_configuration import settings
    chosen=settings(dict(artifactRoot=value['artifactRoot']))
    if previous is None:
        # Only explicit private fixture configuration supplies a first live
        # cleanup authority. Historical replay uses its retained exact URL.
        from ios.adapters.feature_configuration import validate,reader
        validate(config);need('world-navigation' in config['areas'] and same(chosen,config['worldNavigation']))
        client=reader(config)
    else:
        need(type(previous) is dict);fixture_url(previous['fixtureUrl'])
        def forbidden(*_args,**_kwargs):need(False)
        client=object.__new__(Client);client.url=previous['fixtureUrl'];client.request=forbidden
    whole=runtime._navigation_feature(selector,value['runId'],role='primary',client=client,settings=chosen)
    need(type(whole) is NavigationWholeFeature);f=whole.flow
    with f.held():
        whole.load();need(same(whole.previous,value) and same(store.read(),value))
        result=owner(f).finish();need(result['status']=='failed' and result['processEnded'] and result['sdkAbsent'])
    return {'cleaned':True}
