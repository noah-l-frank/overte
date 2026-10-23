// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
#pragma once
#if defined(OVERTE_E2E_FEATURE_TESTS)
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QVariant>
#include <functional>
#include <cmath>

namespace overte::e2e {
struct PendingCommitProvider {
    std::function<QVariantMap(const QVariantMap&)> request;
    explicit operator bool() const { return bool(request); }
    QVariantMap operator()(const QVariantMap& command) const { return request ? request(command) : QVariantMap(); }
};
inline const char* pendingCommitProviderProperty() { return "_overteE2EOriginalPendingCommitOwnerV1"; }
inline bool pendingCommitIdentifier(const QString& value, bool request = false) {
    return QRegularExpression(request ? "\\A(?:ios-)?[0-9a-f]{32}\\z" : "\\A[0-9a-f]{32}\\z").match(value).hasMatch();
}
inline bool pendingCommitInteger(const QJsonValue& value, double minimum = 1) {
    return value.isDouble() && std::isfinite(value.toDouble()) && value.toDouble() >= minimum
        && value.toDouble() <= 1000000000 && std::floor(value.toDouble()) == value.toDouble();
}
inline bool pendingCommitOwnerCommand(const QVariantMap& command) {
    const auto value = QJsonObject::fromVariantMap(command);
    const auto keys = value.keys();
    const auto operation = value.value("operation").toString();
    const bool input = operation == "focus" || operation == "type" || operation == "hold" || operation == "attempt";
    if (!input && operation != "observe" && operation != "release") { return false; }
    QSet<QString> fields{"schemaVersion", "commandId", "action", "operation", "runId", "eventId"};
    if (operation != "observe") { fields.unite({"ownerInstance", "intentSequence"}); }
    if (input) { fields.unite({"fieldToken", "observationSequence"}); }
    if (QSet<QString>(keys.begin(), keys.end()) != fields || value.value("schemaVersion") != QJsonValue(1)
            || value.value("action") != QJsonValue("feature-pending-commit-owner")
            || !value.value("commandId").isString() || !pendingCommitIdentifier(value.value("commandId").toString(), true)
            || !value.value("runId").isString() || !pendingCommitIdentifier(value.value("runId").toString())
            || !value.value("eventId").isString()) { return false; }
    const auto event = value.value("eventId").toString();
    if ((operation == "attempt" || operation == "release") ? !pendingCommitIdentifier(event)
            : operation == "observe" ? (!event.isEmpty() && !pendingCommitIdentifier(event)) : !event.isEmpty()) { return false; }
    if (operation != "observe" && (!value.value("ownerInstance").isString()
            || !pendingCommitIdentifier(value.value("ownerInstance").toString())
            || !pendingCommitInteger(value.value("intentSequence")))) { return false; }
    return !input || (value.value("fieldToken").isString() && pendingCommitIdentifier(value.value("fieldToken").toString())
        && pendingCommitInteger(value.value("observationSequence")));
}
} // namespace overte::e2e
Q_DECLARE_METATYPE(overte::e2e::PendingCommitProvider)
#endif
