using System.Buffers.Binary;
using System.Text;
using System.Text.Json;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// Exercises list-entries --id against a synthetic TWAM manifest, without game assets.
/// </summary>
public class ManifestIdFilterTests
{
  [Fact]
  public void ListEntries_WithoutId_RetainsOriginalListingAndLimit()
  {
    WithManifest((root, manifestPath) =>
    {
      var outputPath = Path.Combine(root, "all.jsonl");
      var rc = global::Program.Main(
          ["list-entries", "--root", root, "--manifest", manifestPath,
           "--limit", "2", "--out", outputPath]);
      Assert.Equal(0, rc);
      var lines = File.ReadAllLines(outputPath);
      Assert.Equal(2, lines.Length);
      using var first = JsonDocument.Parse(lines[0]);
      using var second = JsonDocument.Parse(lines[1]);
      Assert.Equal(0, first.RootElement.GetProperty("Index").GetInt32());
      Assert.Equal(1, second.RootElement.GetProperty("Index").GetInt32());
    });
  }

  [Fact]
  public void ListEntries_ExactIdFilter_PreservesDuplicateRowsAndOrder()
  {
    WithManifest((root, manifestPath) =>
    {
      var outputPath = Path.Combine(root, "matches.jsonl");
      var rc = global::Program.Main(
          ["list-entries", "--root", root, "--manifest", manifestPath,
           "--id", "AABBCCDDEEFF0011", "--out", outputPath]);

      Assert.Equal(0, rc);
      var lines = File.ReadAllLines(outputPath);
      Assert.Equal(2, lines.Length);
      using var first = JsonDocument.Parse(lines[0]);
      using var second = JsonDocument.Parse(lines[1]);
      Assert.Equal("aabbccddeeff0011", first.RootElement.GetProperty("IdPrefix").GetString());
      Assert.Equal("aabbccddeeff0011", second.RootElement.GetProperty("IdPrefix").GetString());
      Assert.Equal(0, first.RootElement.GetProperty("Index").GetInt32());
      Assert.Equal(2, second.RootElement.GetProperty("Index").GetInt32());
      Assert.Equal(101, first.RootElement.GetProperty("PakOffset").GetInt32());
      Assert.Equal(103, second.RootElement.GetProperty("PakOffset").GetInt32());
    });
  }

  [Fact]
  public void ListEntries_IdFilter_AppliesLimitAfterFiltering()
  {
    WithManifest((root, manifestPath) =>
    {
      var outputPath = Path.Combine(root, "limited.jsonl");
      var rc = global::Program.Main(
          ["list-entries", "--root", root, "--manifest", manifestPath,
           "--id", "aabbccddeeff0011", "--limit", "1", "--out", outputPath]);
      Assert.Equal(0, rc);
      var lines = File.ReadAllLines(outputPath);
      Assert.Single(lines);
      using var result = JsonDocument.Parse(lines[0]);
      Assert.Equal(0, result.RootElement.GetProperty("Index").GetInt32());
    });
  }

  [Fact]
  public void ListEntries_NoMatchingId_WritesEmptyFileNotFalsePositive()
  {
    WithManifest((root, manifestPath) =>
    {
      var outputPath = Path.Combine(root, "missing.jsonl");
      var rc = global::Program.Main(
          ["list-entries", "--root", root, "--manifest", manifestPath,
           "--id", "ffffffffffffffff", "--out", outputPath]);
      Assert.Equal(0, rc);
      Assert.Empty(File.ReadAllLines(outputPath));
    });
  }

  [Fact]
  public void ListEntries_InvalidId_RefusesBeforeWriting()
  {
    WithManifest((root, manifestPath) =>
    {
      var outputPath = Path.Combine(root, "invalid.jsonl");
      var rc = global::Program.Main(
          ["list-entries", "--root", root, "--manifest", manifestPath,
           "--id", "not-an-id", "--out", outputPath]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(outputPath));
    });
  }

  private static void WithManifest(Action<string, string> action)
  {
    var root = Path.Combine(Path.GetTempPath(), $"rad-twam-{Guid.NewGuid():N}");
    Directory.CreateDirectory(root);
    try
    {
      var path = Path.Combine(root, "fixture.manifest");
      File.WriteAllBytes(path, BuildManifest());
      action(root, path);
    }
    finally
    {
      Directory.Delete(root, recursive: true);
    }
  }

  private static byte[] BuildManifest()
  {
    const int headerSize = 0x50;
    const int entryStride = 58;
    const int rowCount = 3;
    var bytes = new byte[headerSize + entryStride * rowCount];
    Encoding.ASCII.GetBytes("TWAM").CopyTo(bytes, 0);

    // Table 0 (PAKs) is empty; Table 1 (manifest rows) has three entries.
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(16, 4), headerSize);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(28, 4), 53);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(32, 4), headerSize);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(36, 4), entryStride * rowCount);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(40, 4), rowCount);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(44, 4), entryStride);

    var ids = new[] { "aabbccddeeff0011", "0000111122223333", "aabbccddeeff0011" };
    for (var i = 0; i < rowCount; i++)
    {
      var row = headerSize + i * entryStride;
      Convert.FromHexString(ids[i]).CopyTo(bytes, row);
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(row + 8, 4), (uint)(0xBEEF + i));
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(row + 12, 4), (uint)(101 + i));
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(row + 16, 4), 8);
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(row + 20, 4), 16);
      BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(row + 24, 2), 2);
      bytes.AsSpan(row + 32, 20).Fill((byte)(i + 1));
      BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(row + 56, 2), 7);
    }
    return bytes;
  }
}
