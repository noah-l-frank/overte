"""Pure original Snapshot/upload/account/TLS frame grammar, including OS recovery."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import decode,exact,need,number,validate as account_packet
from adapters.pico4.snapshot_base_frame import original,validate as base_frame,clocks as base_clocks
from adapters.pico4.snapshot_upload_source import validate as upload_packet
from adapters.pico4.snapshot_upload_fixture import validate as provider_packet


def clocks(row):
    upload=decode(row['upload']['raw']);account=decode(row['account']['raw'])
    return (row['hostMonotonic']*1000,)+base_clocks(row['base'])[1:]+(upload['capturedEpochMs'],upload['source']['capturedEpochMs'],
        account['capturedEpochMs'],account['account']['observation']['capturedEpochMs'],row['provider']['capturedEpochMs'])


def validate(row,run,pid,bridge):
    exact(row,{'base','upload','provider','account','hostMonotonic'});native,script,files=base_frame(row['base'],run,pid,bridge)
    upload=original({key:row['upload'][key] for key in ('raw','sha256')},262144)
    exact(row['upload'],{'raw','sha256','request'});upload_packet(upload,row['upload']['request'],pid,upload['capturedEpochMs']);need(upload['runId']==run)
    provider_packet(row['provider'],run,row['provider']['requestId'],row['provider']['capturedEpochMs'])
    account=original(row['account'],262144);account_packet(account,account['requestId'],pid,account['capturedEpochMs'],require_account=True)
    need(upload['instance']==files['instance']==account['instance'])
    need(number(row['hostMonotonic'],0,1e15) and max(clocks(row)[1:])-min(clocks(row)[1:])<=1500)
    return native,script,files,upload,account
