// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Dedicated E2E-build observer. It never supplies audio, normalizes samples,
// drives a sink, changes the preview buffer or evaluates a test expectation.
#include "RecordedPreviewInputOrigin.h"
#include <QAudioFormat>
#include <QByteArray>
#include <QDateTime>
#include <QVariantMap>
#include <QVariantList>
#include <QtGlobal>

namespace overte::e2e {
class RecordedPreviewObservation {
public:
    quint64 begin(const QAudioFormat& format, std::shared_ptr<const RecordedPreviewAdmission> admission = {}) {
        clear();
        ++_cycle;
        _format = format;
        _origin.begin(std::move(admission));
        _started = QDateTime::currentMSecsSinceEpoch();
#if QT_VERSION >= QT_VERSION_CHECK(6, 0, 0)
        // Qt 6 PCM uses native byte order; these original carriers are LE.
        const bool pcm16le = format.sampleFormat() == QAudioFormat::Int16
            && Q_BYTE_ORDER == Q_LITTLE_ENDIAN;
#else
        const bool pcm16le = format.sampleSize() == 16 && format.sampleType() == QAudioFormat::SignedInt
            && format.byteOrder() == QAudioFormat::LittleEndian;
#endif
        _valid = pcm16le && format.channelCount() >= 1 && format.channelCount() <= 2
            && format.sampleRate() >= 8000 && format.sampleRate() <= 48000;
        return _cycle;
    }
    void clear() {
        _valid = false;
        _origin.clear();
        _input.fill(0); _input.clear(); _input.squeeze();
        _sink.fill(0); _sink.clear(); _sink.squeeze();
        _events.clear();
        _started = _inputEpoch = _sinkEpoch = 0;
    }
    quint64 cycle() const { return _cycle; }
    void input(const char* data, qint64 count) { append(_input, _inputEpoch, data, count, 16 * 1024 * 1024); }
    RecordedPreviewInputOrigin& origin() { return _origin; }
    const RecordedPreviewInputOrigin& origin() const { return _origin; }
    void sink(const char* data, qint64 count) { append(_sink, _sinkEpoch, data, count, 32 * 1024 * 1024); }
    void event(const QVariantMap& value) {
        if (!_valid) { return; }
        if (_events.size() >= 64) { clear(); return; }
        _events.append(value);
    }
    QVariantMap snapshot() const {
        if (!_valid) { return {}; }
        QVariantMap result {{"cycle", static_cast<qulonglong>(_cycle)}, {"startedEpochMs", _started},
            {"sampleRate", _format.sampleRate()}, {"channels", _format.channelCount()},
            {"inputLastEpochMs", _inputEpoch}, {"sinkLastEpochMs", _sinkEpoch},
            {"inputPcm", _input}, {"sinkPcm", _sink}, {"events", _events}};
        const auto origin = _origin.snapshot(_input.size(), _started);
        if (!origin.isEmpty()) { result["inputOrigin"] = origin; }
        return result;
    }
private:
    void append(QByteArray& bytes, qint64& epoch, const char* data, qint64 count, int limit) {
        if (!_valid) { return; }
        if (!data || count < 0 || count > limit - bytes.size()) { clear(); return; }
        // A native device may accept a partial frame. Preserve those exact
        // writes; the complete artifact must later have a whole-frame length.
        if (count > 0) {
            bytes.append(data, static_cast<int>(count));
            epoch = QDateTime::currentMSecsSinceEpoch();
        }
    }
    RecordedPreviewInputOrigin _origin;
    QAudioFormat _format;
    QByteArray _input, _sink;
    QVariantList _events;
    quint64 _cycle {0};
    qint64 _started {0}, _inputEpoch {0}, _sinkEpoch {0};
    bool _valid {false};
};
} // namespace overte::e2e
