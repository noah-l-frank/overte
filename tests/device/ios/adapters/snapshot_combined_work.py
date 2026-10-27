"""Closed normal included-Snapshot work profile; separate1 stays literal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from ios.adapters import snapshot_work as shared
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-snapshot-combined-work'
FILE=ACTION+'.json'
LIMIT=shared.LIMIT
PIN_FILE=shared.PIN_FILE.with_name('snapshot-combined-work-source-pins.v1.json')


def command(value):return shared.command(value,_combined=True)
def validate(value,query,pid,epoch=None,previous=None):return shared.validate(value,query,pid,epoch,previous,_combined=True)
def original(value):return shared.original(value,_combined=True)
def admit(value,scripts_root,*,quiet=False):return shared.admit(value,scripts_root,quiet=quiet,_combined=True)


class IOSSnapshotCombinedWork(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotCombinedWorkAcquisitionVersion'
