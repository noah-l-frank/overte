"""Pure actual Create marker identity and source-validated prepared lease.

The lease carries completed original admission, not marker input delivery or a
whole-feature capability. It owns no setup, action, image or cleanup operation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re

from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from ios.adapters import create_state
from ios.adapters.create_marker_files import originals


def marker(packet,nonce,url):
    create_state.original(packet);need(packet['iosCreateStateVersion']>=3);identifier(nonce)
    rows=[]
    for row in packet['source']['entities']:
        if row['type']!='Web' or not row['userData']:continue
        try:data=json.loads(row['userData'])
        except ValueError:continue
        if type(data) is dict and data.get('kind')=='create-marker-v1' and data.get('runId')==packet['runId']:rows.append((row,data))
    need(len(rows)==1);row,data=rows[0];exact(data,{'kind','runId','nonce'})
    need(data['nonce']==nonce and row['name']=='e2e-'+packet['runId']+'-script' and row['sourceUrl']==url
        and row['hostType']=='local' and row['visible'] and row['collisionless'])
    return deepcopy(row)


class PreparedCreateMarker:
    """Immutable ordinary-script admission usable without the setup owner."""
    def __init__(self,binding,run,fixture_url,*,before,after,scripts,files,directory,after_epoch,domain_before,domain_after):
        from ios.adapters.create_marker_measurements import admitted,body_preserved
        binding=deepcopy(context(binding));identifier(run)
        exact(files,{'contractVersion','markerFilesVersion','runId','ownerToken','binding','hashes','fixtureUrl','ticket','nonce'})
        need(type(files['contractVersion']) is int and files['contractVersion']==1 and type(files['markerFilesVersion']) is int and files['markerFilesVersion']==1
            and context(files['binding'])==binding and files['runId']==run and files['fixtureUrl']==fixture_url
            and type(files['ownerToken']) is str and re.fullmatch('[a-f0-9]{64}',files['ownerToken'])
            and before['processId']==after['processId']==int(binding['processIdentity']) and before['runId']==after['runId']==run)
        actual=originals(run,fixture_url,files['ticket'],files['nonce'])
        need(files['hashes']=={name:hashlib.sha256(data).hexdigest() for name,data in actual.items()})
        body_preserved(domain_before,domain_after)
        need(domain_before['processId']==domain_after['processId']==after['processId'] and domain_before['runId']==domain_after['runId']==run)
        admission=admitted(before,after,scripts,files,directory,after_epoch=after_epoch)
        self._binding,self._run,self._fixture,self._admission=binding,run,fixture_url,deepcopy(admission)
    @property
    def binding(self):return deepcopy(self._binding)
    @property
    def run(self):return self._run
    @property
    def fixture_url(self):return self._fixture
    @property
    def state(self):return dict(phase='ready',admission=deepcopy(self._admission))
