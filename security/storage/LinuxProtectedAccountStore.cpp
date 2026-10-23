// SPDX-License-Identifier: Apache-2.0
#include <QString>
#include <QByteArray>
#include <QMap>
#include <QVariant>
#include <QtDBus/QDBusArgument>
#include <QtDBus/QDBusConnection>
#include <QtDBus/QDBusError>
#include <QtDBus/QDBusMessage>
#include <QtDBus/QDBusMetaType>
#include <QtDBus/QDBusObjectPath>
#include <QtDBus/QDBusVariant>

#include "LinuxProtectedAccountStore.h"

namespace overte { namespace security { namespace linux_detail {
struct Secret {
    QDBusObjectPath session;
    QByteArray parameters;
    QByteArray value;
    QString contentType;
    ~Secret() { value.fill('\0'); }
};
QDBusArgument& operator<<(QDBusArgument& wire, const Secret& secret) {
    wire.beginStructure();
    wire << secret.session << secret.parameters << secret.value << secret.contentType;
    wire.endStructure();
    return wire;
}
const QDBusArgument& operator>>(const QDBusArgument& wire, Secret& secret) {
    wire.beginStructure();
    wire >> secret.session >> secret.parameters >> secret.value >> secret.contentType;
    wire.endStructure();
    return wire;
}
}}}
Q_DECLARE_METATYPE(overte::security::linux_detail::Secret)

namespace overte { namespace security {
namespace {
using Paths = QList<QDBusObjectPath>;
using Attributes = QMap<QString, QString>;
using linux_detail::Secret;
const QString SERVICE = QStringLiteral("org.freedesktop.secrets");
const QString ROOT = QStringLiteral("/org/freedesktop/secrets");
const QString SERVICE_INTERFACE = QStringLiteral("org.freedesktop.Secret.Service");
const QString COLLECTION_INTERFACE = QStringLiteral("org.freedesktop.Secret.Collection");
const QString ITEM_INTERFACE = QStringLiteral("org.freedesktop.Secret.Item");
const QString PROPERTIES_INTERFACE = QStringLiteral("org.freedesktop.DBus.Properties");
const QString CONTENT_TYPE = QStringLiteral("application/octet-stream");
const Attributes ATTRIBUTES {
    { QStringLiteral("application"), QStringLiteral("org.overte.interface") },
    { QStringLiteral("record"), QStringLiteral("account-map-v1") }
};

QDBusMessage call(const QString& path, const QString& interface, const QString& method,
                  const QVariantList& arguments = {}) {
    auto message = QDBusMessage::createMethodCall(SERVICE, path, interface, method);
    message.setArguments(arguments);
    // Never wait for interactive keyring prompts from an AccountManager call.
    return QDBusConnection::sessionBus().call(message, QDBus::Block, 3000);
}
StoreResult result(const QDBusMessage& reply) {
    if (reply.type() == QDBusMessage::ReplyMessage) { return StoreResult::Ok; }
    const auto name = reply.errorName();
    if (name == QStringLiteral("org.freedesktop.Secret.Error.IsLocked")) { return StoreResult::Locked; }
    if (name == QStringLiteral("org.freedesktop.DBus.Error.ServiceUnknown")
            || name == QStringLiteral("org.freedesktop.DBus.Error.NameHasNoOwner")
            || name == QStringLiteral("org.freedesktop.DBus.Error.Disconnected")
            || name == QStringLiteral("org.freedesktop.DBus.Error.NoServer")) { return StoreResult::Unavailable; }
    return StoreResult::IoError;
}
struct Found {
    StoreResult status { StoreResult::Unavailable };
    QDBusObjectPath collection;
    Paths unlocked, locked;
};
Found find() {
    Found found;
    if (!QDBusConnection::sessionBus().isConnected()) { return found; }
    auto alias = call(ROOT, SERVICE_INTERFACE, QStringLiteral("ReadAlias"), { QStringLiteral("default") });
    found.status = result(alias);
    if (found.status != StoreResult::Ok) { return found; }
    if (alias.arguments().size() != 1 || alias.signature() != QStringLiteral("o")) {
        found.status = StoreResult::Corrupt; return found;
    }
    found.collection = qdbus_cast<QDBusObjectPath>(alias.arguments().front());
    if (found.collection.path() == QStringLiteral("/")) {
        found.status = StoreResult::Unavailable; return found;
    }
    auto state = call(found.collection.path(), PROPERTIES_INTERFACE, QStringLiteral("Get"),
                      { COLLECTION_INTERFACE, QStringLiteral("Locked") });
    found.status = result(state);
    if (found.status != StoreResult::Ok) { return found; }
    if (state.arguments().size() != 1 || state.signature() != QStringLiteral("v")) {
        found.status = StoreResult::Corrupt; return found;
    }
    const auto locked = qvariant_cast<QDBusVariant>(state.arguments().front()).variant();
    if (locked.userType() != QMetaType::Bool) { found.status = StoreResult::Corrupt; return found; }
    // A locked collection may hide its item list. Never reinterpret that as
    // Absent and migrate legacy credentials into an inaccessible store.
    if (locked.toBool()) { found.status = StoreResult::Locked; return found; }
    auto search = call(ROOT, SERVICE_INTERFACE, QStringLiteral("SearchItems"),
                       { QVariant::fromValue(ATTRIBUTES) });
    found.status = result(search);
    if (found.status != StoreResult::Ok) { return found; }
    if (search.arguments().size() != 2 || search.signature() != QStringLiteral("aoao")) {
        found.status = StoreResult::Corrupt; return found;
    }
    found.unlocked = qdbus_cast<Paths>(search.arguments().at(0));
    found.locked = qdbus_cast<Paths>(search.arguments().at(1));
    if (found.unlocked.size() + found.locked.size() > 256) { found.status = StoreResult::Corrupt; }
    return found;
}
class Session {
public:
    StoreResult open() {
        auto reply = call(ROOT, SERVICE_INTERFACE, QStringLiteral("OpenSession"),
                          { QStringLiteral("plain"), QVariant::fromValue(QDBusVariant(QString())) });
        auto status = result(reply);
        if (status != StoreResult::Ok) { return status; }
        if (reply.arguments().size() != 2 || reply.signature() != QStringLiteral("vo")) { return StoreResult::Corrupt; }
        path = qdbus_cast<QDBusObjectPath>(reply.arguments().at(1));
        return path.path() == QStringLiteral("/") ? StoreResult::Corrupt : StoreResult::Ok;
    }
    ~Session() {
        if (!path.path().isEmpty() && path.path() != QStringLiteral("/")) {
            call(path.path(), QStringLiteral("org.freedesktop.Secret.Session"), QStringLiteral("Close"));
        }
    }
    QDBusObjectPath path;
};
class SecretServiceAccountStore final : public ProtectedAccountStore {
public:
    SecretServiceAccountStore() {
        qDBusRegisterMetaType<Secret>();
        qDBusRegisterMetaType<Attributes>();
        qDBusRegisterMetaType<Paths>();
    }
    StoreResult read(AccountBytes& output) override {
        clearAccountBytes(output);
        auto found = find();
        if (found.status != StoreResult::Ok) { return found.status; }
        if (!found.locked.isEmpty()) { return StoreResult::Locked; }
        if (found.unlocked.isEmpty()) { return StoreResult::Absent; }
        if (found.unlocked.size() != 1) { return StoreResult::Corrupt; }
        Session session;
        auto status = session.open();
        if (status != StoreResult::Ok) { return status; }
        auto reply = call(found.unlocked.front().path(), ITEM_INTERFACE, QStringLiteral("GetSecret"),
                          { QVariant::fromValue(session.path) });
        status = result(reply);
        if (status != StoreResult::Ok) { return status; }
        if (reply.arguments().size() != 1 || reply.signature() != QStringLiteral("(oayays)")) { return StoreResult::Corrupt; }
        auto secret = qdbus_cast<Secret>(reply.arguments().front());
        // GNOME Keyring preserves opaque bytes, including NUL/high bytes, but
        // normalizes the returned MIME type to text/plain. Do not decode or
        // transform the value: the coordinator verifies the serialized map and
        // exact write/readback independently of this provider metadata.
        const bool binaryCompatibleType = secret.contentType == CONTENT_TYPE
            || secret.contentType == QStringLiteral("text/plain");
        if (secret.session.path() != session.path.path() || !secret.parameters.isEmpty()
                || !binaryCompatibleType || secret.value.isEmpty()
                || static_cast<std::size_t>(secret.value.size()) > MAX_ACCOUNT_BYTES) { return StoreResult::Corrupt; }
        output.assign(secret.value.begin(), secret.value.end());
        return StoreResult::Ok;
    }
    StoreResult write(const AccountBytes& input) override {
        if (input.empty() || input.size() > MAX_ACCOUNT_BYTES) { return StoreResult::Corrupt; }
        auto found = find();
        if (found.status != StoreResult::Ok) { return found.status; }
        if (!found.locked.isEmpty()) { return StoreResult::Locked; }
        if (found.unlocked.size() > 1) { return StoreResult::Corrupt; }
        Session session;
        auto status = session.open();
        if (status != StoreResult::Ok) { return status; }
        Secret secret;
        secret.session = session.path;
        secret.value = QByteArray(reinterpret_cast<const char*>(input.data()), static_cast<int>(input.size()));
        secret.contentType = CONTENT_TYPE;
        if (!found.unlocked.isEmpty()) {
            return result(call(found.unlocked.front().path(), ITEM_INTERFACE, QStringLiteral("SetSecret"),
                               { QVariant::fromValue(secret) }));
        }
        QVariantMap properties;
        properties.insert(ITEM_INTERFACE + QStringLiteral(".Attributes"), QVariant::fromValue(ATTRIBUTES));
        properties.insert(ITEM_INTERFACE + QStringLiteral(".Label"), QStringLiteral("Overte account storage"));
        auto reply = call(found.collection.path(), COLLECTION_INTERFACE, QStringLiteral("CreateItem"),
                          { properties, QVariant::fromValue(secret), true });
        status = result(reply);
        if (status != StoreResult::Ok) { return status; }
        if (reply.arguments().size() != 2 || reply.signature() != QStringLiteral("oo")) { return StoreResult::Corrupt; }
        const auto item = qdbus_cast<QDBusObjectPath>(reply.arguments().at(0));
        const auto prompt = qdbus_cast<QDBusObjectPath>(reply.arguments().at(1));
        if (prompt.path() != QStringLiteral("/")) { return StoreResult::Locked; }
        return item.path() == QStringLiteral("/") ? StoreResult::IoError : StoreResult::Ok;
    }
    StoreResult erase() override {
        auto found = find();
        if (found.status != StoreResult::Ok) { return found.status; }
        if (found.unlocked.isEmpty() && found.locked.isEmpty()) { return StoreResult::Absent; }
        auto status = StoreResult::Ok;
        for (const auto& item : found.unlocked + found.locked) {
            auto reply = call(item.path(), ITEM_INTERFACE, QStringLiteral("Delete"));
            auto deleted = result(reply);
            if (deleted == StoreResult::Ok) {
                if (reply.signature() != QStringLiteral("o") || reply.arguments().size() != 1) { deleted = StoreResult::Corrupt; }
                else if (qdbus_cast<QDBusObjectPath>(reply.arguments().front()).path() != QStringLiteral("/")) { deleted = StoreResult::Locked; }
            }
            if (deleted != StoreResult::Ok) { status = deleted; }
        }
        return status;
    }
};
}
std::shared_ptr<ProtectedAccountStore> linuxProtectedAccountStore() {
    return std::make_shared<SecretServiceAccountStore>();
}
}}
