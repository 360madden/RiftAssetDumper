using System.Buffers.Binary;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// RA-2h: a NiMesh target-block index is NOT its attribute-name string index.
/// The 21-byte binding record stores that name index at byte offset +13.
/// </summary>
public class NiMeshSemanticNameTests
{
  [Fact]
  public void RecoversNamesFromBindingStringFieldsRatherThanTargetBlockIds()
  {
    var payload = MakeMesh();
    var refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 22, 23, 24 });
    var names = Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, MakeStrings());
    Assert.Equal(5, names.Count);
    Assert.Equal(new[] { 20, 21, 22, 23, 24 }, names.Select(v => v.TargetBlockIndex));
    Assert.Equal(new[] { 16, 17, 18, 19, 20 }, names.Select(v => v.SemanticStringIndex));
    Assert.Equal(new[] { "INDEX", "POSITION", "NORMAL", "COLOR", "TEXCOORD" },
        names.Select(v => v.SemanticName));
    Assert.Equal(new[] { 134, 155, 176, 197, 218 }, names.Select(v => v.MeshPayloadOffset));
    // Target block #20 also happens to be a string-table index: TEXCOORD.
    // The source record at +13 is #16, which actually says INDEX.
    Assert.Equal("TEXCOORD", MakeStrings()[20].Value);
    Assert.Equal("INDEX", names[0].SemanticName);
  }

  [Fact]
  public void MutatedNameIndexOrNameFailsWithoutFalseSemantic()
  {
    var payload = MakeMesh();
    BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 13, 4), 20);
    var refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 22, 23, 24 });
    Assert.Empty(Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, MakeStrings()));

    payload = MakeMesh();
    var strings = MakeStrings();
    strings[16] = new NifStringInfo(16, "INVALID");
    refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 22, 23, 24 });
    Assert.Empty(Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, strings));
  }

  [Theory]
  [InlineData(4)]
  [InlineData(5)]
  [InlineData(9)]
  [InlineData(17)]
  public void UnexpectedBindingHeaderBytesNeverPromoteNames(int byteOffset)
  {
    var payload = MakeMesh();
    payload[134 + byteOffset] = 9;
    var refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 22, 23, 24 });
    Assert.Empty(Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, MakeStrings()));
  }

  [Fact]
  public void BrokenOrShortBindingSequenceProducesNoSemantics()
  {
    var payload = MakeMesh();
    var refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 23, 24 });
    Assert.Empty(Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, MakeStrings()));

    payload = MakeMesh()[..219];
    refs = new List<(int Offset, int TargetIndex)>
    {
      (134, 20), (155, 21), (176, 22), (197, 23), (218, 24),
    };
    Assert.Empty(Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, MakeStrings()));
  }

  [Fact]
  public void StringTableIndicesNeedNotMatchStreamBlockIndices()
  {
    var payload = MakeMesh();
    var refs = Program.FindConstrainedNiMeshStreamReferences(
        payload, new HashSet<int> { 20, 21, 22, 23, 24 });
    for (var i = 0; i < 5; i++)
    {
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i + 13, 4), i + 4);
    }

    var strings = Enumerable.Range(0, 21)
        .Select(index => new NifStringInfo(index, index is >= 4 and <= 8
            ? new[] { "INDEX", "POSITION", "NORMAL", "COLOR", "TEXCOORD" }[index - 4]
            : $"OTHER-{index}"))
        .ToList();
    var names = Program.ResolveConstrainedNiMeshSemanticBindings(payload, refs, strings);
    Assert.Equal(new[] { 4, 5, 6, 7, 8 }, names.Select(v => v.SemanticStringIndex));
    Assert.Equal("INDEX", names[0].SemanticName);
  }

  private static byte[] MakeMesh()
  {
    var payload = new byte[243];
    for (var i = 0; i < 5; i++)
    {
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i, 4), i + 20);
      payload[134 + 21 * i + 4] = 0;
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i + 5, 4), 1);
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i + 9, 4), 1);
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i + 13, 4), i + 16);
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i + 17, 4), 0);
    }
    return payload;
  }

  private static List<NifStringInfo> MakeStrings() =>
      Enumerable.Range(0, 21)
          .Select(index => new NifStringInfo(index, index is >= 16 and <= 20
              ? new[] { "INDEX", "POSITION", "NORMAL", "COLOR", "TEXCOORD" }[index - 16]
              : $"OTHER-{index}"))
          .ToList();
}
