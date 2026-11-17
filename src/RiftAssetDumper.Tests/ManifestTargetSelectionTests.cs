using System.Buffers.Binary;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Xunit;

namespace RiftAssetDumper.Tests;

/// <summary>
/// RA-1.5a: explicit manifest row selection when several filename rows share one content ID.
/// Fixture contains one tiny raw TWAD payload and three synthetic TWAM rows.
/// </summary>
public class ManifestTargetSelectionTests
{
  [Fact]
  public void ProbeBinary_ExplicitIndexOverridesFirstIdMatch()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "selected.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id,
           "--manifest-index", "2", "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      var source = report.RootElement.GetProperty("Source");
      Assert.Equal(2, source.GetProperty("ManifestEntryIndex").GetInt32());
      Assert.Equal(9, source.GetProperty("PakIndex").GetInt32());
      Assert.Equal(102, source.GetProperty("PakOffset").GetInt32());
      Assert.Equal(id, source.GetProperty("IdPrefix").GetString());
      Assert.Equal("dds", report.RootElement.GetProperty("Type").GetString());
    });
  }

  [Fact]
  public void ProbeBinary_ExplicitIndexWithConflictingIdRefusesOutput()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "mismatch.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id,
           "--manifest-index", "1", "--out", output]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(output));
    });
  }

  [Fact]
  public void ProbeBinary_ExplicitIndexWithConflictingFnvRefusesOutput()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "fnv-mismatch.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id,
           "--manifest-index", "2", "--fnv", "0xAABB", "--out", output]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(output));
    });
  }

  [Fact]
  public void ProbeBinary_IdOnlyPreservesHistoricalFirstRowBehavior()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "legacy.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      Assert.Equal(0, report.RootElement.GetProperty("Source").GetProperty("ManifestEntryIndex").GetInt32());
    });
  }

  [Fact]
  public void ProbeBinary_ManifestIndexOnlyStillSelectsRequestedRow()
  {
    WithFixture((root, manifest, _) =>
    {
      var output = Path.Combine(root, "by-index.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--manifest-index", "2", "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      Assert.Equal(2, report.RootElement.GetProperty("Source").GetProperty("ManifestEntryIndex").GetInt32());
    });
  }

  [Fact]
  public void ProbeBinary_RequireUniqueRefusesDuplicateIdWithoutExactIndex()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "strict-ambiguous.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--require-unique",
           "--out", output]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(output));
    });
  }

  [Fact]
  public void ProbeBinary_RequireUniqueAllowsExactRowForDuplicateId()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "strict-exact.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--manifest-index", "2",
           "--require-unique", "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      Assert.Equal(2, report.RootElement.GetProperty("Source").GetProperty("ManifestEntryIndex").GetInt32());
    });
  }

  [Fact]
  public void ProbeBinary_IdAndFnvSelectsNamedRowForSharedContentId()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "joint-selected.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--fnv", "0xEEFF",
           "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      var source = report.RootElement.GetProperty("Source");
      Assert.Equal(2, source.GetProperty("ManifestEntryIndex").GetInt32());
      Assert.Equal(9, source.GetProperty("PakIndex").GetInt32());
    });
  }

  [Fact]
  public void ProbeBinary_IdAndFnvMismatchRefusesBeforeOutput()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "joint-mismatch.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--fnv", "0x12345678",
           "--out", output]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(output));
    });
  }

  [Fact]
  public void ProbeBinary_IdAndFnvWithRequireUniqueAllowsDistinctFilenameForSharedContent()
  {
    WithFixture((root, manifest, id) =>
    {
      var output = Path.Combine(root, "joint-strict.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--fnv", "0xEEFF",
           "--require-unique", "--out", output]);
      Assert.Equal(0, rc);
      using var report = JsonDocument.Parse(File.ReadAllText(output));
      Assert.Equal(2, report.RootElement.GetProperty("Source").GetProperty("ManifestEntryIndex").GetInt32());
    });
  }

  [Fact]
  public void ProbeBinary_IdAndFnvRefusesNonUniqueJointPair()
  {
    WithFixture((root, manifest, id) =>
    {
      // Make both manifest rows carrying this content ID share the same FNV.
      var bytes = File.ReadAllBytes(manifest);
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(0x50 + 8, 4), 0xEEFF);
      File.WriteAllBytes(manifest, bytes);
      var output = Path.Combine(root, "joint-duplicate.json");
      var rc = global::Program.Main(
          ["probe-binary", "--root", root, "--manifest", manifest,
           "--archive", "assets.001", "--id", id, "--fnv", "0xEEFF",
           "--out", output]);
      Assert.NotEqual(0, rc);
      Assert.False(File.Exists(output));
    });
  }

  private static void WithFixture(Action<string, string, string> action)
  {
    var root = Path.Combine(Path.GetTempPath(), $"rad-manifest-select-{Guid.NewGuid():N}");
    var assets = Path.Combine(root, "Assets");
    Directory.CreateDirectory(assets);
    try
    {
      var payload = new byte[132];
      Encoding.ASCII.GetBytes("DDS ").CopyTo(payload, 0);
      var sha1 = SHA1.HashData(payload);
      var id = Convert.ToHexString(sha1.AsSpan(0, 8)).ToLowerInvariant();
      var manifest = Path.Combine(root, "assets64.manifest");
      File.WriteAllBytes(manifest, BuildManifest(sha1));
      File.WriteAllBytes(Path.Combine(assets, "assets.001"), BuildArchive(payload, sha1));
      action(root, manifest, id);
    }
    finally
    {
      Directory.Delete(root, recursive: true);
    }
  }

  private static byte[] BuildManifest(byte[] sha1)
  {
    const int headerSize = 0x50;
    const int stride = 58;
    var bytes = new byte[headerSize + 3 * stride];
    Encoding.ASCII.GetBytes("TWAM").CopyTo(bytes, 0);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(16, 4), headerSize);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(28, 4), 53);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(32, 4), headerSize);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(36, 4), 3 * stride);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(40, 4), 3);
    BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(44, 4), stride);

    for (var i = 0; i < 3; i++)
    {
      var offset = headerSize + i * stride;
      (i == 1 ? new byte[] { 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff, 0xff } : sha1[..8])
          .CopyTo(bytes, offset);
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(offset + 8, 4), (uint)(i == 2 ? 0xEEFF : 0xAABB));
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(offset + 12, 4), (uint)(100 + i));
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(offset + 16, 4), 132);
      BinaryPrimitives.WriteUInt32LittleEndian(bytes.AsSpan(offset + 20, 4), 132);
      BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(offset + 24, 2), (ushort)(i == 2 ? 9 : 1));
      sha1.CopyTo(bytes, offset + 32);
      BinaryPrimitives.WriteUInt16LittleEndian(bytes.AsSpan(offset + 56, 2), 12);
    }
    return bytes;
  }

  private static byte[] BuildArchive(byte[] payload, byte[] sha1)
  {
    const int headerSize = 20;
    const int entrySize = 44;
    var data = new byte[headerSize + entrySize + payload.Length];
    Encoding.ASCII.GetBytes("TWAD").CopyTo(data, 0);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(4, 4), 1);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(8, 4), headerSize);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(12, 4), 1);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(16, 4), 1);
    sha1.AsSpan(0, 8).CopyTo(data.AsSpan(20, 8));
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(28, 4), headerSize + entrySize);
    BinaryPrimitives.WriteUInt32LittleEndian(data.AsSpan(32, 4), (uint)payload.Length);
    BinaryPrimitives.WriteUInt16LittleEndian(data.AsSpan(40, 2), 1);
    BinaryPrimitives.WriteUInt16LittleEndian(data.AsSpan(42, 2), 0);
    sha1.CopyTo(data, 44);
    payload.CopyTo(data, headerSize + entrySize);
    return data;
  }
}
