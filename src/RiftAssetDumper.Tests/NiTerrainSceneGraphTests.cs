using System.Buffers.Binary;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// RA-2e: NiAVObject source layout, properties/collision and hierarchy safety.
/// Synthetic bytes only; no game assets or inferred world transforms.
/// </summary>
public class NiTerrainSceneGraphTests
{
  [Fact]
  public void TerrainNode_ParsesPropertiesBeforeItsExplicitMeshChild()
  {
    var payload = MakeNode();
    var parsed = global::Program.ParseNifSceneGraphNodePayload(payload);
    Assert.Equal(-1, parsed.NameIndex);
    Assert.Empty(parsed.ExtraData);
    Assert.Equal(-1, parsed.Controller);
    Assert.Equal((ushort)0x110, parsed.Flags);
    Assert.Equal(new[] { 8960f, 0f, 6400f }, parsed.Translation);
    Assert.Equal(new[] { 1f, 0f, 0f, 0f, 1f, 0f, 0f, 0f, 1f }, parsed.Rotation);
    Assert.Equal(1f, parsed.Scale);
    Assert.Equal(new[] { 1 }, parsed.Properties);
    Assert.Equal(-1, parsed.CollisionIndex);
    Assert.Equal(new[] { 2 }, parsed.Children);
    Assert.Empty(parsed.Effects);
    Assert.Equal(90, parsed.BytesParsed);
  }

  [Fact]
  public void DynamicExtraDataAndOptionalEffectSentinelAreHandled()
  {
    var bytes = MakeNode(extraData: [3, 4], children: [2], includeEffectSentinel: true);
    var result = global::Program.ParseNifSceneGraphNodePayload(bytes);
    Assert.Equal(new[] { 3, 4 }, result.ExtraData);
    Assert.Equal(new[] { 1 }, result.Properties);
    Assert.Equal(new[] { 2 }, result.Children);
    Assert.Equal(-1, result.Controller);
    Assert.Equal(102, result.BytesParsed);
  }

  [Fact]
  public void AbsentEffectCountIsAllowedButPartialCountIsRejected()
  {
    var payload = MakeNode(includeEffectCount: false);
    var parsed = global::Program.ParseNifSceneGraphNodePayload(payload);
    Assert.Equal(86, parsed.BytesParsed);
    Assert.Empty(parsed.Effects);

    var partial = payload.Concat(new byte[] { 0, 0 }).ToArray();
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(partial));
  }

  [Fact]
  public void EmptyChildListDoesNotClaimAnImplicitMeshAttachment()
  {
    var bytes = MakeNode(children: []);
    var parsed = global::Program.ParseNifSceneGraphNodePayload(bytes);
    Assert.Empty(parsed.Children);
    Assert.Equal(new[] { 1 }, parsed.Properties);
    Assert.Equal(-1, parsed.CollisionIndex);
  }

  [Fact]
  public void RejectsUnsupportedPropertyCountBeforeReadingChildren()
  {
    var bytes = MakeNode();
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(66, 4), 1000);
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes));
  }

  [Fact]
  public void RejectsUnboundedChildCountAndTruncatedChildren()
  {
    var bytes = MakeNode();
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(78, 4), 500);
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes));
    bytes = MakeNode();
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes[..83]));
  }

  [Fact]
  public void RejectsBadExtraDataCountAndNonFiniteTransform()
  {
    var bytes = MakeNode();
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(4, 4), 100);
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes));
    bytes = MakeNode();
    BinaryPrimitives.WriteSingleLittleEndian(bytes.AsSpan(14, 4), float.NaN);
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes));
    bytes = MakeNode();
    BinaryPrimitives.WriteSingleLittleEndian(bytes.AsSpan(62, 4), 0f);
    Assert.Throws<InvalidDataException>(() => global::Program.ParseNifSceneGraphNodePayload(bytes));
  }

  private static byte[] MakeNode(
      int[]? extraData = null, int[]? children = null,
      bool includeEffectSentinel = false, bool includeEffectCount = true)
  {
    extraData ??= [];
    children ??= [2];
    using var stream = new MemoryStream();
    using var writer = new BinaryWriter(stream);
    writer.Write(-1); // string index
    writer.Write((uint)extraData.Length);
    foreach (var extra in extraData) writer.Write(extra);
    writer.Write(-1); // controller
    writer.Write((ushort)0x110); // flags
    writer.Write(8960f);
    writer.Write(0f);
    writer.Write(6400f);
    for (var index = 0; index < 9; index++) writer.Write(index is 0 or 4 or 8 ? 1f : 0f);
    writer.Write(1f); // scale
    writer.Write(1u); // property count
    writer.Write(1); // property block
    writer.Write(-1); // no collision block
    writer.Write((uint)children.Length);
    foreach (var child in children) writer.Write(child);
    if (includeEffectSentinel) writer.Write(-1);
    if (includeEffectCount) writer.Write(0u); // optional effect count
    return stream.ToArray();
  }
}
