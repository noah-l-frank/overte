// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// E2E input only. Called by the real microphone callback, before the existing
// local preview/resampler/network paths. It cannot start a recording, satisfy
// permission/input availability, run a synthetic clock or report an effect.
#include <QChar>
#include <QByteArray>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QVariantMap>
#include <QtEndian>

namespace overte::e2e {
class PhoneAudioFixtureInput {
public:
    bool arm(const QByteArray& pcm, const QVariantMap& receipt) {
        if (!_pcm.isEmpty() || pcm.size() != 144000 || receipt.isEmpty()) { return false; }
        _pcm = pcm; _receipt = receipt; _position = _callbacks = _frames = 0;
        _cycle = 0; _first = _last = 0; _rate = _channels = 0;
        _emits = _silent = _encodedBytes = 0; _codec.clear(); _complete = true;
        _lease.start(); return true;
    }
    void replace(QByteArray& input, int rate, int channels, bool capturing, quint64 cycle) {
        if (_pcm.isEmpty()) { return; }
        // Expiry also removes the bytes; an old input can never be rearmed by
        // a late callback. Product availability/mute/lifecycle gates are intact.
        if (!_lease.isValid() || _lease.elapsed() >= 15000) { clear(); return; }
        if (rate < 8000 || rate > 48000 || channels < 1 || channels > 2 || input.size() % (2 * channels)
                || (_rate && (_rate != rate || _channels != channels))) { _complete = false; input.fill(0); return; }
        _rate = rate; _channels = channels; ++_callbacks;
        input.fill(0);
        if (!capturing) { return; }
        if (!_cycle) { _cycle = cycle; }
        if (_cycle != cycle || !cycle) { _complete = false; return; }
        const auto now = QDateTime::currentMSecsSinceEpoch();
        if (!_first) { _first = now; }
        _last = now;
        const int frames = input.size() / (2 * channels);
        for (int frame = 0; frame < frames; ++frame, ++_position) {
            const quint64 source = _position * 24000 / static_cast<quint64>(rate);
            if (source >= 72000) { continue; }
            const auto value = qFromLittleEndian<qint16>(reinterpret_cast<const uchar*>(_pcm.constData()) + source * 2);
            for (int channel = 0; channel < channels; ++channel) {
                qToLittleEndian<qint16>(value, reinterpret_cast<uchar*>(input.data()) + (frame * channels + channel) * 2);
            }
        }
        _frames += frames;
    }
    void emitted(int bytes, bool silent, const QString& codec) {
        if (_pcm.isEmpty()) { return; }
        if (bytes < 0 || _emits >= 4096) { _complete = false; return; }
        ++_emits; _silent += silent; _encodedBytes += bytes; _codec = codec;
    }
    QVariantMap snapshot() const {
        return {{"inputVersion", 1}, {"armed", !_pcm.isEmpty()}, {"receipt", _receipt},
            {"pcmBytes", _pcm.size()}, {"pcmSha256", QString::fromLatin1(QCryptographicHash::hash(_pcm, QCryptographicHash::Sha256).toHex())},
            {"complete", _complete}, {"cycle", QVariant::fromValue(_cycle)},
            {"callbacks", QVariant::fromValue(_callbacks)}, {"inputFrames", QVariant::fromValue(_frames)},
            {"inputRate", _rate}, {"inputChannels", _channels}, {"firstInputEpochMs", _first}, {"lastInputEpochMs", _last},
            {"packetEmits", QVariant::fromValue(_emits)}, {"silentEmits", QVariant::fromValue(_silent)},
            {"encodedBytes", QVariant::fromValue(_encodedBytes)}, {"codec", _codec}};
    }
    void clear() {
        _pcm.fill(0); _pcm.clear(); _pcm.squeeze(); _receipt.clear(); _lease.invalidate();
    }
private:
    QByteArray _pcm;
    QVariantMap _receipt;
    QElapsedTimer _lease;
    quint64 _position {0}, _callbacks {0}, _frames {0}, _cycle {0}, _emits {0}, _silent {0}, _encodedBytes {0};
    qint64 _first {0}, _last {0};
    int _rate {0}, _channels {0};
    bool _complete {true};
    QString _codec;
};
}
