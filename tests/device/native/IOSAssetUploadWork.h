// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include <QCoreApplication>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonObject>
#include <QPointer>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <memory>
#include <mutex>

namespace overte::e2e {
// These are actual client upload/callback holders, not server/oven workers.
// Observations retain weak owners only and never keep an upload alive.
class IOSAssetUploadWork {
public:
    static IOSAssetUploadWork& shared() {static IOSAssetUploadWork value;return value;}
    static bool enabled() {return QCoreApplication::instance() && QCoreApplication::arguments().contains("--testScript");}
    void bundle(const QString& id,const std::shared_ptr<void>& owner,const QStringList& files) {
        if (!enabled()) {return;}
        std::lock_guard<std::mutex> guard(_mutex);
        if (!gui() || _rows.size()>=4096 || id.isEmpty() || !owner || files.isEmpty() || files.size()>32) {_complete=false;return;}
        for (const auto& row:_rows) {if (row.id==id) {_complete=false;return;}}
        Row row;row.id=id;row.kind="bundle";row.weak=owner;row.files=files;row.created=stamp();_rows.append(row);
    }
    void upload(QObject* object,const QStringList& files) {
        if (!enabled()) {return;}
        std::lock_guard<std::mutex> guard(_mutex);
        if (!gui() || !object || object->thread()!=QThread::currentThread() || _rows.size()>=4096 || files.isEmpty()
                || object->property("_overteE2EAssetWorkId").isValid()) {_complete=false;return;}
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);object->setProperty("_overteE2EAssetWorkId",id);
        Row row;row.id=id;row.kind="upload";row.object=object;row.files=files;row.created=stamp();_rows.append(row);
    }
    void terminal(const QString& id) {
        if (!enabled()) {return;}
        std::lock_guard<std::mutex> guard(_mutex);
        auto row=find(id);if (!gui() || !row || row->kind!="bundle" || row->terminal) {_complete=false;return;}
        row->terminal=true;row->ended=stamp();
    }
    class Body {
    public:
        explicit Body(const QString& id) : _id(enabled() ? id : QString()) {if (!_id.isEmpty()) {shared().enter(_id);}}
        explicit Body(QObject* object) {
            if (!enabled()) {return;}
            _id=object ? object->property("_overteE2EAssetWorkId").toString() : QString();
            if (_id.isEmpty()) {shared().incomplete();} else {shared().enter(_id);}
        }
        ~Body() {if (!_id.isEmpty()) {shared().leave(_id);}}
        Body(const Body&)=delete;Body& operator=(const Body&)=delete;
    private:QString _id;
    };
    QJsonObject observation() {
        if (!enabled()) {return {};}
        std::lock_guard<std::mutex> guard(_mutex);if (!gui()) {_complete=false;}
        QJsonArray rows;
        for (auto& row:_rows) {
            const bool alive=row.kind=="bundle" ? !row.weak.expired() : !row.object.isNull();
            if (!alive && row.expired.isEmpty()) {row.expired=stamp();}
            QJsonArray files;for (const auto& file:row.files) {files.append(file);}
            rows.append(QJsonObject{{"id",row.id},{"kind",row.kind},{"files",files},{"created",row.created},
                {"alive",alive},{"terminal",row.terminal},{"ended",row.ended.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(row.ended)},
                {"expired",row.expired.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(row.expired)},
                {"entered",static_cast<double>(row.entered)},{"returned",static_cast<double>(row.returned)},
                {"pendingBodies",static_cast<double>(row.entered-row.returned)}});
        }
        return {{"iosAssetUploadWorkVersion",1},{"available",true},{"complete",_complete},{"instance",_instance},
            {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"sequence",static_cast<double>(++_sequence)},
            {"clock",stamp()},{"jobs",rows}};
    }
    bool drained() {
        const auto source=observation();if (source.value("complete")!=QJsonValue(true)) {return false;}
        for (const auto& value:source.value("jobs").toArray()) {
            const auto row=value.toObject();
            if (row.value("alive").toBool() || row.value("pendingBodies").toDouble()!=0
                    || (row.value("kind")==QJsonValue("bundle") && !row.value("terminal").toBool())) {return false;}
        }
        return true;
    }
private:
    struct Row {
        QString id,kind;QStringList files;std::weak_ptr<void> weak;QPointer<QObject> object;
        QJsonObject created,ended,expired;bool terminal {false};quint64 entered {0},returned {0};
    };
    IOSAssetUploadWork() {_clock.start();}
    static bool gui() {return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread();}
    QJsonObject stamp() const {return {{"epochMs",static_cast<double>(QDateTime::currentMSecsSinceEpoch())},{"monotonicMs",static_cast<double>(_clock.elapsed())}};}
    Row* find(const QString& id) {for (auto& row:_rows) {if (row.id==id) {return &row;}}return nullptr;}
    void incomplete() {std::lock_guard<std::mutex> guard(_mutex);_complete=false;}
    void enter(const QString& id) {
        std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);
        if (!gui() || !row || row->entered>=9007199254740991ULL) {_complete=false;return;}++row->entered;
    }
    void leave(const QString& id) {
        std::lock_guard<std::mutex> guard(_mutex);auto row=find(id);
        if (!gui() || !row || row->returned>=row->entered) {_complete=false;return;}++row->returned;
    }
    std::mutex _mutex;QVector<Row> _rows;QElapsedTimer _clock;bool _complete {true};quint64 _sequence {0};
    QString _instance=QUuid::createUuid().toString(QUuid::WithoutBraces);
};
} // namespace overte::e2e
#endif
