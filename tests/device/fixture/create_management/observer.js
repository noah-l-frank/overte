// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Ordinary, read-only diagnostic: never create/edit/delete an entity here.
(function () {
    "use strict";
    var session = OVERTE_CREATE_SESSION;
    function uuid(value) {
        return String(value || "").replace(/[{}-]/g, "").toLowerCase();
    }
    var instance = uuid(Uuid.generate());
    var zero = "00000000000000000000000000000000";
    var sequence = 0, pending = null, frozen = null, ending = false;
    function capture() {
        var result = {complete: true, error: "", queriedEntityCount: 0, entities: []};
        try {
            var ids = Entities.findEntities(MyAvatar.position, 64);
            if (!Array.isArray(ids) || ids.length > 4096) {
                result.complete = false; result.error = "query-budget"; return result;
            }
            result.queriedEntityCount = ids.length;
            var me = uuid(MyAvatar.sessionUUID), self = uuid(MyAvatar.SELF_ID);
            ids.forEach(function (id) {
                var properties = Entities.getEntityProperties(id, ["name", "type", "shape", "dimensions",
                    "color", "parentID", "entityHostType", "owningAvatarID"]);
                if (typeof properties.name !== "string" || properties.name.indexOf(session.prefix) !== 0) { return; }
                var owner = uuid(properties.owningAvatarID);
                result.entities.push({id: uuid(id), name: properties.name,
                    type: String(properties.type), shape: String(properties.shape || ""),
                    dimensions: {x: Number(properties.dimensions.x), y: Number(properties.dimensions.y), z: Number(properties.dimensions.z)},
                    color: {red: Number(properties.color.red), green: Number(properties.color.green), blue: Number(properties.color.blue)},
                    host: String(properties.entityHostType),
                    ownedByCurrentAvatar: owner.length === 32 && owner !== zero && (owner === me || owner === self),
                    _parent: uuid(properties.parentID)});
            });
            if (result.entities.length > 16) {
                result.complete = false; result.error = "matching-entity-budget"; result.entities = []; return result;
            }
            var ownedIds = {};
            result.entities.forEach(function (row) { ownedIds[row.id] = true; });
            result.entities.forEach(function (row) {
                row.parentId = ownedIds[row._parent] ? row._parent : null;
                row.hasExternalParent = row._parent.length === 32 && row._parent !== zero && !ownedIds[row._parent];
                delete row._parent;
            });
            result.entities.sort(function (a, b) { return a.name < b.name ? -1 : a.name > b.name ? 1 : a.id < b.id ? -1 : a.id > b.id ? 1 : 0; });
        } catch (_error) {
            result.complete = false; result.error = "entity-read-error"; result.entities = [];
        }
        return result;
    }
    function send() {
        if (ending || pending) { return; }
        if (!frozen) {
            frozen = capture();
            frozen.token = session.receiptToken; frozen.instance = instance; frozen.sequence = sequence;
        }
        var request = new XMLHttpRequest();
        pending = request;
        request.timeout = 3000;
        request.ontimeout = function () { pending = null; };
        request.onreadystatechange = function () {
            if (request.readyState !== 4 || ending) { return; }
            if (request.status === 200) { sequence += 1; frozen = null; }
            pending = null;
        };
        try {
            request.open("POST", session.eventsUrl, true);
            request.setRequestHeader("Content-Type", "application/json");
            request.send(JSON.stringify(frozen));
        } catch (_error) { pending = null; }
    }
    var timer = Script.setInterval(send, 250);
    Script.scriptEnding.connect(function () {
        ending = true; Script.clearInterval(timer);
        if (pending) { pending.abort(); pending = null; }
    });
    send();
}());
