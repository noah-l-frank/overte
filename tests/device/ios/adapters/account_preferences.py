"""Original Directory Server preference admission, without preference setters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,need
from adapters.native_account_origin import origin_text

VERSION=2
REMEMBER_FIELDS={'rememberPresent','rememberType','rememberValue','savedUsernamePresent','savedUsernameType','savedUsernameSha256'}
CONTROL_ID='account.remember'
CONTROL_FIELDS={'preferenceControlVersion','checked'}
EMPTY=hashlib.sha256(b'').hexdigest()


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate(value):
    need(type(value) is dict and type(value.get('accountPreferenceVersion')) is int and value['accountPreferenceVersion'] in (1,VERSION))
    fields={'accountPreferenceVersion','present','valueType','valueSha256','canonicalOrigin',
        'processOverridePresent','processOverrideSha256','processOverrideCanonical'}
    exact(value,fields | (REMEMBER_FIELDS if value['accountPreferenceVersion']==VERSION else set()))
    need(type(value['accountPreferenceVersion']) is int
         and all(type(value[key]) is bool for key in ('present','canonicalOrigin','processOverridePresent','processOverrideCanonical'))
         and value['valueType'] in ('absent','string','url','unsupported')
         and value['present']==(value['valueType']!='absent'))
    readable=value['valueType'] in ('string','url')
    need((sha(value['valueSha256']) if readable else value['valueSha256'] is None)
         and (readable or value['canonicalOrigin'] is False))
    need((sha(value['processOverrideSha256']) if value['processOverridePresent'] else value['processOverrideSha256'] is None)
         and (value['processOverridePresent'] or value['processOverrideCanonical'] is False))
    if value['accountPreferenceVersion']==VERSION:
        need(type(value['rememberPresent']) is bool and value['rememberType'] in ('absent','bool','unsupported')
             and value['rememberPresent']==(value['rememberType']!='absent')
             and (type(value['rememberValue']) is bool if value['rememberType']=='bool' else value['rememberValue'] is None)
             and type(value['savedUsernamePresent']) is bool and value['savedUsernameType'] in ('absent','string','unsupported')
             and value['savedUsernamePresent']==(value['savedUsernameType']!='absent')
             and (sha(value['savedUsernameSha256']) if value['savedUsernameType']=='string' else value['savedUsernameSha256'] is None))
    return deepcopy(value)


def control_metadata(row):
    need(type(row) is dict and row.get('id')==CONTROL_ID and CONTROL_FIELDS<=set(row)
         and type(row['preferenceControlVersion']) is int and row['preferenceControlVersion']==1
         and type(row['checked']) is bool)


def require_owned(value,origin,*,run=None,initial=False,baseline=None):
    """Fail before input if ordinary Login would alter another preference.

    Generic Login writes this preference even when submitting credentials. Its
    UI offers no operation to remove an originally absent key. A preconfigured
    dedicated fixture origin is therefore an explicit admission prerequisite;
    neither an absent setting nor a different original is silently overwritten.
    """
    origin_text(origin);actual=validate(value);digest=hashlib.sha256(origin.encode()).hexdigest()
    need(actual['present'] and actual['valueType']=='string' and actual['canonicalOrigin']
         and actual['valueSha256']==digest and actual['processOverridePresent']
         and actual['processOverrideCanonical'] and actual['processOverrideSha256']==digest)
    need(type(initial) is bool)
    if run is not None or initial or baseline is not None:
        from feature_journeys.contract import identifier
        need(actual['accountPreferenceVersion']==VERSION and actual['rememberPresent'] and actual['rememberType']=='bool'
             and actual['savedUsernamePresent'] and actual['savedUsernameType']=='string')
        allowed={EMPTY}
        if run is not None:
            identifier(run);allowed.add(hashlib.sha256(('e2e-'+run).encode()).hexdigest())
        need(actual['savedUsernameSha256'] in ({EMPTY} if initial else allowed))
    if baseline is not None:
        require_owned(baseline,origin,initial=True)
        need(actual==baseline)
    return actual


def validate_basis(value,origin):
    """Historical validation for restoration targets; never a fresh sample."""
    from adapters.normal_feature_state import context
    from ios.adapters.normal_input import observation
    from ios.adapters.login_source import nonce
    exact(value,{'binding','receipt','preferences'})
    binding=context(value['binding']);receipt=value['receipt']
    exact(receipt,{'schemaVersion','commandId','observation'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1);nonce(receipt['commandId'])
    raw=receipt['observation'];need(type(raw) is dict)
    observation(raw,int(binding['processIdentity'].split(':')[0]),raw.get('sampleEpochMs'))
    actual=require_owned(raw.get('accountPreferences'),origin,initial=True)
    need(actual==value['preferences'])
    return deepcopy(value)


def validate_intent(value,origin,run):
    from adapters.native_feature_observation import validate as validate_native,fresh
    from ios.adapters.normal_input import observation
    from ios.adapters.login_source import nonce
    exact(value,{'native','receipt'})
    native=value['native'];need(type(native) is dict)
    validate_native(native,native.get('requestId'),native.get('processId'),native.get('capturedEpochMs'),require_account=True)
    nonce(native['requestId']);receipt=value['receipt'];exact(receipt,{'schemaVersion','commandId','observation'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1);nonce(receipt['commandId'])
    raw=receipt['observation'];observation(raw,native['processId'],native['capturedEpochMs'])
    fresh(raw['sampleEpochMs'],native['capturedEpochMs'])
    require_owned(raw.get('accountPreferences'),origin,run=run)
    return deepcopy(value)
