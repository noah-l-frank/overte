// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
'use strict';
// Actual Script functions/request module, with an explicit Qt XHR/native edge.
// No listener, credentials, native runtime or outcome setter is exposed here.
const fs = require('fs');
const vm = require('vm');
const readline = require('readline');
const root = process.argv[2];
const source = fs.readFileSync(root + '/scripts/system/snapshot.js', 'utf8');
const requestSource = fs.readFileSync(root + '/scripts/modules/request.js', 'utf8');
function section(first, last) {
    const begin = source.indexOf(first), end = source.indexOf(last, begin + first.length);
    if (begin < 0 || end < 0) { throw new Error('Missing original Script boundary'); }
    return source.slice(begin, end);
}
const original = section('var request;', 'function removeFromStoryIDsToMaybeDelete') +
    section('function fileExtensionMatches', 'var POLAROID_PRINT_SOUND') +
    section('function isDomainOpen', 'function stillSnapshotTaken');
let context, pending, shares, messages, permissionUpdates, delivered = false;
function emit(value) { process.stdout.write(JSON.stringify(value) + '\n'); }
function result() {
    emit({event: 'result', shares, messages, permissionUpdates,
        pendingUploads: Object.keys(context.nativeUploadPaths).length,
        xhrCallbackReleased: pending === null || pending.onreadystatechange === null,
        filename: context.mostRecentStillSnapshotFilename});
}
const lines = readline.createInterface({input: process.stdin});
lines.on('line', line => {
    try {
        const value = JSON.parse(line);
        if (value.operation === 'start') {
            if (context) { throw new Error('One original dispatch only'); }
            shares = []; messages = []; permissionUpdates = 0; pending = null;
            function XHR() {}
            XHR.prototype.open = function (method, uri, async) { this.method = method; this.uri = uri; this.async = async; };
            XHR.prototype.setRequestHeader = function () { throw new Error('Unexpected explicit Script header'); };
            XHR.prototype.getResponseHeader = function (name) { if (name !== 'content-type') { throw new Error('Unexpected header read'); } return 'application/json'; };
            XHR.prototype.send = function (body) {
                if (pending || this.method !== 'GET' || !this.async || body !== null) { throw new Error('Unexpected original XHR'); }
                pending = this; emit({event: 'http', method: this.method, uri: this.uri, body});
            };
            const requestContext = vm.createContext({module: {exports: {}}, XMLHttpRequest: XHR, print: function () {}});
            vm.runInContext(requestSource, requestContext, {timeout: 1000});
            context = vm.createContext({
                nativeReview: true, nativeReviewRevision: 1, nativeUploadPaths: {},
                METAVERSE_BASE: value.origin,
                Account: {metaverseServerURL: value.origin, isLoggedIn: () => value.loggedIn},
                Settings: {getValue: key => ({previousSnapshotDomainID: value.domain, previousSnapshotHref: value.href})[key]},
                Window: {shareSnapshot: (path, href) => shares.push({path, href})},
                ui: {sendMessage: message => messages.push(message)}, print: function () {},
                Script: {require: name => { if (name !== 'request') { throw new Error('Unexpected module'); } return requestContext.module.exports; }},
                updatePrintPermissions: () => { permissionUpdates++; },
                mostRecentStillSnapshotFilename: '', mostRecentGifSnapshotFilename: '',
                snapshotToShareAfterLogin: [], shareAfterLogin: false
            });
            vm.runInContext(original, context, {timeout: 1000});
            context.message = {type: 'snapshot', action: 'shareSnapshotForUrl', data: value.path};
            vm.runInContext('onMessage(message)', context, {timeout: 1000});
            emit({event: 'returned', pendingUploads: Object.keys(context.nativeUploadPaths).length});
            if (!pending) { result(); }
        } else if (value.operation === 'response') {
            if (!pending || delivered) { throw new Error('No second XHR delivery'); }
            delivered = true;
            if (value.replaceReview) { context.nativeReviewRevision++; }
            pending.status = value.status; pending.statusText = 'Declared original HTTP result';
            pending.responseText = value.body; pending.readyState = 4;
            pending.onreadystatechange(); result();
        } else if (value.operation === 'stop') { lines.close(); process.stdin.pause(); }
        else { throw new Error('Unknown private driver operation'); }
    } catch (_) { emit({event: 'failure', error: 'Original Script boundary rejected'}); process.exitCode = 1; lines.close(); process.stdin.pause(); }
});
