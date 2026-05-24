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
        FirstFloat3: "000000000000803f00000000");

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
                        FirstFloat3: "00000000"),
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
}
