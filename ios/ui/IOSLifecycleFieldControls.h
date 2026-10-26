// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS) && defined(OVERTE_IOS_E2E_TEST_BUILD)
#include "../../tests/device/native/NormalControlUi.h"
#include <PathUtils.h>
#include <QCryptographicHash>
#include <QDateTime>
#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QDir>
#include <QJSValue>
#include <QRegularExpression>
#include <QThread>
#include <QUuid>
#include <QQmlContext>
#include <QtQml/qqml.h>

namespace overte::ios::lifecycle_fields {
// Separate passive editor identity inventory. Existing Create/Chat/Script
// control rows and their literal text grammars are not widened by this source.
struct Object {QPointer<QObject> object;QString id,kind;QJsonObject born,expired;};
struct Field {
    QPointer<QQuickItem> field,root,loader;QPointer<QQmlContext> context;QPointer<QQuickWindow> window;
    QJsonObject identity;
};
struct State {
    QElapsedTimer timer;QString instance=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    QList<Object> objects;QList<Field> fields;QList<QPointer<QQuickItem>> loaders;
    quint64 sequence=0;qint64 epoch=0,monotonic=0;bool complete=true;
    State() {timer.start();}
};
inline State& state() {static State value;return value;}
inline bool enabled() {
    return qApp && QThread::currentThread()==qApp->thread()
        && QCoreApplication::arguments().contains("--testScript");
}
inline QJsonObject clock() {
    auto& s=state();const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=s.timer.elapsed();
    if (epoch<=0 || epoch<s.epoch || mono<s.monotonic || (s.epoch && qAbs(epoch-s.epoch-mono+s.monotonic)>250)) {s.complete=false;}
    s.epoch=epoch;s.monotonic=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline QString id(QObject* object,const QString& kind) {
    if (!object) {return {};}
    auto& s=state();for (const auto& row:s.objects) {
        if (row.object==object) {if (row.kind!=kind) {s.complete=false;}return row.id;}
    }
    if (s.objects.size()>=80) {s.complete=false;return {};}
    // First observation only; actual loader advancement is required to prove a new page.
    Object row;row.object=object;row.kind=kind;row.born=clock();row.id=QUuid::createUuid().toString(QUuid::WithoutBraces).remove('-');
    s.objects.append(row);return row.id;
}
inline QUrl scriptsSource(const QString& relative) {
    const auto directory=PathUtils::defaultScriptsLocation();
    return directory.isLocalFile() ? QUrl::fromLocalFile(QDir(directory.toLocalFile()).filePath(relative)) : QUrl();
}
inline QString role(QQuickItem* field,QQmlContext** original) {
    if (!enabled() || !field || field->thread()!=qApp->thread()) {return {};}
    const auto name=field->objectName();QString expected,qmlId;QUrl source;
    if (name=="NativeCreateText") {expected="create";qmlId="newText";source=scriptsSource("system/create/qml/NativeCreate.qml");}
    else if (name=="chatMessageInput") {expected="chat";qmlId="textArea";source=scriptsSource("communityScripts/armored-chat/armored_chat.qml");}
    else if (name=="scriptFilter") {expected="scripts";qmlId="filter";source=PathUtils::qmlUrl("hifi/dialogs/TabletRunningScripts.qml");}
    else {return {};}
    if (source.isEmpty() || !(field->inherits("QQuickTextInput") || field->inherits("QQuickTextEdit"))) {return {};}
    int depth=0;for (auto context=qmlContext(field);context && ++depth<=128;context=context->parentContext()) {
        if (context->thread()!=qApp->thread()) {return {};}
        if (context->baseUrl()==source && context->nameForObject(field)==qmlId) {*original=context;return expected;}
    }
    return {};
}
inline QObject* objectValue(const QVariant& value) {
    return value.userType()==qMetaTypeId<QJSValue>() ? value.value<QJSValue>().toQObject() : value.value<QObject*>();
}
inline bool noticeLoader(QQuickItem* item) {
    if (!enabled() || !item || item->objectName()!="loader" || item->thread()!=qApp->thread()) {return false;}
    const auto context=qmlContext(item);const auto generation=item->property("qmlLoadGeneration");
    if (!context || context->baseUrl()!=PathUtils::qmlUrl("hifi/tablet/TabletPageLoader.qml")
            || generation.userType()!=QMetaType::Int || generation.toInt()<0) {return false;}
    auto& s=state();for (const auto& old:s.loaders) {if (old==item) {return true;}}
    if (s.loaders.size()>=8) {s.complete=false;return false;}
    id(item,"loader");s.loaders.append(item);return true;
}
inline bool controlled(const QString& value,const QString& editor) {
    if (value.isEmpty()) {return true;}
    const auto prefix=editor=="create" ? QStringLiteral("Overte ä Ω 東京 ") : editor=="chat" ? QStringLiteral("reply-") : QStringLiteral("retry-");
    return value.size()<=128 && QRegularExpression("\\A"+QRegularExpression::escape(prefix)+"[a-f0-9]{32}\\z").match(value).hasMatch();
}
inline QJsonObject current(const Field& row) {
    if (!row.field || !row.root || !row.context || !row.window || !row.loader) {return {};}
    QQmlContext* context=nullptr;const auto editor=role(row.field,&context);
    if (editor!=row.identity.value("editor").toString() || context!=row.context || row.field->window()!=row.window) {return {};}
    const auto generation=row.loader->property("qmlLoadGeneration");
    const auto text=row.field->property("text"),readOnly=row.field->property("readOnly");
    if (generation.userType()!=QMetaType::Int || generation.toInt()<1 || text.userType()!=QMetaType::QString
            || readOnly.userType()!=QMetaType::Bool) {return {};}
    const bool attached=objectValue(row.loader->property("item"))==row.root && generation.toInt()==row.identity.value("loadGeneration").toInt();
    const auto frame=overte::e2e::NormalControlUi::visibleRect(row.field,row.window);
    const bool textOwned=controlled(text.toString(),editor);
    const auto sha=text.toString().size()<=4096 ? QString::fromLatin1(QCryptographicHash::hash(text.toString().toUtf8(),QCryptographicHash::Sha256).toHex()) : QString();
    return {{"identity",row.identity},{"attached",attached},{"visible",!frame.isEmpty()},
        {"focused",row.field->hasActiveFocus()},{"enabled",row.field->isEnabled()},{"readOnly",readOnly.toBool()},
        {"textOwned",textOwned},{"text",textOwned ? QJsonValue(text.toString()) : QJsonValue(QJsonValue::Null)},
        {"textSha256",sha.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(sha)},
        {"textCodeUnits",text.toString().size()}};
}
inline QJsonObject notice(QQuickItem* field) {
    QQmlContext* context=nullptr;const auto editor=role(field,&context);if (editor.isEmpty()) {return {};}
    QQuickItem* root=nullptr;int depth=0;
    for (auto item=field;item && ++depth<=128;item=item->parentItem()) {
        if (context->nameForObject(item)=="root") {root=item;break;}
    }
    if (!root || !field->window()) {return {};}
    QQuickItem* loader=nullptr;depth=0;
    for (auto item=root->parentItem();item && ++depth<=128;item=item->parentItem()) {
        const auto scope=qmlContext(item);
        if (item->objectName()=="loader" && scope && scope->baseUrl()==PathUtils::qmlUrl("hifi/tablet/TabletPageLoader.qml")
                && objectValue(item->property("item"))==root) {loader=item;break;}
    }
    if (!loader || !noticeLoader(loader)) {return {};}
    const auto generation=loader->property("qmlLoadGeneration");
    if (generation.userType()!=QMetaType::Int || generation.toInt()<1) {return {};}
    const auto source=context->baseUrl().toString(QUrl::FullyEncoded);
    QJsonObject identity{{"editor",editor},{"componentSource",source},{"fieldName",field->objectName()},
        {"fieldId",id(field,"field")},{"rootId",id(root,"root")},{"contextId",id(context,"context")},
        {"windowId",id(field->window(),"window")},{"loaderId",id(loader,"loader")},{"loadGeneration",generation.toInt()}};
    auto& s=state();for (const auto& row:s.fields) {if (row.identity==identity) {return current(row);}}
    if (s.fields.size()>=16) {s.complete=false;return {};}
    Field row;row.field=field;row.root=root;row.context=context;row.window=field->window();row.loader=loader;row.identity=identity;
    s.fields.append(row);return current(row);
}
inline QString controlId(QQuickItem* field) {
    if (!field || (field->objectName()!="NativeCreateText" && field->objectName()!="scriptFilter")) {return {};}
    const auto actual=notice(field);if (actual.isEmpty()) {return {};}
    return actual.value("identity").toObject().value("editor")==QJsonValue("create") ? "lifecycle.create.text" : "lifecycle.scripts.filter";
}
inline QString controlSource(QQuickItem* field) {
    const auto actual=notice(field);return actual.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(actual).toJson(QJsonDocument::Compact));
}
inline QJsonObject inventory() {
    if (!enabled()) {return {};}
    auto& s=state();const auto before=clock();QJsonArray fields,objects,loaders;
    for (const auto& loader:s.loaders) {
        if (!loader) {continue;}
        const auto generation=loader->property("qmlLoadGeneration"),source=loader->property("source");
        const auto root=qobject_cast<QQuickItem*>(objectValue(loader->property("item")));
        if (generation.userType()!=QMetaType::Int || generation.toInt()<0 || source.userType()!=QMetaType::QString
                || source.toString().size()>4096) {s.complete=false;continue;}
        const auto digest=QString::fromLatin1(QCryptographicHash::hash(source.toString().toUtf8(),QCryptographicHash::Sha256).toHex());
        const auto window=loader->window();
        loaders.append(QJsonObject{{"loaderId",id(loader,"loader")},{"loadGeneration",generation.toInt()},
            {"rootId",root ? QJsonValue(id(root,"root")) : QJsonValue(QJsonValue::Null)},
            {"windowId",window ? QJsonValue(id(window,"window")) : QJsonValue(QJsonValue::Null)},
            {"sourceSha256",digest}});
    }
    for (const auto& row:s.fields) {
        const auto actual=current(row);
        fields.append(QJsonObject{{"identity",row.identity},{"current",actual.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(actual)}});
    }
    for (auto& row:s.objects) {
        const bool alive=bool(row.object);if (!alive && row.expired.isEmpty()) {row.expired=clock();}
        objects.append(QJsonObject{{"id",row.id},{"kind",row.kind},{"born",row.born},{"alive",alive},
            {"expired",row.expired.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(row.expired)}});
    }
    return {{"iosLifecycleFieldsVersion",1},{"instance",s.instance},{"sequence",static_cast<double>(++s.sequence)},
        {"processId",static_cast<double>(QCoreApplication::applicationPid())},{"complete",s.complete},
        {"clockBefore",before},{"clockAfter",clock()},{"fields",fields},{"objects",objects},{"loaders",loaders}};
}
}
#endif
