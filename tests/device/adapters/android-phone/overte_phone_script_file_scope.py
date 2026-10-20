"""Join actual fixture presence/bytes/clocks and physical Script resources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import re

from adapters.native_feature_observation import exact, fresh, integer, need
from adapters.native_script_files import NativeScriptFiles, originals
from feature_journeys.contract import identifier
from overte_phone_script_measurements import compose

VERSION = 1


def join(run, ticket, directory, fixture_url, pid, sources, files, epoch, after_epoch, *, previous=None):
    """Pure join of original acquisitions, never an input receipt or cache.

    The owning coordinator must acquire these frames under the source lock,
    retain the returned original file cursor before exposing a public result,
    and persist uncertainty before acquisition. No expected state is accepted.
    """
    identifier(run); identifier(ticket)
    exact(sources, {'epochMs', 'execution', 'ui', 'service', 'lifecycle'})
    need(integer(epoch, 1) and integer(sources['epochMs'], 1) and sources['epochMs'] <= epoch)
    measured = compose(run, ticket, directory, fixture_url, pid, sources['execution'], sources['ui'],
                       sources['service'], sources['lifecycle'], epoch, after_epoch)
    exact(files, {'schemaVersion', 'requestId', 'instance', 'sequence', 'requestedEpochMs',
        'capturedEpochMs', 'processId', 'runId', 'operation', 'source'})
    need(type(files['schemaVersion']) is int and files['schemaVersion'] == 1
         and type(files['requestId']) is str and re.fullmatch('[0-9a-f]{32}', files['requestId']) is not None
         and files['instance'] == sources['execution']['instance']
         and integer(files['sequence'], 1) and type(files['processId']) is int and files['processId'] == pid
         and files['runId'] == run and files['operation'] in ('observe', 'locate')
         and integer(files['requestedEpochMs'], 1) and integer(files['capturedEpochMs'], 1)
         and 0 <= files['capturedEpochMs'] - files['requestedEpochMs'] < 5000)
    fresh(files['capturedEpochMs'], epoch)
    clocks = [files['capturedEpochMs']] + [sources[name][clock] for name, clock in
        (('execution', 'capturedEpochMs'), ('ui', 'capturedEpochMs'), ('service', 'sampleEpochMs'),
         ('lifecycle', 'capturedEpochMs'))]
    need(min(clocks) >= after_epoch and max(clocks) - min(clocks) <= 1500)
    source = files['source']
    NativeScriptFiles.validate_source(source, files['operation'], run)
    need(source.get('directory') == directory)
    if source['exists']:
        need(files['operation'] == 'observe' and all(row['exists'] for row in source['files']))
        actual = {row['name']: base64.b64decode(row['base64'], validate=True) for row in source['files']}
        need(actual == originals(run))
    else:
        # Old absence packets do not include an original native path and cannot
        # establish this scope. A successful release/stage ACK is never evidence.
        need(files['operation'] == 'locate')
    cursor = dict(fileScopeVersion=VERSION, instance=files['instance'], sequence=files['sequence'],
                  capturedEpochMs=files['capturedEpochMs'], directory=directory)
    if previous is not None:
        exact(previous, set(cursor))
        need(type(previous['fileScopeVersion']) is int and previous['fileScopeVersion'] == VERSION
             and previous['instance'] == cursor['instance'] and previous['directory'] == directory
             and integer(previous['sequence'], 1) and integer(previous['capturedEpochMs'], 1)
             and cursor['sequence'] > previous['sequence']
             and cursor['capturedEpochMs'] >= previous['capturedEpochMs'])
    resources = []
    if source['exists']: resources.append('file:script-fixtures')
    if measured['state']['open']: resources.append('panel:script-manager')
    if measured['state']['picker']: resources.append('panel:script-picker')
    if measured['state']['running']: resources.append('script:owned-script')
    if measured['effect'] is not None: resources.append('entity:script-effect')
    measured['capturedEpochMs'] = min(clocks)
    return deepcopy(dict(fileScopeVersion=VERSION, measurement=measured, resources=sorted(resources), fileCursor=cursor))
