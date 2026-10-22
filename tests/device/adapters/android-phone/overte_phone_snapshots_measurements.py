"""Snapshot effects joined from original owners; input receipts are not effects.

Historical provenance may stay old. Current inventories, work and OS context
must be freshly acquired; this module never retimes an original completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import PurePosixPath
from adapters.native_feature_observation import exact,fresh,integer,need
from overte_phone_script_history import same
from overte_phone_snapshot_capture_facts import capture_facts
from overte_phone_snapshot_source import source as snapshot_source
from overte_phone_snapshot_measurements import validate as vm_source
from overte_phone_snapshot_settings import validate as settings_source
from overte_phone_snapshot_capture_source import source as files_source
from overte_phone_snapshot_readbacks import source as readback_source
from overte_phone_snapshot_consumer import source as consumer_source,COMPONENT as RECEIVER_COMPONENT
from overte_phone_snapshot_upload_source import source as upload_source,require_retired as upload_retired
from overte_phone_snapshot_upload_fixture import validate as provider_source,join as upload_join
from overte_phone_snapshot_cancel import validate as cancel_source
from overte_phone_snapshot_platform import profile
from overte_phone_snapshot_resolution import original as chooser_source,join_grant
from overte_phone_snapshot_system_ui import PRIMARY,tree
from feature_journeys.contract import state as contract_state
from overte_phone_snapshot_documents import source as documents_source,join as documents_join,continuity as documents_continuity,installed as documents_installed
from overte_phone_snapshot_documents_ui import resolution as documents_resolution


class SnapshotPending(Exception):
    """A valid original owner still reports unfinished work."""


def one(rows,predicate):
    selected=[row for row in rows if predicate(row)];need(len(selected)==1);return selected[0]


def document_binding(value,provider,*,run,epoch):
    exact(value,{'snapshotDocumentsBindingVersion','installed','instance','runId','armId','root','floor'})
    need(type(value['snapshotDocumentsBindingVersion']) is int and value['snapshotDocumentsBindingVersion']==2 and value['runId']==run)
    documents_installed(value['installed']);floor=value['floor']
    documents_source(floor,run,value['armId'],floor['observationId'],value['installed'],floor['capturedEpochMs'])
    need(floor['instance']==value['instance'] and {key:floor['root'][key] for key in ('rootId','path','device','inode')}==value['root'])
    documents_source(provider,run,value['armId'],provider['observationId'],value['installed'],epoch)
    documents_continuity(floor,provider);return value


def capture(group,baseline,files,acquisition,*,run,pid,epoch):
    """One actual VM completion, native capture, closed FD and acquired inode."""
    measured=capture_facts(baseline,group,run=run,pid=pid,epoch=epoch)
    files_source(files,epoch);fresh(files['capturedEpochMs'],epoch)
    need(type(acquisition) is dict and acquisition.get('source')=='snapshot-capture-original')
    context=one(measured['contexts'],lambda row:row['id']==acquisition.get('captureId'))
    need(context['mode']=='still' and context['latest']['kind']=='complete')
    terminal=one(context['native'],lambda row:row['kind']=='capture-status' and row['phase']=='complete')
    row=one(files['rows'],lambda row:row['id']==acquisition.get('fileId'))
    native=one(files['captures'],lambda row:row['captureId']==context['id'])
    plan=one(files['plans'],lambda plan:plan['id']==row['planId'])
    need(plan['runId']==row['runId']==run and plan['prefix']=='e2e-'+run and not plan['sealed']
        and native['terminal']=='complete' and native['terminalPath']==terminal['path']==row['path']==acquisition['path']
        and row['captureId']==context['id'] and row['opened'] and row['closed'] and not row['preexisting']
        and not row['retireId'] and not row['nativeRemoved'] and not row['absent'] and row['links']==1
        and row['bytes']>0 and row['closedEpochMs']==acquisition['nativeClosedEpochMs']
        and all(row[key]==acquisition[key] for key in ('bytes','sha256','device','inode')))
    need(integer(acquisition['capturedEpochMs'],1,epoch)) # Historical completion/acquisition is never retimed.
    return dict(captureId=context['id'],fileId=row['id'],path=row['path'],bytes=row['bytes'],sha256=row['sha256'],
        nativeClosedEpochMs=row['closedEpochMs'])


def export_requests(snapshot,baseline):
    """Slice an immutable original callback prefix, preserving every request."""
    for packet in (baseline,snapshot):snapshot_source(packet['source'],packet['capturedEpochMs'])
    before,after=baseline['source']['androidExport'],snapshot['source']['androidExport']
    need(after['instance']==before['instance'] and after['events'][:before['sequence']]==before['events'])
    events=after['events'][before['sequence']:];requests={}
    for row in events:
        request=row['request']
        if row['kind']=='request-active':need(request not in requests);requests[request]=[]
        need(request in requests);requests[request].append(deepcopy(row))
    return requests


def saved(snapshot,baseline,readbacks,acquisition,captured,*,epoch):
    """A successful normal Save plus actual OS destination and readback bytes."""
    fresh(snapshot['capturedEpochMs'],epoch)
    readback_source(dict(accepted=False,source=readbacks));fresh(readbacks['capturedEpochMs'],epoch)
    need(readbacks['snapshotExportReadbacksVersion']==2 and acquisition.get('source')=='snapshot-saved-original')
    request=acquisition.get('request');events=export_requests(snapshot,baseline).get(request);need(events is not None)
    need(not snapshot['source']['androidExport']['pendingIo'])
    need(all(row['action']=='save' and row['source']==captured['path'] for row in events))
    one(events,lambda row:row['kind']=='result-ready' and row['value']=='success')
    one(events,lambda row:row['kind']=='delivered' and row['value']=='success')
    destination=one(readbacks['destinations'],lambda row:row['request']==request)
    original=one(readbacks['osDestinations']['rows'],lambda row:row['request']==request)
    one(events,lambda row:row['kind']=='destination-copied' and row['value']==destination['uri'])
    need(destination['published'] and original['phase']=='qualified' and not original['deleteIssued']
        and original['identity']['uri']==destination['uri'] and original['identity']['displayName']==PurePosixPath(captured['path']).name
        and original['original']=={key:captured[key] for key in ('bytes','sha256')})
    if destination['inserted']:
        one(events,lambda row:row['kind']=='destination-created' and row['value']==destination['uri'])
        one(events,lambda row:row['kind']=='destination-published' and row['value']==destination['uri'] and row['auxiliary']=='1')
    job=one(readbacks['jobs'],lambda row:row['id']==acquisition.get('job'))
    need(job['request']==request and job['phase']=='complete' and job['original'] is not None)
    file=one(readbacks['files'],lambda row:row['id']==acquisition.get('copy'))
    need(job['original']==file and file['request']==request and file['phase']=='complete'
        and all(file[key]==captured[key]==acquisition[key] for key in ('bytes','sha256'))
        and acquisition.get('originalCompletedEpochMs',acquisition['capturedEpochMs'])==job['completedEpochMs']
        and acquisition['capturedEpochMs']>=job['completedEpochMs'])
    need(integer(acquisition['capturedEpochMs'],1,epoch)) # Historical completion/acquisition is never retimed.
    return dict(request=request,job=job['id'],copy=file['id'],bytes=file['bytes'],sha256=file['sha256'])


def shared(snapshot,baseline,readbacks,consumer,consumer_binding,acquisition,captured,*,run,arm,epoch):
    """Only the separate original ACTION_SEND consumer proves consumption."""
    fresh(snapshot['capturedEpochMs'],epoch)
    readback_source(dict(accepted=False,source=readbacks));fresh(readbacks['capturedEpochMs'],epoch)
    exact(consumer_binding,{'installed','instance'})
    consumer_source(consumer,run,arm,consumer['observationId'],consumer_binding['installed'],epoch)
    need(consumer['instance']==consumer_binding['instance'] and acquisition.get('source')=='snapshot-receiver-original'
        and consumer['phase']=='complete' and not consumer['retired'] and consumer['originalClosed'] and not consumer['cancelled'])
    request=acquisition.get('request');events=export_requests(snapshot,baseline).get(request);need(events is not None)
    need(not snapshot['source']['androidExport']['pendingIo'])
    need(all(row['action']=='share' and row['source']==captured['path'] for row in events))
    chosen=one(events,lambda row:row['kind']=='share-chosen');need(chosen['value']==RECEIVER_COMPONENT)
    one(events,lambda row:row['kind']=='delivered' and row['value']=='success')
    grant=one(readbacks['shareGrants']['rows'],lambda row:row['request']==request)
    identity=consumer['identity'];original=consumer['original'];need(identity is not None and original is not None)
    one(events,lambda row:row['kind']=='share-uri' and row['value']==identity['uri'])
    need(grant['component']==identity['component']==RECEIVER_COMPONENT and grant['uri']==identity['uri']
        and grant['ownerUid']==identity['providerUid'] and grant['receiverUid']==identity['receiverUid']
        and identity['permissionAtOpen'] and original['id']==acquisition.get('copy')
        and all(original[key]==captured[key]==acquisition[key] for key in ('bytes','sha256'))
        and acquisition.get('originalCompletedEpochMs',acquisition['capturedEpochMs'])==consumer['completedEpochMs']
        and acquisition['capturedEpochMs']>=consumer['completedEpochMs'])
    need(integer(acquisition['capturedEpochMs'],1,epoch)) # Historical completion/acquisition is never retimed.
    return dict(request=request,copy=original['id'],bytes=original['bytes'],sha256=original['sha256'])


def uploaded(native,provider,acquisition,captured,*,ticket,epoch):
    """Native HTTP replies join the independently retained actual multipart."""
    upload_source(native,epoch);fresh(native['capturedEpochMs'],epoch)
    upload_retired(native)
    provider_source(provider,provider['runId'],provider['requestId'],epoch)
    need(acquisition.get('source')=='snapshot-upload-original')
    original=one(provider['requests'],lambda row:row['requestId']==acquisition.get('request'))
    job=one(native['jobs'],lambda row:any(request['responseId']==original['response']['responseId'] for request in row['requests']))
    joined=upload_join(native,provider,job['id'],ticket=ticket,image_bytes=captured['bytes'],image_sha256=captured['sha256'],path=captured['path'],success=True)
    metadata=acquisition['metadata']
    need(original in joined['requests'] and original['method']=='POST' and original['target']=='/api/v1/snapshots'
        and all(acquisition[key]==captured[key] for key in ('bytes','sha256'))
        and metadata['instance']==provider['instance'] and metadata['runId']==provider['runId']
        and metadata['requestId']==original['requestId'] and metadata['ticket']==ticket
        and metadata['body']==original['body'] and metadata['image']==original['image']
        and metadata['originalCompletedEpochMs']==original['completedEpochMs']==acquisition['originalCompletedEpochMs'])
    need(integer(acquisition['capturedEpochMs'],1,epoch)) # Historical completion/acquisition is never retimed.
    return joined


def inventory(value,native,*,run,epoch):
    """All actual files in the owned namespace, including unfinished originals."""
    exact(value,{'files','rows','capturedEpochMs'});fresh(value['capturedEpochMs'],epoch)
    files_source(native,epoch);fresh(native['capturedEpochMs'],epoch)
    rows=[row for row in native['rows'] if row['runId']==run]
    need(same(value['rows'],rows))
    actual={row['basename']:row for row in value['files']};need(len(actual)==len(value['files']))
    expected={PurePosixPath(row['path']).name:row for row in rows if not row['absent']}
    need(set(actual)==set(expected))
    for name,row in expected.items():
        if not row['closed']:raise SnapshotPending()
        need(row['opened'] and row['phase']=='closed' and not row['preexisting'] and row['bytes']>0
            and all(actual[name][key]==row[key] for key in ('device','inode','bytes','uid','links','sha256')))
    return deepcopy(rows)


def document(readbacks,provider,binding,acquisition,captured,phone_uid,resolution,*,run,epoch):
    """Independent actual DocumentsProvider creator, writer, FD and bytes."""
    document_binding(binding,provider,run=run,epoch=epoch)
    need(provider['complete'] and provider['instance']==binding['instance'] and binding['runId']==run
        and not provider['retired'] and all(provider['root'][key]==binding['root'][key] for key in ('rootId','path','device','inode')))
    exact(phone_uid,{'snapshotPhoneUidVersion','uid','requestedEpochMs','capturedEpochMs'})
    need(type(phone_uid['snapshotPhoneUidVersion']) is int and phone_uid['snapshotPhoneUidVersion']==1 and integer(phone_uid['uid'],1))
    fresh(phone_uid['requestedEpochMs'],epoch);fresh(phone_uid['capturedEpochMs'],epoch);documents_resolution(resolution)
    need(acquisition.get('source')=='snapshot-document-original')
    actual=one(provider['documents'],lambda row:row['documentId']==acquisition.get('documentId'))
    destination=one(readbacks['osDestinations']['rows'],lambda row:row['identity'] is not None
        and row['identity'].get('documentId')==actual['documentId'])
    need(destination['phase']=='qualified' and not destination['deleteIssued']
        and destination['original']=={key:captured[key] for key in ('bytes','sha256')})
    documents_join(destination['identity'],actual,provider,phone_uid['uid'],resolution)
    need(all(fd['closed'] and not fd['error'] for fd in provider['fdLifetimes'] if fd['documentId']==actual['documentId'])
        and acquisition['uri']==actual['uri'] and acquisition['capturedEpochMs']==actual['writeClosedEpochMs']
        and integer(acquisition['acquiredEpochMs'],actual['writeClosedEpochMs'],epoch)
        and all(acquisition[key]==actual[key]==captured[key] for key in ('bytes','sha256')))
    return deepcopy(actual)


def provider_quiet(value,*,run,epoch,closed=False):
    """Actual story absence; retained wire/image ownership ends at fixture close."""
    provider_source(value,run,value['requestId'],epoch)
    need(value['stories']==0 and value['inflight']==0 and not value['held'])
    if closed:need(value['active'] is False)
    if not value['active']:
        need(value['uploads']==0 and all(row['state']=='retired' for row in value['requests']))
    return value


def no_owned_exports(snapshot,baseline,readbacks):
    """An unavailable backend is not absence; actual native history proves no export."""
    readback_source(dict(accepted=False,source=readbacks));need(readbacks.get('initialized') is False)
    need(not export_requests(snapshot,baseline) and not snapshot['source']['androidExport']['activeRequest']
        and not snapshot['source']['androidExport']['pendingIo'])
    return dict(snapshot=deepcopy(snapshot),baseline=deepcopy(baseline),readbacksUnavailable=deepcopy(readbacks))


def retired(group,native_files,actual_inventory,readbacks,upload,settings,*,run,epoch,consumer=None,consumer_binding=None,documents=None,documents_binding=None,baseline=None):
    """Fresh current absence permits an empty *live scope*, never raw erasure."""
    vm_source(group,run=run,pid=group['snapshot']['processId'],epoch=epoch)
    files_source(native_files,epoch);fresh(native_files['capturedEpochMs'],epoch)
    rows=inventory(actual_inventory,native_files,run=run,epoch=epoch)
    need(not actual_inventory['files'] and all(row['closed'] and row['absent'] and row['retireId'] for row in rows))
    plans=[row for row in native_files['plans'] if row['runId']==run]
    need(plans and all(row['sealed'] and row['sealId'] for row in plans))
    readback_source(dict(accepted=False,source=readbacks));destinations=grants=None
    if readbacks.get('initialized') is False:
        need(baseline is not None);no_owned_exports(group['snapshot'],baseline['snapshot'],readbacks)
        if consumer is not None:need(consumer['original'] is None and not consumer['files'])
        if documents is not None:need(not documents['plans'] and not documents['documents'] and not documents['fdLifetimes'])
    else:
        fresh(readbacks['capturedEpochMs'],epoch)
        need(readbacks['snapshotExportReadbacksVersion']==2 and readbacks['copiesRetired'] and readbacks['workersTerminated']
            and not readbacks['files'] and all(row['phase'] in ('complete','failed') for row in readbacks['jobs']))
        destinations=readbacks['osDestinations'];grants=readbacks['shareGrants'];need(destinations['pending']==0)
        fresh(destinations['checkedEpochMs'],epoch);fresh(grants['checkedEpochMs'],epoch)
        need(all(row['phase']=='retired' and row['absent'] and row['deleteIssued'] for row in destinations['rows'])
            and all(row['revokeIssued'] and not row['granted'] and not row['chooserGranted'] for row in grants['rows']))
    if consumer is not None:
        need(consumer_binding is not None)
        consumer_source(consumer,run,consumer['armId'],consumer['observationId'],consumer_binding['installed'],epoch)
        need(consumer['instance']==consumer_binding['instance'] and consumer['retired'] and consumer['workersTerminated']
            and not consumer['activityAlive'] and not consumer['grantPresent'] and consumer['originalClosed'] and not consumer['files'])
    else:need(consumer_binding is None and (grants is None or not any(row['component'] for row in grants['rows'])))
    if documents is not None:
        need(documents_binding is not None)
        document_binding(documents_binding,documents,run=run,epoch=epoch)
        need(documents['complete'] and documents['instance']==documents_binding['instance'] and documents['retired']
            and documents['workersTerminated'] and not documents['root']['present']
            and all(row['absent'] for row in documents['documents']) and all(row['closed'] and not row['error'] for row in documents['fdLifetimes']))
        fresh(documents['root']['checkedEpochMs'],epoch)
        for destination in destinations['rows'] if destinations is not None else []:
            identity=destination['identity']
            if identity is None or identity.get('storage')!='documents':continue
            actual=one(documents['documents'],lambda row:row['documentId']==identity['documentId'])
            need(identity['providerInstance']==documents['instance'] and identity['runId']==documents['runId']
                and identity['armId']==documents['armId'] and identity['providerUid']==documents['providerUid']
                and all(identity[key]==actual[key] for key in ('documentId','uri','displayName','device','inode','createUid','createdEpochMs'))
                and destination['original']=={key:actual[key] for key in ('bytes','sha256')}
                and actual['deleteCalls']==1 and destination['deleteCount']==1)
    else:need(documents_binding is None and (destinations is None or not any(row['identity'] is not None and row['identity'].get('storage')=='documents' for row in destinations['rows'])))
    upload_retired(upload);fresh(upload['capturedEpochMs'],epoch)
    request=dict(schemaVersion=1,commandId=settings['commandId'],action='phone-snapshot-settings',runId=run,operation=settings['operation'])
    if settings['operation']=='restore':request.update({key:settings['source'][key] for key in ('restoreId','expectedSha256')})
    settings_source(settings,request,group['snapshot']['processId'],epoch)
    need(settings['source']['scopePresent'] is False and settings['source']['closed'] and settings['source']['restored']
        and settings['source']['retired'] and settings['source']['originalSha256']==settings['source']['currentSha256'])
    fresh(settings['capturedEpochMs'],epoch)
    source=group['snapshot']['source'];latest={}
    for row in source['scriptHistory']['events']:latest[row['id']]=row['kind']
    need(not source['review']['present'] and not source['captures'] and not source['uploads']
        and not source['androidExport']['activeRequest'] and not source['androidExport']['pendingIo']
        and not any(kind in ('pending','processing') for kind in latest.values()))
    return True


def state(frame,baseline,*,run,pid,epoch):
    """Project the closed public state from a role's independently read sources.

    Acquisitions are this role's immutable receipts, never primary verdicts or
    expectations. Every retained effect is rejoined to current actual owners.
    Three-second quiet time and host journal retirement are separate duties.
    """
    exact(frame,{'group','captureFiles','inventory','readbacks','upload','provider','platform','system','resolution',
        'consumer','consumerBinding','acquisitions','cancels','settings','documents','documentsBinding','phoneUid','documentResolution'})
    group=frame['group'];measured=capture_facts(baseline,group,run=run,pid=pid,epoch=epoch)
    snapshot=group['snapshot'];source=snapshot['source'];files=frame['captureFiles'];readbacks=frame['readbacks']
    rows=inventory(frame['inventory'],files,run=run,epoch=epoch)
    provider=frame['provider'];provider_source(provider,run,provider['requestId'],epoch)
    upload=frame['upload'];upload_source(upload,epoch);fresh(upload['capturedEpochMs'],epoch)
    platform=frame['platform'];exact(platform,{'requestedEpochMs','capturedEpochMs','source'})
    need(platform['source']==profile(str(platform['source']['sdk'])));fresh(platform['capturedEpochMs'],epoch)
    fresh(platform['requestedEpochMs'],epoch)
    backend=platform['source']['saveBackend'];system=frame['system']
    if backend=='media-store':
        need(all(frame[key] is None for key in ('documents','documentsBinding','phoneUid','documentResolution')))
    else:
        documents=frame['documents'];binding=frame['documentsBinding'];need(documents is not None and binding is not None)
        document_binding(binding,documents,run=run,epoch=epoch)
        need(documents['complete'] and documents['instance']==binding['instance'] and binding['runId']==run
            and all(documents['root'][key]==binding['root'][key] for key in ('rootId','path','device','inode')))
        documents_resolution(frame['documentResolution'])
        uid=frame['phoneUid'];exact(uid,{'snapshotPhoneUidVersion','uid','requestedEpochMs','capturedEpochMs'})
        need(type(uid['snapshotPhoneUidVersion']) is int and uid['snapshotPhoneUidVersion']==1 and integer(uid['uid'],1)
            and uid['uid']!=documents['providerUid'])
        fresh(uid['requestedEpochMs'],epoch);fresh(uid['capturedEpochMs'],epoch)
        need(all(row['createUid']==frame['documentResolution']['uid'] and (row['writerUid']==0 or row['writerUid']==uid['uid']) for row in documents['documents']))
    exact(system,{'snapshotSystemUiVersion','observationId','component','requestedEpochMs','capturedEpochMs','sourceSha256','xml'}
        if 'snapshotSystemUiVersion' in system else {'snapshotDocumentUiVersion','observationId','component','requestedEpochMs','capturedEpochMs','sourceSha256','xml'})
    version=system.get('snapshotSystemUiVersion',system.get('snapshotDocumentUiVersion'))
    need(type(version) is int and version==1);fresh(system['requestedEpochMs'],epoch);fresh(system['capturedEpochMs'],epoch)
    import hashlib
    need(hashlib.sha256(system['xml'].encode()).hexdigest()==system['sourceSha256']);tree(system['xml'])
    component=system['component'];primary=component.split('/')[0]==PRIMARY
    requests=export_requests(snapshot,baseline['snapshot'])
    active=source['androidExport']['activeRequest'];save_sheet=share_sheet=False
    if active:
        events=requests.get(active);need(events is not None);action=events[0]['action']
        if not primary:
            resolution=frame['resolution'];need(resolution is not None and component==resolution['component'])
            if action=='share':
                chooser_source(resolution);need(system.get('snapshotSystemUiVersion')==1)
                share_sheet=True
            else:
                documents_resolution(resolution);need(backend=='document-picker' and system.get('snapshotDocumentUiVersion')==1)
                one(events,lambda row:row['kind']=='document-launched');save_sheet=True
    elif not primary:
        need(component==RECEIVER_COMPONENT and frame['consumer'] is not None)
    if share_sheet:
        need(readbacks.get('snapshotExportReadbacksVersion')==2)
        grant=one(readbacks['shareGrants']['rows'],lambda row:row['request']==active);join_grant(frame['resolution'],grant)
        one(requests[active],lambda row:row['kind']=='share-uri' and row['value']==grant['uri'])
    need(type(frame['acquisitions']) is list and len(frame['acquisitions'])<=256 and type(frame['cancels']) is list and len(frame['cancels'])<=8)
    cancelled={row['id'] for row in measured['contexts'] if row['latest']['kind']=='cancelled'};recipes={}
    for packet in frame['cancels']:
        request=dict(schemaVersion=1,commandId=packet['requestId'],action='phone-snapshot-cancel',runId=run,
            jobId=packet['source']['job'],operation='observe',request={})
        if 'scriptWork' in packet['source']['current']:request['closedReadWorkRequestId']=packet['source']['current']['scriptWork']['requestId']
        cancel_source(packet,request,pid,packet['capturedEpochMs']);recipe=packet['source']
        need(recipe['phase']=='complete' and recipe['request'] in cancelled and recipe['request'] not in recipes)
        context=one(measured['contexts'],lambda row:row['id']==recipe['request'])
        need(recipe['pending']['native']['scriptHistory']['events'][-1]==context['pending']
            and recipe['cancelled']['native']['scriptHistory']['events'][-1]==context['latest'])
        recipes[recipe['request']]=recipe
    need(set(recipes)==cancelled)
    settings=frame['settings']
    if settings is not None and settings['source']['retired']:
        need(primary and not save_sheet and not share_sheet)
        provider_quiet(provider,run=run,epoch=epoch)
        retired(group,files,frame['inventory'],readbacks,upload,settings,run=run,epoch=epoch,
            consumer=frame['consumer'],consumer_binding=frame['consumerBinding'],documents=frame['documents'],documents_binding=frame['documentsBinding'],baseline=baseline)
        result=dict(open=False,pending=False,captureHistory=[],files=0,saved=0,uploads=0,shares=0,
            saveBackend=backend,savePermission=platform['source']['savePermission'],saveSheet=False,shareSheet=False,error='none')
        contract_state('snapshots',result);return result
    live=[row for row in rows if not row['absent']];need(len(live)<=1)
    acquired={}
    for item in frame['acquisitions']:
        need(type(item) is dict and item.get('source') in ('snapshot-capture-original','snapshot-saved-original','snapshot-receiver-original','snapshot-upload-original','snapshot-document-original'))
        key=(item['source'],item.get('fileId',item.get('request',item.get('documentId'))));acquired[key]=item
    captures=[]
    for row in live:
        receipt=acquired.get(('snapshot-capture-original',row['id']));need(receipt is not None)
        captures.append(capture(group,baseline,files,receipt,run=run,pid=pid,epoch=epoch))
    need(len(captures)==len([row for row in measured['contexts'] if row['latest']['kind']=='complete']))
    saved_count=shared_count=uploaded_count=0
    if readbacks.get('initialized') is False:
        # Keep this exact unavailable packet. Before any owned export, the
        # immutable empty export prefix proves no scope-owned export was issued;
        # it does not become a fictional empty OS destination inventory.
        readback_source(dict(accepted=False,source=readbacks))
        need(not requests and not upload['jobs'] and not any(item['source']!='snapshot-capture-original' for item in frame['acquisitions']))
    else:
        readback_source(dict(accepted=False,source=readbacks));fresh(readbacks['capturedEpochMs'],epoch)
        need(readbacks['snapshotExportReadbacksVersion']==2)
        for destination in readbacks['destinations']:
            need(destination['request'] in requests)
            owner=one(readbacks['osDestinations']['rows'],lambda row:row['request']==destination['request'])
            if destination['published'] and owner['phase']!='retired':
                need(len(captures)==1)
                receipt=acquired.get(('snapshot-saved-original',destination['request']));need(receipt is not None)
                saved(snapshot,baseline['snapshot'],readbacks,receipt,captures[0],epoch=epoch)
                if backend=='document-picker':
                    need(owner['identity'].get('storage')=='documents' and frame['documents'] is not None)
                    receipt=acquired.get(('snapshot-document-original',owner['identity']['documentId']));need(receipt is not None)
                    document(readbacks,frame['documents'],frame['documentsBinding'],receipt,captures[0],frame['phoneUid'],
                        frame['documentResolution'],run=run,epoch=epoch)
                else:need(owner['identity'].get('storage') is None)
                saved_count+=1
        if frame['consumer'] is not None and frame['consumer']['phase']=='complete' and not frame['consumer']['retired']:
            receipt=one(list(acquired.values()),lambda row:row['source']=='snapshot-receiver-original')
            need(len(captures)==1)
            shared(snapshot,baseline['snapshot'],readbacks,frame['consumer'],frame['consumerBinding'],receipt,captures[0],
                run=run,arm=frame['consumer']['armId'],epoch=epoch);shared_count=1
    terminal=[]
    for event in upload['events']:
        if event['kind']=='terminal':terminal.append(one(upload['jobs'],lambda row:row['id']==event['jobId']))
    for job in upload['jobs']:
        need(len(captures)==1 and job['path']==captures[0]['path'])
        if job['terminal']=='success':
            original=one(provider['requests'],lambda row:row['response'] is not None and any(request['stage']=='image'
                and request['responseId']==row['response']['responseId'] for request in job['requests']))
            receipt=acquired.get(('snapshot-upload-original',original['requestId']));need(receipt is not None)
            uploaded(upload,provider,receipt,captures[0],ticket=original['ticket'],epoch=epoch);uploaded_count+=1
    review=source['review']['review'] if source['review']['present'] else None
    error='none'
    if review is not None and review['statusError']:
        need(terminal and terminal[-1]['terminal']=='error' and len(captures)==1)
        job=terminal[-1]
        original=one(provider['requests'],lambda row:row['method']=='POST' and row['response'] is not None and row['response']['status']==0
            and row['target']=='/api/v1/snapshots' and row['body']['bytes']<=job['requests'][0]['sentBytes'])
        joined=upload_join(upload,provider,job['id'],ticket=original['ticket'],image_bytes=captures[0]['bytes'],
            image_sha256=captures[0]['sha256'],path=captures[0]['path'],success=False)
        need(joined['offline']);error='offline'
    result=dict(open=bool(review is not None and review['visible']),pending=measured['pending'],captureHistory=measured['history'],
        files=len(captures),saved=saved_count,uploads=uploaded_count,shares=shared_count,saveBackend=backend,
        savePermission=platform['source']['savePermission'],saveSheet=save_sheet,shareSheet=share_sheet,error=error)
    contract_state('snapshots',result);return result
