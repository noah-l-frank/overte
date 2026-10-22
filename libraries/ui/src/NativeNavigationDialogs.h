// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "OffscreenUi.h"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDataStream>
#include <QDateTime>
#include <QDir>
#include <QElapsedTimer>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QIODevice>
#include <QNetworkReply>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickWindow>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QUuid>
#include <QVector>
#include <cmath>

namespace overte::e2e {
// One UI-library-owned passive source. Weak references do not pin a dialog or
// listener. Normal response/removal/destruction behavior is never changed.
class NativeNavigationDialogs {
public:
    NativeNavigationDialogs() { _clock.start(); }
    static bool enabled() {
        return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
            && QCoreApplication::arguments().contains("--testScript");
    }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static QString component(QQuickItem* root) {
        if (!root) { return {}; }int depth {0};
        for (auto context=qmlContext(root);context && ++depth<=128;context=context->parentContext()) {
            const auto url=context->baseUrl();const auto path=url.path();
            if (context->nameForObject(root)=="root" && (url.scheme()=="file" || url.scheme()=="qrc")
                    && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                    && (path.endsWith("/dialogs/MessageDialog.qml") || path.endsWith("/dialogs/TabletMessageBox.qml"))
                    && (url.scheme()=="qrc" || QDir::cleanPath(url.toLocalFile()).startsWith(
                        QDir::cleanPath(QCoreApplication::applicationDirPath())+"/"))) { return url.toString(); }
        }
        return {};
    }
    static bool visible(QQuickItem* item) {
        if (!item || !item->window() || item->width()<=0 || item->height()<=0) { return false; }
        auto rect=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width()) || !std::isfinite(rect.height())) { return false; }
        rect=rect.intersected(QRectF(0,0,item->window()->width(),item->window()->height()));int depth {0};
        for (auto parent=item;parent && ++depth<=128;parent=parent->parentItem()) {
            if (!parent->isVisible() || !std::isfinite(parent->opacity()) || parent->opacity()<=.01) { return false; }
            if (parent->clip()) { rect=rect.intersected(parent->mapRectToScene(parent->clipRect())); }
        }
        return depth<=128 && !rect.isEmpty();
    }
    void record(ModalDialogListener* listener,QQuickItem* creator,const QVariantMap& error) {
        if (!enabled() || error.isEmpty()) { return; } // No ownership for unrelated errors.
        const auto event=error.value("event").toMap();const auto run=event.value("runId").toString();
        if (!_valid || _entries.size()>=128 || !creator || !creator->inherits("AddressBarDialog")
                || error.value("navigationErrorContextVersion")!=QVariant(1)
                || error.value("processId").toLongLong()!=QCoreApplication::applicationPid()
                || !hex(run) || !hex(error.value("instance").toString()) || !hex(event.value("eventId").toString())
                || event.value("current")!=QVariant(true) || event.value("contentNotFound")!=QVariant(true)
                || event.value("networkError").toInt()!=QNetworkReply::ContentNotFoundError) { _valid=false;return; }
        for (const auto& entry:_entries) {
            if (entry.error.value("instance")==error.value("instance") && entry.error.value("event").toMap().value("eventId")==event.value("eventId")) {
                _valid=false;return; // Never give a second modal the first callback's identity.
            }
        }
        Entry entry;entry.id=nonce();entry.run=run;entry.error=error;entry.listener=listener;entry.creator=creator;
        entry.dialog=listener ? listener->getDialogItem() : nullptr;
        entry.createdDialog=entry.dialog!=nullptr;entry.createdListener=listener!=nullptr;
        entry.source=component(entry.dialog);const auto id=entry.id;
        _entries.append(entry);
        append(id,"created",{{"source","AddressBarDialog.displayAddressNotFoundMessage"},{"error",error},
            {"dialogCreated",entry.createdDialog},{"listenerCreated",entry.createdListener},{"qmlSource",entry.source}});
        if (listener) {
            QObject::connect(listener,&ModalDialogListener::response,[this,id](const QVariant& value) {
                bool known {false};
                for (auto& entry:_entries) {
                    if (entry.id==id) { if (entry.responded) { _valid=false;return; }entry.responded=true;known=true;break; }
                }
                if (!known) { _valid=false;return; }
                QByteArray bytes;QDataStream stream(&bytes,QIODevice::WriteOnly);stream<<value;
                if (!enabled() || stream.status()!=QDataStream::Ok || bytes.size()>1024) { _valid=false;return; }
                const auto kind=!value.isValid() || value.isNull() ? "null" : value.userType()==QMetaType::Int ? "int" : "unsupported";
                append(id,"response",{{"kind",kind},{"value",QString(kind)=="int" ? value : QVariant()},
                    {"valueSha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())}});
            });
            QObject::connect(listener,&QObject::destroyed,[this,id] { append(id,"listener-destroyed",{}); });
        }
        if (entry.dialog) { QObject::connect(entry.dialog,&QObject::destroyed,[this,id] { append(id,"dialog-destroyed",{}); }); }
        QObject::connect(creator,&QObject::destroyed,[this,id] { append(id,"creator-destroyed",{}); });
    }
    QVariantMap control(QQuickItem* item,const QList<QObject*>& activeModals) {
        if (!enabled() || !_valid || !item) { return {}; }
        for (const auto& entry:_entries) {
            auto root=entry.dialog.data();if (!root || !entry.listener || entry.responded || !visible(root) || component(root)!=entry.source || entry.source.isEmpty()) { continue; }
            if (!activeModals.contains(entry.listener.data()) || foreignCount(activeModals,entry.run)!=0) { continue; }
            const bool page=item==root;
            if (!page) {
                auto original=item->property("dialog");
                if (original.userType()==qMetaTypeId<QJSValue>()) { original=original.value<QJSValue>().toVariant(); }
                const auto dialog=original.value<QObject*>();
                if (dialog!=root || item->property("button").userType()!=QMetaType::Int
                        || item->property("button").toInt()!=QMessageBox::Ok || item->metaObject()->indexOfSignal("clicked()")<0) { continue; }
            }
            if (root->property("text").userType()!=QMetaType::QString || root->property("buttons").userType()!=QMetaType::Int
                    || root->property("buttons").toInt()!=QMessageBox::Ok || root->property("icon").userType()!=QMetaType::Int
                    || root->property("icon").toInt()!=OffscreenUi::ICON_CRITICAL
                    || root->property("text").toString()!=notFoundText()) { return {}; }
            const auto error=entry.error.value("event").toMap();
            return {{"id",page ? "navigation.error.page" : "navigation.error.ok"},{"profile","ios-navigation-error-v1"},
                {"dialogId",entry.id},{"runId",entry.run},{"errorInstance",entry.error.value("instance")},
                {"errorEventId",error.value("eventId")},{"lookupGeneration",error.value("lookupGeneration")},
                {"qmlSource",entry.source},{"inputReady",!page && item->isEnabled() && visible(item)}};
        }
        return {};
    }
    QVariantMap snapshot(const QVariantMap& command,const QList<QObject*>& activeModals) {
        if (!enabled() || !_valid || _sequence>=1000000000) { return {}; }
        const auto object=QJsonObject::fromVariantMap(command);const auto keys=object.keys();
        if (QSet<QString>(keys.begin(),keys.end())!=QSet<QString>{"schemaVersion","commandId","action","runId"}
                || object.value("schemaVersion")!=QJsonValue(1) || object.value("action")!=QJsonValue("feature-ios-navigation-dialogs")
                || !QRegularExpression("\\Aios-[a-f0-9]{32}\\z").match(object.value("commandId").toString()).hasMatch()
                || !hex(command.value("runId").toString())) { return {}; }
        const auto before=clock();if (before.isEmpty()) { return {}; }
        QVariantList roots,events;bool complete {true};const auto run=command.value("runId").toString();
        for (const auto& entry:_entries) {
            if (entry.run!=run) { continue; }
            QVariant state;
            if (entry.dialog) {
                auto root=entry.dialog.data();const auto source=component(root);
                if (source.isEmpty() || source!=entry.source || root->thread()!=QThread::currentThread()) { complete=false; }
                QVariantMap original {{"qmlSource",source},{"visible",visible(root)},{"windowPresent",root->window()!=nullptr}};
                for (const auto& field:QList<QByteArray>{"text","buttons","icon","clickedButton"}) {
                    const auto value=root->property(field.constData());
                    if ((field=="text" && (value.userType()!=QMetaType::QString || value.toString().size()>4096))
                            || (field!="text" && value.userType()!=QMetaType::Int)) { complete=false; }
                    original.insert(QString::fromLatin1(field),value);
                }
                state=original;
            }
            roots.append(QVariantMap {{"dialogId",entry.id},{"listenerAlive",!entry.listener.isNull()},
                {"creatorAlive",!entry.creator.isNull()},{"creatorVisible",visible(entry.creator)},{"dialog",state}});
        }
        for (const auto& raw:_events) {
            const auto event=raw.toMap();for (const auto& entry:_entries) {
                if (entry.run==run && entry.id==event.value("dialogId").toString()) { events.append(event);break; }
            }
        }
        const auto after=clock();if (!_valid || after.isEmpty()) { return {}; }
        QVariantMap result {{"iosNavigationDialogsVersion",1},{"requestId",command.value("commandId")},{"runId",run},
            {"instance",_instance},{"processId",static_cast<double>(QCoreApplication::applicationPid())},
            {"sequence",static_cast<double>(++_sequence)},{"clockDomain","native-main-navigation-dialogs"},
            {"clockBefore",before},{"clockAfter",after},{"complete",complete},{"dialogs",roots},{"events",events},
            {"foreignModals",foreignCount(activeModals,run)},
            {"enums",QVariantMap {{"okButton",static_cast<int>(QMessageBox::Ok)},{"criticalIcon",static_cast<int>(OffscreenUi::ICON_CRITICAL)}}}};
        if (QJsonDocument::fromVariant(result).toJson(QJsonDocument::Compact).size()>262144) { _valid=false;return {}; }
        return result;
    }
    static QString notFoundText() { return "There is no address information for that user or place"; }
private:
    struct Entry {
        QString id,run,source;QVariantMap error;
        QPointer<ModalDialogListener> listener;QPointer<QQuickItem> dialog,creator;
        bool createdDialog {false},createdListener {false},responded {false};
    };
    int foreignCount(const QList<QObject*>& activeModals,const QString& run) const {
        int count {0};
        for (auto modal:activeModals) {
            bool owned {false};
            for (const auto& entry:_entries) { if (entry.run==run && entry.listener.data()==modal) { owned=true;break; } }
            if (modal && !owned) { ++count; }
        }
        return count;
    }
    static bool hex(const QString& value) { return QRegularExpression("\\A[a-f0-9]{32}\\z").match(value).hasMatch(); }
    QVariantMap clock() {
        const auto epoch=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (epoch<=0 || epoch<_epoch || elapsed<_elapsed) { _valid=false;return {}; }_epoch=epoch;_elapsed=elapsed;
        return {{"epochMs",static_cast<double>(epoch)},{"monotonicMs",static_cast<double>(elapsed)}};
    }
    void append(const QString& id,const QString& kind,const QVariantMap& details) {
        if (!enabled() || !_valid || _events.size()>=512) { _valid=false;return; }
        const auto now=clock();if (now.isEmpty()) { return; }
        _events.append(QVariantMap {{"sequence",_events.size()+1},{"eventId",nonce()},{"dialogId",id},
            {"kind",kind},{"clock",now},{"details",details}});
    }
    QString _instance {nonce()};QElapsedTimer _clock;QVector<Entry> _entries;QVariantList _events;
    quint64 _sequence {0};qint64 _epoch {0},_elapsed {0};bool _valid {true};
};
} // namespace overte::e2e
#endif
