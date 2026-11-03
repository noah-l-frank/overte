// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Dedicated E2E-only passive microphone observer. It reuses the original
// device-input capture buffer, never the preview input/sink PCM, local echo,
// an injector, a mode setter or a requested success value.
#include "AcousticTestCapture.h"
#include "RecordedPreviewInputOrigin.h"
#include <QRegularExpression>

namespace overte::e2e {
struct PassiveAcousticReadTicket {
    PassiveAcousticReadTicket() = default;
    PassiveAcousticReadTicket(const PassiveAcousticReadTicket&) = delete;
    PassiveAcousticReadTicket& operator=(const PassiveAcousticReadTicket&) = delete;
    QPointer<QObject> source, device;
    const QByteArray* bytes {nullptr};
    const QThread* ownerThread {nullptr};
    std::shared_ptr<const RecordedPreviewAdmission> admission;
    unsigned admissionState {0};
    quint64 generation {0}, sequence {0}, captureGeneration {0}, routeRevision {0};
    int rate {0}, channels {0};
    qint64 beforeEpoch {0}, afterEpoch {0}, beforeMono {0}, afterMono {0};
    QByteArray readDigest;
    bool eligible {false}, consumed {false};
};

class PassiveAcousticCapture {
public:
    bool start(const QString& run, const QString& lease, int seconds, int rate, int channels,
            std::shared_ptr<const RecordedPreviewAdmission> admission, QObject* source,
            QObject* device, quint64 generation, quint64 routeRevision) {
        const unsigned epoch = admission ? admission->state() : 0;
        if (_owned || !identifier(run) || !identifier(lease) || !admission ||
                !RecordedPreviewAdmission::available(epoch) || !source || !device ||
                !generation || generation > 1000000000 || _captureGeneration >= 1000000000 ||
                !_capture.start(rate, channels, seconds)) { return false; }
        _owned = true; _invalid = false; _run = run; _lease = lease;
        _admission = std::move(admission); _epoch = epoch;
        _source = source; _device = device; _generation = generation; _routeRevision = routeRevision;
        _rate = rate; _channels = channels; _target = rate * channels * 2 * seconds;
        _startedEpoch = QDateTime::currentMSecsSinceEpoch(); _startedMono = previewOriginMonotonicMs();
        _lastEpoch = _startedEpoch; _lastMono = _startedMono; _sequence = 0; _covered = 0; _rows.clear();
        ++_captureGeneration;
        return true;
    }
    bool owned() const { return _owned; }
    bool active() const { return _owned && !_invalid && _capture.active(); }
    quint64 captureGeneration() const { return _captureGeneration; }
    const std::shared_ptr<const RecordedPreviewAdmission>& admission() const { return _admission; }
    unsigned admissionEpoch() const { return _epoch; }
    bool bound(QObject* source, QObject* device, quint64 generation, quint64 routeRevision) const {
        return _owned && _admission && _admission->state() == _epoch &&
            RecordedPreviewAdmission::available(_epoch) && _source && _device &&
            _source.data() == source && _device.data() == device &&
            _generation == generation && _routeRevision == routeRevision;
    }
    void invalidate() {
        if (!_owned) { return; }
        _invalid = true; _capture.invalidate();
        // Ownership and the original callback history remain until an exact
        // lease release. Invalidation is not an empty-resource end receipt.
    }
    void stop(quint64 captureGeneration) {
        if (_owned && captureGeneration == _captureGeneration && _capture.active()) {
            _capture.stop();
            if (!_capture.complete()) { _invalid = true; }
        }
    }
    void append(PassiveAcousticReadTicket* ticket, const QByteArray& input, bool current,
            QObject* source, QObject* device, quint64 generation, quint64 routeRevision,
            int rate, int channels) {
        if (!active()) { return; }
        const auto tapEpoch = QDateTime::currentMSecsSinceEpoch();
        const auto tapMono = previewOriginMonotonicMs();
        if (!current || !bound(source, device, generation, routeRevision) || !ticket ||
                !ticket->eligible || ticket->consumed || ticket->bytes != &input ||
                ticket->ownerThread != QThread::currentThread() || ticket->admission != _admission ||
                ticket->admissionState != _epoch || !ticket->source || !ticket->device ||
                ticket->source.data() != source || ticket->device.data() != device ||
                ticket->generation != generation || ticket->captureGeneration != _captureGeneration ||
                ticket->routeRevision != routeRevision || ticket->rate != rate || ticket->channels != channels ||
                _rate != rate || _channels != channels || ticket->sequence <= _sequence ||
                input.isEmpty() || input.size() > 16 * 1024 * 1024 || input.size() % (channels * 2) ||
                ticket->beforeEpoch < _lastEpoch || ticket->beforeMono < _lastMono ||
                ticket->afterEpoch < ticket->beforeEpoch || ticket->afterMono < ticket->beforeMono ||
                tapEpoch < ticket->afterEpoch || tapMono < ticket->afterMono || _rows.size() >= 2048 ||
                QCryptographicHash::hash(input, QCryptographicHash::Sha256) != ticket->readDigest) {
            invalidate(); return;
        }
        ticket->consumed = true;
        const int before = _capture.bytes();
        _capture.append(input, rate, channels);
        const int count = _capture.bytes() - before;
        if (_capture.invalid() || count <= 0 || before != _covered || count > input.size()) {
            invalidate(); return;
        }
        _rows.append(QVariantMap{{"sequence", static_cast<qulonglong>(ticket->sequence)},
            {"generation", static_cast<qulonglong>(generation)}, {"routeRevision", QString::number(routeRevision)},
            {"readBeforeEpochMs", ticket->beforeEpoch}, {"readAfterEpochMs", ticket->afterEpoch},
            {"readBeforeMonotonicMs", ticket->beforeMono}, {"readAfterMonotonicMs", ticket->afterMono},
            {"tapEpochMs", tapEpoch}, {"tapMonotonicMs", tapMono},
            {"readBytes", input.size()}, {"readSha256", QString::fromLatin1(ticket->readDigest.toHex())},
            {"offset", before}, {"bytes", count},
            {"sha256", QString::fromLatin1(QCryptographicHash::hash(input.left(count), QCryptographicHash::Sha256).toHex())}});
        _covered += count; _sequence = ticket->sequence; _lastEpoch = tapEpoch; _lastMono = tapMono;
    }
    QVariantMap snapshot(bool current) const {
        const bool complete = _owned && !_invalid && current && _capture.complete() &&
            _covered == _target && _covered == _capture.bytes() && !_rows.isEmpty();
        return {{"passiveAcousticVersion", 1}, {"profile", "qt-source-read-to-passive-acoustic-tap"},
            {"owned", _owned}, {"runId", _run}, {"role", _owned ? "actor" : ""}, {"leaseId", _lease},
            {"instance", _admission ? _admission->instance() : QString()}, {"admissionEpoch", _epoch},
            {"captureGeneration", static_cast<qulonglong>(_captureGeneration)},
            {"inputGeneration", static_cast<qulonglong>(_generation)}, {"inputRouteRevision", QString::number(_routeRevision)},
            {"startedEpochMs", _startedEpoch}, {"startedMonotonicMs", _startedMono},
            {"active", active() && current}, {"complete", complete},
            {"invalid", _owned && (_invalid || !current || _capture.invalid())},
            {"sampleRate", _rate}, {"channels", _channels}, {"bytes", _capture.bytes()},
            {"coveredBytes", _covered}, {"targetBytes", _target},
            {"inputCallbacks", _capture.callbacks()}, {"rows", _rows},
            {"physicalADCQualified", false}, {"acousticQualified", false}, {"peerQualified", false}};
    }
    QByteArray wav(bool current) const {
        return snapshot(current).value("complete").toBool() ? _capture.wav() : QByteArray();
    }
    bool release(const QString& run, const QString& lease, quint64 captureGeneration) {
        if (!_owned || run != _run || lease != _lease || captureGeneration != _captureGeneration) { return false; }
        _capture.resetAndErase(); _owned = _invalid = false;
        _run.clear(); _lease.clear(); _admission.reset(); _epoch = 0;
        _source.clear(); _device.clear(); _generation = _routeRevision = _sequence = 0;
        _rate = _channels = _target = _covered = 0;
        _startedEpoch = _startedMono = _lastEpoch = _lastMono = 0;
        QVariantList().swap(_rows);
        return true;
    }
private:
    static bool identifier(const QString& value) {
        return QRegularExpression("^[0-9a-f]{32}$").match(value).hasMatch();
    }
    AcousticTestCapture _capture;
    std::shared_ptr<const RecordedPreviewAdmission> _admission;
    QPointer<QObject> _source, _device;
    QString _run, _lease;
    QVariantList _rows;
    unsigned _epoch {0};
    quint64 _generation {0}, _routeRevision {0}, _captureGeneration {0}, _sequence {0};
    qint64 _startedEpoch {0}, _startedMono {0}, _lastEpoch {0}, _lastMono {0};
    int _rate {0}, _channels {0}, _target {0}, _covered {0};
    bool _owned {false}, _invalid {false};
};
} // namespace overte::e2e
