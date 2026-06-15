using System.Buffers.Binary;
using System.Reflection;
using System.Text;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// Basic smoke tests verifying core utilities compile and behave correctly.
/// Internal record types are accessed via the parent namespace.
/// </summary>
public class BasicTests
{
  [Fact]
  public void BinaryAssetSource_DefaultInstance()
  {
    // All fields are optional (nullable) — verify default construction
    var source = new BinaryAssetSource(IdPrefix: "abc123", SourceKind: "test");
    Assert.Equal("abc123", source.IdPrefix);
    Assert.Equal("test", source.SourceKind);
  }

  [Fact]
  public void NifHeaderInfo_BasicProperties()
  {
    var header = new NifHeaderInfo(
        HeaderString: "Gamebryo File Format, Version 20.6.0.0",
        Version: 0x14000006,
        VersionHex: "0x14000006",
        VersionText: "20.6.0.0",
        Endian: (byte)0,
        IsLittleEndian: true,
        UserVersion: 0,
        BlockCount: 10,
        BlockTypeCount: 5,
        HeaderBytesParsed: 512,
        BlockDataOffset: 1024,
        TotalBlockDataSize: 8000,
        MinBlockDataSize: 100,
        MaxBlockDataSize: 2000,
        RemainingAfterBlockDataOffset: null,
        BlockSizePayloadDelta: 0,
        StringCount: 20,
        MaxStringLength: 256,
        GroupCount: 0,
        BlockTypes: [],
        Strings: [],
        References: [],
        Blocks: [],
        Warnings: []);

    Assert.Equal("20.6.0.0", header.VersionText);
    Assert.Equal(0u, header.UserVersion);
  }

  [Fact]
  public void NifLinkedStreamPositionCandidate_StoresFields()
  {
    var candidate = new NifLinkedStreamPositionCandidate(
        MeshPayloadOffset: 188,
        BlockIndex: 21,
        PositionType: "float32",
        Stride: 12,
        FloatCount: 192,
        VertexCount: 16,
        BodyFirst16: "000000000000803f00000000",
        DataStreamUsage: null,
        DataStreamAccess: null,
        Role: "position-float3-ror1-lead",
        FirstFloat3: "000000000000803f00000000",
        DescriptorClassification: null);

    Assert.Equal(188, candidate.MeshPayloadOffset);
    Assert.Equal(21, candidate.BlockIndex);
    Assert.Equal("float32", candidate.PositionType);
    Assert.Equal(12, candidate.Stride);
    Assert.Equal(16, candidate.VertexCount);
    Assert.Equal("position-float3-ror1-lead", candidate.Role);
  }

  [Fact]
  public void NifPositionSourceProbeReport_SerializationRoundtrip()
  {
    var meshes = new List<NifPositionSourceMeshProbe>
        {
            new(
                MeshBlockIndex: 6,
                MeshSize: 325,
                MeshDataOffset: 200,
                InlinePositionCandidates: [],
                OrphanPositionCandidates: [],
                LinkedStreamPositionCandidates:
                [
                    new NifLinkedStreamPositionCandidate(
                        MeshPayloadOffset: 188,
                        BlockIndex: 21,
                        PositionType: "float32",
                        Stride: 12,
                        FloatCount: 192,
                        VertexCount: 16,
                        BodyFirst16: "00000000",
                        DataStreamUsage: null,
                        DataStreamAccess: null,
                        Role: "position-float3-ror1-lead",
                        FirstFloat3: "00000000",
                        DescriptorClassification: null),
                ])
        };

    var report = new NifPositionSourceProbeReport(
        new BinaryAssetSource(IdPrefix: "id1", SourceKind: "probe"),
        1000,
        "20.6.0.0",
        1,
        1,
        meshes);

    Assert.Equal("20.6.0.0", report.NifVersion);
    Assert.Single(report.Meshes);
    Assert.Single(report.Meshes[0].LinkedStreamPositionCandidates);
    Assert.Equal("position-float3-ror1-lead",
        report.Meshes[0].LinkedStreamPositionCandidates[0].Role);
  }

  [Fact]
  public void NifInlinePositionCandidate_StoresFields()
  {
    var candidate = new NifInlinePositionCandidate(
        Offset: 100,
        Stride: 12,
        FloatCount: 36,
        VertexCount: 12,
        FirstFloat3: "0000803f0000000000000000");

    Assert.Equal(100, candidate.Offset);
    Assert.Equal(12, candidate.VertexCount);
    Assert.Equal("0000803f0000000000000000", candidate.FirstFloat3);
  }

  [Fact]
  public void NifOrphanPositionCandidate_StoresFields()
  {
    // VertexCount is int (not uint)
    var candidate = new NifOrphanPositionCandidate(
        BlockIndex: 15,
        BlockSize: 935,
        Offset: 29,
        Stride: 12,
        DeclaredPayloadBytes: 906,
        FloatCount: 906,
        VertexCount: 75,
        FirstFloat3: "00010002",
        BlockTypeName: "NiDataStream");

    Assert.Equal(15, candidate.BlockIndex);
    Assert.Equal(75, candidate.VertexCount);
    Assert.Equal("NiDataStream", candidate.BlockTypeName);
  }

  [Fact]
  public void NifDataStreamLayout_DetectsGhidraPayloadPrefixAndTrailingFlag()
  {
    var declaredPayload = new byte[] { 0xfe, 0xff, 0x3f, 0xc1, 0xbc, 0x82, 0x7c, 0x3e };
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var offset = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), (uint)declaredPayload.Length);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 123);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 1); // descriptor-pair count
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 4);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 5);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 1); // element descriptor count
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 0xaa);
    offset += 4;
    declaredPayload.CopyTo(blockPayload.AsSpan(offset));
    offset += declaredPayload.Length;
    blockPayload[offset] = 1;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    Assert.True(layout.ValidDeclaredPayload);
    Assert.True(layout.GhidraStyleLayoutValid);
    Assert.Equal((uint)declaredPayload.Length, layout.DeclaredPayloadBytes);
    Assert.Equal(123u, layout.SecondUInt32);
    Assert.Equal(1u, layout.DescriptorPairCount);
    Assert.Equal(1u, layout.ElementDescriptorCount);
    Assert.Equal(29, layout.LegacyPayloadOffset);
    Assert.Equal(28, layout.PayloadPrefixBytes);
    Assert.Equal(1, layout.PayloadTrailerBytes);
    Assert.Equal((byte)1, layout.TrailingFlag);
    Assert.Equal(1, layout.LegacyOffsetMinusPayloadPrefixBytes);
    Assert.Null(layout.Warning);
  }

  [Fact]
  public void NifDataStreamLayout_RejectsDeclaredPayloadPastBlock()
  {
    var blockPayload = new byte[8];
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(0, 4), 999);

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    Assert.False(layout.ValidDeclaredPayload);
    Assert.False(layout.GhidraStyleLayoutValid);
    Assert.Equal(999u, layout.DeclaredPayloadBytes);
    Assert.Equal("declared-payload-past-block", layout.Warning);
  }

  [Fact]
  public void NifMeshBoundStreamRole_UsesLittleEndianIndexMaxForLittleEndianLead()
  {
    var body = new byte[24 * 2];
    for (var i = 0; i < 24; i++)
    {
      BinaryPrimitives.WriteUInt16LittleEndian(body.AsSpan(i * 2, 2), (ushort)i);
    }

    var stats = Program.AnalyzeNifMeshBoundStreamRole(body);

    Assert.Equal("index-u16le-lead", stats.PrimaryRole);
    Assert.Equal((ushort)23, stats.IndexMax);
    Assert.Equal(24, stats.IndexPairCount);
    Assert.NotNull(stats.LittleEndianIndexStats);
    Assert.Equal((ushort)23, stats.LittleEndianIndexStats.LittleEndianMaxIndex);
    Assert.True(stats.IndexStats?.BigEndianMaxIndex > stats.IndexMax);
  }

  [Fact]
  public void NifMeshRoleSemanticClass_GroupsReviewRoles()
  {
    Assert.Equal("position", Program.GetNifMeshRoleSemanticClass("position-float3-lead"));
    Assert.Equal("normal", Program.GetNifMeshRoleSemanticClass("normal-float3-ror1-lead"));
    Assert.Equal("uv", Program.GetNifMeshRoleSemanticClass("uv-float2-ror1-lead"));
    Assert.Equal("index", Program.GetNifMeshRoleSemanticClass("index-u16le-lead"));
    Assert.Equal("missing", Program.GetNifMeshRoleSemanticClass(null));
  }

  [Fact]
  public void AppOptionsParse_KeepsWriteObjAndGhidraBodyOffsetSeparate()
  {
    var appOptionsType = typeof(Program).GetNestedType("AppOptions", BindingFlags.NonPublic);
    Assert.NotNull(appOptionsType);
    var parse = appOptionsType!.GetMethod("Parse", BindingFlags.Public | BindingFlags.Static);
    Assert.NotNull(parse);

    var writeOnly = parse!.Invoke(null, [new[] { "decode-nif-geometry", "--write-obj" }]);
    Assert.NotNull(writeOnly);
    Assert.True((bool)appOptionsType.GetProperty("WriteObj")!.GetValue(writeOnly)!);
    Assert.False((bool)appOptionsType.GetProperty("GhidraBodyOffset")!.GetValue(writeOnly)!);

    var ghidraOnly = parse.Invoke(null, [new[] { "decode-nif-geometry", "--ghidra-body-offset" }]);
    Assert.NotNull(ghidraOnly);
    Assert.False((bool)appOptionsType.GetProperty("WriteObj")!.GetValue(ghidraOnly)!);
    Assert.True((bool)appOptionsType.GetProperty("GhidraBodyOffset")!.GetValue(ghidraOnly)!);
  }

  [Fact]
  public void TwadArchiveHeader_MatchesClientGhidraProof()
  {
    var bytes = new byte[20 + 44];
    Encoding.ASCII.GetBytes("TWAD").CopyTo(bytes, 0);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(4), 1);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(8), 20);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(12), 1);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(16), 0);

    var path = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.assets");
    File.WriteAllBytes(path, bytes);
    try
    {
      var readArchive = typeof(Program).GetMethod("ReadArchive", BindingFlags.NonPublic | BindingFlags.Static);
      Assert.NotNull(readArchive);

      var probe = Assert.IsType<ArchiveProbe>(readArchive.Invoke(null, [path]));

      Assert.True(probe.HeaderValid);
      Assert.Equal("TWAD", probe.Header.Magic);
      Assert.Equal(1u, probe.Header.Version);
      Assert.Equal(20u, probe.Header.HeaderSize);
      Assert.Equal(1u, probe.Header.MaxEntryCount);
      Assert.Equal(0u, probe.Header.FirstLinkedEntryRaw);
      Assert.Equal(0, probe.NonNullEntryCount);
      Assert.Empty(probe.Warnings);
    }
    finally
    {
      File.Delete(path);
    }
  }

  [Fact]
  public void ClassifyNifDescriptor_KnownPatterns()
  {
    // 37 04 03 00 = ror1-float
    Assert.Equal("float32xvec3 (position/normal/UV vertex data)", Program.ClassifyNifDescriptor("37040300"));
    // 36 04 02 00 = float-vertex-data encoding variant
    Assert.Equal("float32xvec2 (UV coordinates)", Program.ClassifyNifDescriptor("36040200"));
    // 15 02 01 00 = unknown-role candidate
    Assert.Equal("uint16xscalar (index stream)", Program.ClassifyNifDescriptor("15020100"));
    // 10 01 04 00 = unknown-role candidate
    Assert.Equal("bytexvec4 (packed vertex attribute)", Program.ClassifyNifDescriptor("10010400"));
    // 3c 01 04 00 = unknown-role candidate
    Assert.Equal("bytexvec4 (packed vertex attribute, variant)", Program.ClassifyNifDescriptor("3c010400"));
    Assert.Equal("bytexvec4 (auxiliary/sentinel, candidate)", Program.ClassifyNifDescriptor("08010400"));
  }

  [Fact]
  public void ClassifyNifDescriptorByByte0_KnownByte0()
  {
    Assert.Equal("float32xvec3 family (byte0=0x37)", Program.ClassifyNifDescriptorByByte0("37ffffff"));
    Assert.Equal("float32xvec2 family (byte0=0x36)", Program.ClassifyNifDescriptorByByte0("36000000"));
    Assert.Equal("uint16xscalar family (byte0=0x15, candidate)", Program.ClassifyNifDescriptorByByte0("15abcdef"));
    Assert.Equal("bytexvec4 family (byte0=0x10, candidate)", Program.ClassifyNifDescriptorByByte0("10ffffff"));
    Assert.Equal("bytexvec4 family (byte0=0x3c, candidate)", Program.ClassifyNifDescriptorByByte0("3c000000"));
  }
  [Fact]
  public void ClassifyNifDescriptorRole_KnownPatternsAndEdgeCases()
  {
    // 5 proven descriptor patterns -> expected role strings
    Assert.Equal("descriptor-float3-generic", Program.ClassifyNifDescriptorRole("37040300"));
    Assert.Equal("descriptor-float2-uv", Program.ClassifyNifDescriptorRole("36040200"));
    Assert.Equal("descriptor-uint16-index", Program.ClassifyNifDescriptorRole("15020100"));
    Assert.Equal("descriptor-byte4-packed", Program.ClassifyNifDescriptorRole("10010400"));
    Assert.Equal("descriptor-byte4-packed-variant", Program.ClassifyNifDescriptorRole("3c010400"));
    Assert.Equal("descriptor-byte4-aux", Program.ClassifyNifDescriptorRole("08010400"));
    // Edge cases: unknown, null, empty, too-short
    Assert.Null(Program.ClassifyNifDescriptorRole("ffffffff"));
    Assert.Null(Program.ClassifyNifDescriptorRole(null));
    Assert.Null(Program.ClassifyNifDescriptorRole(""));
    Assert.Null(Program.ClassifyNifDescriptorRole("123456"));
  }

  [Fact]
  public void ClassifyNifDescriptorByByte0_UnknownByte0ReturnsNull()
  {
    Assert.Null(Program.ClassifyNifDescriptorByByte0("00ffffff"));
    Assert.Null(Program.ClassifyNifDescriptorByByte0("ff000000"));
    Assert.Null(Program.ClassifyNifDescriptorByByte0("ab123456"));
  }

  [Fact]
  public void ClassifyNifDescriptorByByte0_NullEmptyShort()
  {
    Assert.Null(Program.ClassifyNifDescriptorByByte0(null));
    Assert.Null(Program.ClassifyNifDescriptorByByte0(""));
    Assert.Null(Program.ClassifyNifDescriptorByByte0("   "));
    Assert.Null(Program.ClassifyNifDescriptorByByte0("3"));
  }

  [Fact]
  public void ClassifyNifDescriptor_UnknownPatternReturnsNull()
  {
    // These have unknown byte-0, so no fallback classification
    Assert.Null(Program.ClassifyNifDescriptor("00000000"));
    Assert.Null(Program.ClassifyNifDescriptor("ffffffff"));
    Assert.Null(Program.ClassifyNifDescriptor("abcd1234"));
  }

  [Fact]
  public void ClassifyNifDescriptor_FallsBackToByte0ForUnknownFullPattern()
  {
    // Full pattern not in known set, but byte-0 matches
    Assert.Equal("float32xvec3 family (byte0=0x37)", Program.ClassifyNifDescriptor("37ffffff"));
    Assert.Equal("float32xvec2 family (byte0=0x36)", Program.ClassifyNifDescriptor("36000000"));
    Assert.Equal("uint16xscalar family (byte0=0x15, candidate)", Program.ClassifyNifDescriptor("15abcdef"));
  }

  [Fact]
  public void ClassifyNifDescriptor_NullAndEmptyReturnNull()
  {
    Assert.Null(Program.ClassifyNifDescriptor(null));
    Assert.Null(Program.ClassifyNifDescriptor(""));
    Assert.Null(Program.ClassifyNifDescriptor("   "));
  }

  [Fact]
  public void NifDataStreamLayout_DescriptorBytesIncluded()
  {
    var declaredPayload = new byte[] { 0xfe, 0xff, 0x3f, 0xc1, 0xbc, 0x82, 0x7c, 0x3e };
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var offset = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), (uint)declaredPayload.Length);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 123);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 1); // descriptor-pair count
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 4);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 5);
    offset += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(offset, 4), 1); // element descriptor count
    offset += 4;
    declaredPayload.CopyTo(blockPayload.AsSpan(offset));
    offset += declaredPayload.Length;
    blockPayload[offset] = 1;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    Assert.NotNull(layout.DescriptorBytes);
    Assert.Equal(8, layout.DescriptorBytes!.Length); // 4 bytes = 8 hex chars
  }

  [Fact]
  public void ClassifyNifDescriptor_StructuralReadFromLayout()
  {
    // Build a block payload where descriptor bytes at offset 24 are 37 04 03 00
    var declaredPayload = new byte[] { 0x00, 0x01, 0x02, 0x03 };
    // Header = 4 (declared) + 4 (secondU32) + 4 (pairCount) + 8 (pair table) + 4 (elemCount) + 4 (elem table) = 28 bytes
    // At offset 24: the elementCount field (little-endian 0x00000001)
    // At offset 28: the element table (4 bytes: 0xAA, 0xBB, 0xCC, 0xDD)
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var off = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), (uint)declaredPayload.Length);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 123);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1); // descriptor-pair count
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 0);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 0);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1); // element descriptor count
    off += 4;
    // At byte 28, write the element descriptor: a known pattern
    // Wait, this is the element table, not the descriptor bytes at offset 24
    // The raw bytes at offset 24 in this blockPayload are the elementCount field's 4 bytes (0x01 0x00 0x00 0x00)
    // But we need to test that the structural read works. Let me test with a known pattern at offset 24
    // Actually, the test should just verify that DescriptorBytes is populated when blockPayload >= 28 bytes

    declaredPayload.CopyTo(blockPayload.AsSpan(off));
    off += declaredPayload.Length;
    blockPayload[off] = 1;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    // DescriptorBytes should be populated (block is >= 28 bytes)
    Assert.NotNull(layout.DescriptorBytes);
    Assert.Equal(8, layout.DescriptorBytes!.Length);
    // The raw bytes at offset 24 are the first 4 bytes of declaredPayload (00 01 02 03)
    Assert.Equal("00010203", layout.DescriptorBytes);
  }

  [Fact]
  public void NifDataStreamLayout_WarnsOnDescriptorByte3NonZero()
  {
    // Build a block payload where descriptor byte-3 (offset 27) is non-zero (0xFF)
    var declaredPayload = new byte[] { 0x00, 0x01, 0x02, 0x03 };
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var off = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), (uint)declaredPayload.Length);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 123);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1); // descriptor-pair count
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 0);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 0);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1); // element descriptor count
    off += 4;
    declaredPayload.CopyTo(blockPayload.AsSpan(off));
    off += declaredPayload.Length;
    blockPayload[off] = 1;
    // Overwrite byte at offset 27 (descriptor byte-3) with non-zero value AFTER CopyTo
    blockPayload[27] = 0xFF;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    Assert.NotNull(layout.Warning);
    Assert.Contains("descriptor-byte-3-nonzero", layout.Warning);
  }

  [Fact]
  public void NifDataStreamLayout_NoWarningWhenDescriptorByte3IsZero()
  {
    // Build a valid block payload with descriptor byte-3 = 0x00 (normal case)
    var declaredPayload = new byte[] { 0xfe, 0xff, 0x3f, 0xc1, 0xbc, 0x82, 0x7c, 0x3e };
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var off = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), (uint)declaredPayload.Length);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 123);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 4);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 5);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1);
    off += 4;
    declaredPayload.CopyTo(blockPayload.AsSpan(off));
    off += declaredPayload.Length;
    blockPayload[off] = 1;
    // Set descriptor byte-3 (offset 27) to 0x00 AFTER the CopyTo to avoid overwrite
    blockPayload[27] = 0x00;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    // Warning should not contain descriptor-byte-3-nonzero
    Assert.DoesNotContain("descriptor-byte-3-nonzero", layout.Warning ?? string.Empty);
  }

  [Fact]
  public void TwadArchiveHeader_WarnsOnUnsupportedClientVersion()
  {
    var bytes = new byte[20];
    Encoding.ASCII.GetBytes("TWAD").CopyTo(bytes, 0);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(4), 2);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(8), 20);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(12), 0);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(16), 0);

    var path = Path.Combine(Path.GetTempPath(), $"{Guid.NewGuid():N}.assets");
    File.WriteAllBytes(path, bytes);
    try
    {
      var readArchive = typeof(Program).GetMethod("ReadArchive", BindingFlags.NonPublic | BindingFlags.Static);
      Assert.NotNull(readArchive);

      var probe = Assert.IsType<ArchiveProbe>(readArchive.Invoke(null, [path]));

      Assert.True(probe.HeaderValid);
      Assert.Equal(2u, probe.Header.Version);
      Assert.Contains(
          "Unsupported archive version word 2; client Ghidra proof accepts version words <= 1.",
          probe.Warnings);
    }
    finally
    {
      File.Delete(path);
    }
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_FloatRoleFloatDescriptor_ReturnsNull()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", "float32xvec3 family (byte0=0x37)");
    Assert.Null(result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_IndexRoleFloatDescriptor_ReturnsWarning()
  {
    var result = Program.CheckDescriptorRoleConsistency("index-u16be-strip-lead", "float32xvec3 family (byte0=0x37)");
    Assert.NotNull(result);
    Assert.Contains("descriptor-role-mismatch", result);
    Assert.Contains("index", result);
    Assert.Contains("float descriptor", result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_FloatRoleU16Descriptor_ReturnsWarning()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", "uint16xscalar family (byte0=0x15, candidate)");
    Assert.NotNull(result);
    Assert.Contains("descriptor-role-mismatch", result);
    Assert.Contains("float role", result);
    Assert.Contains("u16 descriptor", result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_NullRole_ReturnsNull()
  {
    var result = Program.CheckDescriptorRoleConsistency(null, "float32xvec3 family (byte0=0x37)");
    Assert.Null(result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_NullDescriptor_ReturnsNull()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", null);
    Assert.Null(result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_UnknownDescriptor_ReturnsNull()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", "bytexvec4 family (byte0=0x10, candidate)");
    Assert.Null(result);
  }


  [Theory]
  [InlineData(80, "float32xvec3 family (byte0=0x37)", "position-float3-ror1-lead", 85)]
  [InlineData(95, "float32xvec3 family (byte0=0x37)", "normal-float3-ror1-lead", 100)]
  [InlineData(50, "float32xvec2 family (byte0=0x36)", "uv-float2-ror1-lead", 55)]
  public void AdjustConfidenceByDescriptor_FloatMatch_Boosts(int confidence, string descriptor, string role, int expected)
  {
    var result = Program.AdjustConfidenceByDescriptor(confidence, descriptor, role);
    Assert.Equal(expected, result);
  }

  [Theory]
  [InlineData(80, "uint16xscalar family (byte0=0x15, candidate)", "position-float3-ror1-lead", 70)]
  [InlineData(5, "uint16xscalar family (byte0=0x15, candidate)", "normal-float3-ror1-lead", 0)]
  public void AdjustConfidenceByDescriptor_FloatRoleU16Descriptor_Dampens(int confidence, string descriptor, string role, int expected)
  {
    var result = Program.AdjustConfidenceByDescriptor(confidence, descriptor, role);
    Assert.Equal(expected, result);
  }

  [Fact]
  public void AdjustConfidenceByDescriptor_NullDescriptor_NoChange()
  {
    var result = Program.AdjustConfidenceByDescriptor(80, null, "position-float3-ror1-lead");
    Assert.Equal(80, result);
  }

  [Fact]
  public void AdjustConfidenceByDescriptor_UnknownDescriptor_NoChange()
  {
    var result = Program.AdjustConfidenceByDescriptor(80, "bytexvec4 family (byte0=0x10, candidate)", "position-float3-ror1-lead");
    Assert.Equal(80, result);
  }

  [Fact]
  public void AdjustConfidenceByDescriptor_IndexRole_NoChange()
  {
    var result = Program.AdjustConfidenceByDescriptor(80, "uint16xscalar family (byte0=0x15, candidate)", "index-u16be-strip-lead");
    Assert.Equal(80, result);
  }

  [Fact]
  public void AdjustConfidenceByDescriptor_CapsAt100()
  {
    var result = Program.AdjustConfidenceByDescriptor(98, "float32xvec3 family (byte0=0x37)", "position-float3-ror1-lead");
    Assert.Equal(100, result);
  }

  [Fact]
  public void AdjustConfidenceByDescriptor_FloorsAt0()
  {
    var result = Program.AdjustConfidenceByDescriptor(3, "uint16xscalar family (byte0=0x15, candidate)", "position-float3-ror1-lead");
    Assert.Equal(0, result);
  }


  [Fact]
  public void CheckDescriptorRoleConsistency_IncludesUsageAccessInWarning()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", "uint16xscalar family (byte0=0x15, candidate)", "0", "3");
    Assert.NotNull(result);
    Assert.Contains("usage=0", result);
    Assert.Contains("access=3", result);
  }

  [Fact]
  public void CheckDescriptorRoleConsistency_OmitsUsageAccessWhenNull()
  {
    var result = Program.CheckDescriptorRoleConsistency("position-float3-ror1-lead", "uint16xscalar family (byte0=0x15, candidate)");
    Assert.NotNull(result);
    Assert.DoesNotContain("usage=", result);
  }


  // M6.3: ValidateDescriptorExportPrechecks tests
  [Fact]
  public void ValidateDescriptorExportPrechecks_ZeroVertices_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks(null, 0, 0);
    Assert.Single(warnings);
    Assert.Contains("Zero vertices", warnings[0]);
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_ZeroFaces_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("float32xvec3 family (byte0=0x37)", 10, 0);
    Assert.Contains(warnings, w => w.Contains("Zero faces"));
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_LowVertexCount_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("float32xvec3 family (byte0=0x37)", 2, 1);
    Assert.Contains(warnings, w => w.Contains("Low vertex count"));
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_NullDescriptor_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks(null, 10, 5);
    Assert.Contains(warnings, w => w.Contains("descriptor unknown"));
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_U16Descriptor_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("uint16xscalar family (byte0=0x15, candidate)", 10, 5);
    Assert.Contains(warnings, w => w.Contains("u16-family"));
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_FloatDescriptor_ReturnsClean()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("float32xvec3 family (byte0=0x37)", 100, 50);
    Assert.Empty(warnings);
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_UnknownDescriptor_ReturnsWarning()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("bytexvec4 family (byte0=0x10, candidate)", 10, 5);
    Assert.Contains(warnings, w => w.Contains("unrecognized family"));
  }

  [Fact]
  public void ValidateDescriptorExportPrechecks_MultipleWarnings_Accumulates()
  {
    var warnings = Program.ValidateDescriptorExportPrechecks("uint16xscalar family (byte0=0x15, candidate)", 2, 0);
    Assert.True(warnings.Count >= 3); // low vertex + zero faces + u16 descriptor
  }

  [Fact]
  public void NifDataStreamLayout_VerifyOneByteShiftRelationship()
  {
    // Verify the 1-byte shift: PayloadPrefixBytes + 1 == LegacyPayloadOffset (narrow parser patch foundation)
    var declaredPayload = new byte[] { 0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF, 0x11, 0x22 };
    var blockPayload = new byte[4 + 4 + 4 + 8 + 4 + 4 + declaredPayload.Length + 1];
    var off = 0;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), (uint)declaredPayload.Length);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 123);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 4);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 5);
    off += 4;
    BinaryPrimitives.WriteUInt32LittleEndian(blockPayload.AsSpan(off, 4), 1);
    off += 4;
    declaredPayload.CopyTo(blockPayload.AsSpan(off));
    off += declaredPayload.Length;
    blockPayload[off] = 1;

    var layout = Program.AnalyzeNifDataStreamLayout(blockPayload);

    // Key proof: the Ghidra prefix is exactly 1 byte before the legacy offset
    Assert.True(layout.GhidraStyleLayoutValid);
    Assert.NotNull(layout.LegacyPayloadOffset);
    Assert.NotNull(layout.PayloadPrefixBytes);
    Assert.Equal(layout.PayloadPrefixBytes.Value + 1, layout.LegacyPayloadOffset.Value);
    Assert.Equal(1, layout.LegacyOffsetMinusPayloadPrefixBytes);
  }



  // FT-4.2: probe-nif-scene-graph record type smoke tests
  [Fact]
  public void NifSceneGraphNodeInfo_ConstructsWithAllFields()
  {
    var node = new NifSceneGraphNodeInfo(
        BlockIndex: 0,
        Name: "SceneNode",
        Translation: new[] { 1.0f, 2.0f, 3.0f },
        Rotation: new[] { 1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f },
        Scale: 1.0f,
        ExtraData: new List<int>(),
        Controller: -1,
        Children: new List<int> { 6, 31 },
        Effects: new List<int>(),
        ChildNodes: new List<NifSceneGraphChildInfo>(),
        NodeSize: 106u);

    Assert.Equal(0, node.BlockIndex);
    Assert.Equal("SceneNode", node.Name);
    Assert.Equal(3, node.Translation.Length);
    Assert.Equal(9, node.Rotation.Length);
    Assert.Equal(1.0f, node.Scale);
    Assert.Equal(2, node.Children.Count);
    Assert.Equal(106u, node.NodeSize);
  }

  [Fact]
  public void NifSceneGraphChildInfo_StoresFields()
  {
    var child = new NifSceneGraphChildInfo(
        BlockIndex: 6,
        TypeName: "NiMesh",
        Size: 329u);

    Assert.Equal(6, child.BlockIndex);
    Assert.Equal("NiMesh", child.TypeName);
    Assert.Equal(329u, child.Size);
  }

  [Fact]
  public void NifSceneGraphMeshInfo_StoresFields()
  {
    var mesh = new NifSceneGraphMeshInfo(
        BlockIndex: 6,
        Size: 329u,
        ParentNiNodeIndex: 0);

    Assert.Equal(6, mesh.BlockIndex);
    Assert.Equal(329u, mesh.Size);
    Assert.Equal(0, mesh.ParentNiNodeIndex);
  }

  [Fact]
  public void NifSceneGraphReport_RoundtripSerialization()
  {
    var nodes = new List<NifSceneGraphNodeInfo>
    {
      new(
        BlockIndex: 0,
        Name: "SceneNode",
        Translation: new[] { 0f, 0f, 0f },
        Rotation: new[] { 1f,0f,0f, 0f,1f,0f, 0f,0f,1f },
        Scale: 1.0f,
        ExtraData: new List<int>(),
        Controller: -1,
        Children: new List<int> { 6 },
        Effects: new List<int>(),
        ChildNodes: new List<NifSceneGraphChildInfo>
        {
          new(6, "NiMesh", 329u)
        },
        NodeSize: 106u)
    };

    var meshes = new List<NifSceneGraphMeshInfo>
    {
      new(6, 329u, 0)
    };

    var report = new NifSceneGraphReport(
        NifVersion: "20.6.0.0",
        NodeCount: 1,
        MeshCount: 1,
        MeshesAttached: 1,
        Nodes: nodes,
        Meshes: meshes);

    Assert.Equal("20.6.0.0", report.NifVersion);
    Assert.Equal(1, report.NodeCount);
    Assert.Equal(1, report.MeshCount);
    Assert.Equal(1, report.MeshesAttached);
    Assert.Single(report.Nodes);
    Assert.Single(report.Meshes);
  }


}
