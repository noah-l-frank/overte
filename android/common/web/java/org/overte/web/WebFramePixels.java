// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
package org.overte.web;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.IntBuffer;

/** GL RGBA bottom-up rows become the existing little-endian premultiplied QImage ARGB32 (BGRA) contract. */
final class WebFramePixels {
    static void pack(ByteBuffer source, ByteBuffer destination, int width, int height, int rowStride, int pixelStride) {
        if (width < 1 || height < 1 || width > 2048 || height > 2048 || pixelStride < 4
                || rowStride < (long) width * pixelStride
                || source.limit() < (long) (height - 1) * rowStride + (long) (width - 1) * pixelStride + 4
                || destination.capacity() < (long) width * height * 4) throw new IllegalArgumentException("invalid frame layout");
        destination.clear();
        if (pixelStride == 4 && rowStride % 4 == 0) {
            // GL readback is packed RGBA. Bulk copies avoid a direct-buffer
            // byte access for every channel; convert one bounded row on heap.
            // Explicit byte order preserves BGRA bytes regardless of the
            // caller's buffer order or the host's native integer order.
            ByteBuffer input = source.duplicate().order(ByteOrder.LITTLE_ENDIAN);
            input.position(0);
            IntBuffer rows = input.asIntBuffer();
            IntBuffer output = destination.duplicate().order(ByteOrder.LITTLE_ENDIAN).asIntBuffer();
            int[] row = new int[width];
            for (int y = height - 1; y >= 0; --y) {
                rows.position(y * (rowStride / 4));
                rows.get(row);
                for (int x = 0; x < width; ++x) {
                    int rgba = row[x];
                    row[x] = (rgba & 0xff00ff00) | ((rgba & 0xff) << 16) | ((rgba >>> 16) & 0xff);
                }
                output.put(row);
            }
        } else {
            for (int y = 0; y < height; ++y) for (int x = 0; x < width; ++x) {
                int input = (height - y - 1) * rowStride + x * pixelStride;
                int output = (y * width + x) * 4;
                destination.put(output, source.get(input + 2)); destination.put(output + 1, source.get(input + 1));
                destination.put(output + 2, source.get(input)); destination.put(output + 3, source.get(input + 3));
            }
        }
        destination.position(0); destination.limit(width * height * 4);
    }
}
