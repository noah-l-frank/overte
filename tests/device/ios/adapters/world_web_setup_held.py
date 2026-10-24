"""Actual partial-setup native holders remain owned until independent OS end."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from feature_journeys.terminal import held

KINDS={'scenegraph-node':'qsg-root','native-bitmap':'qimage','offscreen-image':'qimage','upload-image':'qimage','native-view':'wk-view'}


def original(proof):
    need(type(proof) is dict and type(proof.get('iosWorldWebSetupRestorationVersion')) is int
        and proof['iosWorldWebSetupRestorationVersion']==1)
    rows=[]
    def append(kind,source,owner):
        private=dict(iosWorldWebSetupHeldResourceVersion=1,binding=deepcopy(proof['binding']),runId=proof['runId'],source=source,owner=deepcopy(owner))
        identity=digest([proof['binding'],proof['runId'],source,owner]);rows.append(dict(resource='panel:world-web-'+kind+'-'+identity[:20],
            kind=kind,originalSha256=digest(private),original=private))
    for row in proof['scriptRoots']['roots']:
        if row['weakAlive']:append('qt-root','script-ui-'+row['kind'],dict(instance=proof['scriptRoots']['instance'],processId=proof['scriptRoots']['processId'],root=row))
    for row in proof['surfaces']:
        if row['surfaceAlive']:append('qt-root','offscreen-surface',dict(proof['surfaceSource'],birth=row['birth'],rootSource=row['rootSource']))
        if row['rootAlive']:append('qt-root','qml-root',dict(proof['surfaceSource'],birth=row['rootBirth'],rootSource=row['rootSource']))
    for context in proof['resources']['contexts']:
        if context['id'] not in proof['ownedContexts']:continue
        for name,counter in context['resources'].items():
            if counter['pending']:
                need(name!='policy-grant');append(KINDS.get(name,'native-holder'),'web-'+name,dict(instance=proof['resources']['source']['instance'],
                    processId=proof['resources']['source']['processId'],contextId=context['id'],descriptor=context['descriptor'],counter=counter))
    rows.sort(key=lambda row:row['resource']);held([{key:row[key] for key in ('resource','kind','originalSha256')} for row in rows]);return rows
