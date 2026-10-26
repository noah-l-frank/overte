"""Closed passive domain route for the separately credentialed Assets reader.

The route can issue only native observations. It cannot change permissions,
publish peer facts, upload/delete mappings or control fixture processes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import threading
from adapters.asset_backend_files import AssetsBackendFiles
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same

VERSION=1


def command(value):
    exact(value,{'schemaVersion','operation','commandId','runId','ticket'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['operation'] in ('observe','poll','original')
        and type(value['commandId']) is str and re.fullmatch('assets-[0-9a-f]{32}',value['commandId']) is not None)
    for key in ('runId','ticket'):need(type(value[key]) is str and re.fullmatch('[0-9a-f]{32}',value[key]) is not None)
    return value


class AssetsBackendControl:
    def __init__(self,process,journal):
        self.process,self.journal=process,journal;self.collector=None;self.lock=threading.RLock()

    def handle(self,value):
        command(value)
        with self.lock:
            need(self.process.guard() is True)
            if self.collector is None:
                need(value['operation']=='observe');self.collector=AssetsBackendFiles(self.process,self.journal,value['runId'])
            collector=self.collector;collector.guard();need(value['runId']==collector.run_id)
            native=dict(schemaVersion=1,commandId=value['commandId'],action='feature-assets-backend-observe',runId=value['runId'],ticket=value['ticket'],
                processId=collector.admission['processId'],instance=collector.admission['instance'])
            old=[row['event']['query'] for row in collector.rows if row['event']['tag']=='intent' and row['event']['query']['commandId']==value['commandId']]
            if old:need(len(old)==1 and same(old[0],native))
            else:
                need(value['operation']=='observe');collector.send(native)
            # An idempotent Observe retry can only inspect its old query. It
            # never reissues one after lost delivery or changes its ticket.
            if collector.pending is not None and collector.pending['query']['commandId']==value['commandId']:
                if value['operation']!='original':collector.poll()
            acquired=[row['event'] for row in collector.rows if row['event']['tag']=='acquired' and row['event']['requestId']==value['commandId']]
            result=None if not acquired else collector.export(value['commandId'])
            return dict(assetsBackendControlVersion=VERSION,requestId=value['commandId'],runId=value['runId'],ticket=value['ticket'],
                status='pending' if result is None else 'original',original=result)

    def detach(self):
        """Close only reader handles; retain all journal/server responsibility."""
        if self.collector is not None:self.collector.detach()
        self.process.close()
