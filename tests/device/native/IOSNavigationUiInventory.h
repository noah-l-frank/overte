// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS) && defined(Q_OS_IOS)
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QPointer>
#include <QQmlContext>
#include <QQmlEngine>
#include <QQuickItem>
#include <QUuid>
#include <QVector>
#include <QDir>
#include <QVariant>
#include <QUrl>

namespace overte::e2e {
// This inventory is collected before hit testing and modal input suppression.
// Hidden retained roots remain objects; an unavailable tree is never empty.
class IOSNavigationUiInventory {
public:
    static QString source(QQuickItem* root) {
        if (!QCoreApplication::arguments().contains("--testScript")
                || !root || root->objectName()!="AddressBarDialog") { return {}; }
        int depth {0};
        for (auto context=qmlContext(root);context && ++depth<=128;context=context->parentContext()) {
            if (context->nameForObject(root)!="root") { continue; }
            const auto url=context->baseUrl();
            if ((url.scheme()!="file" && url.scheme()!="qrc") || !url.authority().isEmpty()
                    || url.hasQuery() || url.hasFragment()
                    || !url.path().endsWith("/+android_phoneInterface/AddressBarDialog.qml")) { return {}; }
            if (url.scheme()=="file" && !QDir::cleanPath(url.toLocalFile()).startsWith(
                    QDir::cleanPath(QCoreApplication::applicationDirPath())+"/")) { return {}; }
            return url.toString(QUrl::FullyEncoded);
        }
        return {};
    }

    void visit(QQuickItem* item) {
        if (!QCoreApplication::arguments().contains("--testScript") || !_complete || !item) { return; }
        const auto url=source(item);
        if (url.isEmpty()) {
            // The normal field must belong to the selected original component.
            if (item->objectName()=="PhoneAddressField") {
                bool found {false};int depth {0};
                for (auto parent=item->parentItem();parent && ++depth<=128;parent=parent->parentItem()) {
                    if (!source(parent).isEmpty()) { found=true;break; }
                }
                if (!found) { _complete=false; }
            }
            return;
        }
        if (_roots.size()>=16) { _complete=false;return; }
        const auto shown=item->property("shown");
        if (shown.userType()!=QMetaType::Bool) { _complete=false;return; }
        QQuickItem* field {nullptr};
        const auto objects=item->findChildren<QQuickItem*>("PhoneAddressField",Qt::FindChildrenRecursively);
        for (auto candidate:objects) {
            bool original {false};int depth {0};
            for (auto context=qmlContext(candidate);context && ++depth<=128;context=context->parentContext()) {
                if (context->nameForObject(candidate)=="addressField" && context->baseUrl().toString(QUrl::FullyEncoded)==url) {
                    original=true;break;
                }
            }
            if (!original || field) { _complete=false;return; }field=candidate;
        }
        if (!field || field->property("text").userType()!=QMetaType::QString
                || field->property("text").toString().size()>4096) { _complete=false;return; }
        const auto id=identity(item);
        if (id.isEmpty()) { _complete=false;return; }
        _roots.append(QJsonObject{{"rootId",id},{"qmlSource",url},{"shown",shown.toBool()},
            {"visible",item->isVisible()},{"windowPresent",item->window()!=nullptr},
            {"field",QJsonObject{{"text",field->property("text").toString()},
                {"visible",field->isVisible()},{"focused",field->hasActiveFocus()}}}});
    }

    QJsonObject observation(bool treeComplete) const {
        const bool complete=treeComplete && _complete
            && QCoreApplication::arguments().contains("--testScript");
        return {{"iosNavigationUiInventoryVersion",1},{"complete",complete},
            {"roots",complete ? _roots : QJsonArray()}};
    }

private:
    static QString identity(QQuickItem* item) {
        struct Entry {QPointer<QQuickItem> item;QString id;};static QVector<Entry> entries;
        for (int i=entries.size()-1;i>=0;--i) { if (!entries[i].item) { entries.remove(i); } }
        for (const auto& entry:entries) { if (entry.item==item) { return entry.id; } }
        if (entries.size()>=256) { return {}; }
        const auto id=QUuid::createUuid().toString(QUuid::WithoutBraces);
        entries.append(Entry{item,id});return id;
    }
    bool _complete {true};QJsonArray _roots;
};
} // namespace overte::e2e
#endif
