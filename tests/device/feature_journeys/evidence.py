"""Byte-level evidence assertions. Adapter-provided measurements are insufficient."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
from pathlib import Path
import tempfile
from .contract import exact
from .fixtures import challenge, document

MAX_BYTES = 32 * 1024 * 1024


def rectangle(value, size):
    if (type(value) is not list or len(value) != 4 or any(type(x) is not int for x in value)
            or not 0 <= value[0] < value[2] <= size[0] or not 0 <= value[1] < value[3] <= size[1]):
        raise ValueError('Evidence ROI is outside the original screenshot')
    return tuple(value)


def image_observation(content, run, ticket, policy, previous=None, changed=False):
    from PIL import Image, ImageChops, ImageStat
    exact(policy, {'marker', 'subject', 'source'}, 'external feature image policy')
    if policy['source'] not in {'native-screen', 'world-render-target'}:
        raise ValueError('Unsupported original image capture source')
    if content[:8] != b'\x89PNG\r\n\x1a\n' or content[-8:-4] != b'IEND':
        raise AssertionError('A complete original lossless PNG capture is required')
    with Image.open(io.BytesIO(content)) as source:
        if source.width * source.height > 16_000_000:
            raise ValueError('Feature image exceeds its decode pixel budget')
        source.load()
        image = source.convert('RGB')
    marker = image.crop(rectangle(policy['marker'], image.size))
    # marker ROI excludes the card's outer border; all 128 cells must match.
    if marker.width < 128 or marker.height < 32:
        raise ValueError('Challenge marker is too small for independent decoding')
    bits = []
    for index in range(128):
        x = int((index % 32 + 0.5) * marker.width / 32)
        y = int((index // 32 + 0.5) * marker.height / 4)
        rgb = marker.getpixel((x, y))
        if max(rgb) < 70:
            bits.append('0')
        elif min(rgb) > 185:
            bits.append('1')
        else:
            raise AssertionError('Rendered challenge marker is ambiguous')
    wanted = ''.join(f'{byte:08b}' for byte in challenge(run, ticket))
    if ''.join(bits) != wanted:
        raise AssertionError('Screenshot contains a stale or foreign challenge')
    subject_rect = rectangle(policy['subject'], image.size)
    marker_rect = rectangle(policy['marker'], image.size)
    if (max(marker_rect[0], subject_rect[0]) < min(marker_rect[2], subject_rect[2])
            and max(marker_rect[1], subject_rect[1]) < min(marker_rect[3], subject_rect[3])):
        raise ValueError('Challenge and feature subject ROIs must be disjoint')
    subject = image.crop(subject_rect).resize((128, 96))
    if max(ImageStat.Stat(subject).stddev) < 8:
        raise AssertionError('Feature subject is blank or uniform')
    difference = None
    if changed:
        if previous is None:
            raise ValueError('A subject-change assertion requires a previous original image')
        delta = ImageChops.difference(subject, previous)
        pixels = delta.load()
        difference = sum(max(pixels[x, y]) > 25 for y in range(96) for x in range(128)) / (128 * 96)
        if difference < 0.05:
            raise AssertionError('Actual feature subject pixels did not change')
    return dict(sha256=hashlib.sha256(content).hexdigest(), subjectChangedFraction=difference), subject


def audio_observation(content, run, ticket, silence=False):
    from voice_peer.voice_signal import analyze
    with tempfile.TemporaryDirectory(prefix='overte-feature-pcm-') as directory:
        path = Path(directory) / 'capture.wav'
        path.write_bytes(content)
        import wave
        try:
            result = analyze(path, challenge(run, ticket).hex(), 'absent' if silence else 'present')
        except (ValueError, EOFError, wave.Error) as error:
            raise AssertionError('Original PCM capture is malformed or incomplete') from error
    if not result['passed']:
        raise AssertionError('Actual PCM lacks the complete fresh challenge or required silence')
    return result


def file_observation(content, area, run, ticket, policy, fixture_url=None, model_ticket=None, texture_ticket=None):
    if area == 'audio':
        return audio_observation(content, run, ticket)
    if area == 'snapshots':
        from snapshot_observation import inspect_snapshot
        try:
            decoded = inspect_snapshot(content, mode='still', file_format='png')
        except (ValueError, EOFError) as error:
            raise AssertionError('Original SNAP output is malformed or incomplete') from error
        observed, _subject = image_observation(content, run, ticket, policy['file'])
        return dict(decoded=decoded, image=observed)
    if area == 'create':
        try:
            parsed = json.loads(content)
        except (ValueError, UnicodeError) as error:
            raise AssertionError('Original export is not a complete JSON document') from error
        if (type(parsed) is not dict or type(parsed.get('DataVersion')) is not int or parsed.get('DataVersion') != 3
                or type(parsed.get('Entities')) is not list or len(parsed['Entities']) != 1):
            raise AssertionError('Original export must contain exactly the owned model')
        entity = parsed['Entities'][0]
        from .contract import typed_equal
        expected = document(run, fixture_url, model_ticket, texture_ticket)['Entities'][0]
        for field, wanted in expected.items():
            if field == 'textures':
                observed = entity.get(field)
                if type(observed) is str:
                    try:
                        observed = json.loads(observed)
                    except ValueError as error:
                        raise AssertionError('Original texture assignment is malformed') from error
            else:
                observed = entity.get(field)
            if field == 'textures':
                if type(observed) is dict and len(observed) == 1:
                    observed = {'material': next(iter(observed.values()))}
            if field == 'dimensions' and type(observed) is dict and set(observed) == {'x', 'y', 'z'}:
                valid = all(type(observed[k]) in (float, int) and abs(observed[k] - wanted[k]) < 0.0001 for k in wanted)
            else:
                valid = typed_equal(observed, wanted)
            if not valid:
                raise AssertionError('Original export lost owned model geometry, source or texture assignment')
    elif area == 'assets':
        from .fixtures import companion
        if content != companion('gltf-bundle/main.gltf'):
            raise AssertionError('Downloaded mapping bytes differ from the pinned original glTF')
    else:
        raise ValueError('This feature has no file-evidence contract')
    return dict(bytes=len(content), sha256=hashlib.sha256(content).hexdigest())


def read_private_artifact(directory, name):
    import os
    import stat
    import re
    if type(name) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name) is None:
        raise ValueError('Artifact must be a direct private-run filename')
    # Open relative to an already opened directory; reject symlinks, nonregular
    # files, hardlinks and concurrent replacement, even within the private root.
    root = os.open(directory, os.O_DIRECTORY | os.O_RDONLY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root)
        with os.fdopen(descriptor, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= MAX_BYTES:
                raise ValueError('Original feature artifact is not a bounded private regular file')
            content = stream.read(MAX_BYTES + 1)
            after = os.fstat(stream.fileno())
            identity = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_ctime_ns)
            if identity(before) != identity(after) or len(content) != before.st_size:
                raise ValueError('Feature artifact changed during independent reading')
            return content
    finally:
        os.close(root)
