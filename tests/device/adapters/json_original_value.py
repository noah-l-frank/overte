# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Bounded immutable historical JSON value seal; no source or budget authority.

The caller preholds ``capacity`` in its existing authority, keeps the resident
charge until destruction, and binds reuse to the original object/index/profile.
Existing entries' resident charges must be subtracted before construction. The
original payload owner must remain alive; this helper cannot extend its credit.
Every hit compares the complete current value. Mismatch never permits resealing.
Unsupported/oversized values use the caller's unchanged original digest path.
"""
import math
import struct


class _NoSeal(Exception):
    pass


def scratch_bound(max_depth):
    # Sequential count/fill/compare stacks: frames/iterators plus fixed objects.
    return 8192 + 1024 * (max_depth + 1)


def _count(item, depth, limits, counts):
    counts[0] += 1
    if counts[0] > limits[0] or depth > limits[1]:
        raise _NoSeal
    kind = type(item)
    if kind is dict or kind is list:
        if len(item) > limits[0] - counts[0]:
            raise _NoSeal
        counts[1] += 5
        if kind is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise _NoSeal
                counts[0] += 1
                counts[2] += 1
                if counts[0] > limits[0]:
                    raise _NoSeal
                _count(child, depth + 1, limits, counts)
        else:
            for child in item:
                _count(child, depth + 1, limits, counts)
        return
    if kind is float:
        if not math.isfinite(item):
            raise _NoSeal
    elif not (kind is str or kind is int or kind is bool or kind is type(None)):
        raise _NoSeal
    counts[1] += 1
    counts[2] += 1


def dimensions(value, *, max_nodes=16384, max_depth=64):
    """Count without key/value/payload copies or per-node metadata containers."""
    if type(max_nodes) is not int or type(max_depth) is not int:
        return None
    if not (1 <= max_nodes <= 65536 and 0 <= max_depth <= 64):
        return None
    counts = [0, 0, 0]
    try:
        _count(value, 0, (max_nodes, max_depth), counts)
    except (_NoSeal, RuntimeError):
        return None
    nodes, shape, refs = counts
    # Fixed bytearray+bytes and list+tuple coexist during construction.
    # 2048 covers headers, counters, plans and result tuples, no payload copies.
    resident = shape + 8 * refs + 2048
    peak = 2 * shape + 16 * refs + 2048 + scratch_bound(max_depth)
    return shape, refs, nodes, resident, peak


def _reference(item, refs, cursors):
    pos = cursors[1]
    if pos >= len(refs):
        raise _NoSeal
    refs[pos] = item
    cursors[1] += 1


def _fill(item, depth, max_depth, shape, refs, cursors):
    pos = cursors[0]
    if depth > max_depth or pos >= len(shape):
        raise _NoSeal
    kind = type(item)
    if kind is dict or kind is list:
        if pos + 5 > len(shape):
            raise _NoSeal
        shape[pos] = 6 if kind is dict else 5
        struct.pack_into('>I', shape, pos + 1, len(item))
        cursors[0] += 5
        if kind is dict:
            for key, child in item.items():
                if type(key) is not str:
                    raise _NoSeal
                _reference(key, refs, cursors)
                _fill(child, depth + 1, max_depth, shape, refs, cursors)
        else:
            for child in item:
                _fill(child, depth + 1, max_depth, shape, refs, cursors)
        return
    if kind is type(None):
        tag = 0
    elif kind is bool:
        tag = 1
    elif kind is int:
        tag = 2
    elif kind is float and math.isfinite(item):
        tag = 3
    elif kind is str:
        tag = 4
    else:
        raise _NoSeal
    shape[pos] = tag
    cursors[0] += 1
    _reference(item, refs, cursors)


def capture(value, *, capacity=131072, max_nodes=16384, max_depth=64):
    """Return ((shape bytes, existing scalar refs), resident, peak), or None."""
    if type(max_depth) is not int or not 0 <= max_depth <= 64:
        return None
    if type(capacity) is not int or capacity < scratch_bound(max_depth):
        return None
    plan = dimensions(value, max_nodes=max_nodes, max_depth=max_depth)
    if plan is None or plan[4] > capacity:
        return None
    shape_size, ref_count, _, resident, peak = plan
    shape = bytearray(shape_size)
    refs = [None] * ref_count
    cursors = [0, 0]
    try:
        _fill(value, 0, max_depth, shape, refs, cursors)
        if cursors != [shape_size, ref_count]:
            return None
    except (_NoSeal, RuntimeError):
        return None
    return (bytes(shape), tuple(refs)), resident, peak


def _compare(item, shape, refs, cursors):
    pos = cursors[0]
    if pos >= len(shape):
        return False
    tag = shape[pos]
    cursors[0] += 1
    kind = type(item)
    if tag == 5 or tag == 6:
        if not (kind is list if tag == 5 else kind is dict):
            return False
        size = struct.unpack_from('>I', shape, pos + 1)[0]
        cursors[0] += 4
        if len(item) != size:
            return False
        if tag == 6:
            for key in item:
                if type(key) is not str:
                    return False
            for _ in range(size):
                key = refs[cursors[1]]
                cursors[1] += 1
                if key not in item or not _compare(item[key], shape, refs, cursors):
                    return False
        else:
            for child in item:
                if not _compare(child, shape, refs, cursors):
                    return False
        return True
    original = refs[cursors[1]]
    cursors[1] += 1
    if tag == 0:
        return kind is type(None)
    if tag == 1:
        return kind is bool and item is original
    if tag == 2:
        return kind is int and item == original
    if tag == 3:
        return kind is float and float.hex(item) == float.hex(original)
    if tag == 4:
        return kind is str and item == original
    return False


def matches(value, seal):
    """Freshly compare every current built-in type/key/value, not identity only."""
    shape, refs = seal
    cursors = [0, 0]
    return _compare(value, shape, refs, cursors) and cursors == [len(shape), len(refs)]


def _compare_original_refs(item,shape,refs,cursors):
    pos=cursors[0]
    if pos>=len(shape):return False
    tag=shape[pos];cursors[0]+=1;kind=type(item)
    if tag==5 or tag==6:
        if not (kind is list if tag==5 else kind is dict) or pos+5>len(shape):return False
        size=struct.unpack_from('>I',shape,pos+1)[0];cursors[0]+=4
        if len(item)!=size:return False
        if tag==6:
            for key in item:
                if type(key) is not str or cursors[1]>=len(refs) or key is not refs[cursors[1]]:return False
                cursors[1]+=1
                if not _compare_original_refs(item[key],shape,refs,cursors):return False
        else:
            for child in item:
                if not _compare_original_refs(child,shape,refs,cursors):return False
        return True
    if cursors[1]>=len(refs):return False
    original=refs[cursors[1]];cursors[1]+=1
    if tag==0:return kind is type(None) and item is original
    if tag==1:return kind is bool and item is original
    if tag==2:return kind is int and item is original
    if tag==3:return kind is float and item is original
    if tag==4:return kind is str and item is original
    return False


def matches_original_refs(value,seal):
    if type(seal) is not tuple or len(seal)!=2:return False
    shape,refs=seal
    if type(shape) is not bytes or type(refs) is not tuple:return False
    cursors=[0,0]
    return _compare_original_refs(value,shape,refs,cursors) and cursors==[len(shape),len(refs)]
