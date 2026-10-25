"""Whole live Tablet quiescence, preserving concrete cache-held owners.

Only fully decoded TabletWebTail originals are inputs. This is a pre-Stop
boundary: held Qt/UIKit/native bitmaps remain explicit responsibilities. No
ACK, hidden keyboard, absent row or ended touch is treated as weak death.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.native_clock_join import digest
from adapters.native_script_terminal import terminal as terminal_done,validate as terminal_original,ACTION as TERMINAL_ACTION
from adapters.script_feature.history import same
from ios.adapters import tablet_web_state as state,uikit_input as uikit,world_web_keys as keys,pointer_state as pointer
from ios.adapters.tablet_web_app_origin import admitted
from ios.adapters.tablet_web_tail import READS,host
from ios.adapters.tablet_web_held_groups import terminal_aliases


def dialog_drained(before,current,managers):
    """Actual newly born listeners need BOTH callback return and weak death."""
    from ios.adapters import script_dialogs as dialogs
    dialogs.validate(current,dict(schemaVersion=1,action=dialogs.ACTION,commandId=current['requestId'],runId=current['runId']),current['processId'],previous=before)
    floor=before['source']['eventSequence'];rows=current['source']['events'];new=rows[floor:]
    # A listener already born before this role's cleanup baseline may still
    # be live. A quiet new suffix cannot turn that original lifetime into
    # death. Historical unrelated completed dialogs need no owned-manager
    # attribution, but every actual observed listener must be returned/dead.
    for identity in {row['dialogInstance'] for row in rows}:
        kinds=[row['kind'] for row in rows if row['dialogInstance']==identity]
        need(len(kinds)==4 and set(kinds)=={'listener-created','response-entered','response-returned','listener-destroyed'}
            and kinds[0]=='listener-created' and kinds.index('response-entered')<kinds.index('response-returned'))
    born=[row for row in new if row['kind']=='listener-created']
    identities={row['dialogInstance'] for row in born}
    existing={row['dialogInstance'] for row in before['source']['events'] if row['kind']=='listener-created'}
    # Cleanup may begin with its real file picker/listener already open. The
    # immutable prefix identifies that exact old birth; actual new response
    # return and destruction must complete it without inventing another birth.
    need(all(row['dialogInstance'] in identities|existing for row in new))
    for row in new:
        if row['kind']=='response-returned' and row['manager'] is not None:
            need(any(same(row['manager'],manager) for manager in managers))
    for identity in identities:
        events=[row for row in new if row['dialogInstance']==identity]
        kinds=[row['kind'] for row in events]
        need(len(kinds)==4 and set(kinds)=={'listener-created','response-entered','response-returned','listener-destroyed'}
            and kinds[0]=='listener-created' and kinds.index('response-entered')<kinds.index('response-returned'))
        returned=next(row['manager'] for row in events if row['kind']=='response-returned')
        if returned is not None:need(any(same(returned,manager) for manager in managers))
    return deepcopy(born)


def _held(alias,kind,actual):
    return dict(resource='panel:tablet-'+alias,kind=kind,originalSha256=digest(actual))


def input_holds(touches):
    """Exact physical UIKit holds; a native UIButton is never a WK view."""
    uikit.original(touches)
    own_views={row['view'] for row in touches['targets'] if uikit._owned(row,touches)}
    wk_views={row['view'] for row in touches['targets'] if 'identity' in row and uikit._owned(row,touches)}
    owned_objects=set(own_views)
    for contact in touches['contacts']:
        if contact['source'] is not None and contact['source']['view'] in own_views:
            owned_objects.add(contact['object']);owned_objects.update(contact['source']['ancestry'])
    for dispatch in touches['dispatches']:
        if any(row['source'] is not None and row['source']['view'] in own_views for row in dispatch['phases']):owned_objects.add(dispatch['event'])
    return [_held('uikit-'+row['id'],'wk-view' if row['id'] in wk_views else 'native-holder',dict(instance=touches['instance'],row=row))
        for row in touches['objects'] if row['id'] in owned_objects and row['alive']]


def retired_vm(stop,current,manager,code,*,after_epoch):
    """Keep an already observed exact VM exit without moving its epoch.

    A prior app generation can genuinely finish before final cleanup begins.
    Only its original complete terminal triple qualifies that retained state;
    a new VM/code/generation still needs fresh post-stop terminal originals.
    """
    terminal_original(current,dict(schemaVersion=1,commandId=current['commandId'],action=TERMINAL_ACTION),current['processId'],
        current['capturedEpochMs'],previous=stop)
    old=[row for row in stop['source']['events'] if row['manager']['instance']==manager['instance']]
    if len(old)==3:
        original=terminal_done(stop,manager,code,after_sequence=old[0]['eventSequence'],after_epoch=manager['assignedEpochMs'])
        actual=terminal_done(current,manager,code,after_sequence=old[0]['eventSequence'],after_epoch=manager['assignedEpochMs'])
        need(same(original,actual));return actual
    return terminal_done(current,manager,code,after_sequence=stop['source']['eventSequence'],after_epoch=after_epoch)


def scripts_drained(before,stop,current,apps):
    """Original VM/ScriptEnding/thread and dialog closure before file deletion."""
    need(all(type(value) is dict and value['row']['status']=='returned' for value in (before,stop,current)))
    packet=current['packets'];stop_packets=stop['packets'];baseline=before['packets']
    managers=[];profiles=[];file_scopes=set()
    for app in apps:
        proof=admitted(app['owner'],app['files'],app['scripts'],app['buttons'],app['controls'],
            current['row']['source']['observation']['binding'],after_epoch=app['afterEpochMs'])
        profiles.append(proof);managers.append(proof['manager']);file_scopes.add(proof['storageRun'])
        retired_vm(stop_packets['terminal'],packet['terminal'],proof['manager'],proof['profile']['code'],
            after_epoch=stop['source']['nativeAfter']['capturedEpochMs'])
    source=packet['scripts']['source'];need(source.get('sourceIdentityVersion')==1 and source.get('membershipSourceVersion')==1 and source['membership']['complete'])
    identities={row['instance'] for row in managers}
    need(not any(row['instance'] in identities for row in source['membership']['managers'])
        and not any(row['required']['instance'] in identities for row in source['engines']))
    dialog_drained(baseline['dialogs'],packet['dialogs'],managers)
    return dict(profiles=profiles,managers=managers,fileScopes=file_scopes)


def bridge_drained(frame,profiles):
    """Actual callback return and queue capture death are separate duties."""
    from ios.adapters import tablet_web_source as trace,web_script_emissions as emissions
    ledger,emitter=frame['ledger'],frame['emitter']
    need(not trace.pending(ledger) and all(ledger[key]==emitter[key] for key in ('runId','fixtureUrl','processId')))
    emissions.original(emitter);need(emitter['complete'])
    for profile in profiles:emissions.settled(emitter,profile['profile'])


def inspect(before,stop,current,apps):
    """Inspect actual restored live originals; every hold retains its identity."""
    need(all(type(value) is dict and value['row']['status']=='returned' for value in (before,stop,current)))
    packet=current['packets'];frame=current['frame'];baseline=before['packets'];stop_packets=stop['packets']
    need(set(READS)<=set(packet) and set(READS)<=set(baseline))
    keys.privacy_qualified(packet['keys']);keys.drained(packet['keys'])
    pointer.drained(baseline['pointer'],packet['pointer'],after_epoch=stop['source']['nativeAfter']['capturedEpochMs'])
    uikit.quiescent(before['frame']['touches'],frame['touches'],after_epoch=stop['source']['nativeAfter']['capturedEpochMs'])
    state.closed(frame['state'],frame['sources'],frame['ledger'],frame['touches'],require_observed=bool(apps))
    native=packet['geometry']['observation']['nativeUi'];need(native['valid'] and native['keyboardVisible'] is False and native['imeInsetBottom']==0)
    widgets=packet['widgets']['observation'];need(widgets['tabletShown'] is False)
    from adapters.script_ui_inventory import validate as inventory
    ui=widgets['scriptInventory'];inventory(ui,pid=frame['ledger']['processId'],epoch=widgets['sampleEpochMs'])
    need(ui['inventoryVersion']==2 and ui['complete'] and not ui['tabletShown']
        and not any(row['rootVisible'] or row['labelVisible'] for row in ui['managers'])
        and not any(row['visible'] or row['closing'] or row['requestId'] for row in ui['pickers'])
        and not any(row['id'].startswith(('scripts.','script-file.','tablet-web-app.')) for row in widgets['controls']))
    roots=ui['rootOwnership'];need(roots['available'] and roots['complete'] and roots['wholeTreeReady'])
    scope=scripts_drained(before,stop,current,apps);file_scopes=scope['fileScopes']
    bridge_drained(frame,scope['profiles'])
    files={name[6:]:value for name,value in packet.items() if name.startswith('files:')}
    need(file_scopes<=set(files) and all(value['operation']=='observe' and value['source']==dict(exists=False,files=[]) for value in files.values()))
    for carrier in frame['sources']['carriers']:
        need('retired' in carrier and 'retireReturned' in carrier and all(not binding['current'] and 'revoked' in binding for binding in carrier['bindings']))
    deferred=frame['deferred'];need(deferred['complete'])
    for row in deferred['records']:
        need(not row['bufferPending'] and not row['callbackAlive'])
        if row['original'] is None:need(row['discarded'] is not None)
        elif row['discarded'] is None:need(row['returned'] is not None and row['finally'] is not None and row['expired'] is not None)
    for row in deferred['commands']:need(row['status']!='issued')
    for row in frame['closures']['contexts']:
        need(all(counter['pending']==0 for counter in row['callbacks'].values()) and row['resources']['policy-grant']['pending']==0)
    for row in frame['buttons']['buttons']:need(row['removed'] is not None)
    held=[]
    for row in roots['roots']:
        if row['weakAlive']:held.append(_held('script-root-'+row['observedIdentity'],'qt-root',row))
    for row in frame['state']['owners']:
        if row['alive']:held.append(_held('native-owner-'+row['id'],'native-holder',dict(instance=frame['state']['instance'],row=row)))
    held.extend(input_holds(frame['touches']))
    for group in ('buttons','controls'):
        for row in frame['buttons'][group]:
            if row['alive']:held.append(_held('app-'+group+'-'+row['id'],'qt-root',dict(instance=frame['buttons']['instance'],row=row)))
    for carrier in frame['sources']['carriers']:
        if carrier['alive'] or any(row['contextAlive'] or row['pageAlive'] for row in carrier['bindings']):
            held.append(_held('carrier-'+carrier['id'],'native-holder',dict(instance=frame['sources']['instance'],row=carrier)))
    for row in frame['closures']['contexts']:
        pending={name:counter for name,counter in row['resources'].items() if counter['pending']}
        if pending:held.append(_held('web-context-'+str(row['id']),'native-holder',dict(instance=frame['closures']['instance'],descriptor=row['descriptor'],pending=pending)))
    need(len({row['resource'] for row in held})==len(held));held.sort(key=lambda row:row['resource'])
    return dict(heldResources=terminal_aliases(held),keysInstance=packet['keys']['source']['instance'],uikitInstance=frame['touches']['instance'],
        nativeSourceInstance=current['source']['nativeAfter']['instance'],inputSequence=packet['keys']['source']['eventSequence'],
        pointerSequence=packet['pointer']['source']['eventSequence'],uikitSequence=frame['touches']['dispatchSequence'],
        terminalSequence=packet['terminal']['source']['eventSequence'],dialogSequence=packet['dialogs']['source']['eventSequence'])


def quiet(before,stop,frames,apps):
    """A three-second native AND host interval excluding acquisition endpoints."""
    need(type(frames) is list and len(frames)>=3)
    proofs=[inspect(before,stop,frame,apps) for frame in frames]
    need(all(same(proof,proofs[0]) for proof in proofs[1:]))
    for left,right in zip(frames,frames[1:]):host(right['row']['before'],left['row']['after'])
    first,last=frames[0],frames[-1]
    need(last['row']['before']['epochMs']-first['row']['after']['epochMs']>=3000
        and last['row']['before']['monotonic']-first['row']['after']['monotonic']>=3)
    for packet_kind in ('keys','pointer','dialogs'):
        a,b=first['packets'][packet_kind],last['packets'][packet_kind]
        need(b['clockBefore']['epochMs']-a['clockAfter']['epochMs']>=3000
            and b['clockBefore']['monotonicMs']-a['clockAfter']['monotonicMs']>=3000)
    for source_kind in ('touches','state'):
        a,b=first['frame'][source_kind],last['frame'][source_kind]
        need(b['clockBefore']['epochMs']-a['clockAfter']['epochMs']>=3000
            and b['clockBefore']['monotonicMs']-a['clockAfter']['monotonicMs']>=3000)
    return dict(tabletWebLiveQuietVersion=1,proof=proofs[-1],first=digest(first['row']),last=digest(last['row']),
        hostBeforeEpochMs=first['row']['after']['epochMs'],hostAfterEpochMs=last['row']['before']['epochMs'],
        hostBeforeMonotonic=first['row']['after']['monotonic'],hostAfterMonotonic=last['row']['before']['monotonic'])
