// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive identity/lifetime observation of the actual original whole UI walk.
// firstObserved* is explicitly not an allocation or component creation time.
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QQuickItem>
#include <QThread>
#include <QUuid>
#include <atomic>
#include <vector>

namespace overte::e2e::script_ui_roots {
inline bool enabled() noexcept {
    try {
    const auto args=QCoreApplication::arguments();
    for (const auto& flag:{QStringLiteral("--testScript"),QStringLiteral("--testResultsLocation")}) {
        const int index=args.indexOf(flag);
        if (index<0 || index+1>=args.size() || args[index+1].isEmpty() || args[index+1].startsWith("--")) { return false; }
    }
    return true;
    } catch (...) {return false;}
}

enum class Profile {Scripts,Login};

class Ledger {
    struct Root {
        QString id,kind,source;
        QPointer<QQuickItem> item;
        qint64 observedEpoch,observedMono,expiredEpoch {0},expiredMono {0};
        quint64 observedSequence;
    };
    Profile _profile;
    QString schema() const {return _profile==Profile::Scripts ? QStringLiteral("iosScriptUiRootOwnershipVersion") : QStringLiteral("iosLoginUiRootOwnershipVersion");}
    const QString _instance {QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-')};
    QElapsedTimer _timer;
    std::vector<Root> _roots;
    std::atomic_bool _complete {true};
    quint64 _sequence {0},_observations {0};
    bool main() const noexcept {return qApp && QThread::currentThread()==qApp->thread();}
public:
    explicit Ledger(Profile profile=Profile::Scripts) : _profile(profile) { _timer.start(); }
    QString observe(QQuickItem* item,const QString& kind,const QString& source) noexcept {
        if (!enabled()) { return {}; }
        if (!main()) { _complete.store(false);return {}; }
        try {
            if (!item || item->thread()!=qApp->thread() || (_profile==Profile::Scripts ? kind!="manager" && kind!="picker" : kind!="tablet" && kind!="overlay" && kind!="dialog") || source.isEmpty() || source.size()>4096) {
                _complete.store(false);return {};
            }
            for (const auto& root:_roots) {
                if (root.item.data()==item) {
                    if (root.kind!=kind || root.source!=source) { _complete.store(false); }
                    return root.id;
                }
            }
            if (_roots.size()>=64 || _observations>=9007199254740991ULL) { _complete.store(false);return {}; }
            _roots.push_back(Root{QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'),kind,source,QPointer<QQuickItem>(item),
                QDateTime::currentMSecsSinceEpoch(),_timer.elapsed(),0,0,++_observations});
            return _roots.back().id;
        } catch (...) { _complete.store(false);return {}; }
    }
    QJsonObject read(bool wholeTreeReady) noexcept {
        if (!enabled()) { return {{schema(),1},{"available",false}}; }
        if (!main()) { _complete.store(false);return {{schema(),1},{"available",false}}; }
        try {
            if (_sequence>=9007199254740991ULL) { _complete.store(false); }
            else { ++_sequence; }
            QJsonArray roots;
            for (auto& root:_roots) {
                const bool alive=!root.item.isNull();
                if (!alive && !root.expiredEpoch) { root.expiredEpoch=QDateTime::currentMSecsSinceEpoch();root.expiredMono=_timer.elapsed(); }
                roots.append(QJsonObject{{"observedIdentity",root.id},{"kind",root.kind},{"componentSource",root.source},
                    {"firstObservedSequence",static_cast<double>(root.observedSequence)},
                    {"firstObservedEpochMs",root.observedEpoch},{"firstObservedMonotonicMs",root.observedMono},
                    {"weakAlive",alive},{"weakExpiredObservedEpochMs",root.expiredEpoch},{"weakExpiredObservedMonotonicMs",root.expiredMono}});
            }
            QJsonObject value{{schema(),1},{"available",true},{"instance",_instance},
                {"clockDomain",_profile==Profile::Scripts ? "native-main-ios-script-ui-roots" : "native-main-ios-login-ui-roots"},
                {"sequence",static_cast<double>(_sequence)},{"processId",QCoreApplication::applicationPid()},
                {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"monotonicMs",_timer.elapsed()},
                {"complete",_complete.load()},{"wholeTreeReady",wholeTreeReady},{"observationSequence",static_cast<double>(_observations)},
                {"roots",roots}};
            if (QJsonDocument(value).toJson(QJsonDocument::Compact).size()>16384) {
                _complete.store(false);value["complete"]=false;value["roots"]=QJsonArray();
            }
            return value;
        } catch (...) { _complete.store(false);return {{schema(),1},{"available",false}}; }
    }
};
inline Ledger& ledger() {static Ledger value;return value;}
inline std::atomic_bool& unavailable() noexcept {static std::atomic_bool value {false};return value;}
inline QString observe(QQuickItem* item,const QString& kind,const QString& source) noexcept {
    if (!enabled() || unavailable().load()) {return {};}
    try {return ledger().observe(item,kind,source);} catch (...) {unavailable().store(true);return {};}
}
inline QJsonObject read(bool wholeTreeReady) {
    if (!enabled() || unavailable().load()) {return {{"iosScriptUiRootOwnershipVersion",1},{"available",false}};}
    try {return ledger().read(wholeTreeReady);} catch (...) {unavailable().store(true);return {{"iosScriptUiRootOwnershipVersion",1},{"available",false}};}
}
} // namespace overte::e2e::script_ui_roots
#endif
