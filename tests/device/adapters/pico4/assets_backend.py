"""Closed original AssetServer/upload joins selected from frozen Phone source.

No task, backend, process, service, permission or UI command is started here.
The supplied source must be actual independent AssetServer originals, not client
GetAll projections or desired fixture state. Native execution remains separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit,unquote
import uuid
from adapters.native_feature_observation import exact,integer,need,fresh
from adapters.assets_input import documents,PREFIX
from adapters.pico4.assets_source import mappings
from adapters.pico4.assets_uploads import source as upload_original
from adapters.script_journey.history import canonical,same
from feature_journeys.contract import identifier
from feature_journeys.asset_fixture import BUNDLES
from fixture.messages_mixer import start_identity

def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None

def backend_original(value,*,domain=None,process=None,epoch=None):
    exact(value,{'assetsBakeOriginalsVersion','instance','sequence','processId','processStart','domainId','assetServerId','capturedEpochMs','contextCapturedEpochMs','valid','jobs','mappings','blobs','pending'})
    need(type(value['assetsBakeOriginalsVersion']) is int and value['assetsBakeOriginalsVersion']==2 and value['valid'] is True)
    identifier(value['instance']);need(integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and type(value['processStart']) is str and value['processStart'].isdecimal())
    for key in ('domainId','assetServerId'):need(str(uuid.UUID(value[key]))==value[key] and uuid.UUID(value[key]).int!=0)
    need(domain is None or value['domainId']==domain)
    need(process is None or (value['processId'],value['processStart'])==(process.pid,start_identity(process.pid)))
    need(integer(value['capturedEpochMs'],1));captured=value['capturedEpochMs']
    need(integer(value['contextCapturedEpochMs'],1,captured))
    if epoch is not None:fresh(captured,epoch);fresh(value['contextCapturedEpochMs'],epoch)
    need(type(value['jobs']) is list and len(value['jobs'])<=64 and type(value['mappings']) is list and len(value['mappings'])<=4096
        and type(value['blobs']) is list and len(value['blobs'])<=4096 and integer(value['pending'],0,64))
    seen=set();pending=0
    for row in value['jobs']:
        exact(row,{'instance','hash','path','version','queuedEpochMs','startedEpochMs','runExitedEpochMs','ovenProcessId','ovenFinishedEpochMs','exitCode','exitStatus','terminalEpochMs','outcome','destroyedEpochMs'})
        identifier(row['instance']);need(row['instance'] not in seen);seen.add(row['instance'])
        need(digest(row['hash']) and type(row['path']) is str and row['path'].startswith('/') and integer(row['version'],0,65535) and integer(row['queuedEpochMs'],1,captured))
        if row['startedEpochMs'] is not None:need(integer(row['startedEpochMs'],row['queuedEpochMs'],captured))
        if row['runExitedEpochMs'] is not None:need(row['startedEpochMs'] is not None and integer(row['runExitedEpochMs'],row['startedEpochMs'],captured))
        if row['ovenProcessId'] is not None:need(row['startedEpochMs'] is not None and integer(row['ovenProcessId'],1))
        if row['ovenFinishedEpochMs'] is not None:need(row['ovenProcessId'] is not None and integer(row['ovenFinishedEpochMs'],row['startedEpochMs'],captured) and integer(row['exitCode'],-2**31,2**31-1) and integer(row['exitStatus'],0,1))
        else:need(row['exitCode'] is None and row['exitStatus'] is None)
        if row['terminalEpochMs'] is None:need(row['outcome'] is None);pending+=1
        else:need(integer(row['terminalEpochMs'],row['queuedEpochMs'],captured) and row['outcome'] in ('complete','failed','aborted'))
        if row['outcome']=='complete':need(row['ovenFinishedEpochMs'] is not None and row['exitCode']==0 and row['exitStatus']==0 and row['terminalEpochMs']>=row['ovenFinishedEpochMs'])
        if row['destroyedEpochMs'] is not None:need(row['terminalEpochMs'] is not None and integer(row['destroyedEpochMs'],row['terminalEpochMs'],captured))
    # All actual pending tasks must have one retained original. A lost or
    # destroyed task cannot disappear into a fabricated empty worker count.
    need(pending==value['pending'])
    for key,fields in (('mappings',{'path','hash'}),('blobs',{'hash','actualSha256','bytes'})):
        names=set()
        for row in value[key]:
            exact(row,fields);name=row['path'] if key=='mappings' else row['hash'];need(name not in names);names.add(name)
            need(digest(row['hash']))
            if key=='mappings':need(type(name) is str and len(name)<=1024 and name.startswith('/') and not name.endswith('/') and '\\' not in name and all(part not in ('','.','..') for part in name[1:].split('/')))
            else:need(row['actualSha256']==row['hash'] and integer(row['bytes'],1,1048576))
    return value


def sha(value):return hashlib.sha256(value if type(value) is bytes else value.encode()).hexdigest()
def connection(source):return {key:source[key] for key in ('domainId','sessionId','assetServerId')}
def inventory(packet):return {row['path']:deepcopy(row) for row in mappings(packet['source'])['mappings']}
def public(path,run):return path.startswith('/e2e-'+run+'/') or path.startswith('/renamed-'+run+'/')
def hidden(path,hashes):return any(path.startswith('/.baked/'+digest+'/') for digest in hashes)


def baseline(packet,backend,run):
    rows=inventory(packet);b=backend_original(backend['source']);need(b['domainId']==packet['source']['domainId'] and b['assetServerId']==packet['source']['assetServerId'])
    need({row['path']:row['hash'] for row in b['mappings']}=={path:row['hash'] for path,row in rows.items()})
    need({row['hash'] for row in b['blobs']}<={row['hash'] for row in b['mappings']})
    pinned={sha(raw) for raw in documents().values()}
    need(not any(public(path,run) or hidden(path,pinned) or row['hash'] in pinned for path,row in rows.items())
        and not any(row['hash'] in pinned for row in b['blobs']) and b['pending']==0
        and all(row['terminalEpochMs'] is not None and row['runExitedEpochMs'] is not None and row['destroyedEpochMs'] is not None for row in b['jobs']))
    return dict(connection=connection(packet['source']),mappings=deepcopy(packet),backend=deepcopy(backend))


def responsibility(upload_packet,files_packet,resource,run,context):
    """Claim only actual successful normal requests tied to original filenames.

    Partial completed uploads retain blob responsibility even before any mapping
    was published. No missing request can become an intended successful file.
    """
    u=upload_original(upload_packet['source'],run,upload_packet['capturedEpochMs']);f=files_packet['source'];need(f['exists'] and not f['retiring'])
    primary,names=BUNDLES[resource];prefix=PREFIX[resource];directory=unquote(urlsplit(f['directory']).path)+'/'+prefix
    expected={name:row for row in f['files'] for name in names if row['name']==prefix+'/'+name and row['exists']}
    need(set(expected)==set(names))
    matches=[row for row in u['bundles'] if row['directorySha256']==sha(directory)]
    need(len(matches)==1);bundle=matches[0];need(bundle['primary']==primary and bundle['connection']==context
        and {row['relativePath']:row['filenameSha256'] for row in bundle['files']}=={name:sha(directory+'/'+name) for name in names})
    uploads={};published={}
    for request in bundle['requests']:
        original=request['original']
        if original is None:continue
        if request['kind']=='upload':
            name=next(name for name in names if sha(directory+'/'+name)==original['filenameSha256'])
            need(name not in uploads)
            if original['errorCode']==0:
                row=expected[name];need(original['originalSha256']==row['sha256'] and original['originalBytes']==row['bytes'] and original['returnedHash']==row['sha256'])
                uploads[name]=deepcopy(original)
        elif original['errorCode']==0:
            name=original['path'][len(bundle['destination']):];need(name in uploads and name not in published and original['hash']==uploads[name]['returnedHash'])
            published[name]=deepcopy(original)
    terminal=not bundle['active'] and all(row['destroyedEpochMs'] is not None for row in bundle['requests'])
    complete=terminal and bundle['errorSha256']==sha('') and set(published)==set(names) and set(uploads)==set(names)
    return dict(bundleId=bundle['id'],resource=resource,primary=primary,files=deepcopy(expected),uploads=uploads,published=published,complete=complete,terminal=terminal,
        source=deepcopy(upload_packet),fileOriginal=deepcopy(files_packet))


def owned_inventory(packet,backend,original,claims,run):
    rows=inventory(packet);b=backend_original(backend['source']);need(connection(packet['source'])==original['connection']
        and b['domainId']==original['connection']['domainId'] and b['assetServerId']==original['connection']['assetServerId'])
    need({row['path']:row['hash'] for row in b['mappings']}=={path:row['hash'] for path,row in rows.items()})
    hashes={item['returnedHash'] for claim in claims for item in claim['uploads'].values()}
    before=inventory(original['mappings']);outside={path:row['hash'] for path,row in rows.items() if not public(path,run) and not hidden(path,hashes)}
    need(outside=={path:row['hash'] for path,row in before.items()})
    published={path:digest for claim in claims for path,digest in claim.get('currentPaths',{item['path']:item['hash'] for item in claim['published'].values()}).items()}
    owned={path:row for path,row in rows.items() if public(path,run)}
    need(all(path in published and row['hash']==published[path] for path,row in owned.items()))
    original_blobs={row['hash']:row for row in original['backend']['source']['blobs']};current_blobs={row['hash']:row for row in b['blobs']}
    hidden_hashes={row['hash'] for path,row in rows.items() if hidden(path,hashes)}
    allowed=hashes|hidden_hashes
    need({key:row for key,row in current_blobs.items() if key not in allowed or key in original_blobs}==original_blobs)
    need(all(current_blobs.get(key)==row for key,row in original_blobs.items()))
    return owned
