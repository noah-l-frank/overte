"""Original fixture activation times and immutable closed input history.

This source is input metadata. It supplies no target facts, peer facts,
resource-delivery proof or product-lifetime/cleanup proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import secrets
import time

from .contract import exact, identifier, number, typed_equal
from .scenarios import SCENARIOS, actions, expand
from .fixtures import context
from .witness import Client

VERSION = 1


def integer(value, low=0):
    return type(value) is int and low <= value <= 9007199254740991


def check(condition):
    if not condition:
        raise ValueError('Original fixture phase metadata is unavailable or inconsistent')


def validate(value, *, run, area, request, epoch, previous=None):
    exact(value, {'fixturePhaseVersion', 'instance', 'sequence', 'requestId', 'runId', 'area',
                  'capturedEpochMs', 'active', 'createdEpochMs', 'retiredEpochMs', 'activations'}, 'fixture phase')
    check(type(value['fixturePhaseVersion']) is int and value['fixturePhaseVersion'] == VERSION
          and integer(value['sequence'], 1) and value['requestId'] == identifier(request)
          and value['runId'] == identifier(run) and area in SCENARIOS and value['area'] == area
          and type(value['active']) is bool)
    identifier(value['instance'])
    captured = number(value['capturedEpochMs'], 1)
    created = number(value['createdEpochMs'], 1)
    check(created <= captured and -250 <= number(epoch, 1)-captured <= 1500)
    if value['active']:
        check(value['retiredEpochMs'] is None)
    else:
        check(created <= number(value['retiredEpochMs'], 1) <= captured)
    rows = value['activations']
    check(type(rows) is list and len(rows) <= 256)
    tickets = set()
    last = created
    for index, row in enumerate(rows):
        exact(row, {'sequence', 'ticket', 'activatedEpochMs', 'stimulus'}, 'fixture activation')
        check(integer(row['sequence'], 1) and row['sequence'] == index+1)
        ticket = identifier(row['ticket'])
        check(ticket not in tickets)
        tickets.add(ticket)
        activated = number(row['activatedEpochMs'], 1)
        check(last <= activated <= captured)
        if not value['active']:
            check(activated <= value['retiredEpochMs'])
        last = activated
        stimulus = row['stimulus']
        exact(stimulus, {'verb', 'inputs'}, 'fixture stimulus')
        check(type(stimulus['verb']) is str)
        if stimulus['verb'] in ('baseline', 'cleanup'):
            check(type(stimulus['inputs']) is dict and stimulus['inputs'] == {})
        else:
            check(stimulus['verb'] in actions(area) and any(typed_equal(stimulus['inputs'], expand(candidate, context(run)))
                for candidate in actions(area)[stimulus['verb']]))
    if previous is not None:
        # Validate the complete retained original, not just its cursor or prefix.
        validate(previous, run=run, area=area, request=previous['requestId'], epoch=previous['capturedEpochMs'])
        check(value['instance'] == previous['instance'] and created == previous['createdEpochMs']
              and value['sequence'] > previous['sequence'] and value['requestId'] != previous['requestId']
              and captured >= previous['capturedEpochMs'] and len(rows) >= len(previous['activations'])
              and typed_equal(rows[:len(previous['activations'])], previous['activations']))
        if not previous['active']:
            check(value['active'] is False and value['retiredEpochMs'] == previous['retiredEpochMs']
                  and typed_equal(rows, previous['activations']))
    return value


class PhasePending(ValueError):
    """The current owned run has no active input ticket yet."""


class PhaseRetired(PhasePending):
    def __init__(self, status):
        super().__init__('Original fixture input journal has retired')
        self.status = deepcopy(status)


class PhaseFixtureReader:
    def __init__(self, client, run, area, *, epoch_ms=lambda: time.time()*1000, monotonic=time.monotonic):
        check(isinstance(client, Client) and area in SCENARIOS and callable(epoch_ms) and callable(monotonic))
        self.client, self.run, self.area = client, identifier(run), area
        self.epoch_ms, self.monotonic = epoch_ms, monotonic
        self.fixture_url = client.url+'/runs/'+run+'/'
        self.previous = None

    def status(self, previous=None):
        started = number(self.monotonic(), 0)
        epoch = number(self.epoch_ms(), 1)
        request = secrets.token_hex(16)
        value = self.client.request('/runs/'+self.run+'/phase', phase_nonce=request)
        now = number(self.monotonic(), started)
        current_epoch = number(self.epoch_ms(), epoch)
        validate(value, run=self.run, area=self.area, request=request, epoch=current_epoch, previous=self.previous)
        if previous is not None:
            validate(value, run=self.run, area=self.area, request=request, epoch=current_epoch, previous=previous)
        check(max(current_epoch-value['capturedEpochMs'], epoch-value['capturedEpochMs']+(now-started)*1000) <= 1500)
        self.previous = deepcopy(value)
        return deepcopy(value)

    def read(self, previous=None):
        value = self.status(previous)
        if not value['active']:
            raise PhaseRetired(value)
        if not value['activations']:
            raise PhasePending('The original fixture has no active input ticket')
        last = value['activations'][-1]
        return dict(ticket=last['ticket'], afterEpochMs=last['activatedEpochMs'],
                    **deepcopy(last['stimulus']), status=value)
