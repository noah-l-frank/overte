// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDateTime>
#include <QFileInfo>
#include <QMutex>
#include <QMutexLocker>
#include <QRegularExpression>
#include <QSet>
#include <QUuid>
#include <QVariantMap>
#include <memory>
#include "../../../interface/src/ui/SnapshotCapture.h"
#include <vector>

namespace overte::e2e {
// SnapshotCaptureRequest is the original production type, included by Snapshot.
// Only actual accepted native requests and actually emitted callbacks enter
// this observer. It neither creates requests nor extends their shared lifetime.
class SnapshotCaptureOriginals {
public:
    void begin(const SnapshotCapture& original) {
        QMutexLocker lock(&_mutex);
        if (_run.isEmpty() || !runtime() || !original) {return;}
        if (_requests.size()>=32) {_overflow=true;return;}
        for(const auto& row:_requests) {
            if(!row.weak.owner_before(original) && !original.owner_before(row.weak)) {return;}
        }
        _requests.push_back({original,birth(),original->id,QDateTime::currentMSecsSinceEpoch(),{}});
    }
    void emitted(const SnapshotCapture& original,const QString& phase,const QString& path,const QString& error) {
        QMutexLocker lock(&_mutex);
        if (_run.isEmpty() || !runtime() || !original) {return;}
        for(auto& row:_requests) {
            if(row.weak.owner_before(original) || original.owner_before(row.weak)) {continue;}
            if(row.events.size()>=16) {_overflow=true;return;}
            row.events.append(QVariantMap{{"sequence",row.events.size()+1},{"phase",phase},
                {"publishedEpochMs",QDateTime::currentMSecsSinceEpoch()},
                {"pathSha256",path.isEmpty() ? QString() : hash(_run,path)},
                {"basenameSha256",path.isEmpty() ? QString() : hash(_run,QFileInfo(path).fileName())},
                {"error",error}});
            return;
        }
        _overflow=true; // An unmatched actual callback cannot be silently omitted.
    }
    QVariantMap snapshot(const QVariantMap& command,const QVariantMap& resources) {
        QMutexLocker lock(&_mutex);
        const auto request=command.value("commandId"),run=command.value("runId"),operation=command.value("operation");
        if(!runtime() || command.size()!=4 || (command.value("schemaVersion").userType()!=QMetaType::Int && command.value("schemaVersion").userType()!=QMetaType::Double)
                || command.value("schemaVersion").toDouble()!=1 || request.userType()!=QMetaType::QString
                || run.userType()!=QMetaType::QString || operation.userType()!=QMetaType::QString
                || !nonce(request.toString()) || !nonce(run.toString()) || _seen.size()>=4096
                || _seen.contains(request.toString()) || _overflow) {return {};}
        const auto resourceKeys=resources.keys();
        if(QSet<QString>(resourceKeys.begin(),resourceKeys.end())!=QSet<QString>{"nativeReviewEnabled","activeRequests","taking360","waitingOnSnapshot","projectionTimerActive","projectionImagesBytes"}
                || resources.value("activeRequests").userType()!=QMetaType::Int || resources.value("activeRequests").toInt()<0
                || resources.value("projectionImagesBytes").userType()!=QMetaType::ULongLong) {return {};}
        for(const auto& key:{"nativeReviewEnabled","taking360","waitingOnSnapshot","projectionTimerActive"}) {
            if(resources.value(key).userType()!=QMetaType::Bool) {return {};}
        }
        _seen.insert(request.toString());
        if(operation.toString()=="arm") {
            // First admission only. No reset, replacement, history truncation,
            // request cancellation or product preference mutation is provided.
            if(!_run.isEmpty() || resources.value("activeRequests").toInt()!=0 || resources.value("projectionImagesBytes").toULongLong()!=0
                    || resources.value("taking360").toBool() || resources.value("waitingOnSnapshot").toBool()
                    || resources.value("projectionTimerActive").toBool()) {return {};}
            _run=run.toString();
        } else if(operation.toString()!="read" || _run!=run.toString()) {return {};}
        QVariantList requests;
        for(const auto& row:_requests) {
            const auto original=row.weak.lock();QString state;
            if(original) {
                const auto observed=original->state.load();
                state=observed==SnapshotCaptureRequest::State::Active ? "active"
                    : observed==SnapshotCaptureRequest::State::Cancelled ? "cancelled" : "completed";
            }
            requests.append(QVariantMap{{"birth",row.birth},{"requestId",row.id},{"registeredEpochMs",row.epoch},
                {"alive",bool(original)},{"nativeState",state},{"events",row.events}});
        }
        return {{"snapshotNativeCaptureVersion",1},{"commandId",request},{"runId",_run},
            {"instance",_instance},{"sequence",++_sequence},{"pid",QCoreApplication::applicationPid()},
            {"capturedEpochMs",QDateTime::currentMSecsSinceEpoch()},{"resources",resources},{"requests",requests}};
    }
private:
    struct Original {std::weak_ptr<SnapshotCaptureRequest> weak;QString birth,id;qint64 epoch;QVariantList events;};
    static bool runtime() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    static bool nonce(const QString& value) {return QRegularExpression(QStringLiteral("^[0-9a-f]{32}$")).match(value).hasMatch();}
    static QString birth() {return QUuid::createUuid().toString(QUuid::WithoutBraces);}
    static QString hash(const QString& run,const QString& value) {return QString::fromLatin1(QCryptographicHash::hash(run.toUtf8()+QByteArray(1,'\0')+value.toUtf8(),QCryptographicHash::Sha256).toHex());}
    QMutex _mutex;QString _run;const QString _instance{birth()};qulonglong _sequence{0};bool _overflow{false};
    QSet<QString> _seen;std::vector<Original> _requests;
};
} // namespace overte::e2e
#endif
