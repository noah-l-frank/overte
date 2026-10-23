"""Fixed Phone5527 original readback/OS/grant validation with Pico roots.

The conservative SAF full-run filename proof is unchanged. It does not yet
qualify normal Pico parity names on SDK26. No Phone facade/transport is copied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_export_originals import uri

# Original validation only. The original transport is Pico NativeNavigationIO.
OPERATIONS={'observe','read','cancel','remove-copy','retire-copies','remove-destination','inspect-destinations','revoke-share','inspect-shares'}
ROOTS={'/data/'+base+'/org.overte.pico/files/' for base in ('user/0','data')}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None
def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','operation','exportRequest','resourceId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-pico-snapshot-exports'
        and nonce(value['commandId']) and nonce(value['runId']) and type(value['operation']) is str and value['operation'] in OPERATIONS)
    operation=value['operation'];request=value['exportRequest'];id=value['resourceId']
    if operation in ('observe','retire-copies'):need(request==id=='')
    elif operation in ('read','remove-destination','revoke-share'):need(nonce(request) and nonce(id))
    else:need(request=='' and nonce(id))
    return value


def original(value,epoch):
    exact(value,{'id','request','path','phase','bytes','sha256','capturedEpochMs'})
    need(nonce(value['id']) and nonce(value['request']) and value['phase'] in ('planned','reading','failed','complete')
        and integer(value['bytes'],0,256*1024*1024) and integer(value['capturedEpochMs'],0,epoch))
    need(type(value['path']) is str and any(re.fullmatch(re.escape(root)+r'overte-snapshot-e2e-[0-9a-f]{32}/'+value['id']+r'\.bin',value['path']) for root in ROOTS))
    if value['phase']=='complete' or value['bytes']:
        need(value['bytes']>0 and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256'])
            and value['capturedEpochMs']>0)
    else:need(value['sha256']=='' and value['capturedEpochMs']==0)
    return value


def source(value):
    exact(value,{'accepted','source'});need(type(value['accepted']) is bool)
    row=value['source'];need(type(row) is dict)
    if 'initialized' in row:
        exact(row,{'snapshotExportReadbacksVersion','initialized','complete'})
        need(type(row['snapshotExportReadbacksVersion']) is int and row['snapshotExportReadbacksVersion']==1
            and row['initialized'] is False and row['complete'] is True and value['accepted'] is False)
        return value # Uninitialized means unavailable, never an empty OS destination inventory.
    version=row.get('snapshotExportReadbacksVersion')
    exact(row,{'snapshotExportReadbacksVersion','instance','sequence','elapsedMs','complete','copiesRetired','capturedEpochMs',
        'workersTerminated','destinations','jobs','files','removedCopies'}|({'osDestinations','shareGrants'} if version==2 else set()))
    need(type(version) is int and version in (1,2)
        and nonce(row['instance']) and integer(row['sequence'],1) and integer(row['elapsedMs'],0)
        and row['complete'] is True and type(row['copiesRetired']) is bool and type(row['workersTerminated']) is bool
        and integer(row['capturedEpochMs'],1) and all(type(row[key]) is list and len(row[key])<=64 for key in ('destinations','jobs','files','removedCopies')))
    need(not row['workersTerminated'] or row['copiesRetired'])
    destinations={}
    for destination in row['destinations']:
        exact(destination,{'request','uri','inserted','published'});uri(destination['uri'])
        need(nonce(destination['request']) and destination['request'] not in destinations
            and type(destination['inserted']) is bool and type(destination['published']) is bool)
        destinations[destination['request']]=destination
    files={};folders=set()
    for item in row['files']:
        original(item,row['capturedEpochMs']);need(item['id'] not in files and item['request'] in destinations)
        files[item['id']]=item;folders.add(item['path'].rsplit('/',1)[0])
    need(len(folders)<=1 and len(set(row['removedCopies']))==len(row['removedCopies'])
        and all(nonce(id) and id not in files for id in row['removedCopies']))
    jobs=set()
    for job in row['jobs']:
        exact(job,{'id','request','phase','startedEpochMs','completedEpochMs','original'})
        need(nonce(job['id']) and job['id'] not in jobs and job['request'] in destinations
            and destinations[job['request']]['published'] and job['phase'] in ('queued','reading','complete','failed'))
        jobs.add(job['id'])
        need(integer(job['startedEpochMs'],0,row['capturedEpochMs']) and integer(job['completedEpochMs'],0,row['capturedEpochMs']))
        if job['phase']=='queued':need(job['startedEpochMs']==job['completedEpochMs']==0 and job['original'] is None)
        elif job['phase']=='reading':need(job['startedEpochMs']>0 and job['completedEpochMs']==0 and job['original'] is None)
        else:need(job['startedEpochMs']>0 and job['completedEpochMs']>=job['startedEpochMs'])
        if job['original'] is not None:
            item=original(job['original'],job['completedEpochMs']);need(item['request']==job['request'] and item['phase']=='complete'
                and job['phase'] in ('complete','failed') and (files.get(item['id'])==item or item['id'] in row['removedCopies']))
        if job['phase']=='complete':need(job['original'] is not None)
    if row['copiesRetired']:need(not files and all(job['phase'] in ('complete','failed') for job in row['jobs']))
    if version==2:
        os_destinations(row['osDestinations'],destinations,row['capturedEpochMs'])
        share_grants(row['shareGrants'],row['capturedEpochMs'])
    return value


def os_destinations(value,destinations,epoch):
    exact(value,{'snapshotOsDestinationsVersion','complete','pending','checkId','checkedEpochMs','rows'})
    need(type(value['snapshotOsDestinationsVersion']) is int and value['snapshotOsDestinationsVersion'] in (1,2,3) and value['complete'] is True
        and integer(value['pending'],0,64) and (value['checkId']=='' or nonce(value['checkId'])) and integer(value['checkedEpochMs'],0,epoch)
        and type(value['rows']) is list and len(value['rows'])<=64)
    seen=set()
    for row in value['rows']:
        exact(row,{'request','inserted','phase','identity','original','acquiredEpochMs','deleteId','deleteIssued','deleteCount','checkedEpochMs','absent'}|({'verifiedEpochMs'} if value['snapshotOsDestinationsVersion']==3 else set()))
        request=row['request'];need(nonce(request) and request in destinations and request not in seen and type(row['inserted']) is bool
            and row['inserted']==destinations[request]['inserted'] and row['phase'] in ('planned','created','qualified','checking-delete','deleting','delete-uncertain','retired')
            and type(row['deleteIssued']) is bool and type(row['absent']) is bool and integer(row['deleteCount'],-1,2**31-1)
            and integer(row['acquiredEpochMs'],0,epoch) and integer(row['checkedEpochMs'],0,epoch) and (row['deleteId']=='' or nonce(row['deleteId'])))
        seen.add(request)
        if value['snapshotOsDestinationsVersion']==3:
            need(integer(row['verifiedEpochMs'],0,epoch) and (row['original'] is None and row['verifiedEpochMs']==0
                or row['original'] is not None and row['verifiedEpochMs']>=row['acquiredEpochMs']>0))
        if row['identity'] is not None:
            identity=row['identity'];need(type(identity) is dict);documents=identity.get('storage')=='documents'
            exact(identity,{'uri','providerUid','ownerPackage','displayName','device','inode'} | ({'providerPackage','storage','runId','armId','providerInstance','documentId','createUid','createdEpochMs'} if documents else set()))
            parsed=uri(identity['uri']);need(identity['uri']==destinations[request]['uri'] and integer(identity['providerUid'],1)
                and type(identity['displayName']) is str and 0<len(identity['displayName'])<=255 and '/' not in identity['displayName'] and integer(identity['device']) and integer(identity['inode'],1))
            if documents:
                need(value['snapshotOsDestinationsVersion']>=2 and not row['inserted'] and parsed.netloc=='org.overte.e2e.snapshotreceiver.documents'
                    and identity['ownerPackage']==identity['providerPackage']=='org.overte.e2e.snapshotreceiver'
                    and all(nonce(identity[key]) for key in ('runId','armId','providerInstance')) and type(identity['documentId']) is str
                    and re.fullmatch('doc-'+identity['runId']+'-'+identity['armId']+'-[0-9a-f]{32}',identity['documentId'])
                    and parsed.path=='/document/'+identity['documentId'] and integer(identity['createUid'],1) and integer(identity['createdEpochMs'],1,epoch)
                    and re.fullmatch('e2e-'+identity['runId']+r'-[A-Za-z0-9_-]{1,160}\.png',identity['displayName']))
            else:need(parsed.netloc=='media' and identity['ownerPackage']=='org.overte.pico')
        if row['original'] is not None:
            original=row['original'];exact(original,{'bytes','sha256'});need(integer(original['bytes'],1,(32 if row['identity'] is not None and row['identity'].get('storage')=='documents' else 256)*1024*1024) and type(original['sha256']) is str and re.fullmatch('[0-9a-f]{64}',original['sha256']) and row['acquiredEpochMs']>0 and row['identity'] is not None)
        if row['phase']=='planned':need(row['identity'] is row['original'] is None and row['acquiredEpochMs']==0)
        elif row['phase']=='created':need(row['identity'] is not None and row['original'] is None)
        else:need(row['identity'] is not None and row['original'] is not None)
        if row['deleteIssued']:need((row['inserted'] or value['snapshotOsDestinationsVersion']>=2 and row['identity'] is not None and row['identity'].get('storage')=='documents') and nonce(row['deleteId']))
        else:need(row['deleteId']=='' and row['deleteCount']==-1 and not row['absent'])
        if row['phase']=='retired':need(row['deleteIssued'] and row['absent'] and row['checkedEpochMs']>0)
    need(seen==set(destinations))


def share_grants(value,epoch):
    exact(value,{'snapshotShareGrantsVersion','complete','checkId','checkedEpochMs','rows'})
    need(type(value['snapshotShareGrantsVersion']) is int and value['snapshotShareGrantsVersion']==1 and value['complete'] is True
        and (value['checkId']=='' or nonce(value['checkId'])) and integer(value['checkedEpochMs'],0,epoch) and type(value['rows']) is list and len(value['rows'])<=64)
    requests=set()
    for row in value['rows']:
        exact(row,{'request','uri','ownerUid','component','receiverUid','chooserComponent','chooserUid','revokeId','revokeIssued','granted','chooserGranted','checkedEpochMs'})
        parsed=uri(row['uri']);need(parsed.netloc=='org.overte.pico.snapshot.files' and nonce(row['request']) and row['request'] not in requests
            and integer(row['ownerUid'],1) and integer(row['receiverUid'],0) and integer(row['chooserUid'],1) and integer(row['checkedEpochMs'],0,epoch)
            and type(row['component']) is str and (row['component']=='' or re.fullmatch(r'[a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+',row['component']))
            and type(row['chooserComponent']) is str and re.fullmatch(r'[a-zA-Z0-9_.]+/[a-zA-Z0-9_.]+',row['chooserComponent'])
            and all(type(row[key]) is bool for key in ('revokeIssued','granted','chooserGranted')))
        requests.add(row['request']);need(row['revokeId']=='' if not row['revokeIssued'] else nonce(row['revokeId']))
        need((row['receiverUid']==0)==(row['component']==''))
        if row['component']:need(row['ownerUid']!=row['receiverUid'])
    return value


def continuity(before,after):
    # Selected original component-prefix checks. Native request/run/process
    # continuity is independently enforced by the enclosing Pico source.
    a,b=before,after
    if 'initialized' in a:return
    need('initialized' not in b and b['instance']==a['instance'] and b['sequence']>a['sequence']
        and b['elapsedMs']>=a['elapsedMs'] and b['capturedEpochMs']>=a['capturedEpochMs']
        and (not a['copiesRetired'] or b['copiesRetired']) and b['removedCopies'][:len(a['removedCopies'])]==a['removedCopies'])
    destinations={row['request']:row for row in b['destinations']}
    for row in a['destinations']:
        current=destinations.get(row['request']);need(current is not None
            and all(current[key]==row[key] for key in ('request','uri','inserted')) and (not row['published'] or current['published']))
    need(b['snapshotExportReadbacksVersion']>=a['snapshotExportReadbacksVersion'])
    if 'osDestinations' in a:
        need(b['osDestinations']['snapshotOsDestinationsVersion']>=a['osDestinations']['snapshotOsDestinationsVersion'])
        old={row['request']:row for row in a['osDestinations']['rows']};new={row['request']:row for row in b['osDestinations']['rows']}
        for request,row in old.items():
            current=new.get(request);need(type(current) is dict)
            if 'verifiedEpochMs' in row:need(current['verifiedEpochMs']>=row['verifiedEpochMs'])
            for key in ('identity','original'):
                if row[key] is not None:need(current[key]==row[key])
            if row['deleteIssued']:need(current['deleteIssued'] and current['deleteId']==row['deleteId'])
            if row['absent']:need(current['absent'] and current['phase']=='retired' and current['checkedEpochMs']>=row['checkedEpochMs'])
    if 'shareGrants' in a:
        current={row['request']:row for row in b['shareGrants']['rows']}
        for row in a['shareGrants']['rows']:
            item=current.get(row['request']);need(type(item) is dict)
            need(all(item[key]==row[key] for key in ('uri','ownerUid','chooserComponent','chooserUid')))
            if row['component']:need(item['component']==row['component'] and item['receiverUid']==row['receiverUid'])
            if row['revokeIssued']:need(item['revokeIssued'] and item['revokeId']==row['revokeId'])
            need(item['checkedEpochMs']>=row['checkedEpochMs'])
    jobs={row['id']:row for row in b['jobs']}
    for row in a['jobs']:
        current=jobs.get(row['id']);need(current is not None and current['request']==row['request'])
        if row['phase'] in ('complete','failed'):need(current==row)
        elif row['phase']=='reading':need(current['phase']!='queued' and current['startedEpochMs']==row['startedEpochMs'])
