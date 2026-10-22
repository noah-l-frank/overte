// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QThread>
#include <QUuid>
#include <QUrl>
#include <QUrlQuery>
#include <QVariantMap>
#include <functional>

namespace overte::e2e {
// Last actual successful import, not a requested scene or a mutable baseline.
// Product/native lifetime history remains in the separate scene-load source.
class SceneCommitOrigin {
public:
    SceneCommitOrigin() {
        if (_enabled) { _clock.start(); }
    }
    void committed(quint64 generation,const QUrl& url,const QByteArray& body,
            const std::function<QVariantMap()>& inventory) {
        if (!active()) { return; }
        if (_commits>=128 || !generation || generation<=_generation || body.isEmpty() || !inventory) {
            _complete=false;return;
        }
        const auto before=clock();const auto tree=inventory();
        auto resource=url;QUrlQuery query(resource);query.removeAllQueryItems("location");
        if (query.isEmpty()) { resource.setQuery(QString()); } else { resource.setQuery(query); }
        _latest={{"generation",static_cast<qulonglong>(generation)},
            {"resourceSha256",QString::fromLatin1(QCryptographicHash::hash(resource.toEncoded(QUrl::FullyEncoded),QCryptographicHash::Sha256).toHex())},
            {"bodyBytes",static_cast<qulonglong>(body.size())},
            {"bodySha256",QString::fromLatin1(QCryptographicHash::hash(body,QCryptographicHash::Sha256).toHex())},
            {"clockBefore",before},{"clockAfter",clock()},{"tree",tree}};
        _generation=generation;++_commits;
        if (tree.isEmpty() || !tree.value("complete").toBool()) { _complete=false; }
    }
    QVariantMap snapshot(quint64 currentGeneration) const {
        if (!active()) { return {}; }
        return {{"iosSceneCommitOriginVersion",1},{"instance",_instance},
            {"processId",static_cast<qulonglong>(QCoreApplication::applicationPid())},
            {"currentGeneration",static_cast<qulonglong>(currentGeneration)},
            {"commits",static_cast<qulonglong>(_commits)},{"complete",_complete},
            {"latest",_latest.isEmpty() ? QVariant() : QVariant(_latest)}};
    }
private:
    bool active() const {
        const auto app=QCoreApplication::instance();
        return _enabled && app && QThread::currentThread()==app->thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    QVariantMap clock() const {
        return {{"epochMs",static_cast<qulonglong>(QDateTime::currentMSecsSinceEpoch())},
            {"monotonicMs",static_cast<qulonglong>(_clock.elapsed())}};
    }
    const bool _enabled {QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript")};
    const QString _instance {_enabled ? QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-') : QString()};
    QElapsedTimer _clock;quint64 _commits {0},_generation {0};bool _complete {true};QVariantMap _latest;
};
} // namespace overte::e2e
#endif
