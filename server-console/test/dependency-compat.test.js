'use strict';

const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const cheerio = require('cheerio');
const request = require('@cypress/request');

test('ASAR packaging preserves traversal, symlinks and unpack patterns', async function(t) {
    const asar = await import('@electron/asar');
    const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'overte-asar-'));
    t.after(function() {
        fs.rmSync(directory, { recursive: true, force: true });
    });
    const source = path.join(directory, 'source');
    fs.mkdirSync(path.join(source, 'nested'), { recursive: true });
    fs.mkdirSync(path.join(source, 'native'), { recursive: true });
    fs.writeFileSync(path.join(source, 'nested', 'content.txt'), 'overte');
    fs.writeFileSync(path.join(source, 'native', 'addon.node'), 'native-addon');
    fs.writeFileSync(path.join(source, 'native', 'support.txt'), 'native-support');
    fs.writeFileSync(path.join(source, 'external.node'), 'external-addon');
    const archive = path.join(directory, 'app.asar');
    await asar.createPackageWithOptions(source, archive, {
        unpack: '**/*.node',
        unpackDir: 'native'
    });
    assert.equal(asar.extractFile(archive, 'nested/content.txt').toString(), 'overte');
    for (const file of ['native/addon.node', 'native/support.txt', 'external.node']) {
        assert.equal(asar.statFile(archive, file).unpacked, true);
        assert.equal(fs.readFileSync(path.join(archive + '.unpacked', file), 'utf8'),
            fs.readFileSync(path.join(source, file), 'utf8'));
    }
    const extracted = path.join(directory, 'extracted');
    asar.extractAll(archive, extracted);
    assert.equal(fs.readFileSync(path.join(extracted, 'native/support.txt'), 'utf8'), 'native-support');
    await t.test('symlink traversal and extraction', async function(t) {
        try {
            fs.symlinkSync('nested/content.txt', path.join(source, 'content-link'));
        } catch (error) {
            if (process.platform === 'win32' && error.code === 'EPERM') {
                t.skip('Creating symlinks requires Windows Developer Mode or administrator rights');
                return;
            }
            throw error;
        }
        const linkedArchive = path.join(directory, 'linked.asar');
        await asar.createPackageWithOptions(source, linkedArchive, {});
        assert.equal(asar.statFile(linkedArchive, 'content-link', false).link, 'nested/content.txt');
        const linkedExtracted = path.join(directory, 'linked-extracted');
        asar.extractAll(linkedArchive, linkedExtracted);
        assert.equal(fs.readFileSync(path.join(linkedExtracted, 'content-link'), 'utf8'), 'overte');
    });
});

test('request replacement preserves callback and stream APIs', async function(t) {
    var server = http.createServer(function(req, res) {
        res.writeHead(200, { 'content-type': 'text/plain' });
        res.end('overte');
    });
    await new Promise(function(resolve, reject) {
        server.listen(0, '127.0.0.1', resolve);
        server.once('error', reject);
    });
    t.after(function() {
        server.close();
    });
    var address = server.address();
    var target = 'http://127.0.0.1:' + address.port + '/';

    var body = await new Promise(function(resolve, reject) {
        request.get(target, function(error, response, responseBody) {
            if (error) {
                reject(error);
            } else {
                assert.equal(response.statusCode, 200);
                resolve(responseBody);
            }
        });
    });

    assert.equal(body, 'overte');
    var streamRequest = request.get(target);
    assert.equal(typeof streamRequest.pipe, 'function');
    streamRequest.abort();
});

test('Cheerio still parses the build-feed selectors used by the updater', function() {
    var xml = '<projects><project name="interface"><platform name="windows">' +
        '<build><stable_version>1.2.3</stable_version><url>https://example.test/build</url></build>' +
        '</platform></project></projects>';
    var $ = cheerio.load(xml, { xmlMode: true });
    var latestBuild = $('project[name="interface"] platform[name="windows"]').children().first();

    assert.equal(latestBuild.find('stable_version').text(), '1.2.3');
    assert.equal(latestBuild.find('url').text(), 'https://example.test/build');
});
