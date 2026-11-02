"""Decode actual SNAP output bytes without accepting adapter success verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
import hashlib
import math


MAX_BYTES = 256 * 1024 * 1024
MAX_PIXELS = 64_000_000
FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'gif': 'GIF'}


def inspect_snapshot(content: bytes, *, mode: str, file_format: str) -> dict:
    """Inspect encoding, complete frames and the documented projection geometry.

    This does not prove camera orientation, scene fidelity, capture provenance,
    export/share or cancellation. Static scenes may produce identical GIF frames;
    decoded frame count and duration are deliberately not a motion observation.
    """
    from PIL import Image
    if mode not in {'still', 'animated', 'panorama', 'cubemap'} or file_format not in FORMATS:
        raise ValueError('Unknown snapshot observation mode or file format')
    if (mode == 'animated') != (file_format == 'gif'):
        raise ValueError('Animated snapshot observation requires its actual GIF file')
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_BYTES:
        raise ValueError('Snapshot file exceeds the bounded byte budget')
    # Do not let a permissive decoder accept an in-progress or truncated stream.
    if file_format == 'gif' and content[-1:] != b';':
        raise ValueError('GIF trailer is missing')
    if file_format == 'jpg' and content[-2:] != b'\xff\xd9':
        raise ValueError('JPEG end marker is missing')
    with Image.open(BytesIO(content)) as image:
        if image.format != FORMATS[file_format]:
            raise ValueError('Actual snapshot encoding differs from the selected format')
        if not 1 <= image.width * image.height <= MAX_PIXELS:
            raise ValueError('Snapshot dimensions exceed the bounded decode budget')
        dimensions = image.size
        if mode == 'panorama' and dimensions != (8192, 4096):
            raise ValueError('Panorama is not the actual 8192x4096 equirectangular output')
        if mode == 'cubemap' and dimensions != (8192, 6144):
            raise ValueError('Cubemap is not the actual 8192x6144 four-by-three cross output')
        count = getattr(image, 'n_frames', 1)
        if not 1 <= count <= 126 or count * image.width * image.height > 256_000_000:
            raise ValueError('Snapshot frame count exceeds the bounded decode budget')
        if mode == 'animated' and count < 2:
            raise ValueError('Animated snapshot contains fewer than two encoded frames')
        if mode != 'animated' and count != 1:
            raise ValueError('Still/projection output unexpectedly contains multiple frames')
        frames, duration = [], 0
        for index in range(count):
            image.seek(index)
            image.load()  # Decode every frame, not just the header or first preview.
            if image.size != dimensions:
                raise ValueError('Snapshot frames disagree about their canvas dimensions')
            if 'A' in image.getbands() or 'transparency' in image.info:
                rgba = image.convert('RGBA')
                pixels = Image.new('RGB', dimensions, 'black')
                pixels.paste(rgba, mask=rgba.getchannel('A'))
                del rgba
            else:
                pixels = image.convert('RGB')
            # The controlled scene is nonuniform. This only rejects an empty or
            # single-color output, never qualifies the scene or its orientation.
            if pixels.getcolors(maxcolors=1) is not None:
                raise ValueError('Controlled-scene snapshot contains a single-color frame')
            delay = image.info.get('duration', 0)
            if mode == 'animated':
                if type(delay) not in (int, float) or not math.isfinite(delay) or not 0 < delay <= 15_000:
                    raise ValueError('Animated snapshot has no usable encoded frame delay')
                duration += delay
            frames.append({'index': index, 'durationMilliseconds': delay,
                           'decodedRgbSha256': hashlib.sha256(pixels.tobytes()).hexdigest()})
        if mode == 'animated' and duration < 1_000:
            raise ValueError('Animated snapshot is shorter than the supported one-second minimum')
    if file_format == 'png':
        with Image.open(BytesIO(content)) as image:
            image.verify()  # Includes the PNG chunk checksums and terminal chunk.
    return {'qualification': 'SNAPSHOT_OUTPUT_BYTES_ONLY', 'mode': mode,
            'format': file_format, 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(),
            'width': dimensions[0], 'height': dimensions[1],
            'decodedFrames': frames, 'durationMilliseconds': duration,
            'deviceAcceptance': False,
            'limitations': 'Original app-file provenance and freshness, scene fidelity/orientation, visual motion, cancellation and system save/share require independent evidence.'}
