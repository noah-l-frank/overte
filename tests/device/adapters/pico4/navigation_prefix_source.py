"""Original eight-field Navigation observations for the normal opening prefix.

This reader performs no ordinary input and receives no desired state. The
initial prefix deliberately refuses a modal, non-directory tab or changed
acquisition bracket; later lookup/transit/restart joins remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_location_bookmarks import validate as bookmarks_packet
from adapters.native_navigation_directory import validate as directory_packet, joined_directory
from adapters.native_navigation_directory import continuation as directory_advance, profile as script_profile
from adapters.native_navigation_environment import validate as environment_packet, logged_out
from adapters.native_navigation_environment import continuation as environment_advance, endpoint
from adapters.native_navigation_modals import validate as modals_packet
from adapters.native_navigation_modals import validate_continuation as modals_advance
from adapters.native_navigation_panels import validate as panels_packet
from adapters.native_navigation_panels import continuation as panels_advance
from adapters.navigation_arrival import pose_packet, advance as pose_advance
from adapters.normal_feature_state import context as binding_context
from adapters.script_journey.history import same
from adapters.token_places_ui import snapshot, TokenPlacesUI, sha
from feature_journeys.contract import state as public_state
from feature_journeys.fixtures import context
from feature_journeys.navigation_fixture import validate_status, configuration
from feature_journeys.phase_fixture import validate as phase_packet
from navigation_observation import viewpoint_urls

VERSION=1


def request(value,action):
    return dict(schemaVersion=1,commandId=value['commandId'],action=action,runId=value['runId'])


def current_roots(value):
    return [row for row in value['roots'] if row['alive'] and row['inCurrentTree']]


def advance(before,after):
    pose_advance(before['pose'],after['pose'])
    for key,validator in (('panels',panels_advance),('environment',environment_advance),
                          ('modals',modals_advance),('directory',directory_advance)):
        validator(before[key],after[key])
    old,new=before['bookmarks'],after['bookmarks']
    need(old['instance']==new['instance'] and new['sequence']>old['sequence']
        and new['requestedEpochMs']>=old['capturedEpochMs'] and new['commandId']!=old['commandId'])
    a,b=before['ui'],after['ui']
    need(a['scope']['instance']==b['scope']['instance'] and a['scope']['processId']==b['scope']['processId']
        and b['scope']['sequence']>=a['scope']['sequence'] and b['scope']['elapsedMs']>=a['scope']['elapsedMs']
        and b['observedEpochMs']>=a['observedEpochMs'])


def projection(frame,run,binding,inputs,provider_instance,origin,profile,receipt,epoch):
    """Validate retained originals at their actual timestamp before projection."""
    exact(frame,{'navigationPrefixSourceVersion','runId','binding','phase','before','after','provider','receipt'})
    need(type(frame['navigationPrefixSourceVersion']) is int and frame['navigationPrefixSourceVersion']==VERSION
        and frame['runId']==run and same(frame['binding'],binding) and same(frame['receipt'],receipt))
    binding_context(binding);pid=int(binding['processIdentity'].split(':',1)[0]);ctx=context(run)
    validate_status(frame['provider'],instance=provider_instance,run=run,inputs=inputs)
    phase=frame['phase'];phase_packet(phase,run=run,area='world-navigation',request=phase['requestId'],epoch=phase['capturedEpochMs'])
    need(phase['active'] and phase['activations'] and frame['provider']['ticket']==phase['activations'][-1]['ticket'])
    if receipt is not None:
        exact(receipt,{'ticket','afterEpochMs'})
        need(integer(receipt['afterEpochMs'],1) and any(row['ticket']==receipt['ticket']
            and row['stimulus']==dict(verb='open',inputs={}) and row['activatedEpochMs']<=receipt['afterEpochMs']
            for row in phase['activations']))
    fresh(frame['provider']['capturedEpochMs'],epoch)
    need(frame['provider']['active'])
    labels=[];pages=[];bookmarks=[]
    for bracket in ('before','after'):
        value=frame[bracket]
        exact(value,{'ui','panels','bookmarks','environment','modals','pose','directory'})
        snapshot(value['ui']);ui=value['ui'];scope=ui['scope']
        need(scope['processId']==pid and scope['instance']==binding['sessionId'])
        fresh(ui['observedEpochMs'],epoch)
        for key,action,validator in (
            ('panels','feature-navigation-panels',panels_packet),
            ('bookmarks','feature-location-bookmarks',bookmarks_packet),
            ('environment','feature-navigation-environment',environment_packet),
            ('modals','feature-navigation-modals',modals_packet),
            ('directory','feature-navigation-directory',directory_packet)):
            packet=value[key];validator(packet,request(packet,action),pid,epoch)
            need(packet['runId']==run)
        panels=value['panels'];pui=panels['ui'];modals=value['modals'];env=value['environment']
        need(all(pui[key]==scope[target] for key,target in (
            ('bridgeId','instance'),('generation','generation'),('sequence','sequence')))
            and pui['open']==ui['open'] and pui['ready']==ui['ready']
            and modals['uiBridgeId']==scope['instance'] and modals['uiGeneration']==scope['generation']
            and modals['uiInputSequence']==scope['sequence'] and modals['tabletOpen']==ui['open'])
        # A later named-error component must join its actual callback and HTTP
        # receipt. This prefix never turns an unrelated/hidden modal into none.
        need(not any(row['rootAlive'] or row['listenerAlive'] for row in modals['records']))
        logged_out(env)
        if env['navigationEnvironmentVersion']==2:need(env['ui']['open']==ui['open'] and env['ui']['ready']==ui['ready'])
        need(env['selectedSettingPresent'] and env['selectedServer']==env['effectiveServer']==origin
            and not env['environmentOverride'] and env['account']['observation']['endpointSha256']==sha(origin)
            and not env['ui']['loginPageAlive'])
        labels.append(pose_packet(value['pose'],run,binding,inputs['sceneUrl'],epoch))
        need(labels[-1] in ('A','B'))
        owned=value['bookmarks']['storage']['owned'];need(len(owned)<=1)
        need(all(row['addressSha256']==sha(viewpoint_urls(inputs['sceneUrl'])['A']) for row in owned))
        bookmarks.append(owned)
        page_rows=[row for row in ui['controls'] if row['id']=='places.page']
        roots=current_roots(panels)
        need(not any(row['profile']=='pico-address-v1' for row in roots))
        if page_rows:
            need(len(page_rows)==1 and ui['open'] and ui['ready'] and receipt is not None)
            page=page_rows[0]
            need(len(roots)==1 and roots[0]['profile']=='pico-places-v1'
                and roots[0]['rootId']==page['rootInstance'] and roots[0]['sourceSha256']==page['componentSourceSha256']
                and roots[0]['visible'] and page['tab']==0 and not page['dialog']['visible']
                and page['currentAddressSha256']==sha(viewpoint_urls(inputs['sceneUrl'])[labels[-1]]))
            # All projected strings are decoded from actual original SHA/length
            # pairs, not from the current verb or a requested search value.
            choices=['',ctx['hidden'],ctx['name']]
            query=[text for text in choices if page['querySha256']==sha(text) and page['queryLength']==len(text)]
            need(len(query)==1)
            joined_directory(value['directory'],ui,frame['provider'],run=run,ticket=frame['provider']['ticket'],
                receipt_ticket=receipt['ticket'],after_epoch=receipt['afterEpochMs'],owned_origin=origin,
                provider_instance=provider_instance,provider_inputs=inputs,source_profile=profile,
                visible=any(row['placeIdSha256']==sha(ctx['destination']) for row in page['directory']['rows']))
            results=[ctx['destination'] for row in page['directory']['rows'] if row['placeIdSha256']==sha(ctx['destination'])]
            need(len(results)<=1)
            owned_hashes={sha(ctx[key]) for key in ('name','renamed')}
            ui_owned=[row for row in page['bookmarks']['rows'] if row['bookmarkNameSha256'] in owned_hashes]
            need(ui_owned==[dict(bookmarkNameSha256=sha(row['name']),bookmarkAddressSha256=row['addressSha256']) for row in owned])
            pages.append(dict(panel=True,searchQuery=query[0],searchResults=results))
        else:
            need(not roots and not any(row['current'] for row in value['directory']['roots']))
            pages.append(dict(panel=False,searchQuery='',searchResults=[]))
    before,after=frame['before'],frame['after']
    need(labels[0]==labels[1] and labels[1] in ('A','B') and same(bookmarks[0],bookmarks[1]) and same(pages[0],pages[1])
        and same(before['ui']['controls'],after['ui']['controls'])
        and all(before['ui']['scope'][k]==after['ui']['scope'][k] for k in ('instance','generation','sequence','processId'))
        and same(before['bookmarks']['storage'],after['bookmarks']['storage'])
        and before['environment']['otherSettingsSha256']==after['environment']['otherSettingsSha256'])
    advance(before,after)
    # Both independently acquired sides agree on current source ownership.
    for key in ('panels','bookmarks','environment','modals','directory'):
        need(before[key]['instance']==after[key]['instance'] and after[key]['sequence']>before[key]['sequence']
            and after[key]['commandId']!=before[key]['commandId']
            and after[key]['capturedEpochMs']>=before[key]['capturedEpochMs'])
    selected=bookmarks[1]
    actual=dict(location=labels[1],bookmark=bool(selected),bookmarkName=selected[0]['name'] if selected else '',
        **pages[1],error='none',addressDialog=False)
    return deepcopy(public_state('world-navigation',actual,run))


class NavigationPrefixSource:
    def __init__(self,normal,arrival,bookmarks,panels,environment,modals,directory,status,
                 run,binding,inputs,provider_instance,origin,profile,clock_ms,guard):
        need(isinstance(normal,TokenPlacesUI) and normal.run==run and all(callable(f) for f in (status,clock_ms,guard)))
        binding_context(binding);configuration(inputs);script_profile(profile);endpoint(origin)
        need(binding['sourceRevision']==inputs['sourceRevision']==profile['sourceRevision']
            and same(arrival.binding,binding) and arrival.run==run and arrival.scene_url==inputs['sceneUrl'])
        self.normal,self.arrival=normal,arrival
        self.readers=dict(bookmarks=bookmarks,panels=panels,environment=environment,modals=modals,directory=directory)
        self.status,self.run,self.binding,self.inputs=status,run,deepcopy(binding),deepcopy(inputs)
        self.provider_instance,self.origin,self.profile=provider_instance,origin,deepcopy(profile)
        self.clock_ms,self.guard=clock_ms,guard
        need(all(reader.pid==int(binding['processIdentity'].split(':',1)[0]) for reader in self.readers.values()))

    def side(self):
        ui=self.normal.capture()
        # Read the original directory after the UI frame updated frameRevision.
        result=dict(ui=ui,pose=self.arrival.read())
        result.update({key:reader.read(self.run) for key,reader in self.readers.items()})
        return result

    def capture(self,receipt,phase):
        need(self.guard() is not False)
        value=dict(navigationPrefixSourceVersion=VERSION,runId=self.run,binding=deepcopy(self.binding),phase=deepcopy(phase),
            before=self.side(),provider=self.status(),after=self.side(),receipt=deepcopy(receipt))
        return value

    def project(self,value):
        return projection(value,self.run,self.binding,self.inputs,self.provider_instance,self.origin,self.profile,
            value['receipt'],value['after']['directory']['capturedEpochMs'])

    def advance_frames(self,before,after):
        advance(before['after'],after['before'])
        validate_status(after['provider'],instance=self.provider_instance,run=self.run,inputs=self.inputs,previous=before['provider'])
        phase=after['phase'];phase_packet(phase,run=self.run,area='world-navigation',request=phase['requestId'],
            epoch=phase['capturedEpochMs'],previous=before['phase'])
