# Bug Report: Incorrect Classification of GGUF Custom Nodes as Missing

## Summary
The DeepLoyd Comfy system incorrectly attempts to resolve `DualCLIPLoaderGGUF` and `UnetLoaderGGUF` as missing custom nodes, despite the fact that these are legitimate custom nodes from the ComfyUI-GGUF extension that should be properly detected and handled.

## Issue Details

### Current Behavior
```
Warning: Could not resolve repository for custom node 'DualCLIPLoaderGGUF'
Warning: Could not resolve repository for custom node 'UnetLoaderGGUF'
```

### Expected Behavior
These nodes should be properly identified as custom nodes from the `ComfyUI-GGUF` repository and resolved automatically without warnings.

## Root Cause Analysis

### 1. Node Classification Accuracy
- **Issue**: The system correctly identifies these as custom nodes (not built-in)
- **Problem**: The custom node repository resolution fails for these specific nodes
- **Verification**: These are NOT native ComfyUI nodes - they are custom nodes from `https://github.com/city96/ComfyUI-GGUF`

### 2. Repository Resolution Failure
The current custom node resolution process in `/src/containers/custom_node_installer.py` fails to map these node types to their source repository due to:

1. **Insufficient Database Coverage**: ComfyUI-Manager database may not have complete coverage of GGUF nodes
2. **Name Matching Issues**: The heuristic matching in `find_repository_by_class_name()` doesn't properly handle GGUF suffix patterns
3. **Missing GGUF-Specific Resolution**: No special handling for GGUF quantization nodes

## Technical Details

### Affected Files
- `/src/containers/custom_node_installer.py` - Lines 135-200 (repository resolution logic)
- `/src/workflows/constants.py` - Lines 1-149 (BUILTIN_NODES definition)
- `/main.py` - Lines 356-434 (workflow processing)

### Node Information
```json
{
  "DualCLIPLoaderGGUF": {
    "repository": "https://github.com/city96/ComfyUI-GGUF",
    "category": "loaders",
    "description": "Load CLIP models in GGUF format for quantized inference"
  },
  "UnetLoaderGGUF": {
    "repository": "https://github.com/city96/ComfyUI-GGUF",
    "category": "loaders",
    "description": "Load UNET models in GGUF format for quantized inference"
  }
}
```

### Current Resolution Logic Issues
```python
# Current problematic logic in find_repository_by_class_name()
if (class_name.lower() in entry_title.lower() or
    class_name in entry_title or
    class_name.replace('|', '').replace(' ', '') in entry_title.replace(' ', '')):
```

**Problem**: This doesn't handle GGUF suffix patterns or the specific naming conventions of the ComfyUI-GGUF extension.

## Impact Assessment

### Severity: Medium
- **User Experience**: Confusing warning messages suggest missing dependencies
- **Workflow Processing**: Still succeeds but with false warnings
- **Containerization**: May fail if interactive prompts are disabled

### Affected Workflows
- Any workflow using FLUX GGUF models
- Workflows requiring quantized model inference
- Production deployments with `--no-interactive` flag

## Proposed Solutions

### Solution 1: Enhanced GGUF Node Detection (Recommended)
Add specialized detection for GGUF nodes with known repository mapping:

```python
# Add to CustomNodeInstaller class
KNOWN_GGUF_NODES = {
    "UnetLoaderGGUF": "https://github.com/city96/ComfyUI-GGUF",
    "DualCLIPLoaderGGUF": "https://github.com/city96/ComfyUI-GGUF",
    "CLIPLoaderGGUF": "https://github.com/city96/ComfyUI-GGUF",
    # Add other GGUF nodes as discovered
}

def find_repository_by_class_name(self, class_name: str) -> str | None:
    # Check GGUF nodes first
    if class_name in self.KNOWN_GGUF_NODES:
        return self.KNOWN_GGUF_NODES[class_name]

    # Continue with existing logic...
```

### Solution 2: Pattern-Based Detection
Enhance the repository resolution to detect GGUF patterns:

```python
def resolve_gguf_nodes(self, class_name: str) -> str | None:
    """Resolve GGUF-related custom nodes."""
    if class_name.endswith('GGUF') or 'GGUF' in class_name:
        # Check common GGUF repositories
        gguf_repos = [
            "https://github.com/city96/ComfyUI-GGUF",
            # Add other known GGUF repos
        ]
        return gguf_repos[0]  # Default to most common
    return None
```

### Solution 3: ComfyUI-JSON Integration (Future Enhancement)
Integrate with the `comfyui-json` package mentioned in the original conversation for more accurate dependency resolution.

## Testing Requirements

### Test Cases
1. **GGUF Node Detection**: Verify `DualCLIPLoaderGGUF` and `UnetLoaderGGUF` resolve correctly
2. **Repository Mapping**: Ensure correct GitHub URL is returned
3. **Workflow Processing**: Test complete workflow with GGUF nodes
4. **Non-Interactive Mode**: Verify no failures in `--no-interactive` mode

### Test Data
Use the provided workflow file: `workflow-flux-lora-upscaler-Mk8Yz49ROXjkQObezVMp-beaver_absolute_68-openart.ai.json`

## Implementation Priority

### High Priority
- [ ] Add known GGUF node mappings to `CustomNodeInstaller`
- [ ] Update repository resolution logic
- [ ] Add unit tests for GGUF node detection

### Medium Priority
- [ ] Implement pattern-based GGUF detection
- [ ] Update documentation about GGUF support
- [ ] Add integration tests with actual GGUF workflows

### Low Priority
- [ ] Investigate ComfyUI-JSON integration
- [ ] Add configuration for custom node repository overrides

## Additional Notes

### ComfyUI-GGUF Extension Details
- **Purpose**: Quantization support for ComfyUI models (FLUX, SD3.5, T5)
- **Installation**: `git clone https://github.com/city96/ComfyUI-GGUF`
- **Dependencies**: `gguf` Python package
- **Model Location**: `ComfyUI/models/unet/` for GGUF files

### Related Issues
- Custom node repository detection needs general improvement
- Consider implementing the suggested `comfyui-json` integration for better dependency analysis
- The current ComfyUI-Manager database may be incomplete for newer extensions

## Validation Steps
1. Fix the repository resolution for GGUF nodes
2. Test with the provided complex workflow
3. Verify no false warnings are generated
4. Confirm successful containerization with GGUF dependencies
