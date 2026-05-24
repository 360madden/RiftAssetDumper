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
