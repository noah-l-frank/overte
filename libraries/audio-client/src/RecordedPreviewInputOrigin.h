// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive diagnostic objects only. No audio owner, capture API or mode setter.
#include <atomic>
#include <memory>
#include <utility>
#include <QByteArray>
#include <QVariantList>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QPointer>
#include <QThread>
#include <QVariantMap>

namespace overte::e2e {
class RecordedPreviewAdmission {
public:
    explicit RecordedPreviewAdmission(QString instance) : _instance(std::move(instance)) {}
    const QString& instance() const { return _instance; }
    unsigned state() const { return _state.load(std::memory_order_acquire); }
    static bool available(unsigned state) { return (state & 3U) == 1U; }
    // Revocation is permanent for this exact token. A later lifecycle event
    // cannot revive a token whose TestResults owner changed/disappeared.
    void revoke() { _state.fetch_or(2U, std::memory_order_acq_rel); }
    void advance(bool valid) {
        auto old = state();
        while (!(old & 2U)) {
            if (old >= 4000000000U) { revoke(); return; }
            const unsigned next = ((old >> 2) + 1U) * 4U + (valid ? 1U : 0U);
            if (_state.compare_exchange_weak(old, next, std::memory_order_acq_rel)) { return; }
        }
    }
private:
    const QString _instance;
    std::atomic<unsigned> _state {0};
};

inline qint64 previewOriginMonotonicMs() {
    QElapsedTimer timer; timer.start(); return timer.msecsSinceReference();
}

// Stack-only, explicit synchronous argument. Its address never enters a
// QObject property, queued invocation, collector member or latest-read slot.
struct RecordedPreviewReadTicket {
    RecordedPreviewReadTicket() = default;
    RecordedPreviewReadTicket(const RecordedPreviewReadTicket&) = delete;
    RecordedPreviewReadTicket& operator=(const RecordedPreviewReadTicket&) = delete;
    QPointer<QObject> source, device;
    const QByteArray* bytes {nullptr};
    const QThread* ownerThread {nullptr};
    std::shared_ptr<const RecordedPreviewAdmission> admission;
    unsigned admissionState {0};
    quint64 generation {0}, sequence {0}, cycle {0};
    int rate {0}, channels {0};
    quint64 routeRevision {0};
    qint64 beforeEpoch {0}, afterEpoch {0}, beforeMono {0}, afterMono {0};
    QByteArray readDigest;
    bool eligible {false}, consumed {false};
};

class RecordedPreviewInputOrigin {
public:
    void begin(std::shared_ptr<const RecordedPreviewAdmission> admission) {
        clear();
        if (admission && RecordedPreviewAdmission::available(admission->state())) {
            _admission = std::move(admission); _epoch = _admission->state();
            _armed = RecordedPreviewAdmission::available(_epoch); _complete = _armed;
        }
    }
    void clear() {
        _admission.reset(); _epoch = 0; _armed = _complete = false;
        _rows.clear(); _covered = 0; _generation = _sequence = 0;
        _lastEpoch = _lastMono = 0; _routeRevision = 0; _rate = _channels = 0;
    }
    bool armed() const { return _armed; }
    bool current() const {
        return _armed && _admission && _admission->state() == _epoch
            && RecordedPreviewAdmission::available(_epoch);
    }
    unsigned epoch() const { return _epoch; }
    const std::shared_ptr<const RecordedPreviewAdmission>& admission() const { return _admission; }
    void unavailable() { _complete = false; }
    void append(RecordedPreviewReadTicket* ticket, const QByteArray& actualInput,
            const char* output, qint64 outputSize, qint64 offset, qint64 count,
            bool nativeCurrent, quint64 currentGeneration, QObject* source, QObject* device,
            quint64 cycle, int inputRate, int inputChannels, quint64 routeRevision, bool resamplerUsed) {
        if (!_armed || count == 0) { return; }
        const auto tapEpoch = QDateTime::currentMSecsSinceEpoch();
        const auto tapMono = previewOriginMonotonicMs();
        if (!_complete || !current() || !ticket || !ticket->eligible || ticket->consumed
                || !nativeCurrent || ticket->admission != _admission || ticket->admissionState != _epoch
                || ticket->bytes != &actualInput || ticket->ownerThread != QThread::currentThread()
                || !ticket->source || !ticket->device || ticket->source.data() != source || ticket->device.data() != device
                || ticket->generation != currentGeneration || !currentGeneration || currentGeneration > 1000000000
                || ticket->cycle != cycle || ticket->rate != inputRate || ticket->channels != inputChannels
                || ticket->routeRevision != routeRevision || ticket->sequence <= _sequence
                || (_generation && (_generation != currentGeneration || _routeRevision != routeRevision
                    || _rate != inputRate || _channels != inputChannels)) || offset != _covered
                || count <= 0 || outputSize < count || outputSize > 16 * 1024 * 1024 || !output
                || inputChannels < 1 || inputChannels > 2 || inputRate < 8000 || inputRate > 48000
                || actualInput.isEmpty() || actualInput.size() > 16 * 1024 * 1024
                || actualInput.size() % (inputChannels * 2) != 0
                || ticket->beforeEpoch < _lastEpoch || ticket->beforeMono < _lastMono
                || ticket->afterEpoch < ticket->beforeEpoch || tapEpoch < ticket->afterEpoch
                || ticket->afterMono < ticket->beforeMono || tapMono < ticket->afterMono
                || _rows.size() >= 384
                || QCryptographicHash::hash(actualInput, QCryptographicHash::Sha256) != ticket->readDigest) {
            unavailable(); return;
        }
        ticket->consumed = true;
        _rows.append(QVariantMap{{"sequence", static_cast<qulonglong>(ticket->sequence)},
            {"generation", static_cast<qulonglong>(currentGeneration)}, {"readBytes", actualInput.size()},
            {"readSha256", QString::fromLatin1(ticket->readDigest.toHex())},
            {"inputRate", inputRate}, {"inputChannels", inputChannels}, {"resamplerUsed", resamplerUsed},
            {"routeRevision", QString::number(routeRevision)},
            {"readBeforeEpochMs", ticket->beforeEpoch}, {"readAfterEpochMs", ticket->afterEpoch},
            {"readBeforeMonotonicMs", ticket->beforeMono}, {"readAfterMonotonicMs", ticket->afterMono},
            {"tapEpochMs", tapEpoch}, {"tapMonotonicMs", tapMono},
            {"offset", offset}, {"bytes", count}, {"convertedBytes", outputSize},
            {"sha256", QString::fromLatin1(QCryptographicHash::hash(QByteArray(output, static_cast<int>(count)),
                QCryptographicHash::Sha256).toHex())}});
        _covered += count; _generation = currentGeneration; _sequence = ticket->sequence;
        _routeRevision = routeRevision; _rate = inputRate; _channels = inputChannels;
        _lastEpoch = tapEpoch; _lastMono = tapMono;
    }
    QVariantMap snapshot(qint64 inputBytes, qint64 started) const {
        if (!_armed) { return {}; }
        if (!_complete || !current() || _covered != inputBytes || inputBytes <= 0
                || _rows.isEmpty() || _rows.first().toMap().value("readBeforeEpochMs").toLongLong() < started) {
            return {{"originVersion", 1}, {"available", false}};
        }
        return {{"originVersion", 1}, {"available", true}, {"profile", "qt-source-read-to-preview-tap"},
            {"instance", _admission->instance()}, {"admissionEpoch", _epoch},
            {"coveredBytes", _covered}, {"rows", _rows}, {"physicalADCQualified", false},
            {"acousticQualified", false}, {"peerQualified", false}, {"resamplerHistoryQualified", false}};
    }
private:
    std::shared_ptr<const RecordedPreviewAdmission> _admission;
    unsigned _epoch {0};
    bool _armed {false}, _complete {false};
    QVariantList _rows;
    qint64 _covered {0}, _lastEpoch {0}, _lastMono {0};
    quint64 _generation {0}, _sequence {0}, _routeRevision {0};
    int _rate {0}, _channels {0};
};
} // namespace overte::e2e
