#!/usr/bin/env node
/**
 * Node.js bridge for interfacing with comfyui-json library
 * This script resolves custom node repositories from ComfyUI workflows
 */

const fs = require('fs');
const path = require('path');

// Ensure we always return JSON even on unexpected crashes
process.on('uncaughtException', (err) => {
  try {
    console.log(JSON.stringify({ success: false, error: err && err.message, stack: err && err.stack }));
  } catch {}
  process.exit(1);
});
process.on('unhandledRejection', (reason) => {
  try {
    const msg = (reason && reason.message) || String(reason);
    console.log(JSON.stringify({ success: false, error: msg }));
  } catch {}
  process.exit(1);
});

async function loadComfyJson() {
    const vendorPath = path.join(__dirname, 'vendor', 'comfyui-json', 'dist', 'index.js');
    try {
        if (fs.existsSync(vendorPath)) {
            // Load vendored comfyui-json first (no external install required)
            // eslint-disable-next-line global-require, import/no-unresolved
            return require(vendorPath);
        }
    } catch (_) {
        // Continue to fallback attempts below
    }
    try {
        // Prefer CJS require when available
        // eslint-disable-next-line global-require, import/no-unresolved
        return require('comfyui-json');
    } catch (e) {
        try {
            // Fallback to dynamic ESM import
            const mod = await import('comfyui-json');
            return mod;
        } catch (err) {
            throw new Error(`comfyui-json not available: ${(err && err.message) || String(err)}`);
        }
    }
}

function hasGlobalFetch() {
    try { return typeof fetch === 'function'; } catch { return false; }
}

async function fetchUrl(url) {
    if (hasGlobalFetch()) {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
        return res.json();
    }
    // Minimal https JSON fetch fallback
    const https = require('https');
    return new Promise((resolve, reject) => {
        https.get(url, (resp) => {
            let data = '';
            resp.on('data', (chunk) => { data += chunk; });
            resp.on('end', () => {
                try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
            });
        }).on('error', reject);
    });
}

// Ensure global.fetch exists and inject overlays for Manager maps
function ensureGlobalFetchWithOverlay() {
    const EXT_MAP_URL = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json';

    // Overlay additions for missing or newly-introduced nodes
    const overlayEntries = {
        // Map the specific UI node "easy seed_seed" to Custom-Scripts pack
        'https://github.com/pythongosssss/ComfyUI-Custom-Scripts': [
            [],
            {
                title: 'ComfyUI-Custom-Scripts',
                title_aux: 'Custom-Scripts',
                // Be precise to avoid conflicts with Easy-Use pack (e.g., 'easy seed')
                nodename_pattern: '^easy\\sseed_seed$'
            }
        ]
    };

    function applyOverlay(map) {
        try {
            for (const [url, data] of Object.entries(overlayEntries)) {
                map[url] = data;
            }
        } catch (_) {}
        return map;
    }

    // If no global fetch, polyfill with overlay support
    if (!hasGlobalFetch()) {
        const https = require('https');
        global.fetch = (input) => {
            const url = typeof input === 'string' ? input : (input && input.url);
            return new Promise((resolve, reject) => {
                https.get(url, (resp) => {
                    let data = '';
                    resp.on('data', (chunk) => { data += chunk; });
                    resp.on('end', () => {
                        const makeResponse = (jsonObj) => ({
                            ok: true,
                            status: 200,
                            json: async () => jsonObj
                        });
                        try {
                            if (url === EXT_MAP_URL) {
                                const parsed = JSON.parse(data);
                                return resolve(makeResponse(applyOverlay(parsed)));
                            }
                            return resolve(makeResponse(JSON.parse(data)));
                        } catch (e) { return reject(e); }
                    });
                }).on('error', reject);
            });
        };
        return;
    }

    // Wrap existing fetch to inject overlay when the extension map is requested
    const originalFetch = global.fetch.bind(global);
    global.fetch = async (input, init) => {
        const url = typeof input === 'string' ? input : (input && input.url);
        const res = await originalFetch(input, init);
        if (url === EXT_MAP_URL) {
            try {
                const json = await res.json();
                const patched = applyOverlay(json);
                // Return a response-like with .json() resolving to patched data
                return { ok: true, status: res.status, json: async () => patched };
            } catch (_) {
                return res;
            }
        }
        return res;
    };
}

async function resolveWorkflow(workflowPath, options = {}) {
    try {
        ensureGlobalFetchWithOverlay();
        const lib = await loadComfyJson();

        // Silence noisy console logs from downstream libs to keep stdout JSON-clean
        const origLog = console.log; const origWarn = console.warn; const origInfo = console.info;
        console.log = () => {}; console.warn = () => {}; console.info = () => {};
        // Read workflow file
        const workflowContent = fs.readFileSync(workflowPath, 'utf8');
        const workflow = JSON.parse(workflowContent);

        // Detect workflow format
        const isUIFormat = workflow.nodes && Array.isArray(workflow.nodes);

        let result;
        if (isUIFormat) {
            // UI format (nodes array)
            result = await lib.generateDependencyGraphJson({
                workflow_json: workflow,
                snapshot: options.snapshot,
                pullLatestHashIfMissing: options.pullLatestHash !== false
            });
        } else {
            // API format
            result = await lib.generateDependencyGraph({
                workflow_api: workflow,
                snapshot: options.snapshot,
                pullLatestHashIfMissing: options.pullLatestHash !== false
            });
        }

        // Transform result for Python consumption
        const output = {
            success: true,
            format: isUIFormat ? 'ui' : 'api',
            comfyui_hash: result.comfyui,
            custom_nodes: {},
            missing_nodes: result.missing_nodes || [],
            conflicting_nodes: result.conflicting_nodes || {}
        };

        // Process custom nodes
        for (const [url, nodeData] of Object.entries(result.custom_nodes || {})) {
            output.custom_nodes[url] = {
                url: nodeData.url,
                name: nodeData.name,
                hash: nodeData.hash || null,
                pip: nodeData.pip || [],
                files: nodeData.files || [],
                install_type: nodeData.install_type || 'git-clone',
                warning: nodeData.warning || null
            };
        }

        // Restore console
        console.log = origLog; console.warn = origWarn; console.info = origInfo;
        return output;

    } catch (error) {
        try { // Restore console if we errored before restore
            const origLog = console.log; const origWarn = console.warn; const origInfo = console.info;
            console.log = origLog; console.warn = origWarn; console.info = origInfo;
        } catch (_) {}
        return {
            success: false,
            error: error.message,
            stack: error.stack
        };
    }
}

async function resolveCustomNodes(nodeClasses, options = {}) {
    /**
     * Resolve a list of custom node class names to their repositories
     */
    try {
        // Fetch the extension-node-map using an environment-agnostic fetch
        const extensionMapUrl = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json';
        const customNodeListUrl = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json';

        ensureGlobalFetchWithOverlay();
        const [extensionMapRaw, customNodeList] = await Promise.all([
            fetchUrl(extensionMapUrl),
            fetchUrl(customNodeListUrl)
        ]);

        // Apply the same overlay adjustments used for the library path
        const extensionMap = (() => {
            try {
                const map = extensionMapRaw || {};
                // Same entries as ensureGlobalFetchWithOverlay
                map['https://github.com/pythongosssss/ComfyUI-Custom-Scripts'] = [
                    [],
                    {
                        title: 'ComfyUI-Custom-Scripts',
                        title_aux: 'Custom-Scripts',
                        nodename_pattern: '^easy\\sseed_seed$'
                    }
                ];
                return map;
            } catch (_) {
                return extensionMapRaw;
            }
        })();

        const resolved = {};
        const unresolved = [];

        for (const nodeClass of nodeClasses) {
            let found = false;

            // Check extension map
            for (const [url, [nodeClasses, metadata]] of Object.entries(extensionMap)) {
                if (nodeClasses.includes(nodeClass)) {
                    resolved[nodeClass] = {
                        url: url,
                        name: metadata.title_aux || metadata.title,
                        title: metadata.title
                    };

                    // Find additional info from custom node list
                    const nodeInfo = customNodeList.custom_nodes.find(n =>
                        n.reference === url || n.files.includes(url)
                    );

                    if (nodeInfo) {
                        resolved[nodeClass].pip = nodeInfo.pip || [];
                        resolved[nodeClass].install_type = nodeInfo.install_type || 'git-clone';
                    }

                    found = true;
                    break;
                }

                // Check pattern matching
                if (metadata.nodename_pattern) {
                    const pattern = new RegExp(metadata.nodename_pattern);
                    if (pattern.test(nodeClass)) {
                        resolved[nodeClass] = {
                            url: url,
                            name: metadata.title_aux || metadata.title,
                            title: metadata.title,
                            matched_by_pattern: true
                        };
                        found = true;
                        break;
                    }
                }
            }

            if (!found) {
                unresolved.push(nodeClass);
            }
        }

        return {
            success: true,
            resolved: resolved,
            unresolved: unresolved
        };

    } catch (error) {
        return {
            success: false,
            error: error.message,
            stack: error.stack
        };
    }
}

// Main execution
if (require.main === module) {
    const args = process.argv.slice(2);
    const command = args[0];

    if (!command) {
        console.error('Usage: node node_bridge.js <command> [options]');
        console.error('Commands:');
        console.error('  resolve-workflow <path>  - Resolve all dependencies from workflow file');
        console.error('  resolve-nodes <nodes>    - Resolve specific node classes (comma-separated)');
        process.exit(1);
    }

    (async () => {
        let result;

        switch (command) {
            case 'resolve-workflow':
                if (!args[1]) {
                    console.error('Error: workflow path required');
                    process.exit(1);
                }
                result = await resolveWorkflow(args[1], {
                    pullLatestHash: args[2] !== 'false'
                });
                break;

            case 'resolve-nodes':
                if (!args[1]) {
                    console.error('Error: node classes required');
                    process.exit(1);
                }
                const nodeClasses = args[1].split(',').map(n => n.trim());
                result = await resolveCustomNodes(nodeClasses);
                break;

            default:
                console.error(`Unknown command: ${command}`);
                process.exit(1);
        }

        // Output JSON result
        console.log(JSON.stringify(result, null, 2));
    })();
}

module.exports = { resolveWorkflow, resolveCustomNodes };
