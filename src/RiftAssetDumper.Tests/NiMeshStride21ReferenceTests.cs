using System.Buffers.Binary;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// RA-2c: targeted 21-byte NiMesh stream-reference recovery.
/// Only repeated validated stream IDs qualify; random unaligned integers do not.
/// </summary>
public class NiMeshStride21ReferenceTests
{
  [Fact]
  public void FindsFiveConsecutiveNiDataStreamReferencesAtUnalignedOffsets()
  {
    var payload = MakePayload(20, 21, 22, 23, 24);
    var eligible = new HashSet<int> { 20, 21, 22, 23, 24 };
    var refs = Program.FindConstrainedNiMeshStreamReferences(payload, eligible);

    Assert.Equal(5, refs.Count);
    Assert.Equal(new[] { 134, 155, 176, 197, 218 }, refs.Select(x => x.Offset));
    Assert.Equal(new[] { 20, 21, 22, 23, 24 }, refs.Select(x => x.TargetIndex));
  }

  [Fact]
  public void RejectsBrokenSequenceEvenIfSomeIntegersLookLikeStreams()
  {
    var payload = MakePayload(20, 21, 99, 23, 24);
    var eligible = new HashSet<int> { 20, 21, 22, 23, 24 };
    Assert.Empty(Program.FindConstrainedNiMeshStreamReferences(payload, eligible));
  }

  [Fact]
  public void RejectsRepeatedSameTargetAndUnrelatedNumericNoise()
  {
    var payload = MakePayload(20, 20, 20, 20, 20);
    var eligible = new HashSet<int> { 20, 21, 22, 23, 24 };
    Assert.Empty(Program.FindConstrainedNiMeshStreamReferences(payload, eligible));

    var simple = new byte[243];
    BinaryPrimitives.WriteUInt32LittleEndian(simple.AsSpan(176, 4), 22);
    Assert.Empty(Program.FindConstrainedNiMeshStreamReferences(simple, eligible));
  }

  [Fact]
  public void RejectsSequenceWhenAnyTargetIsNotAnEligibleStream()
  {
    var payload = MakePayload(20, 21, 22, 23, 24);
    // No three consecutive valid, distinct refs after excluding the middle #22.
    var eligible = new HashSet<int> { 20, 21, 23, 24 };
    Assert.Empty(Program.FindConstrainedNiMeshStreamReferences(payload, eligible));
  }

  private static byte[] MakePayload(params int[] ids)
  {
    var payload = new byte[243];
    for (var i = 0; i < ids.Length; i++)
    {
      BinaryPrimitives.WriteInt32LittleEndian(payload.AsSpan(134 + 21 * i, 4), ids[i]);
    }
    return payload;
  }
}
