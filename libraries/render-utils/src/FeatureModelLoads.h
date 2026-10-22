// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QMutex>
#include <QMutexLocker>
#include <QUrl>
#include <QUuid>
#include <QVariantMap>
namespace overte::e2e {
// Original request and loader-callback facts only. This never starts/cancels a
// request, changes a URL, decides fallback, or supplies a loaded/render verdict.
class FeatureModelLoads {
public:
    void requested(const QUrl& url) {
        if (!enabled()) { return; }QMutexLocker guard(&_mutex);
        if (!_complete || _rows.size()>=256 || _generation>=1000000000) { _complete=false;return; }
        ++_generation;_requested=hash(url);append("requested",QVariant(),QString());
    }
    void finished(bool success,const QUrl& actualResource) {
        if (!enabled()) { return; }QMutexLocker guard(&_mutex);
        if (!_complete || !_generation || _rows.size()>=256) { _complete=false;return; }
        append("finished",success,hash(actualResource));
    }
    QVariantMap snapshot() {
        if (!enabled()) { return {}; }QMutexLocker guard(&_mutex);
        const auto now=tick();if (!now) { return {}; }
        return {{"modelLoadsVersion",1},{"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},
            {"capturedEpochMs",now},{"complete",_complete},{"currentGeneration",static_cast<qulonglong>(_generation)},
            {"requestedSha256",_requested},{"events",_rows}};
    }
private:
    static bool enabled() { return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript"); }
    static QString hash(const QUrl& url) { return QString::fromLatin1(QCryptographicHash::hash(url.toString().toUtf8(),QCryptographicHash::Sha256).toHex()); }
    qint64 tick() { const auto now=QDateTime::currentMSecsSinceEpoch();if (now<1 || now<_epoch) { _complete=false;return 0; }_epoch=now;return now; }
    void append(const QString& kind,const QVariant& success,const QString& resource) {
        const auto now=tick();if (!now) { return; }
        _rows.append(QVariantMap{{"eventSequence",_rows.size()+1},{"generation",static_cast<qulonglong>(_generation)},
            {"kind",kind},{"capturedEpochMs",now},{"requestedSha256",_requested},{"resourceSha256",resource},{"success",success}});
    }
    QMutex _mutex;QString _instance{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')},_requested;
    QVariantList _rows;quint64 _generation{0},_sequence{0};qint64 _epoch{0};bool _complete{true};
};
}
#endif
