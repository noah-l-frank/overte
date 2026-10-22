// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(ANDROID_APP_PICO_INTERFACE)
#include "NormalLoginControls.h"
#include <OffscreenUi.h>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJSValue>
#include <QPointer>
#include <QQuickWindow>
#include <QSet>
#include <QUuid>
#include <cmath>

namespace overte::e2e {
// Original callback -> actual asyncCritical listener/root. No creation, signal
// emission, click handler, strong ownership or product result setter exists.
class NavigationFailureModals {
public:
    static bool command(const QVariantMap& value) {
        // The actual V8 QVariantMap demarshaller carries JavaScript numbers
        // as doubles. Compare the exact JSON number, rejecting bool/string
        // aliases without requiring an impossible native Int carrier.
        const auto object=QJsonObject::fromVariantMap(value);const auto keys=object.keys();
        return QSet<QString>(keys.begin(),keys.end())==QSet<QString>{"schemaVersion","commandId","action","runId"}
            && object.value("schemaVersion")==QJsonValue(1) && object.value("action")==QJsonValue("feature-navigation-modals")
            && object.value("commandId").isString() && identifier(object.value("commandId").toString())
            && object.value("runId").isString() && identifier(object.value("runId").toString());
    }
    void observeRoot(QQuickItem* root,QQuickWindow* window,bool open,const QString& bridge,const QString& generation,
            qint64 sequence,qint64 elapsed) {
        if (!enabled()) { return; }
        const auto now=epoch();if (!now) { return; }
        _root=root;_window=window;_open=open;_bridge=bridge;_generation=generation;_inputSequence=sequence;_uiElapsed=elapsed;_uiEpoch=now;
        _complete=(root && window && root->thread()==QCoreApplication::instance()->thread()
            && window->thread()==root->thread() && root->window()==window) || (!root && !window && !open);
    }
    void record(const QVariantMap& event,ModalDialogListener* listener) {
        if (!enabled() || event.isEmpty()) { return; }
        const auto now=epoch();
        if (!_valid || !now || !identifier(event.value("eventId").toString())
                || !identifier(event.value("runId").toString()) || !event.value("current").toBool()
                || !event.value("contentNotFound").toBool() || _rows.size()>=128
                || !listener || listener->thread()!=QCoreApplication::instance()->thread()) { _valid=false;return; }
        auto root=listener->getDialogItem();
        if (root && root->thread()!=QCoreApplication::instance()->thread()) { _valid=false;return; }
        for (const auto& row:_rows) { if (row.listener==listener || (root && row.root==root)) { _valid=false;return; } }
        Row row;row.id=nonce();row.event=event;row.created=now;row.listener=listener;row.root=root;
        row.profile=component(root).isEmpty() ? "unavailable" : "pico-tablet-critical-v1";
        if (root && root->property("text").userType()==QMetaType::QString) { row.createdText=loginEndpointDigest(root->property("text").toString()); }
        _rows.append(row);
        QObject::connect(listener,&ModalDialogListener::response,QCoreApplication::instance(),[this,id=row.id](const QVariant& result) {
            if (!enabled()) { _valid=false;return; }
            const auto now=epoch();bool okay{false};const auto button=result.toInt(&okay);
            if (!now || !okay || result.userType()==QMetaType::Bool || button<0 || button>QMessageBox::RestoreDefaults) { _valid=false;return; }
            for (auto& current:_rows) {
                if (current.id!=id) { continue; }
                if (current.finished || now<current.created) { _valid=false;return; }
                current.finished=true;current.callback=now;current.button=button;return;
            }
            _valid=false;
        },Qt::DirectConnection);
    }
    QVariantMap snapshot(const QVariantMap& request) {
        if (!enabled() || !_valid || !command(request) || _requests.size()>=4096
                || _requests.contains(request.value("commandId").toString())) { return {}; }
        _requests.insert(request.value("commandId").toString());
        const auto now=epoch();
        if (!now || !_uiEpoch || now<_uiEpoch || now-_uiEpoch>1500) { return {}; }
        QVariantList rows;
        for (int index=0;index<_rows.size();++index) {
            const auto& row=_rows[index];
            if (row.event.value("runId").toString()!=request.value("runId").toString()) { continue; }
            const auto root=row.root.data();QVariant text;
            if (root) {
                if (root->thread()!=QCoreApplication::instance()->thread() || root->property("text").userType()!=QMetaType::QString) { return {}; }
                text=loginEndpointDigest(root->property("text").toString());
            }
            rows.append(QVariantMap{{"modalId",row.id},{"sequence",index+1},{"event",row.event},{"createdEpochMs",row.created},
                {"profile",row.profile},{"createdMessageSha256",row.createdText.isEmpty()?QVariant():QVariant(row.createdText)},
                {"messageSha256",text},{"rootAlive",root!=nullptr},{"listenerAlive",!row.listener.isNull()},
                {"inCurrentTree",within(root,_root)},{"visible",visible(root)},
                {"callbackFinished",row.finished},{"callbackEpochMs",row.callback},
                {"selectedButton",row.finished?QVariant(row.button):QVariant()}});
        }
        return {{"navigationModalVersion",1},{"commandId",request.value("commandId")},{"runId",request.value("runId")},
            {"instance",_instance},{"sequence",static_cast<qulonglong>(++_sequence)},{"processId",QCoreApplication::applicationPid()},
            {"capturedEpochMs",now},{"uiEpochMs",_uiEpoch},{"uiElapsedMs",_uiElapsed},{"uiInputSequence",_inputSequence},
            {"uiBridgeId",_bridge},{"uiGeneration",_generation},{"tabletOpen",_open},{"rootComplete",_complete},{"records",rows}};
    }
    QString controlId(QQuickItem* item) const {
        if (!loginGuiItem(item) || item->metaObject()->indexOfSignal("clicked()")<0) { return {}; }
        const auto value=item->property("dialog");
        auto dialog=value.value<QObject*>();
        if (!dialog && value.userType()==qMetaTypeId<QJSValue>()) { dialog=value.value<QJSValue>().toQObject(); }
        if (item->property("button").userType()!=QMetaType::Int || item->property("button").toInt()!=QMessageBox::Ok) { return {}; }
        for (const auto& row:_rows) {
            if (row.root && dialog==row.root.data() && component(row.root).size()>0
                    && within(item,row.root) && buttonComponent(item)) { return "navigation.error.ok."+row.id; }
        }
        return {};
    }
    void appendControl(QJsonObject& value,QQuickItem* item,const QString& id) const {
        if (!loginGuiItem(item) || controlId(item)!=id) { return; }
        for (const auto& row:_rows) {
            if (id!="navigation.error.ok."+row.id) { continue; }
            const auto root=row.root.data();
            value["modalId"]=row.id;value["eventId"]=row.event.value("eventId").toString();
            value["runId"]=row.event.value("runId").toString();
            value["lookupGeneration"]=QJsonValue::fromVariant(row.event.value("lookupGeneration"));
            value["createdEpochMs"]=static_cast<double>(row.created);
            value["messageSha256"]=root?loginEndpointDigest(root->property("text").toString()):QString();
            value["inputReady"]=_valid && _open && _complete && root && row.listener && !row.finished
                && within(root,_root) && visible(root) && item->isEnabled()
                && root->property("text").userType()==QMetaType::QString
                && root->property("text").toString()==QStringLiteral("There is no address information for that user or place")
                && root->property("title").toString().isEmpty()
                && root->property("buttons").toInt()==QMessageBox::Ok && root->property("icon").toInt()==OffscreenUi::ICON_CRITICAL;
            return;
        }
    }
    QString controlSource(QQuickItem* item,const QString& id) const {
        QJsonObject value;appendControl(value,item,id);
        if (!value.contains("modalId")) { return {}; }
        const auto rect=item->mapRectToScene(QRectF(0,0,item->width(),item->height()));
        if (!std::isfinite(rect.x()) || !std::isfinite(rect.y()) || !std::isfinite(rect.width()) || !std::isfinite(rect.height())) { return {}; }
        value["sceneX"]=rect.x();value["sceneY"]=rect.y();value["width"]=rect.width();value["height"]=rect.height();
        return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
    }
private:
    struct Row {
        QString id,profile,createdText;QVariantMap event;QPointer<ModalDialogListener> listener;QPointer<QQuickItem> root;
        qint64 created{0},callback{0};int button{0};bool finished{false};
    };
    static bool identifier(const QString& text) { return QRegularExpression("\\A[0-9a-f]{32}\\z").match(text).hasMatch(); }
    static QString nonce() { return QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-'); }
    static bool enabled() { return QCoreApplication::instance() && QThread::currentThread()==QCoreApplication::instance()->thread()
        && QCoreApplication::arguments().contains("--testScript"); }
    static QString component(QQuickItem* root) {
        if (!loginGuiItem(root)) { return {}; }int depth{0};
        for (auto context=qmlContext(root);context && ++depth<=128;context=context->parentContext()) {
            const auto url=context->baseUrl();
            if (context->nameForObject(root)=="root" && (url.scheme()=="file" || url.scheme()=="qrc") && url.authority().isEmpty()
                    && !url.hasQuery() && !url.hasFragment() && url.path().endsWith("/dialogs/TabletMessageBox.qml")) { return url.toString(); }
        }
        return {};
    }
    static bool buttonComponent(QQuickItem* item) {
        int depth{0};
        for (auto context=qmlContext(item);context && ++depth<=128;context=context->parentContext()) {
            const auto url=context->baseUrl();
            if ((url.scheme()=="file" || url.scheme()=="qrc") && url.authority().isEmpty() && !url.hasQuery() && !url.hasFragment()
                    && url.path().endsWith("/dialogs/messageDialog/MessageDialogButton.qml")) { return true; }
        }
        return false;
    }
    static bool within(QQuickItem* item,QQuickItem* root) {
        if (!item || !root || item->window()!=root->window()) { return false; }int depth{0};
        for (auto node=item;node && ++depth<=128;node=node->parentItem()) { if (node==root) { return true; } }
        return false;
    }
    static bool visible(QQuickItem* item) {
        if (!item || !item->window() || item->width()<=0 || item->height()<=0) { return false; }int depth{0};
        for (auto node=item;node;node=node->parentItem()) {
            if (++depth>128 || !node->isVisible() || !std::isfinite(node->opacity()) || node->opacity()<=.01) { return false; }
        }
        return true;
    }
    qint64 epoch() {
        const auto now=QDateTime::currentMSecsSinceEpoch(),elapsed=_clock.elapsed();
        if (now<=0 || now<_lastEpoch || elapsed<_lastElapsed) { _valid=false;return 0; }
        _lastEpoch=now;_lastElapsed=elapsed;return now;
    }
    NavigationFailureModals() { _clock.start(); }
    friend NavigationFailureModals& navigationFailureModals();
    QString _instance{nonce()},_bridge,_generation;QList<Row> _rows;QSet<QString> _requests;
    QPointer<QQuickItem> _root;QPointer<QQuickWindow> _window;QElapsedTimer _clock;
    quint64 _sequence{0};qint64 _lastEpoch{0},_lastElapsed{0},_uiEpoch{0},_uiElapsed{0},_inputSequence{0};
    bool _valid{true},_open{false},_complete{false};
};
inline NavigationFailureModals& navigationFailureModals() { static NavigationFailureModals source;return source; }
}
#endif
