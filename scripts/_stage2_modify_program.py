#!/usr/bin/env python3
"""Edit Program.cs to add ExperimentalPositionSource flag."""

with open('src/RiftAssetDumper/Program.cs', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. AppOptions record - add ExperimentalPositionSource field
old1 = '      bool Experimental,\n      bool WriteObj)\n  {'
new1 = '      bool Experimental,\n      bool ExperimentalPositionSource,\n      bool WriteObj)\n  {'
if old1 in content:
    content = content.replace(old1, new1, 1)
    changes += 1
    print('OK: AppOptions record')
else:
    idx = content.find('      bool Experimental,')
    print(f'FAIL AppOptions record at {idx}')
    if idx >= 0:
        print(repr(content[idx:idx+80]))

# 2. Var declaration
old2 = '      var experimental = false;\n      var writeObj = false;'
new2 = '      var experimental = false;\n      var experimentalPositionSource = false;\n      var writeObj = false;'
if old2 in content:
    content = content.replace(old2, new2, 1)
    changes += 1
    print('OK: var declaration')
else:
    idx = content.find('var experimental = false;')
    print(f'FAIL var declaration at {idx}')
    if idx >= 0:
        print(repr(content[idx:idx+80]))

# 3. Case parsing - insert after --experimental case
old3_search = 'case "--experimental":\n            experimental = true;\n            break;\n          case "--write-obj"'
idx = content.find(old3_search)
if idx >= 0:
    end_idx = content.find('\n            break;', idx + len(old3_search))
    old3 = content[idx:end_idx + 16]
    new3 = old3.replace(
        'case "--experimental":\n            experimental = true;\n            break;\n          case "--write-obj"',
        'case "--experimental":\n            experimental = true;\n            break;\n          case "--experimental-position-source":\n            experimentalPositionSource = true;\n            break;\n          case "--write-obj"'
    )
    content = content[:idx] + new3 + content[end_idx + 16:]
    changes += 1
    print('OK: case parsing')
else:
    print('FAIL case parsing')

# 4. Constructor call
old4 = '          experimental,\n          writeObj);'
new4 = '          experimental,\n          experimentalPositionSource,\n          writeObj);'
if content.count(old4) == 1:
    content = content.replace(old4, new4, 1)
    changes += 1
    print('OK: constructor')
else:
    print(f'FAIL constructor count={content.count(old4)}')

# 5. Help usage line
old5 = 'Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- decode-nif-geometry --root <SourceFolder> --id <16hex> --mesh-block <n> [--write-obj] [--experimental]");'
new5 = 'Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- decode-nif-geometry --root <SourceFolder> --id <16hex> --mesh-block <n> [--write-obj] [--experimental] [--experimental-position-source]");'
if old5 in content:
    content = content.replace(old5, new5, 1)
    changes += 1
    print('OK: help usage')
else:
    idx = content.find('decode-nif-geometry --root')
    print(f'FAIL help usage at {idx}')
    if idx >= 0:
        print(repr(content[idx-5:idx+150]))

# 6. Help description
old6 = 'Console.WriteLine("  --write-obj"); Console.WriteLine("                  Write decoded geometry to Wavefront OBJ file");'
new6 = 'Console.WriteLine("  --experimental-position-source"); Console.WriteLine("                  Use linked-stream position-source probe when no attribute sets found");\n      Console.WriteLine("  --write-obj"); Console.WriteLine("                  Write decoded geometry to Wavefront OBJ file");'
if old6 in content:
    content = content.replace(old6, new6, 1)
    changes += 1
    print('OK: help description')
else:
    idx = content.find('--write-obj')
    print(f'FAIL help description at {idx}')
    if idx >= 0:
        print(repr(content[idx-30:idx+100]))

# 7. DecodeNifGeometry - modify the no-attribute-sets block (first occurrence)
old7 = '    if (attributeSets.Count == 0)\n    {\n      Console.Error.WriteLine("ERROR: no attribute sets found for this mesh.");\n      return 1;\n    }'
if content.count(old7) == 2:
    # Use context to target only the DecodeNifGeometry one
    old7_ctx = '    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);\n\n    if (attributeSets.Count == 0)\n    {\n      Console.Error.WriteLine("ERROR: no attribute sets found for this mesh.");\n      return 1;\n    }\n\n    Console.WriteLine($"NIF geometry decode:'
    new7_ctx = '    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);\n\n    var objVertices = new List<string>();\n    var objNormals = new List<string>();\n    var objTexCoords = new List<string>();\n    var objFaces = new List<string>();\n    var totalPositions = 0;\n    var totalNormals = 0;\n    var totalUvs = 0;\n    var objVertexBase = 0;\n\n    if (attributeSets.Count == 0)\n    {\n      if (options.ExperimentalPositionSource)\n      {\n        Console.WriteLine("  [*] ExperimentalPositionSource mode: scanning linked streams for position candidates...");\n        var linkedCandidates = ScanNifLinkedStreamPositionCandidates(payload, header, streamSummaries);\n        Console.WriteLine($"    linked stream candidates: {linkedCandidates.Count}");\n        var float32Candidates = linkedCandidates.Where(static c => c.PositionType == "float32").ToList();\n        if (float32Candidates.Count > 0)\n        {\n          Console.WriteLine($"    float32 position candidates: {float32Candidates.Count}");\n          foreach (var candidate in float32Candidates.Take(4))\n          {\n            Console.WriteLine($"      #{candidate.BlockIndex} offset=@{candidate.MeshPayloadOffset} type={candidate.PositionType} vertexCount={candidate.VertexCount} role={candidate.Role}");\n          }\n\n          // Decode positions from the first float32 candidate\n          var leadCandidate = float32Candidates[0];\n          var vertexCount = leadCandidate.VertexCount;\n          var vertexIndices = Enumerable.Range(0, vertexCount).ToList();\n          var positionSamples = BuildNifAttributeFloatVertexSamples(\n              payload, blocksByIndex, leadCandidate.BlockIndex,\n              "position", leadCandidate.Role, components: 3, vertexIndices);\n          Console.WriteLine($"    decoded positions: {positionSamples.Count}/{vertexCount}");\n\n          // Print sample vertices\n          var sampleCount = Math.Min(4, vertexCount);\n          if (positionSamples.Count > 0)\n          {\n            Console.WriteLine($"    position samples ({sampleCount}):");\n            for (var i = 0; i < sampleCount && i < positionSamples.Count; i++)\n            {\n              var s = positionSamples[i];\n              Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)}, {FormatNullableDouble(s.Z)}) prevDist={FormatNullableDouble(s.PreviousDistance)} nextDist={FormatNullableDouble(s.NextDistance)}");\n            }\n          }\n\n          // Build OBJ data\n          if (options.WriteObj)\n          {\n            for (var i = 0; i < positionSamples.Count; i++)\n            {\n              var s = positionSamples[i];\n              if (s.X.HasValue && s.Y.HasValue && s.Z.HasValue)\n              {\n                objVertices.Add($"v {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Z.Value.ToString("F6", CultureInfo.InvariantCulture)}");\n              }\n            }\n          }\n\n          totalPositions += positionSamples.Count;\n        }\n        else\n        {\n          Console.Error.WriteLine("ERROR: no float32 position candidates found in linked streams.");\n          Console.WriteLine($"  Found {linkedCandidates.Count} non-float32 candidates: {string.Join(", ", linkedCandidates.Select(static c => c.PositionType).Distinct())}");\n        }\n      }\n      else\n      {\n        Console.Error.WriteLine("ERROR: no attribute sets found for this mesh. Use --experimental-position-source to probe linked streams.");\n      }\n\n      if (objVertices.Count == 0)\n      {\n        return 1;\n      }\n    }\n\n    Console.WriteLine($"NIF geometry decode:'
    if old7_ctx in content:
        content = content.replace(old7_ctx, new7_ctx, 1)
        changes += 1
        print('OK: DecodeNifGeometry fallback')
    else:
        print('FAIL DecodeNifGeometry fallback - context not found')
        idx = content.find('    var blocksByIndex = header.Blocks.ToDictionary')
        if idx >= 0:
            print(repr(content[idx:idx+250]))
else:
    print(f'FAIL: attrsets block count = {content.count(old7)}')

with open('src/RiftAssetDumper/Program.cs', 'w', encoding='utf-8') as f:
    f.write(content)
print(f'\nDone: {changes} changes applied')
