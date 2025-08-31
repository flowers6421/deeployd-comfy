#!/usr/bin/env node
/**
 * Node.js bridge for interfacing with comfyui-json library
 * This script resolves custom node repositories from ComfyUI workflows
 */

const fs = require('fs');
const path = require('path');
const { generateDependencyGraph, generateDependencyGraphJson } = require('comfyui-json');

async function resolveWorkflow(workflowPath, options = {}) {
    try {
        // Read workflow file
        const workflowContent = fs.readFileSync(workflowPath, 'utf8');
        const workflow = JSON.parse(workflowContent);

        // Detect workflow format
        const isUIFormat = workflow.nodes && Array.isArray(workflow.nodes);

        let result;
        if (isUIFormat) {
            // UI format (nodes array)
            result = await generateDependencyGraphJson({
                workflow_json: workflow,
                snapshot: options.snapshot,
                pullLatestHashIfMissing: options.pullLatestHash !== false
            });
        } else {
            // API format
            result = await generateDependencyGraph({
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

        return output;

    } catch (error) {
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
        // Fetch the extension-node-map
        const extensionMapUrl = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json';
        const customNodeListUrl = 'https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json';

        const [extensionMapResponse, customNodeListResponse] = await Promise.all([
            fetch(extensionMapUrl),
            fetch(customNodeListUrl)
        ]);

        const extensionMap = await extensionMapResponse.json();
        const customNodeList = await customNodeListResponse.json();

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
