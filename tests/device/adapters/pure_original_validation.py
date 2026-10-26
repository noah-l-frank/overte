"""Bounded call-local reuse for pure input/None-returning validators.

Inactive by default. The explicit historical owner must guard its complete
original inventory before and after the scope. No result or clock is minted.
Keys are disposable, type-preserving Python marshal bytes, never persisted or
loaded as code. Unsupported input types run the original validator directly.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import marshal
from adapters.normal_ui import NativeUIError

VERSION=4
PROFILE='ios-emote-rooted-archive-v1'
AVATAR_PROFILE='ios-avatar-held-scene-archive-v1'
AVATAR_FINAL_PROFILE='ios-avatar-held-final-archive-v1'
PROFILES=frozenset((PROFILE,AVATAR_PROFILE,AVATAR_FINAL_PROFILE))
LIMIT=4096
_ACTIVE=ContextVar('original_pure_validation_round',default=None)
_PROFILE=ContextVar('original_pure_validation_profile',default=None)


@contextmanager
def scope(profile,guard):
    if type(profile) is not str or profile not in PROFILES or not callable(guard):raise NativeUIError('Historical validation scope is unavailable')
    if guard() is False:raise NativeUIError('Historical validation inventory changed')
    token=_ACTIVE.set({});profile_token=_PROFILE.set(profile)
    try:yield
    finally:
        try:
            if guard() is False:raise NativeUIError('Historical validation inventory changed')
        finally:
            _PROFILE.reset(profile_token);_ACTIVE.reset(token)


@contextmanager
def inherited_scope(profile,guard):
    """Explicitly share pure successes with an unchanged enclosing read.

    Both owners still check their own inventories. Ordinary scope() retains
    its isolated-cache behavior; live guards and parser results never enter
    this cache. No cache survives the outer operation's read boundary.
    """
    if _ACTIVE.get() is None:
        with scope(profile,guard):yield
        return
    if type(profile) is not str or profile not in PROFILES or profile!=_PROFILE.get() or not callable(guard):raise NativeUIError('Historical validation scope is unavailable')
    if guard() is False:raise NativeUIError('Historical validation inventory changed')
    try:yield
    finally:
        if guard() is False:raise NativeUIError('Historical validation inventory changed')


def returning_input(function,value,*context):
    cache=_ACTIVE.get()
    if cache is None:return function(value,*context)
    try:key=(function,hashlib.sha256(marshal.dumps((value,context),4)).digest())
    except (ValueError,TypeError,OverflowError,RecursionError):return function(value,*context)
    if key in cache:return value
    result=function(value,*context)
    if result is value:
        if len(cache)>=LIMIT:cache.pop(next(iter(cache)))
        cache[key]=True
    return result


def without_result(function,*arguments):
    cache=_ACTIVE.get()
    if cache is None:return function(*arguments)
    try:key=(function,'none',hashlib.sha256(marshal.dumps(arguments,4)).digest())
    except (ValueError,TypeError,OverflowError,RecursionError):return function(*arguments)
    if key in cache:return None
    result=function(*arguments)
    if result is None:
        if len(cache)>=LIMIT:cache.pop(next(iter(cache)))
        cache[key]=True
    return result
