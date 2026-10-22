// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#include <QtCore/qglobal.h>
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include "IOSTabletSourcesObservation.h"
#include <QJsonArray>

namespace overte::e2e::tablet_app_buttons {
// API return, model membership, QML control and zeroing weak death are distinct
// observations. No observer retains a proxy, model, tablet or visual control.
struct Object { QString id;QPointer<QObject> pointer;QVariantMap born,expired; };
struct Button {
    QString id,uuid,semantic,run,nonce,verb,fixture,model,tablet,root;
    QPointer<QObject> proxy;QPointer<QQuickItem> rootItem;
    QVariantMap caller,inserted,returned,removed,expired;QVariantList clicks;
};
struct Control { QString id,button,root;QPointer<QQuickItem> item;QVariantMap born,expired; };
struct State {
    const QString instance{tablet_sources::id()};QElapsedTimer timer;qint64 epoch{0},mono{0};quint64 sequence{0};bool complete{true};
    QList<std::shared_ptr<Object>> models,tablets;QList<std::shared_ptr<Button>> buttons;QList<std::shared_ptr<Control>> controls;
    State() {timer.start();}
};
inline State& state() {static State actual;return actual;}
inline bool active() {return tablet_sources::enabled() && tablet_sources::mainThread();}
inline QVariantMap clock(State& actual) {
    const auto epoch=QDateTime::currentMSecsSinceEpoch(),mono=actual.timer.elapsed();
    if (epoch<=0 || mono<0 || epoch<actual.epoch || mono<actual.mono || (actual.epoch && qAbs(epoch-actual.epoch-mono+actual.mono)>250)) {actual.complete=false;}
    actual.epoch=epoch;actual.mono=mono;return {{"epochMs",epoch},{"monotonicMs",mono}};
}
inline QRegularExpressionMatch semantic(const QString& text) {
    static const QRegularExpression expression("\\Atablet-web-app\\.([0-9a-f]{32})\\.([0-9a-f]{32})\\.(open|inline|return)\\z");return expression.match(text);
}
inline std::shared_ptr<Object> object(QList<std::shared_ptr<Object>>& rows,QObject* pointer) {
    if (!pointer) {return {};}
    for (const auto& row:rows) {if (row->pointer==pointer) {return row;}}
    auto& actual=state();if (rows.size()>=128) {actual.complete=false;return {};}
    auto row=std::make_shared<Object>();row->id=tablet_sources::id();row->pointer=pointer;row->born=clock(actual);rows.push_back(row);return row;
}
inline std::shared_ptr<Button> find(QObject* proxy) {
    if (!proxy) {return {};}
    for (const auto& row:state().buttons) {if (row->proxy==proxy) {return row;}}return {};
}
inline QString inserted(QObject* proxy,QObject* model,const QVariantMap& properties,const QVariantMap& caller) noexcept {
    if (!active()) {return {};}
    try {
        const auto text=properties.value("semanticId").toString();const auto match=semantic(text);if (!match.hasMatch()) {return {};}
        auto& actual=state();const auto fixture=properties.value("fixtureUrl").toString();
        const QVariantMap query{{"schemaVersion",1},{"action","feature-ios-tablet-sources"},{"commandId","ios-00000000000000000000000000000000"},
            {"runId",match.captured(1)},{"fixtureUrl",fixture}};
        if (!tablet_sources::command(query)) {actual.complete=false;return {};}
        const auto owner=object(actual.models,model);
        const auto uuid=properties.value("uuid").toUuid().toString(QUuid::WithoutBraces);
        if (!proxy || !owner || uuid==QUuid().toString(QUuid::WithoutBraces) || actual.buttons.size()>=384 || find(proxy)) {actual.complete=false;return {};}
        auto row=std::make_shared<Button>();row->id=tablet_sources::id();row->proxy=proxy;row->model=owner->id;row->uuid=uuid;row->semantic=text;
        row->fixture=fixture;row->run=match.captured(1);row->nonce=match.captured(2);row->verb=match.captured(3);row->caller=caller;row->inserted=clock(actual);
        actual.buttons.push_back(row);return row->id;
    } catch (...) {state().complete=false;return {};}
}
inline void returned(QObject* proxy,QObject* tablet,QQuickItem* root,const QString& rootBirth) noexcept {
    if (!active()) {return;}
    try {
        auto row=find(proxy);if (!row) {return;}auto& actual=state();auto owner=object(actual.tablets,tablet);
        if (!owner || !row->returned.isEmpty() || !root || rootBirth.isEmpty()) {actual.complete=false;return;}
        row->tablet=owner->id;row->root=rootBirth;row->rootItem=root;row->returned=clock(actual);
    } catch (...) {state().complete=false;}
}
inline QString removing(QObject* proxy) noexcept {
    if (!active()) {return {};}try {const auto row=find(proxy);return row ? row->id : QString();}catch (...) {state().complete=false;return {};}
}
inline void removed(const QString& id) noexcept {
    if (!active() || id.isEmpty()) {return;}
    try {auto& actual=state();for (const auto& row:actual.buttons) {if (row->id==id) {
        if (!row->removed.isEmpty()) {actual.complete=false;return;}row->removed=clock(actual);return;
    }}actual.complete=false;}catch (...) {state().complete=false;}
}
inline void clicked(const QString& id) noexcept {
    if (!active() || id.isEmpty()) {return;}
    try {auto& actual=state();for (const auto& row:actual.buttons) {if (row->id==id) {
        if (row->clicks.size()>=512 || !row->proxy || !row->removed.isEmpty() || row->returned.isEmpty()) {actual.complete=false;return;}
        row->clicks.push_back(clock(actual));return;
    }}actual.complete=false;}catch (...) {state().complete=false;}
}
inline QVariantMap control(QQuickItem* item) noexcept {
    if (!active() || !item) {return {};}
    try {
        const auto text=item->property("semanticId").toString();if (!semantic(text).hasMatch()) {return {};}
        const auto uuid=item->property("uuid").toUuid().toString(QUuid::WithoutBraces);auto& actual=state();std::shared_ptr<Button> button;
        for (const auto& row:actual.buttons) {if (row->semantic==text && row->uuid==uuid && row->proxy && row->removed.isEmpty()) {
            if (button) {actual.complete=false;return {};}button=row;
        }}
        if (!button || button->returned.isEmpty() || !button->rootItem || !button->rootItem->isAncestorOf(item)
                || item->metaObject()->indexOfSignal("clicked()")<0 || button->caller.isEmpty()) {return {};}
        std::shared_ptr<Control> found;
        for (const auto& row:actual.controls) {if (row->item==item) {found=row;break;}}
        if (found && (found->button!=button->id || found->root!=button->root)) {actual.complete=false;return {};}
        if (!found) {
            if (actual.controls.size()>=1024) {actual.complete=false;return {};}
            found=std::make_shared<Control>();found->id=tablet_sources::id();found->button=button->id;found->root=button->root;found->item=item;found->born=clock(actual);actual.controls.push_back(found);
        }
        return {{"instance",actual.instance},{"button",button->id},{"control",found->id},{"root",button->root},
            {"rootInstance",tablet_sources::state().instance},{"semanticId",text},{"uuid",button->uuid},
            {"featureRun",button->run},{"fixtureUrl",button->fixture},{"nonce",button->nonce},{"verb",button->verb}};
    }catch (...) {state().complete=false;return {};}
}
inline QString controlId(QQuickItem* item) {const auto source=control(item);return source.isEmpty() ? QString() : "tablet-web-app."+source.value("verb").toString();}
inline QString controlSource(QQuickItem* item) {
    const auto source=control(item);return source.isEmpty() ? QString() : QString::fromUtf8(QJsonDocument(QJsonObject::fromVariantMap(source)).toJson(QJsonDocument::Compact));
}
inline QVariantMap observe(const QVariantMap& query) {
    auto canonical=query;canonical["action"]="feature-ios-tablet-sources";
    if (!active() || QJsonObject::fromVariantMap(query).value("action")!=QJsonValue("feature-ios-tablet-app-buttons") || !tablet_sources::command(canonical)) {return {};}
    auto& actual=state();const auto before=clock(actual);QVariantList buttons,controls,models,tablets;QSet<QString> ids,modelIds,tabletIds;
    for (const auto& row:actual.buttons) {
        if (!row->proxy && row->expired.isEmpty()) {row->expired=clock(actual);}
        if (row->run!=query.value("runId").toString() || row->fixture!=query.value("fixtureUrl").toString()) {continue;}ids.insert(row->id);modelIds.insert(row->model);tabletIds.insert(row->tablet);
        buttons.push_back(QVariantMap{{"id",row->id},{"uuid",row->uuid},{"semanticId",row->semantic},{"fixtureUrl",row->fixture},{"caller",row->caller.isEmpty()?QVariant():QVariant(row->caller)},
            {"model",row->model},{"tablet",row->tablet.isEmpty()?QVariant():QVariant(row->tablet)},
            {"root",row->root.isEmpty()?QVariant():QVariant(row->root)},{"inserted",row->inserted},
            {"returned",row->returned.isEmpty()?QVariant():QVariant(row->returned)},{"removed",row->removed.isEmpty()?QVariant():QVariant(row->removed)},
            {"expired",row->expired.isEmpty()?QVariant():QVariant(row->expired)},{"alive",!row->proxy.isNull()},{"clicks",row->clicks}});
    }
    for (const auto& row:actual.controls) {
        if (!row->item && row->expired.isEmpty()) {row->expired=clock(actual);}
        if (ids.contains(row->button)) {controls.push_back(QVariantMap{{"id",row->id},{"button",row->button},{"root",row->root},{"born",row->born},
            {"expired",row->expired.isEmpty()?QVariant():QVariant(row->expired)},{"alive",!row->item.isNull()}});}
    }
    auto objects=[&](const QList<std::shared_ptr<Object>>& originals,const QSet<QString>& selected,QVariantList& result) {
        for (const auto& row:originals) {
            if (!row->pointer && row->expired.isEmpty()) {row->expired=clock(actual);}
            if (selected.contains(row->id)) {result.push_back(QVariantMap{{"id",row->id},{"born",row->born},{"expired",row->expired.isEmpty()?QVariant():QVariant(row->expired)},{"alive",!row->pointer.isNull()}});}
        }
    };objects(actual.models,modelIds,models);objects(actual.tablets,tabletIds,tablets);
    if (actual.sequence>=9007199254740991ULL) {actual.complete=false;return {};}
    QVariantMap result{{"iosTabletAppButtonsVersion",1},{"commandId",query.value("commandId")},{"runId",query.value("runId")},{"fixtureUrl",query.value("fixtureUrl")},
        {"instance",actual.instance},{"sequence",static_cast<qulonglong>(++actual.sequence)},{"processId",QCoreApplication::applicationPid()},
        {"clockDomain","native-main-ios-tablet-app-buttons"},{"clockBefore",before},{"clockAfter",clock(actual)},{"complete",actual.complete},
        {"rootInstance",tablet_sources::state().instance},{"models",models},{"tablets",tablets},{"buttons",buttons},{"controls",controls}};
    if (QJsonDocument(QJsonObject::fromVariantMap(result)).toJson(QJsonDocument::Compact).size()>2097152) {actual.complete=false;return {};}return result;
}
} // namespace overte::e2e::tablet_app_buttons
#endif
