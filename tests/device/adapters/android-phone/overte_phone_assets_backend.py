"""Join independent actual backend, upload and file originals; no desired state.

Controlled input manifests bound authority. They never supply observed mappings,
workers, bytes, selection or render facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import time
from urllib.request import ProxyHandler,Request,build_opener
from urllib.parse import urlsplit,unquote,urljoin

from adapters.native_feature_observation import exact,fresh,integer,need,number
from feature_journeys.contract import json_document
from feature_journeys.asset_fixture import BUNDLES
from fixture.assets_originals import original as bake_original
from fixture.create_permissions import NoRedirect
from overte_phone_assets_fixture import documents,PREFIX
from overte_phone_assets_source import mappings,download,resolve
from overte_phone_assets_uploads import source as upload_original
from overte_phone_script_history import canonical,same


def sha(value):return hashlib.sha256(value if type(value) is bytes else value.encode()).hexdigest()
def connection(source):return {key:source[key] for key in ('domainId','sessionId','assetServerId')}
def inventory(packet):return {row['path']:deepcopy(row) for row in mappings(packet['source'])['mappings']}
def public(path,run):return path.startswith('/e2e-'+run+'/') or path.startswith('/renamed-'+run+'/')
def hidden(path,hashes):return any(path.startswith('/.baked/'+digest+'/') for digest in hashes)


class PhoneAssetsBackend:
    def __init__(self,url,token,run,domain,guard,clock_ms,*,monotonic=time.monotonic):
        parsed=urlsplit(url);need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.path=='/v1/assets-originals'
            and parsed.netloc=='127.0.0.1:'+str(parsed.port) and integer(parsed.port,1,65535) and not parsed.query and not parsed.fragment)
        need(type(token) is str and 32<=len(token)<=128 and all(33<=ord(ch)<=126 for ch in token))
        self.url,self.token,self.run,self.domain,self.guard,self.clock_ms,self.monotonic=url,token,run,domain,guard,clock_ms,monotonic;self.last=None
    def read(self):
        need(self.guard() is not False);started=self.monotonic();requested=self.clock_ms()
        call=dict(schemaVersion=1,runId=self.run)
        request=Request(self.url,data=canonical(call),headers={'Content-Type':'application/json','X-Overte-E2E-Token':self.token})
        with build_opener(ProxyHandler({}),NoRedirect()).open(request,timeout=5) as response:
            need(response.status==200 and response.geturl()==self.url);raw=response.read(1048577)
        need(len(raw)<=1048576 and number(self.monotonic(),started,started+5) and self.monotonic()-started<5)
        value=json_document(raw);exact(value,{'schemaVersion','runId','source'});need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==self.run)
        source=bake_original(value['source'],domain=self.domain,epoch=self.clock_ms());need(source['capturedEpochMs']>=requested-1500)
        if self.last is not None:
            before=self.last['source'];need(all(source[key]==before[key] for key in ('instance','processId','processStart','domainId','assetServerId'))
                and source['sequence']>=before['sequence'] and source['capturedEpochMs']>=before['capturedEpochMs'] and len(source['jobs'])>=len(before['jobs']))
            for a,b in zip(before['jobs'],source['jobs']):need(all(b[key]==item for key,item in a.items() if item is not None))
        need(self.guard() is not False);fresh(source['capturedEpochMs'],self.clock_ms());need(self.monotonic()-started<5)
        self.last=deepcopy(value);return deepcopy(value)


def baseline(packet,backend,run):
    rows=inventory(packet);b=bake_original(backend['source']);need(b['domainId']==packet['source']['domainId'] and b['assetServerId']==packet['source']['assetServerId'])
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
    rows=inventory(packet);b=bake_original(backend['source']);need(connection(packet['source'])==original['connection']
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


def bytes_for(packet,digest):
    source=download(packet['source'],dict(hash=digest));return base64.b64decode(source['base64'],validate=True)


def bake(selected,packet,backend,resolution,downloads,barrier=None):
    """Original status + worker + current meta + actual readable redirect bytes."""
    rows=inventory(packet);row=rows[selected];r=resolve(resolution['source'],dict(path=selected));need(connection(r)==connection(packet['source']))
    status=row['bakeStatus'];need(not row['bakeError'] and status!=5)
    if status==0:need(not r['redirected'] and r['hash']==row['hash']);return 'unsupported'
    jobs=[job for job in backend['source']['jobs'] if job['hash']==row['hash']]
    if status in (2,3):need(any(job['terminalEpochMs'] is None for job in jobs));return 'baking'
    prefix='/.baked/'+row['hash']+'/'
    if status==1:
        need(r['hash']==row['hash'] and not r['redirected'] and r['redirectedPath']=='' and any(path.startswith(prefix) and item['hash']==row['hash'] for path,item in rows.items())
            and all(job['terminalEpochMs'] is not None and job['runExitedEpochMs'] is not None for job in jobs));return 'disabled'
    need(status==4 and r['redirected'] and r['redirectedPath'].startswith(prefix) and r['hash']!=row['hash'] and rows.get(r['redirectedPath'],{}).get('hash')==r['hash'])
    meta_row=rows.get(prefix+'meta.json');need(meta_row is not None and meta_row['hash'] in downloads and r['hash'] in downloads)
    meta=json_document(bytes_for(downloads[meta_row['hash']],meta_row['hash']))
    exact(meta,{'bake_version','failed_last_bake','last_bake_errors','redirect_target'})
    need(type(meta['bake_version']) is int and meta['failed_last_bake'] is False and meta['last_bake_errors']=='' and meta['redirect_target']==r['redirectedPath'])
    completed=[job for job in jobs if job['outcome']=='complete' and job['runExitedEpochMs'] is not None and job['destroyedEpochMs'] is not None and job['version']==meta['bake_version']]
    need(completed and all(job['terminalEpochMs'] is not None and job['runExitedEpochMs'] is not None for job in jobs))
    if barrier is not None:
        need(backend['source']['instance']==barrier['instance'] and backend['source']['sequence']>barrier['sequence']
            and any(job['instance'] not in barrier['jobs'] and job['queuedEpochMs']>=barrier['epochMs'] for job in completed))
    bytes_for(downloads[r['hash']],r['hash']);return 'ready'


def reader_chain(selected,packet,resolution,downloads):
    """Follow only original ATP/FST relative references inside owned bake output."""
    rows=inventory(packet);r=resolution['source'];need(r['requestedPath']==selected)
    path=r['redirectedPath'] if r['redirected'] else selected;digest=r['hash'];body=bytes_for(downloads[digest],digest)
    for _ in range(3):
        if not path.lower().endswith('.fst'):return dict(path=path,url='atp:'+path,sha256=digest,bytes=len(body),body=body)
        fields={}
        for line in body.decode('utf-8').splitlines():
            if '=' not in line or line.strip().startswith('#'):continue
            key,value=line.split('=',1);key=key.strip();value=value.strip()
            if key in ('filename','baseURL'):need(key not in fields);fields[key]=value
        need(fields.get('filename') and not any(':' in value or value.startswith('/') or '\\' in value for value in fields.values()))
        base=urljoin('http://fixture'+path,fields.get('baseURL',''))
        path=urlsplit(urljoin(base,fields['filename'])).path
        need(path.startswith('/.baked/'+rows[selected]['hash']+'/') and path in rows);digest=rows[path]['hash'];body=bytes_for(downloads[digest],digest)
    need(False)
