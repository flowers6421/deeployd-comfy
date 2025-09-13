// src/computeFileMap.ts
async function computeFileMap({
  workflow_api,
  folder,
  map,
  includeTypeInPath,
  getFileHash,
  handleFileUpload,
  existingFiles
}) {
  const cross = await Promise.all(Object.entries(workflow_api).map(async ([_, value]) => {
    const classType = value.class_type;
    if (classType && map[classType]) {
      const a = map[classType].inputs.map(async (inputKey) => {
        console.log("map", map[classType].inputs);
        console.log("inputkey.name: ", inputKey.name);
        if (Array.isArray(value.inputs[inputKey.name]) || value.inputs[inputKey.name] === undefined)
          return null;
        const file_path = `${folder}${includeTypeInPath ? `/${inputKey.type}` : ""}/${value.inputs[inputKey.name]}`;
        console.log("file_path", file_path);
        const hash = await getFileHash?.(file_path);
        let url = undefined;
        if (hash) {
          const existingFile = existingFiles?.[inputKey.type]?.find((file) => file.name === value.inputs[inputKey.name]);
          url = existingFile?.url;
          if (existingFile?.url === undefined || existingFile.hash !== hash && hash !== undefined) {
            if (handleFileUpload) {
              url = await handleFileUpload(file_path, hash, existingFile?.hash);
            }
          }
        }
        console.log(value.inputs[inputKey.name]);
        return value.inputs[inputKey.name] ? {
          value: value.inputs[inputKey.name],
          type: inputKey.type,
          hash,
          url
        } : null;
      });
      console.log(await Promise.all(a));
      return (await Promise.all(a)).filter((inputValue) => inputValue !== null);
    }
    return null;
  }));
  const groupedByType = cross.flat().filter((item) => item !== null).reduce((acc, input) => {
    if (!acc[input.type]) {
      acc[input.type] = [];
    }
    acc[input.type].push({
      name: input.value,
      hash: input.hash,
      url: input.url
    });
    return acc;
  }, {});
  return groupedByType;
}

// src/computeCustomModelsMap.ts
async function computeCustomModelsMap(props) {
  const resourcesMapping = {
    CheckpointLoaderSimple: {
      inputs: [
        {
          name: "ckpt_name",
          type: "checkpoints"
        }
      ]
    },
    IPAdapterModelLoader: {
      inputs: [
        {
          name: "ipadapter_file",
          type: "ipadapter"
        }
      ]
    },
    CLIPVisionLoader: {
      inputs: [
        {
          name: "clip_name",
          type: "clip_vision"
        }
      ]
    },
    LoraLoader: {
      inputs: [
        {
          name: "lora_name",
          type: "loras"
        }
      ]
    },
    VAELoader: {
      inputs: [
        {
          name: "vae_name",
          type: "vae"
        }
      ]
    },
    UNETLoader: {
      inputs: [
        {
          name: "unet_name",
          type: "unet"
        }
      ]
    },
    CLIPLoader: {
      inputs: [
        {
          name: "clip_name",
          type: "clip"
        }
      ]
    },
    DualCLIPLoader: {
      inputs: [
        {
          name: "clip_name1",
          type: "clip"
        },
        {
          name: "clip_name2",
          type: "clip"
        }
      ]
    },
    unCLIPCheckpointLoader: {
      inputs: [
        {
          name: "ckpt_name",
          type: "checkpoints"
        }
      ]
    },
    ControlNetLoader: {
      inputs: [
        {
          name: "controlnet_name",
          type: "controlnet"
        }
      ]
    },
    DiffControlNetLoader: {
      inputs: [
        {
          name: "controlnet_name",
          type: "controlnet"
        }
      ]
    },
    StyleModelLoader: {
      inputs: [
        {
          name: "style_model_name",
          type: "style_models"
        }
      ]
    },
    GLIGENLoader: {
      inputs: [
        {
          name: "gligen_name",
          type: "gligen"
        }
      ]
    },
    DiffusersLoader: {
      inputs: [
        {
          name: "model_path",
          type: "diffusers"
        }
      ]
    },
    LoraLoaderModelOnly: {
      inputs: [
        {
          name: "lora_name",
          type: "loras"
        }
      ]
    },
    HypernetworkLoader: {
      inputs: [
        {
          name: "hypernetwork_name",
          type: "hypernetworks"
        }
      ]
    },
    PhotoMakerLoader: {
      inputs: [
        {
          name: "photomaker_model_name",
          type: "photomaker"
        }
      ]
    },
    ImageOnlyCheckpointLoader: {
      inputs: [
        {
          name: "ckpt_name",
          type: "checkpoints"
        }
      ]
    },
    ControlNetLoaderAdvanced: {
      inputs: [
        {
          name: "controlnet_name",
          type: "controlnet"
        }
      ]
    },
    ACN_SparseCtrlLoaderAdvanced: {
      inputs: [
        {
          name: "sparsectrl_name",
          type: "controlnet"
        }
      ]
    },
    ACN_SparseCtrlMergedLoaderAdvanced: {
      inputs: [
        {
          name: "sparsectrl_name",
          type: "controlnet"
        },
        {
          name: "control_net_name",
          type: "controlnet"
        }
      ]
    },
    UpscaleModelLoader: {
      inputs: [
        {
          name: "model_name",
          type: "upscale_models"
        }
      ]
    },
    ADE_LoadAnimateDiffModel: {
      inputs: [
        {
          name: "model_name",
          type: "animate_diff_model"
        }
      ]
    }
  };
  return computeFileMap({
    folder: "models",
    includeTypeInPath: true,
    map: resourcesMapping,
    ...props
  });
}

// src/computeExternalFilesMap.ts
async function computeExternalFilesMap(props) {
  const fileInputMapping = {
    LoadImage: {
      inputs: [
        {
          name: "image",
          type: "images"
        }
      ]
    }
  };
  return computeFileMap({
    folder: "input",
    map: fileInputMapping,
    ...props
  });
}

// src/getBranchInfo.tsx
import {z} from "zod";
var extractRepoName = function(repoUrl) {
  const url = new URL(repoUrl);
  const pathParts = url.pathname.split("/");
  const repoName = pathParts[2].replace(".git", "");
  const author = pathParts[1];
  return `${author}/${repoName}`;
};
async function getBranchInfo(gitUrl) {
  const repoName = extractRepoName(gitUrl);
  console.log(`Fetching repo info... ${gitUrl}`);
  const repo = await fetch(`https://api.github.com/repos/${repoName}`).then((x) => x.json()).then((x) => {
    return x;
  }).then((x) => RepoSchema.parse(x)).catch((e) => {
    console.log(`Failed to fetch repo info (probably rate limited)`);
    return null;
  });
  if (!repo)
    return;
  const branch = repo.default_branch;
  const branchInfo = await fetch(`https://api.github.com/repos/${repoName}/branches/${branch}`).then((x) => x.json()).then((x) => {
    return x;
  }).then((x) => BranchInfoSchema.parse(x)).catch((e) => {
    console.log(`Failed to fetch branch info ${e.message}`);
    return null;
  });
  return branchInfo;
}
var RepoSchema = z.object({
  default_branch: z.string()
});
var BranchInfoSchema = z.object({
  commit: z.object({
    sha: z.string()
  })
});

// src/computeCustomNodesMap.ts
async function fetchExtensionNodeMap() {
  return await (await fetch("https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/extension-node-map.json")).json();
}
async function getCustomNodesMap() {
  return await (await fetch("https://raw.githubusercontent.com/ltdrdata/ComfyUI-Manager/main/custom-node-list.json")).json();
  console.log("Getting extension-node-map.json");
}
async function computeCustomNodesMap({
  workflow_api,
  snapshot,
  includeNodes,
  extensionNodeMap,
  pullLatestHashIfMissing = true
}) {
  let data = extensionNodeMap ? extensionNodeMap : await fetchExtensionNodeMap();
  data = filterBlacklistedUrls(data);
  const custom_nodes = await getCustomNodesMap();
  const missingNodes = new Set;
  const crossCheckedApi = Object.entries(workflow_api).map(([_, value]) => {
    const classType = value.class_type;
    const classTypeMatches = classType ? Object.entries(data).filter(([url, nodeArray]) => nodeArray[0].includes(classType) || nodeArray[1].nodename_pattern && new RegExp(nodeArray[1].nodename_pattern).test(classType)) : [];
    if (classTypeMatches.length > 1) {
      console.warn(`Conflict detected for classType '${classType}' in node pack '${classTypeMatches.reduce((acc, curr, index, array) => acc + curr[1][1].title_aux + (index < array.length - 1 ? ", " : ""), "")}': multiple matches found.`);
    }
    const classTypeData = classTypeMatches.length == 1 ? classTypeMatches[0] : undefined;
    if (!classTypeData && value.class_type) {
      missingNodes.add(value.class_type);
    }
    return classTypeData ? { node: value, classTypeData } : null;
  }).filter((item) => item !== null);
  const groupedByAuxName = crossCheckedApi.reduce(async (_acc, data2) => {
    if (!data2)
      return _acc;
    const acc = await _acc;
    const { node, classTypeData } = data2;
    const auxName = classTypeData[1][1].title_aux;
    if (!acc[classTypeData[0]]) {
      let warning = undefined;
      let url = classTypeData[0];
      let customNodeHash = snapshot?.git_custom_nodes[classTypeData[0]]?.hash;
      if (url == "https://github.com/comfyanonymous/ComfyUI") {
        customNodeHash = snapshot?.comfyui;
      }
      if (!customNodeHash && pullLatestHashIfMissing) {
        if (classTypeData[0].endsWith(".git")) {
          url = classTypeData[0].split("/").pop()?.split(".")[0];
          if (url)
            customNodeHash = snapshot?.git_custom_nodes[url]?.hash;
        } else {
          url = classTypeData[0] + ".git";
          if (url)
            customNodeHash = snapshot?.git_custom_nodes[url]?.hash;
        }
        if (!customNodeHash && url) {
          const info = await getBranchInfo(url);
          if (info) {
            customNodeHash = info.commit.sha;
          }
          warning = "No hash found in snapshot, using latest commit hash";
        }
      }
      acc[classTypeData[0]] = {
        url: classTypeData[0],
        name: auxName,
        hash: customNodeHash
      };
      if (warning) {
        acc[classTypeData[0]].warning = warning;
      }
      if (includeNodes) {
        acc[classTypeData[0]].node = [];
      }
      const custom_node_details = custom_nodes.custom_nodes.find((x) => x.files.includes(classTypeData[0]));
      if (custom_node_details && custom_node_details.pip) {
        acc[classTypeData[0]].pip = custom_node_details.pip;
      }
      if (custom_node_details) {
        acc[classTypeData[0]].files = custom_node_details.files;
        acc[classTypeData[0]].install_type = custom_node_details.install_type;
      }
    }
    if (includeNodes)
      acc[classTypeData[0]].node?.push(node);
    return acc;
  }, Promise.resolve({}));
  console.log("Missing nodes", missingNodes);
  return {
    customNodes: await groupedByAuxName,
    missingNodes: Array.from(missingNodes)
  };
}
async function computeCustomNodesMapJson({
  workflow_json,
  snapshot,
  includeNodes,
  extensionNodeMap,
  pullLatestHashIfMissing = true
}) {
  let data = extensionNodeMap ? extensionNodeMap : await fetchExtensionNodeMap();
  data = filterBlacklistedUrls(data);
  const custom_nodes = await getCustomNodesMap();
  const missingNodes = new Set;
  const conflictNodeMap = {};
  const crossCheckedApi = workflow_json.nodes.map((value) => {
    const classType = value.type;
    const classTypeMatches = classType ? Object.entries(data).filter(([_, nodeArray]) => nodeArray[0].includes(classType) || nodeArray[1].nodename_pattern && new RegExp(nodeArray[1].nodename_pattern).test(classType)) : [];
    if (classTypeMatches.length > 1) {
      console.warn(`Conflict detected for classType '${classType}' in node pack '${classTypeMatches.reduce((acc, curr, index, array) => acc + curr[1][1].title_aux + (index < array.length - 1 ? ", " : ""), "")}': multiple matches found.`);
    }
    const classTypeData = classTypeMatches.length == 1 ? classTypeMatches[0] : undefined;
    if (!classTypeData && classType) {
      missingNodes.add(classType);
      const urls = classTypeMatches.map(([url, _]) => ({ url }));
      conflictNodeMap[classType] = custom_nodes.custom_nodes.filter((x) => {
        return urls.some((item) => x.files.includes(item.url));
      });
    }
    return classTypeData ? { node: value, classTypeData } : null;
  }).filter((item) => item !== null);
  const groupedByAuxName = crossCheckedApi.reduce(async (_acc, data2) => {
    if (!data2)
      return _acc;
    const acc = await _acc;
    const { node, classTypeData } = data2;
    const auxName = classTypeData[1][1].title_aux;
    if (!acc[classTypeData[0]]) {
      let warning = undefined;
      let url = classTypeData[0];
      let customNodeHash = snapshot?.git_custom_nodes[classTypeData[0]]?.hash;
      if (url == "https://github.com/comfyanonymous/ComfyUI") {
        customNodeHash = snapshot?.comfyui;
      }
      if (!customNodeHash && pullLatestHashIfMissing) {
        if (classTypeData[0].endsWith(".git")) {
          url = classTypeData[0].split("/").pop()?.split(".")[0];
          if (url)
            customNodeHash = snapshot?.git_custom_nodes[url]?.hash;
        } else {
          url = classTypeData[0] + ".git";
          if (url)
            customNodeHash = snapshot?.git_custom_nodes[url]?.hash;
        }
        if (!customNodeHash && url) {
          const info = await getBranchInfo(url);
          if (info) {
            customNodeHash = info.commit.sha;
          }
          warning = "No hash found in snapshot, using latest commit hash";
        }
      }
      acc[classTypeData[0]] = {
        url: classTypeData[0],
        name: auxName,
        hash: customNodeHash
      };
      if (warning) {
        acc[classTypeData[0]].warning = warning;
      }
      if (includeNodes) {
        acc[classTypeData[0]].node = [];
      }
      const custom_node_details = custom_nodes.custom_nodes.find((x) => x.files.includes(classTypeData[0]));
      if (custom_node_details && custom_node_details.pip) {
        acc[classTypeData[0]].pip = custom_node_details.pip;
      }
      if (custom_node_details) {
        acc[classTypeData[0]].files = custom_node_details.files;
        acc[classTypeData[0]].install_type = custom_node_details.install_type;
      }
    }
    if (includeNodes)
      acc[classTypeData[0]].node?.push({
        class_type: node.type,
        inputs: {}
      });
    return acc;
  }, Promise.resolve({}));
  console.log("Missing nodes", missingNodes);
  return {
    customNodes: await groupedByAuxName,
    missingNodes: Array.from(missingNodes),
    conflictNodes: conflictNodeMap
  };
}
var BLACKLISTED_URLS = ["https://github.com/Seedsa/Fooocus_Nodes"];
var filterBlacklistedUrls = (data) => {
  Object.entries(data).forEach(([key, _]) => {
    if (BLACKLISTED_URLS.includes(key)) {
      delete data[key];
    }
  });
  return data;
};

// src/generateDependencyGraph.ts
import {z as z3} from "zod";

// src/workflowAPIType.ts
import {z as z2} from "zod";
var workflowType = z2.object({
  last_node_id: z2.number(),
  last_link_id: z2.number(),
  nodes: z2.array(z2.object({
    id: z2.number(),
    type: z2.string(),
    widgets_values: z2.array(z2.any())
  }))
});
var snapshotType = z2.object({
  comfyui: z2.string(),
  git_custom_nodes: z2.record(z2.object({
    hash: z2.string(),
    disabled: z2.boolean()
  })),
  file_custom_nodes: z2.array(z2.any())
});
var workflowAPINodeType = z2.object({
  inputs: z2.record(z2.any()),
  class_type: z2.string().optional()
});
var CustomNodesDepsType = z2.record(z2.object({
  name: z2.string(),
  node: z2.array(workflowAPINodeType).optional(),
  hash: z2.string().optional(),
  url: z2.string(),
  files: z2.array(z2.string()).optional(),
  install_type: z2.union([z2.enum(["copy", "unzip", "git-clone"]), z2.string()]).optional(),
  warning: z2.string().optional(),
  pip: z2.array(z2.string()).optional()
}));
var FileReferenceType = z2.object({
  name: z2.string(),
  hash: z2.string().optional(),
  url: z2.string().optional()
});
var FileReferencesType = z2.record(z2.array(FileReferenceType));
var workflowAPIType = z2.record(workflowAPINodeType);

// src/generateDependencyGraph.ts
async function generateDependencyGraph({
  workflow_api,
  snapshot,
  computeFileHash,
  handleFileUpload,
  existingDependencies,
  cachedExtensionsMap,
  pullLatestHashIfMissing = true
}) {
  const {
    customNodes: deps,
    missingNodes
  } = await computeCustomNodesMap({
    workflow_api,
    snapshot,
    pullLatestHashIfMissing,
    extensionNodeMap: cachedExtensionsMap
  });
  const comfyuihash = deps["https://github.com/comfyanonymous/ComfyUI"]?.hash ?? snapshot?.comfyui;
  delete deps["https://github.com/comfyanonymous/ComfyUI"];
  return {
    comfyui: comfyuihash,
    custom_nodes: deps,
    missing_nodes: missingNodes,
    models: await computeCustomModelsMap({
      workflow_api,
      getFileHash: computeFileHash
    }),
    files: await computeExternalFilesMap({
      workflow_api,
      getFileHash: computeFileHash,
      handleFileUpload,
      existingFiles: existingDependencies?.files
    })
  };
}
async function generateDependencyGraphJson({
  workflow_json,
  snapshot,
  computeFileHash,
  handleFileUpload,
  existingDependencies,
  cachedExtensionsMap,
  pullLatestHashIfMissing = true
}) {
  const {
    customNodes: deps,
    missingNodes,
    conflictNodes
  } = await computeCustomNodesMapJson({
    workflow_json,
    snapshot,
    pullLatestHashIfMissing,
    extensionNodeMap: cachedExtensionsMap
  });
  const comfyuihash = deps["https://github.com/comfyanonymous/ComfyUI"]?.hash ?? snapshot?.comfyui;
  delete deps["https://github.com/comfyanonymous/ComfyUI"];
  return {
    comfyui: comfyuihash,
    custom_nodes: deps,
    missing_nodes: missingNodes,
    conflicting_nodes: conflictNodes
  };
}
var DependencyGraphType = z3.object({
  comfyui: z3.string(),
  missing_nodes: z3.array(z3.string()),
  custom_nodes: CustomNodesDepsType,
  models: FileReferencesType,
  files: FileReferencesType
});

// src/graphToPrompt.ts
async function graphToPrompt(graph) {
  for (const outerNode of graph.computeExecutionOrder(false, undefined)) {
    if (outerNode.widgets) {
      for (const widget of outerNode.widgets) {
        widget.beforeQueued?.();
      }
    }
    const innerNodes = outerNode.getInnerNodes ? outerNode.getInnerNodes() : [outerNode];
    for (const node of innerNodes) {
      if (node.isVirtualNode) {
        if (node.applyToGraph) {
          node.applyToGraph();
        }
      }
    }
  }
  const workflow = graph.serialize();
  const output = {};
  for (const outerNode of graph.computeExecutionOrder(false, undefined)) {
    const skipNode = outerNode.mode === 2 || outerNode.mode === 4;
    const innerNodes = !skipNode && outerNode.getInnerNodes ? outerNode.getInnerNodes() : [outerNode];
    for (const node of innerNodes) {
      if (node.isVirtualNode) {
        continue;
      }
      if (node.mode === 2 || node.mode === 4) {
        continue;
      }
      const inputs = {};
      const widgets = node.widgets;
      if (widgets) {
        for (const i in widgets) {
          const widget = widgets[i];
          if (!widget.options || widget.options.serialize !== false) {
            inputs[widget.name] = widget.serializeValue ? await widget.serializeValue(node, i) : widget.value;
          }
        }
      }
      console.log("node: ", node);
      for (const i in node.inputs) {
        let parent = node.getInputNode(i);
        if (parent) {
          let link = node.getInputLink(i);
          while (parent.mode === 4 || parent.isVirtualNode) {
            let found = false;
            if (parent.isVirtualNode) {
              link = parent.getInputLink(link.origin_slot);
              if (link) {
                parent = parent.getInputNode(link.target_slot);
                if (parent) {
                  found = true;
                }
              }
            } else if (link && parent.mode === 4) {
              let all_inputs = [link.origin_slot];
              if (parent.inputs) {
                all_inputs = all_inputs.concat(Object.keys(parent.inputs));
                for (let parent_input in all_inputs) {
                  parent_input = all_inputs[parent_input];
                  if (parent.inputs[parent_input]?.type === node.inputs[i].type) {
                    link = parent.getInputLink(parent_input);
                    if (link) {
                      parent = parent.getInputNode(parent_input);
                    }
                    found = true;
                    break;
                  }
                }
              }
            }
            if (!found) {
              break;
            }
          }
          if (link) {
            if (parent?.updateLink) {
              link = parent.updateLink(link);
            }
            if (link) {
              inputs[node.inputs[i].name] = [
                String(link.origin_id),
                parseInt(link.origin_slot)
              ];
            }
          }
        }
      }
      const node_data = {
        inputs,
        class_type: node.type
      };
      output[String(node.id)] = node_data;
    }
  }
  for (const o in output) {
    for (const i in output[o].inputs) {
      if (Array.isArray(output[o].inputs[i]) && output[o].inputs[i].length === 2 && !output[output[o].inputs[i][0]]) {
        delete output[o].inputs[i];
      }
    }
  }
  return { workflow, output };
}
export {
  graphToPrompt,
  generateDependencyGraphJson,
  generateDependencyGraph,
  FileReferenceType,
  DependencyGraphType,
  CustomNodesDepsType
};
