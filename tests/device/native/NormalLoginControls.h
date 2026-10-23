// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once

// Passive normal-login UI identities. No credentials, handler invocation,
// AccountManager mutation or preferred login result is exposed by this reader.
#include <QCoreApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QQuickItem>
#include <QThread>
#include <QDateTime>
#include <QRegularExpression>
#include <QVariantMap>
#include "GenericLoginControls.h"
#include "PrivateAccountOrigin.h"
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QQmlEngine>
#include <QQmlProperty>
#endif

namespace overte::e2e {
struct LoginUiContext {
    bool valid {false}, pending {false}, tokenPresent {false};
    QString instance, endpoint;
    quint64 generation {0};
    static LoginUiContext fromNative(const QVariantMap& account) {
        LoginUiContext result;
#if defined(OVERTE_E2E_FEATURE_TESTS)
        const auto value=account.value("observation").toMap();
        bool okay {false};
        const auto generation=value.value("credentialGeneration").toULongLong(&okay);
        const auto now=QDateTime::currentMSecsSinceEpoch();
        const auto captured=value.value("capturedEpochMs").toLongLong();
        if (okay && value.value("credentialGeneration").userType()==QMetaType::ULongLong
                && generation>0 && generation<=9007199254740991ULL
                && value.value("accountVersion").userType()==QMetaType::Int && value.value("accountVersion").toInt()==1
                && QRegularExpression("\\A[0-9a-f]{32}\\z").match(value.value("instance").toString()).hasMatch()
                && QRegularExpression("\\A[0-9a-f]{64}\\z").match(value.value("endpointSha256").toString()).hasMatch()
                && value.value("endpointPresent").userType()==QMetaType::Bool && value.value("endpointPresent").toBool()
                && value.value("loginPending").userType()==QMetaType::Bool
                && value.value("tokenPresent").userType()==QMetaType::Bool
                && captured>0 && now>=captured && now-captured<=1500) {
            result.valid=true;result.instance=value.value("instance").toString();result.generation=generation;
            result.endpoint=value.value("endpointSha256").toString();result.pending=value.value("loginPending").toBool();
            result.tokenPresent=value.value("tokenPresent").toBool();
        }
#else
        Q_UNUSED(account)
#endif
        return result;
    }
};
inline bool loginGuiItem(QQuickItem* item) {
#if defined(OVERTE_E2E_FEATURE_TESTS)
    return item && qApp && QThread::currentThread() == qApp->thread()
        && item->thread() == qApp->thread() && QCoreApplication::arguments().contains("--testScript");
#else
    Q_UNUSED(item)
    return false;
#endif
}

inline QQuickItem* phoneLoginPage(QQuickItem* item) {
    if (!loginGuiItem(item)) { return nullptr; }
    int depth {0};
    for (auto node = item; node && ++depth <= 128; node = node->parentItem()) {
        if (node->objectName() == "PhoneLoginBody"
                && node->property("domainLogin").userType() == QMetaType::Bool
                && node->property("waiting").userType() == QMetaType::Bool
                && node->property("closing").userType() == QMetaType::Bool) { return node; }
    }
    return nullptr;
}

inline QString loginControlId(QQuickItem* item) {
    if (!loginGuiItem(item)) { return {}; }
    const auto page = phoneLoginPage(item);
    if (page == item) { return "login.page"; }
    if (page) {
        const auto name = item->objectName();
        if (name == "PhoneLoginUsername" && item->property("text").userType() == QMetaType::QString) { return "login.username"; }
        if (name == "PhoneLoginPassword" && item->property("text").userType() == QMetaType::QString
                && item->property("echoMode").toInt() == 2) { return "login.password"; } // QQuickTextInput::Password
        if (item->metaObject()->indexOfSignal("clicked()") >= 0) {
            if (name == "PhoneLoginSubmit") { return "login.submit"; }
            if (name == "PhoneLoginCancel") { return "login.cancel"; }
        }
        return {};
    }
    const auto generic=genericLoginControlId(item);
    if (!generic.isEmpty()) { return generic; }
#if defined(OVERTE_E2E_FEATURE_TESTS)
    // Existing TabletHome login MouseArea; no instrumentation-only UI entry.
    const auto context = QQmlEngine::contextForObject(item);
    if (item->inherits("QQuickMouseArea") && context
            && QQmlProperty(item,"Accessible.description",context).read().toString()
                == QCoreApplication::translate("TabletHome", "Open the login dialog")
            && !QQmlProperty(item,"Accessible.ignored",context).read().toBool()) { return "login.entry"; }
#endif
    return {};
}

inline QString phoneLoginError(QQuickItem* page) {
    if (!loginGuiItem(page)) { return "unavailable"; }
    // Original error label, including its genuinely empty/hidden state. Never
    // read username/password text for an error, nor export unknown raw strings.
    const auto labels = page->findChildren<QQuickItem*>("PhoneLoginError");
    if (labels.size() != 1 || labels.first()->property("text").userType() != QMetaType::QString) { return "unavailable"; }
    const auto error = labels.first()->property("text").toString();
    if (error.isEmpty()) { return "none"; }
    if (error == QCoreApplication::translate("LinkAccountBody", "Username or password incorrect.")) { return "invalid-credentials"; }
    return "other";
}

inline void appendLoginControlObservation(QJsonObject& row, QQuickItem* item, const QString& id, const LoginUiContext& context) {
    if (!loginGuiItem(item)) { return; }
    const auto phone=phoneLoginPage(item);
    const auto generic=genericLoginRoot(item);
    bool inputReady=context.valid && item->isEnabled() && id!="login.page";
    bool domain {false},waiting {false},closing {false};
    QString stage,error,submission;
    if (phone) {
        domain=phone->property("domainLogin").toBool();waiting=phone->property("waiting").toBool();
        closing=phone->property("closing").toBool();error=phoneLoginError(phone);
        stage=waiting ? "pending" : "credentials";submission=context.endpoint;
    } else if (generic) {
        stage=genericLoginStage(generic);error=genericLoginError(generic);
        const auto body=uniqueLoginItem(generic,{"linkAccountBody","loggingInBody"});
        if (!body || body->property("isLoggingInToDomain").userType()!=QMetaType::Bool) {
            row["inputReady"]=false;return; // Missing required metadata cannot become false facts.
        }
        domain=body->property("isLoggingInToDomain").toBool();waiting=stage=="pending";
        // This source has no closing transaction: an actual alive/visible root
        // is observed; destruction/hidden state removes the page. No timer/input
        // ACK is substituted for its actual lifetime.
        closing=!generic->isVisible();
        const auto text=genericSubmissionText(generic);
        submission=stage=="credentials" ? loginEndpointDigest(accountOriginText(text) ? text : QString()) : context.endpoint;
        const bool same=accountOriginText(text) && (loginEndpointDigest(text)==context.endpoint
            || loginEndpointDigest(text+'/')==context.endpoint);
        if (id!="login.server" && id!="login.cancel" && !same) { inputReady=false; }
    } else if (id!="login.entry") { inputReady=false; }
    if (phone || generic) {
        inputReady=inputReady && !domain && !closing && stage!="unavailable"
            && (id=="login.cancel" || (stage=="credentials" && !waiting && !context.pending && !context.tokenPresent));
        if (id=="login.page") {
            row["profile"]=phone ? "phone-login-v1" : "qml-login-v1";
            row["stage"]=stage;row["submitEndpointSha256"]=submission;
            row["domain"]=domain;row["waiting"]=waiting;row["closing"]=closing;row["error"]=error;
            row["accountInstance"]=context.instance;
            row["credentialGeneration"]=static_cast<double>(context.generation);
            row["endpointSha256"]=context.endpoint;
            row["nativePending"]=context.pending;row["tokenPresent"]=context.tokenPresent;
        }
    } else { inputReady=inputReady && !context.tokenPresent; }
    row["inputReady"]=inputReady;
}

inline QString loginControlSource(QQuickItem* item, const QString& id, const LoginUiContext& context) {
    QJsonObject value;
    appendLoginControlObservation(value,item,id,context);
    const auto page=phoneLoginPage(item) ? phoneLoginPage(item) : genericLoginRoot(item);
    if (page) {
        QJsonObject state;appendLoginControlObservation(state,page,"login.page",context);
        value["page"]=state;
    }
    value["accountInstance"]=context.instance;value["endpointSha256"]=context.endpoint;
    value["credentialGeneration"]=static_cast<double>(context.generation);
    value["nativePending"]=context.pending;value["tokenPresent"]=context.tokenPresent;
    // Secret field contents, lengths and hashes are intentionally absent.
    return QString::fromUtf8(QJsonDocument(value).toJson(QJsonDocument::Compact));
}

inline bool validLoginText(const QString& text) {
    if (text.isEmpty() || text.size() > 4096) { return false; }
    for (const auto character : text) {
        // Controlled fixture credentials are printable ASCII; reject embedded
        // native key codes and all non-reviewed text instead of interpreting it.
        if (character.unicode() < 0x20 || character.unicode() > 0x7e) { return false; }
    }
    return true;
}
} // namespace overte::e2e
