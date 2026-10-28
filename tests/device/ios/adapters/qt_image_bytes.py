"""Existing installed-byte binding extended to one actual Qt API entry image.

This derives a historical byte association only. Qt source/SDK provenance and
imports/AOT admission remain unavailable; no requested revision is an effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.bundle_identity import compare,name,artifact_member_image
from ios.adapters.chat_qml_sources import identity,digest


def decimal(value,maximum,*,positive=False):
    need(type(value) is str and re.fullmatch('0|[1-9][0-9]{0,19}',value)
        and int(value)<=maximum and (not positive or int(value)>0));return int(value)


def validate(value,pid):
    need(integer(pid,1))
    exact(value,{'iosQtEntryImageVersion','source','instance','sequence','processId','beforeEpochMs','afterEpochMs',
        'bundlePreparedEpochMs','bundle','relativePath','fileBytes','fileSha256','imageUuid',
        'headerSha256','symbolFileOffset','fileDevice','fileInode'})
    need(type(value['iosQtEntryImageVersion']) is int and value['iosQtEntryImageVersion']==1
        and value['source']=='native-main-image-entry-fd' and type(value['processId']) is int and value['processId']==pid
        and integer(value['sequence'],1,1000000000) and integer(value['beforeEpochMs'],1)
        and integer(value['afterEpochMs'],value['beforeEpochMs'],value['beforeEpochMs']+1499)
        and integer(value['bundlePreparedEpochMs'],1,value['beforeEpochMs']))
    identity(value['instance']);identity(value['imageUuid']);digest(value['fileSha256']);digest(value['headerSha256'])
    compare(value['bundle'],value['bundle']);need(name(value['relativePath'])==value['relativePath'] and '/' not in value['relativePath'])
    count=decimal(value['fileBytes'],1024**3,positive=True);decimal(value['symbolFileOffset'],count-1)
    decimal(value['fileDevice'],2**64-1);decimal(value['fileInode'],2**64-1,positive=True);return value


def bind(binding,value,artifact,artifact_sha256):
    from ios.adapters.installed_code import InstalledCodeBinding
    need(type(binding) is InstalledCodeBinding)
    before=binding.record();need(before is not None and before['phase']=='bound')
    binding.continuity();pid=before['process']['pid'];validate(value,pid)
    need(before['scope']['artifactSha256']==artifact_sha256
        and value['instance']==before['observation']['instance']
        and value['bundlePreparedEpochMs']==before['observation']['preparedEpochMs'])
    compare(value['bundle'],before['observation']['bundle'])
    actual=artifact_member_image(artifact,artifact_sha256,value['relativePath']);compare(actual['bundle'],value['bundle'])
    image=actual['image'];need(image['isMainExecutable'] is True
        and image['fileBytes']==int(value['fileBytes']) and image['fileSha256']==value['fileSha256']
        and image['macho']['uuid']==value['imageUuid'] and image['macho']['headerSha256']==value['headerSha256'])
    offset=int(value['symbolFileOffset'])
    need(any(start<=offset<start+length for start,length in image['macho']['executableFileRanges']))
    binding.continuity();need(same(binding.record(),before))
    return dict(qtEntryImageByteBindingVersion=1,original=deepcopy(value),artifactSha256=image['artifactSha256'],
        bundleSha256=actual['bundle']['bundleSha256'],imageBytesBound=True,
        qtSdkSourceAvailable=False,importGraphAvailable=False,aotGraphAvailable=False)


def bind_many(binding,values,artifact,artifact_sha256):
    """Two actual Qt callsites in one existing IPA view; no verdict cache."""
    from ios.adapters.installed_code import InstalledCodeBinding
    need(type(binding) is InstalledCodeBinding and type(values) is list and len(values)==2)
    before=binding.record();need(before is not None and before['phase']=='bound')
    binding.continuity();pid=before['process']['pid']
    for value in values:
        validate(value,pid)
        need(before['scope']['artifactSha256']==artifact_sha256
            and value['instance']==before['observation']['instance']
            and value['bundlePreparedEpochMs']==before['observation']['preparedEpochMs'])
        compare(value['bundle'],before['observation']['bundle'])
    need(values[0]['relativePath']==values[1]['relativePath'])
    actual=artifact_member_image(artifact,artifact_sha256,values[0]['relativePath']);image=actual['image']
    output=[]
    for value in values:
        compare(actual['bundle'],value['bundle'])
        need(image['isMainExecutable'] is True and image['fileBytes']==int(value['fileBytes'])
            and image['fileSha256']==value['fileSha256'] and image['macho']['uuid']==value['imageUuid']
            and image['macho']['headerSha256']==value['headerSha256'])
        offset=int(value['symbolFileOffset'])
        need(any(start<=offset<start+length for start,length in image['macho']['executableFileRanges']))
        output.append(dict(qtEntryImageByteBindingVersion=1,original=deepcopy(value),artifactSha256=image['artifactSha256'],
            bundleSha256=actual['bundle']['bundleSha256'],imageBytesBound=True,
            qtSdkSourceAvailable=False,importGraphAvailable=False,aotGraphAvailable=False))
    binding.continuity();need(same(binding.record(),before));return output
