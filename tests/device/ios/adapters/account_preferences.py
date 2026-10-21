"""Original Directory Server preference admission, without preference setters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,need
from adapters.native_account_origin import origin_text

VERSION=1


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate(value):
    exact(value,{'accountPreferenceVersion','present','valueType','valueSha256','canonicalOrigin',
        'processOverridePresent','processOverrideSha256','processOverrideCanonical'})
    need(type(value['accountPreferenceVersion']) is int and value['accountPreferenceVersion']==VERSION
         and all(type(value[key]) is bool for key in ('present','canonicalOrigin','processOverridePresent','processOverrideCanonical'))
         and value['valueType'] in ('absent','string','url','unsupported')
         and value['present']==(value['valueType']!='absent'))
    readable=value['valueType'] in ('string','url')
    need((sha(value['valueSha256']) if readable else value['valueSha256'] is None)
         and (readable or value['canonicalOrigin'] is False))
    need((sha(value['processOverrideSha256']) if value['processOverridePresent'] else value['processOverrideSha256'] is None)
         and (value['processOverridePresent'] or value['processOverrideCanonical'] is False))
    return deepcopy(value)


def require_owned(value,origin):
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
    return actual
