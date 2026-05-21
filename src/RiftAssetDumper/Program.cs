using System.Buffers.Binary;
using System.Globalization;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
using System.Xml;
using SharpCompress.Compressors.Xz;

internal static class Program
{
  private const int ManifestHeaderSize = 0x50;
  private const int ArchiveHeaderSize = 0x14;
  private const int ArchiveEntrySize = 44;

  public static int Main(string[] args)
  {
    try
    {
      var options = AppOptions.Parse(args);
      if (options.ShowHelp)
      {
        PrintUsage();
        return 0;
      }

      if (options.Command == "extract-archives")
      {
        return ExtractArchives(options);
      }

      if (options.Command == "match-ids")
      {
        return MatchIds(options);
      }

      if (options.Command == "list-paks")
      {
        return ListPaks(options);
      }

      if (options.Command == "list-entries")
      {
        return ListEntries(options);
      }

      if (options.Command == "hash-name")
      {
        return HashName(options);
      }

      if (options.Command == "match-names")
      {
        return MatchNames(options);
      }

      if (options.Command == "inventory-archives")
      {
        return InventoryArchives(options);
      }

      if (options.Command == "scan-compression")
      {
        return ScanCompression(options);
      }

      if (options.Command == "mine-strings")
      {
        return MineStrings(options);
      }

      if (options.Command == "inventory-asset-signatures")
      {
        return BuildAssetSemanticIndex(options, includeEntries: false);
      }

      if (options.Command == "build-asset-semantic-index")
      {
        return BuildAssetSemanticIndex(options, includeEntries: true);
      }

      if (options.Command == "inventory-binary-signatures")
      {
        return InventoryBinarySignatures(options);
      }

      if (options.Command == "probe-binary")
      {
        return ProbeBinary(options);
      }

      if (options.Command == "probe-nif")
      {
        return ProbeNif(options);
      }

      if (options.Command == "probe-nif-streams")
      {
        return ProbeNifStreams(options);
      }

      if (options.Command == "probe-nif-mesh")
      {
        return ProbeNifMesh(options);
      }

      if (options.Command == "decode-nif-geometry")
      {
        return DecodeNifGeometry(options);
      }

      if (options.Command == "validate-uint16-positions")
      {
        return ValidateUInt16Positions(options);
      }

      if (options.Command == "probe-nif-attribute-extra")
      {
        return ProbeNifAttributeExtra(options);
      }

      if (options.Command == "probe-nif-stream-body")
      {
        return ProbeNifStreamBody(options);
      }

      if (options.Command == "probe-nif-position-source")
      {
        return ProbeNifPositionSource(options);
      }

      if (options.Command == "inventory-nif")
      {
        return InventoryNif(options);
      }

      if (options.Command == "inventory-nif-blocks")
      {
        return InventoryNifBlocks(options);
      }

      if (options.Command == "inventory-nif-mesh-streams")
      {
        return InventoryNifMeshStreams(options);
      }

      if (options.Command == "inventory-nif-mesh-bindings")
      {
        return InventoryNifMeshBindings(options);
      }

      if (options.Command == "inventory-nif-stream-headers")
      {
        return InventoryNifStreamHeaders(options);
      }

      if (options.Command == "inventory-nif-stream-bodies")
      {
        return InventoryNifStreamBodies(options);
      }

      if (options.Command == "inventory-nif-stream-endianness")
      {
        return InventoryNifStreamEndianness(options);
      }

      if (options.Command == "inventory-nif-index-candidates")
      {
        return InventoryNifIndexCandidates(options);
      }

      if (options.Command == "probe-nif-position-source")
      {
        return ProbeNifPositionSource(options);
      }

      if (options.Command == "mine-nif-references")
      {
        return MineNifReferences(options);
      }

      if (options.Command == "link-nif-textures")
      {
        return LinkNifTextures(options);
      }

      if (options.Command == "extract-linked-textures")
      {
        return ExtractLinkedTextures(options);
      }

      if (options.Command == "extract-nif-bundle")
      {
        return ExtractNifBundle(options);
      }

      if (options.Command == "extract-nif-bundles")
      {
        return ExtractNifBundles(options);
      }

      if (options.Command == "inventory-nif-bundles")
      {
        return InventoryNifBundles(options);
      }

      if (options.Command == "plan-nif-bundle-archives")
      {
        return PlanNifBundleArchives(options);
      }

      var report = Probe(options.RootDirectory);
      PrintReport(report, options.RedactPaths);

      if (options.WriteJson)
      {
        var jsonPath = Path.Combine(options.RootDirectory, "probe-report.json");
        var json = JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths));
        File.WriteAllText(jsonPath, json + Environment.NewLine, Encoding.UTF8);
        Console.WriteLine();
        Console.WriteLine($"Wrote JSON report: {DisplayPath(options, jsonPath)}");
      }

      return report.Errors.Count == 0 ? 0 : 2;
    }
    catch (Exception ex)
    {
      Console.Error.WriteLine($"ERROR: {RedactSensitivePath(ex.Message, redactPaths: true)}");
      return 1;
    }
  }

  private static ProbeReport Probe(string rootDirectory)
  {
    rootDirectory = Path.GetFullPath(rootDirectory);
    var report = new ProbeReport(rootDirectory);

    if (!Directory.Exists(rootDirectory))
    {
      report.Errors.Add($"Root directory does not exist: {rootDirectory}");
      return report;
    }

    foreach (var manifestPath in Directory.EnumerateFiles(rootDirectory, "*.manifest", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      try
      {
        report.Manifests.Add(ReadManifest(manifestPath));
      }
      catch (Exception ex)
      {
        report.Errors.Add($"{manifestPath}: {ex.Message}");
      }
    }

    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (Directory.Exists(assetsDirectory))
    {
      foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
      {
        try
        {
          report.Archives.Add(ReadArchive(archivePath));
        }
        catch (Exception ex)
        {
          report.Errors.Add($"{archivePath}: {ex.Message}");
        }
      }
    }
    else
    {
      report.Errors.Add($"Assets directory does not exist: {assetsDirectory}");
    }

    return report;
  }

  private static ManifestProbe ReadManifest(string path)
  {
    var bytes = File.ReadAllBytes(path);
    if (bytes.Length < ManifestHeaderSize)
    {
      throw new InvalidDataException($"manifest is too short: {bytes.Length} bytes");
    }

    var magic = Encoding.ASCII.GetString(bytes, 0, 4);
    var header = new ManifestHeader(
        Magic: magic,
        MajorVersion: ReadUInt16(bytes, 4),
        MinorVersion: ReadUInt16(bytes, 6),
        BlockTableOffset: ReadUInt32(bytes, 8),
        BlockTableSize: ReadUInt32(bytes, 12),
        Table0PakListing: ReadTableReference(bytes, 16),
        Table1EntryTable: ReadTableReference(bytes, 32),
        Table2Unknown: ReadTableReference(bytes, 48));

    var probe = new ManifestProbe(
        Path: path,
        FileName: Path.GetFileName(path),
        Length: bytes.Length,
        Header: header,
        HeaderValid: magic == "TWAM",
        PakSamples: [],
        EntrySamples: [],
        Warnings: []);

    if (magic != "TWAM")
    {
      probe.Warnings.Add($"Unexpected manifest magic '{magic}'. Expected TWAM.");
      return probe;
    }

    ValidateTable(bytes.Length, header.BlockTableOffset, header.BlockTableSize, "256 block table", probe.Warnings);
    ValidateTable(bytes.Length, header.Table0PakListing.Offset, header.Table0PakListing.Size, "table 0 / PAK listing", probe.Warnings);
    ValidateTable(bytes.Length, header.Table1EntryTable.Offset, header.Table1EntryTable.Size, "table 1 / entry table", probe.Warnings);
    ValidateTable(bytes.Length, header.Table2Unknown.Offset, header.Table2Unknown.Size, "table 2 / unknown", probe.Warnings);

    probe.PakSamples.AddRange(ReadPakSamples(bytes, header.Table0PakListing, sampleCount: 8));
    probe.EntrySamples.AddRange(ReadManifestEntrySamples(bytes, header.Table1EntryTable, sampleCount: 8));

    return probe;
  }

  private static ArchiveProbe ReadArchive(string path)
  {
    var bytes = File.ReadAllBytes(path);
    if (bytes.Length < ArchiveHeaderSize)
    {
      throw new InvalidDataException($"archive is too short: {bytes.Length} bytes");
    }

    var magic = Encoding.ASCII.GetString(bytes, 0, 4);
    var header = new ArchiveHeader(
        Magic: magic,
        Version: ReadUInt32(bytes, 4),
        HeaderSize: ReadUInt32(bytes, 8),
        MaxEntryCount: ReadUInt32(bytes, 12),
        FirstLinkedEntryRaw: ReadUInt32(bytes, 16));

    var probe = new ArchiveProbe(
        path,
        Path.GetFileName(path),
        bytes.Length,
        header,
        magic == "TWAD",
        0,
        null,
        [],
        [],
        []);

    if (magic != "TWAD")
    {
      probe.Warnings.Add($"Unexpected archive magic '{magic}'. Expected TWAD.");
      return probe;
    }

    if (header.HeaderSize != ArchiveHeaderSize)
    {
      probe.Warnings.Add($"Unexpected archive header size {header.HeaderSize}; expected {ArchiveHeaderSize}.");
    }

    var tableOffset = checked((int)header.HeaderSize);
    var maxEntries = checked((int)Math.Min(header.MaxEntryCount, int.MaxValue));
    var tableBytes = checked((long)maxEntries * ArchiveEntrySize);
    if (tableOffset + tableBytes > bytes.Length)
    {
      probe.Warnings.Add($"Archive entry table extends past EOF: offset={tableOffset}, bytes={tableBytes}, file={bytes.Length}.");
      return probe;
    }

    var entries = new List<ArchiveEntrySample>(maxEntries);
    long? firstDataOffset = null;
    for (var i = 0; i < maxEntries; i++)
    {
      var entry = ReadArchiveEntry(bytes, tableOffset + i * ArchiveEntrySize, i);
      entries.Add(entry);
      if (entry.IsNull)
      {
        continue;
      }

      probe.NonNullEntryCount++;
      if (entry.Offset > 0 && (firstDataOffset is null || entry.Offset < firstDataOffset.Value))
      {
        firstDataOffset = entry.Offset;
      }

      if (probe.PhysicalEntrySamples.Count < 8)
      {
        probe.PhysicalEntrySamples.Add(entry);
      }

      if (entry.Offset + entry.Size > bytes.Length)
      {
        probe.Warnings.Add($"Entry {i} extends past EOF: offset={entry.Offset}, size={entry.Size}, file={bytes.Length}.");
      }
    }

    probe.FirstDataOffset = firstDataOffset;
    probe.LinkedEntrySamples.AddRange(WalkLinkedEntries(entries, header.FirstLinkedEntryRaw, maxSamples: 12, probe.Warnings));

    return probe;
  }

  private static IEnumerable<PakListingSample> ReadPakSamples(byte[] bytes, TableReference table, int sampleCount)
  {
    if (table.Stride < 53)
    {
      yield break;
    }

    var count = Math.Min(table.Count, (uint)sampleCount);
    for (var i = 0; i < count; i++)
    {
      var offset = checked((int)(table.Offset + i * table.Stride));
      if (offset + 53 > bytes.Length)
      {
        yield break;
      }

      var stringOffset = ReadUInt32(bytes, offset);
      yield return new PakListingSample(
          Index: i,
          StringOffset: stringOffset,
          Path: ReadNullTerminatedAscii(bytes, stringOffset, maxLength: 512),
          UncompressedSize: ReadUInt32(bytes, offset + 4),
          CompressedSize: ReadUInt32(bytes, offset + 8),
          Compression: bytes[offset + 12],
          Sha1WhenUncompressed: ToHex(bytes.AsSpan(offset + 13, 20)),
          Sha1WhenCompressed: ToHex(bytes.AsSpan(offset + 33, 20)));
    }
  }

  private static IEnumerable<ManifestEntrySample> ReadManifestEntrySamples(byte[] bytes, TableReference table, int sampleCount)
  {
    if (table.Stride < 56)
    {
      yield break;
    }

    var count = Math.Min(table.Count, (uint)sampleCount);
    for (var i = 0; i < count; i++)
    {
      var offset = checked((int)(table.Offset + i * table.Stride));
      if (offset + table.Stride > bytes.Length)
      {
        yield break;
      }

      yield return new ManifestEntrySample(
          Index: i,
          ContentIdPrefix: ToHex(bytes.AsSpan(offset, 8)),
          FilenameFnv1Hash: ReadUInt32(bytes, offset + 8),
          PakOffset: ReadUInt32(bytes, offset + 12),
          CompressedSize: ReadUInt32(bytes, offset + 16),
          Size: ReadUInt32(bytes, offset + 20),
          PakIndex: ReadUInt16(bytes, offset + 24),
          Bitfield1: ReadUInt16(bytes, offset + 26),
          Bitfield2: ReadUInt16(bytes, offset + 28),
          UnknownByte: bytes[offset + 30],
          Language: bytes[offset + 31],
          Hash: ToHex(bytes.AsSpan(offset + 32, 20)),
          UnknownInt: ReadUInt32(bytes, offset + 52),
          NameLength: table.Stride >= 58 ? ReadUInt16(bytes, offset + 56) : null);
    }
  }

  private static ArchiveEntrySample ReadArchiveEntry(byte[] bytes, int offset, int index)
  {
    var id = bytes.AsSpan(offset, 8);
    var dataOffset = ReadUInt32(bytes, offset + 8);
    var size = ReadUInt32(bytes, offset + 12);
    var streamedOrUnknown = ReadUInt32(bytes, offset + 16);
    var nextRaw = ReadUInt16(bytes, offset + 20);
    var compression = ReadUInt16(bytes, offset + 22);
    var sha1 = bytes.AsSpan(offset + 24, 20);
    var isNull = id.SequenceEqual(stackalloc byte[8])
        && dataOffset == 0
        && size == 0
        && streamedOrUnknown == 0
        && nextRaw == 0
        && compression == 0
        && sha1.SequenceEqual(stackalloc byte[20]);

    return new ArchiveEntrySample(
        Index: index,
        IdPrefix: ToHex(id),
        Offset: dataOffset,
        Size: size,
        StreamedOrUnknown: streamedOrUnknown,
        NextRaw: nextRaw,
        NextIndex: nextRaw == 0 ? null : nextRaw - 1,
        Compression: compression,
        Sha1: ToHex(sha1),
        IsNull: isNull);
  }

  private static IEnumerable<ArchiveEntrySample> WalkLinkedEntries(IReadOnlyList<ArchiveEntrySample> entries, uint firstLinkedEntryRaw, int maxSamples, List<string> warnings)
  {
    if (firstLinkedEntryRaw == 0)
    {
      yield break;
    }

    var index = checked((int)firstLinkedEntryRaw) - 1;
    var seen = new HashSet<int>();
    for (var emitted = 0; emitted < maxSamples; emitted++)
    {
      if (index < 0 || index >= entries.Count)
      {
        warnings.Add($"Linked entry index {index} is outside table bounds 0..{entries.Count - 1}.");
        yield break;
      }

      if (!seen.Add(index))
      {
        warnings.Add($"Linked entry chain loops at index {index}.");
        yield break;
      }

      var entry = entries[index];
      yield return entry;
      if (entry.NextIndex is null)
      {
        yield break;
      }

      index = entry.NextIndex.Value;
    }
  }

  private static TableReference ReadTableReference(byte[] bytes, int offset)
  {
    return new TableReference(
        Offset: ReadUInt32(bytes, offset),
        Size: ReadUInt32(bytes, offset + 4),
        Count: ReadUInt32(bytes, offset + 8),
        Stride: ReadUInt32(bytes, offset + 12));
  }

  private static void ValidateTable(long fileLength, uint offset, uint size, string name, List<string> warnings)
  {
    if ((long)offset + size > fileLength)
    {
      warnings.Add($"{name} extends past EOF: offset={offset}, size={size}, file={fileLength}.");
    }
  }

  private static string ReadNullTerminatedAscii(byte[] bytes, uint offset, int maxLength)
  {
    if (offset >= bytes.Length)
    {
      return $"<offset {offset} outside file>";
    }

    var length = 0;
    var start = checked((int)offset);
    while (start + length < bytes.Length && length < maxLength && bytes[start + length] != 0)
    {
      length++;
    }

    return Encoding.ASCII.GetString(bytes, start, length);
  }

  private static ushort ReadUInt16(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(offset, 2));

  private static uint ReadUInt32(byte[] bytes, int offset) => BinaryPrimitives.ReadUInt32LittleEndian(bytes.AsSpan(offset, 4));

  private static string ToHex(ReadOnlySpan<byte> bytes)
  {
    return Convert.ToHexString(bytes).ToLowerInvariant();
  }

  private static void PrintReport(ProbeReport report, bool redactPaths)
  {
    Console.WriteLine($"RIFT asset probe root: {RedactSensitivePath(report.RootDirectory, redactPaths)}");

    Console.WriteLine();
    Console.WriteLine($"Manifests ({report.Manifests.Count}):");
    foreach (var manifest in report.Manifests)
    {
      Console.WriteLine($"- {manifest.FileName} ({manifest.Length:N0} bytes) magic={manifest.Header.Magic} valid={manifest.HeaderValid}");
      Console.WriteLine($"  version={manifest.Header.MajorVersion}.{manifest.Header.MinorVersion} blockTable offset={manifest.Header.BlockTableOffset} size={manifest.Header.BlockTableSize}");
      Console.WriteLine($"  table0/paks     offset={manifest.Header.Table0PakListing.Offset} size={manifest.Header.Table0PakListing.Size} count={manifest.Header.Table0PakListing.Count} stride={manifest.Header.Table0PakListing.Stride}");
      Console.WriteLine($"  table1/entries  offset={manifest.Header.Table1EntryTable.Offset} size={manifest.Header.Table1EntryTable.Size} count={manifest.Header.Table1EntryTable.Count} stride={manifest.Header.Table1EntryTable.Stride}");
      Console.WriteLine($"  table2/unknown  offset={manifest.Header.Table2Unknown.Offset} size={manifest.Header.Table2Unknown.Size} count={manifest.Header.Table2Unknown.Count} stride={manifest.Header.Table2Unknown.Stride}");
      Console.WriteLine("  sample PAK rows:");
      foreach (var pak in manifest.PakSamples.Take(5))
      {
        Console.WriteLine($"    [{pak.Index}] comp={pak.Compression} uncomp={pak.UncompressedSize:N0} compSize={pak.CompressedSize:N0} path={pak.Path}");
      }
      Console.WriteLine("  sample entry rows:");
      foreach (var entry in manifest.EntrySamples.Take(5))
      {
        Console.WriteLine($"    [{entry.Index}] pak={entry.PakIndex} pakOffset={entry.PakOffset} compSize={entry.CompressedSize:N0} size={entry.Size:N0} fnv=0x{entry.FilenameFnv1Hash:x8} nameLen={entry.NameLength}");
      }
      foreach (var warning in manifest.Warnings)
      {
        Console.WriteLine($"  WARNING: {RedactSensitivePath(warning, redactPaths)}");
      }
    }

    Console.WriteLine();
    Console.WriteLine($"Archives ({report.Archives.Count}):");
    foreach (var archive in report.Archives)
    {
      Console.WriteLine($"- {archive.FileName} ({archive.Length:N0} bytes) magic={archive.Header.Magic} valid={archive.HeaderValid}");
      Console.WriteLine($"  version={archive.Header.Version} headerSize={archive.Header.HeaderSize} maxEntries={archive.Header.MaxEntryCount} firstLinkedRaw={archive.Header.FirstLinkedEntryRaw}");
      Console.WriteLine($"  nonNullEntries={archive.NonNullEntryCount} firstDataOffset={archive.FirstDataOffset}");
      Console.WriteLine("  first physical non-null entries:");
      foreach (var entry in archive.PhysicalEntrySamples.Take(5))
      {
        Console.WriteLine($"    [{entry.Index}] offset={entry.Offset} size={entry.Size:N0} comp={entry.Compression} nextRaw={entry.NextRaw} id={entry.IdPrefix}");
      }
      Console.WriteLine("  linked-list samples:");
      foreach (var entry in archive.LinkedEntrySamples.Take(5))
      {
        Console.WriteLine($"    [{entry.Index}] offset={entry.Offset} size={entry.Size:N0} comp={entry.Compression} nextRaw={entry.NextRaw} id={entry.IdPrefix}");
      }
      foreach (var warning in archive.Warnings)
      {
        Console.WriteLine($"  WARNING: {RedactSensitivePath(warning, redactPaths)}");
      }
    }

    if (report.Errors.Count > 0)
    {
      Console.WriteLine();
      Console.WriteLine("Errors:");
      foreach (var error in report.Errors)
      {
        Console.WriteLine($"- {RedactSensitivePath(error, redactPaths)}");
      }
    }
  }

  private static int ExtractArchives(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    var outDirectory = Path.GetFullPath(options.OutDirectory ?? Path.Combine(rootDirectory, "..", "Extracted", "archive-payloads"));

    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var manifestLookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, manifestLookup);
    var recoveredNames = LoadRecoveredNames(
        options.UseRecoveredNamesPath,
        string.IsNullOrWhiteSpace(options.UseRecoveredNamesPath) ? options.MinConfidence : Math.Max(options.MinConfidence, 80));

    Directory.CreateDirectory(outDirectory);
    Console.WriteLine($"Extracting TWAD archive payloads from: {DisplayPath(options, assetsDirectory)}");
    Console.WriteLine($"Manifest: {DisplayPath(options, manifestPath)}");
    Console.WriteLine($"Output: {DisplayPath(options, outDirectory)}");
    Console.WriteLine($"Max per archive: {options.MaxPerArchive}");
    if (options.MaxTotal > 0)
    {
      Console.WriteLine($"Max total: {options.MaxTotal}");
    }
    if (filter.Describe() is { Length: > 0 } filterDescription)
    {
      Console.WriteLine($"Filter: {filterDescription}");
    }
    Console.WriteLine();

    var totalWritten = 0;
    var totalSkipped = 0;
    var totalFailed = 0;

    var archiveReports = new List<ArchiveExtractResult>();
    var archivePaths = Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly)
        .OrderBy(static p => p)
        .Where(p => filter.ArchiveMatches(Path.GetFileName(p)))
        .ToArray();
    if (archivePaths.Length == 0)
    {
      Console.Error.WriteLine("ERROR: no copied archives matched the requested archive filter.");
      return 1;
    }

    foreach (var archivePath in archivePaths)
    {
      if (options.MaxTotal > 0 && totalWritten >= options.MaxTotal)
      {
        break;
      }

      var remainingTotal = options.MaxTotal > 0 ? options.MaxTotal - totalWritten : int.MaxValue;
      var maxForThisArchive = Math.Min(options.MaxPerArchive, remainingTotal);
      var result = ExtractArchive(archivePath, outDirectory, maxForThisArchive, manifestLookup, filter, recoveredNames, options);
      archiveReports.Add(result);
      totalWritten += result.Written;
      totalSkipped += result.Skipped;
      totalFailed += result.Failed;

      Console.WriteLine($"- {Path.GetFileName(archivePath)}: wrote={result.Written}, skipped={result.Skipped}, failed={result.Failed}");
      foreach (var sample in result.Samples)
      {
        var manifestText = sample.ManifestEntryIndex is null
            ? "manifest=<none>"
            : $"manifest={sample.ManifestEntryIndex} fnv=0x{sample.FilenameFnv1Hash.GetValueOrDefault():x8}";
        Console.WriteLine($"    [{sample.EntryIndex}] comp={sample.Compression} packed={sample.PackedSize:N0} unpacked={sample.UnpackedSize:N0} {manifestText} -> {sample.RelativePath}");
      }
      foreach (var warning in result.Warnings.Take(5))
      {
        Console.WriteLine($"    WARNING: {warning}");
      }
    }

    Console.WriteLine();
    Console.WriteLine($"Done. written={totalWritten}, skipped={totalSkipped}, failed={totalFailed}");

    if (options.WriteJson)
    {
      var report = new ExtractionRunReport(
          RootDirectory: rootDirectory,
          OutputDirectory: outDirectory,
          ManifestPath: manifestPath,
          Archives: archiveReports);
      var reportPath = Path.Combine(outDirectory, "extract-report.json");
      File.WriteAllText(reportPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);
      Console.WriteLine($"Wrote extraction report: {DisplayPath(options, reportPath)}");
    }

    return totalFailed == 0 ? 0 : 2;
  }

  private static int MatchIds(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(rootDirectory))
    {
      Console.Error.WriteLine($"ERROR: root directory does not exist: {DisplayPath(options, rootDirectory)}");
      return 1;
    }

    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPaths = Directory.EnumerateFiles(rootDirectory, "*.manifest", SearchOption.TopDirectoryOnly)
        .OrderBy(static p => p)
        .ToArray();
    if (manifestPaths.Length == 0)
    {
      Console.Error.WriteLine($"ERROR: no *.manifest files found in {DisplayPath(options, rootDirectory)}");
      return 1;
    }

    var archives = Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly)
        .OrderBy(static p => p)
        .ToArray();

    Console.WriteLine($"Manifest/archive ID diagnostics");
    Console.WriteLine($"Root: {DisplayPath(options, rootDirectory)}");
    Console.WriteLine($"Archives: {archives.Length}");
    Console.WriteLine();

    foreach (var manifestPath in manifestPaths)
    {
      var lookup = ReadManifestLookup(manifestPath);
      Console.WriteLine($"Manifest: {lookup.FileName}");
      Console.WriteLine($"  table0/paks={lookup.PakCount:N0} table1/entries={lookup.EntryCount:N0}");

      foreach (var archivePath in archives)
      {
        var result = MatchArchiveIds(archivePath, lookup);
        Console.WriteLine($"  {Path.GetFileName(archivePath)}: entries={result.NonNullEntries:N0} table1IdMatches={result.Table1IdMatches:N0} table1ShaMatches={result.Table1ShaMatches:N0} pakShaPrefixMatches={result.PakShaPrefixMatches:N0} pakShaMatches={result.PakShaMatches:N0}");
        foreach (var sample in result.Samples.Take(5))
        {
          Console.WriteLine($"    entry[{sample.ArchiveEntryIndex}] id={sample.IdPrefix} -> manifest[{sample.ManifestEntryIndex}] pak={sample.PakIndex} pakOffset={sample.PakOffset} size={sample.Size:N0} compSize={sample.CompressedSize:N0} fnv=0x{sample.FilenameFnv1Hash:x8} nameLen={sample.NameLength}");
        }
      }

      Console.WriteLine();
    }

    return 0;
  }

  private static int ListPaks(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var records = options.Limit > 0 ? lookup.Paks.Take(options.Limit) : lookup.Paks;
    var outPath = ResolveOutputPath(
        rootDirectory,
        options.OutDirectory,
        $"{Path.GetFileNameWithoutExtension(manifestPath)}.paks.jsonl");

    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    WriteJsonLines(outPath, records, options.RedactPaths);

    Console.WriteLine($"Manifest: {DisplayPath(options, manifestPath)}");
    Console.WriteLine($"PAK rows: {lookup.Paks.Count:N0}");
    Console.WriteLine($"Written: {(options.Limit > 0 ? Math.Min(options.Limit, lookup.Paks.Count) : lookup.Paks.Count):N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int ListEntries(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var records = options.Limit > 0 ? lookup.Entries.Take(options.Limit) : lookup.Entries;
    var outPath = ResolveOutputPath(
        rootDirectory,
        options.OutDirectory,
        $"{Path.GetFileNameWithoutExtension(manifestPath)}.entries.jsonl");

    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    WriteJsonLines(outPath, records, options.RedactPaths);

    Console.WriteLine($"Manifest: {DisplayPath(options, manifestPath)}");
    Console.WriteLine($"Entry rows: {lookup.Entries.Count:N0}");
    Console.WriteLine($"Written: {(options.Limit > 0 ? Math.Min(options.Limit, lookup.Entries.Count) : lookup.Entries.Count):N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int HashName(AppOptions options)
  {
    var names = ReadCandidateNames(options).ToArray();
    if (names.Length == 0)
    {
      Console.Error.WriteLine("ERROR: no names provided. Use --name or --names-file.");
      return 1;
    }

    foreach (var name in names)
    {
      var normalized = NormalizeAssetName(name);
      var fnv1 = ComputeFnv1Hash(normalized);
      var fnv1A = ComputeFnv1AHash(normalized);
      Console.WriteLine($"{normalized}\tfnv1=0x{fnv1:x8}\tfnv1a=0x{fnv1A:x8}\tlength={Encoding.UTF8.GetByteCount(normalized)}");
    }

    return 0;
  }

  private static int MatchNames(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var names = ReadCandidateNames(options).ToArray();
    if (names.Length == 0)
    {
      Console.Error.WriteLine("ERROR: no names provided. Use --name or --names-file.");
      return 1;
    }

    var matches = new List<NameMatchRecord>();
    foreach (var name in names)
    {
      var normalized = NormalizeAssetName(name);
      var byteLength = Encoding.UTF8.GetByteCount(normalized);
      var fnv1 = ComputeFnv1Hash(normalized);
      var fnv1A = ComputeFnv1AHash(normalized);

      if (options.Algorithm is "fnv1" or "both")
      {
        AddNameMatches(matches, lookup, normalized, byteLength, "fnv1", fnv1, options);
      }

      if (options.Algorithm is "fnv1a" or "both")
      {
        AddNameMatches(matches, lookup, normalized, byteLength, "fnv1a", fnv1A, options);
      }
    }

    if (options.Limit > 0)
    {
      matches = matches.Take(options.Limit).ToList();
    }

    var outPath = string.IsNullOrWhiteSpace(options.OutDirectory)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "RecoveredNames", "recovered-names.jsonl"))
        : ResolveOutputPath(rootDirectory, options.OutDirectory, $"{Path.GetFileNameWithoutExtension(manifestPath)}.name-matches.jsonl");

    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    WriteJsonLines(outPath, matches, options.RedactPaths);

    Console.WriteLine($"Manifest: {DisplayPath(options, manifestPath)}");
    Console.WriteLine($"Candidates: {names.Length:N0}");
    Console.WriteLine($"Matches: {matches.Count:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int InventoryArchives(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var manifestLookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, manifestLookup);
    var archivePaths = Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly)
        .OrderBy(static p => p)
        .Where(p => filter.ArchiveMatches(Path.GetFileName(p)))
        .ToArray();

    if (archivePaths.Length == 0)
    {
      Console.Error.WriteLine("ERROR: no copied archives matched the requested archive filter.");
      return 1;
    }

    var reports = new List<ArchiveInventoryReport>();
    foreach (var archivePath in archivePaths)
    {
      var report = InspectArchiveInventory(archivePath, options.MaxPerArchive, manifestLookup, filter);
      reports.Add(report);
      var types = string.Join(", ", report.TypeCounts.OrderBy(static kvp => kvp.Key).Select(static kvp => $"{kvp.Key}={kvp.Value}"));
      Console.WriteLine($"- {report.ArchiveName}: entries={report.NonNullEntries:N0} inspected={report.Inspected:N0} failed={report.Failed:N0} types=[{types}]");
    }

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "archive-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    var runReport = new ArchiveInventoryRunReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        MaxPerArchive: options.MaxPerArchive,
        Filter: filter.Describe(),
        Archives: reports);
    File.WriteAllText(outPath, JsonSerializer.Serialize(runReport, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine();
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return reports.Any(static r => r.Failed > 0) ? 2 : 0;
  }

  private static ArchiveInventoryReport InspectArchiveInventory(string archivePath, int maxPerArchive, ManifestLookup? manifestLookup, ExtractionFilter filter)
  {
    var report = new ArchiveInventoryReport { ArchiveName = Path.GetFileName(archivePath) };
    var bytes = File.ReadAllBytes(archivePath);
    if (bytes.Length < ArchiveHeaderSize || Encoding.ASCII.GetString(bytes, 0, 4) != "TWAD")
    {
      report.Failed++;
      report.Warnings.Add("Archive is missing a valid TWAD header.");
      return report;
    }

    var tableOffset = checked((int)ReadUInt32(bytes, 8));
    var maxEntries = checked((int)Math.Min(ReadUInt32(bytes, 12), int.MaxValue));
    for (var i = 0; i < maxEntries && report.Inspected < maxPerArchive; i++)
    {
      var entryOffset = tableOffset + i * ArchiveEntrySize;
      if (entryOffset + ArchiveEntrySize > bytes.Length)
      {
        report.Warnings.Add($"Entry table ended early at index {i}.");
        break;
      }

      var entry = ReadArchiveEntry(bytes, entryOffset, i);
      if (entry.IsNull)
      {
        continue;
      }

      report.NonNullEntries++;
      IncrementCount(report.CompressionCounts, entry.Compression.ToString());

      ManifestEntryBrief? manifestEntry = null;
      manifestLookup?.Table1ById.TryGetValue(entry.IdPrefix, out manifestEntry);
      if (!filter.EntryMatches(entry, manifestEntry))
      {
        continue;
      }

      try
      {
        if (entry.Offset + entry.Size > bytes.Length)
        {
          throw new InvalidDataException($"Entry {i} extends past EOF.");
        }

        var packed = bytes.AsSpan(checked((int)entry.Offset), checked((int)entry.Size)).ToArray();
        var packedSha = ComputeSha1Hex(packed);
        if (!StringComparer.OrdinalIgnoreCase.Equals(packedSha, entry.Sha1))
        {
          throw new InvalidDataException($"Entry {i} packed SHA1 mismatch.");
        }

        var detected = entry.Compression switch
        {
          0 => DetectFileType(packed),
          1 => DetectFileType(InflateZlibWithDeflateFallback(packed)),
          2 => new DetectedFileType("lzma2"),
          _ => new DetectedFileType($"comp{entry.Compression}")
        };

        if (!filter.TypeMatches(detected.Extension))
        {
          continue;
        }

        report.Inspected++;
        IncrementCount(report.TypeCounts, detected.Extension);
        if (report.Samples.Count < 20)
        {
          report.Samples.Add(new ArchiveInventorySample(
              EntryIndex: i,
              IdPrefix: entry.IdPrefix,
              Type: detected.Extension,
              Compression: entry.Compression,
              PackedSize: entry.Size,
              Width: detected.Width,
              Height: detected.Height,
              MipMapCount: detected.MipMapCount,
              Format: detected.Format,
              RiffType: detected.RiffType,
              ManifestEntryIndex: manifestEntry?.Index,
              FilenameFnv1Hash: manifestEntry?.FilenameFnv1Hash,
              NameLength: manifestEntry?.NameLength));
        }
      }
      catch (Exception ex)
      {
        report.Failed++;
        report.Warnings.Add($"Entry {i} failed: {ex.Message}");
      }
    }

    return report;
  }

  private static void IncrementCount(Dictionary<string, int> counts, string key)
  {
    counts.TryGetValue(key, out var current);
    counts[key] = current + 1;
  }

  private static void AddCount(Dictionary<string, int> counts, string key, int amount)
  {
    if (amount <= 0)
    {
      return;
    }

    counts.TryGetValue(key, out var current);
    counts[key] = current + amount;
  }

  private static int ScanCompression(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.LiveRoot ?? options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);

    var manifestCounts = lookup.Paks
        .GroupBy(static p => p.Compression)
        .ToDictionary(static g => g.Key.ToString(), static g => g.Count(), StringComparer.OrdinalIgnoreCase);
    var manifestSamples = lookup.Paks
        .GroupBy(static p => p.Compression)
        .Select(static g => g.First())
        .Select(p => BuildCompressionManifestSample(rootDirectory, assetsDirectory, p))
        .ToList();

    var archiveCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    var archiveSamples = new Dictionary<string, CompressionArchiveSample>(StringComparer.OrdinalIgnoreCase);
    var nonNullEntries = 0;
    var archiveCount = 0;
    if (Directory.Exists(assetsDirectory))
    {
      foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
      {
        var archiveName = Path.GetFileName(archivePath);
        if (archiveFilter is not null && !string.Equals(archiveName, archiveFilter, StringComparison.OrdinalIgnoreCase))
        {
          continue;
        }

        archiveCount++;
        ScanArchiveCompression(archivePath, archiveCounts, archiveSamples, ref nonNullEntries);
      }
    }

    var report = new CompressionScanReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        AssetsDirectory: assetsDirectory,
        ArchiveFilesScanned: archiveCount,
        ManifestPakCompressionCounts: manifestCounts,
        ArchiveEntryCompressionCounts: archiveCounts,
        ArchiveNonNullEntries: nonNullEntries,
        ManifestSamples: manifestSamples,
        ArchiveSamples: archiveSamples.Values.OrderBy(static s => s.Compression).ToList());

    var outputRoot = Path.GetFullPath(options.RootDirectory);
    var outPath = ResolveOutputPath(outputRoot, options.OutDirectory, "compression-scan.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Root: {DisplayPath(options, rootDirectory)}");
    Console.WriteLine($"Manifest: {DisplayPath(options, manifestPath)}");
    Console.WriteLine($"Manifest PAK compression: {FormatCounts(manifestCounts)}");
    Console.WriteLine($"Copied TWAD entry compression: {FormatCounts(archiveCounts)}");
    Console.WriteLine($"Copied TWAD non-null entries: {nonNullEntries:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static List<ArchiveEntrySample>? ReadArchiveEntryTable(FileStream stream)
  {
    if (stream.Length < ArchiveHeaderSize)
    {
      return null;
    }

    stream.Position = 0;
    Span<byte> header = stackalloc byte[ArchiveHeaderSize];
    stream.ReadExactly(header);
    if (Encoding.ASCII.GetString(header[..4]) != "TWAD")
    {
      return null;
    }

    var tableOffset = BinaryPrimitives.ReadUInt32LittleEndian(header.Slice(8, 4));
    var maxEntries = checked((int)Math.Min(BinaryPrimitives.ReadUInt32LittleEndian(header.Slice(12, 4)), int.MaxValue));
    if (tableOffset >= stream.Length || maxEntries <= 0)
    {
      return [];
    }

    var readableTableBytes = Math.Min((long)maxEntries * ArchiveEntrySize, stream.Length - tableOffset);
    var readableEntries = checked((int)(readableTableBytes / ArchiveEntrySize));
    if (readableEntries <= 0)
    {
      return [];
    }

    var tableBytes = new byte[readableEntries * ArchiveEntrySize];
    stream.Position = tableOffset;
    stream.ReadExactly(tableBytes);
    var entries = new List<ArchiveEntrySample>(readableEntries);
    for (var i = 0; i < readableEntries; i++)
    {
      entries.Add(ReadArchiveEntry(tableBytes, i * ArchiveEntrySize, i));
    }

    return entries;
  }

  private static byte[] ReadArchivePayload(FileStream stream, ArchiveEntrySample entry, string archiveName)
  {
    if ((long)entry.Offset + entry.Size > stream.Length)
    {
      throw new InvalidDataException($"Entry {entry.Index} in {archiveName} extends past EOF.");
    }

    var packed = new byte[checked((int)entry.Size)];
    stream.Position = entry.Offset;
    stream.ReadExactly(packed);
    return packed;
  }

  private static void ScanArchiveCompression(
      string archivePath,
      Dictionary<string, int> archiveCounts,
      Dictionary<string, CompressionArchiveSample> archiveSamples,
      ref int nonNullEntries)
  {
    var archiveName = Path.GetFileName(archivePath);
    using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
    if (stream.Length < ArchiveHeaderSize)
    {
      return;
    }

    var entries = ReadArchiveEntryTable(stream);
    if (entries is null)
    {
      return;
    }

    foreach (var entry in entries)
    {
      if (entry.IsNull)
      {
        continue;
      }

      nonNullEntries++;
      var key = entry.Compression.ToString();
      IncrementCount(archiveCounts, key);
      if (archiveSamples.ContainsKey(key))
      {
        continue;
      }

      var firstBytes = "";
      if (entry.Size > 0 && entry.Offset < stream.Length)
      {
        var available = stream.Length - entry.Offset;
        var length = checked((int)Math.Min(Math.Min(entry.Size, 16), available));
        var sample = new byte[length];
        stream.Position = entry.Offset;
        stream.ReadExactly(sample);
        firstBytes = ToHex(sample);
      }

      archiveSamples.Add(key, new CompressionArchiveSample(
          archiveName,
          entry.Index,
          entry.Compression,
          entry.Offset,
          entry.Size,
          firstBytes));
    }
  }

  private static int MineStrings(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var inputDirectory = Path.GetFullPath(options.InputPath ?? Path.Combine(rootDirectory, "..", "Extracted"));
    if (!Directory.Exists(inputDirectory))
    {
      Console.Error.WriteLine($"ERROR: input directory does not exist: {DisplayPath(options, inputDirectory)}");
      return 1;
    }

    var candidates = new Dictionary<string, StringMineRecord>(StringComparer.OrdinalIgnoreCase);
    var files = Directory.EnumerateFiles(inputDirectory, "*", SearchOption.AllDirectories)
        .Where(static p => p.EndsWith(".bin", StringComparison.OrdinalIgnoreCase) || p.EndsWith(".txt", StringComparison.OrdinalIgnoreCase))
        .ToArray();

    foreach (var file in files)
    {
      var bytes = File.ReadAllBytes(file);
      var asciiRuns = ExtractAsciiRuns(bytes, minLength: 8);
      foreach (var run in asciiRuns)
      {
        foreach (Match match in PathLikeRegex().Matches(run))
        {
          var candidate = NormalizeAssetName(match.Value);
          if (!candidates.TryGetValue(candidate, out var record))
          {
            record = new StringMineRecord(candidate, 0, []);
            candidates.Add(candidate, record);
          }

          record.Count++;
          if (record.SampleSources.Count < 5)
          {
            record.SampleSources.Add(Path.GetRelativePath(inputDirectory, file));
          }
        }
      }
    }

    var records = candidates.Values
        .OrderByDescending(static r => r.Count)
        .ThenBy(static r => r.Candidate)
        .ToArray();
    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "mined-names.jsonl");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    WriteJsonLines(outPath, records, options.RedactPaths);

    Console.WriteLine($"Input: {DisplayPath(options, inputDirectory)}");
    Console.WriteLine($"Files scanned: {files.Length:N0}");
    Console.WriteLine($"Candidates: {records.Length:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int BuildAssetSemanticIndex(AppOptions options, bool includeEntries)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var groups = new Dictionary<string, AssetSignatureAccumulator>(StringComparer.OrdinalIgnoreCase);
    var typeCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    var semanticCategoryCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    var entries = new List<AssetSemanticIndexEntry>();
    var inspected = 0;
    var failed = 0;
    var maxTotal = options.MaxTotalOrUnlimited();

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      if (inspected >= maxTotal)
      {
        break;
      }

      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var archiveEntries = ReadArchiveEntryTable(stream);
      if (archiveEntries is null)
      {
        continue;
      }

      foreach (var archiveEntry in archiveEntries)
      {
        if (inspected >= maxTotal)
        {
          break;
        }

        if (archiveEntry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(archiveEntry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(archiveEntry, manifestEntry))
        {
          continue;
        }

        try
        {
          var packed = ReadArchivePayload(stream, archiveEntry, archiveName);
          var payload = DecompressPayload(archiveEntry.Compression, packed, archiveEntry.Sha1, archiveEntry.IdPrefix, options.Lzma2Mode);
          var detected = DetectFileType(payload.Bytes);
          if (!filter.TypeMatches(detected.Extension))
          {
            continue;
          }

          inspected++;

          var probe = BuildAssetSemanticProbe(
              payload.Bytes,
              detected,
              scanSemanticStrings: includeEntries || options.SemanticCategoryFilters.Count > 0);
          if (!SemanticCategoryMatches(probe.SemanticCategories, options.SemanticCategoryFilters))
          {
            continue;
          }

          IncrementCount(typeCounts, detected.Extension);
          foreach (var category in probe.SemanticCategories)
          {
            IncrementCount(semanticCategoryCounts, category);
          }

          var signatureKey = $"{detected.Extension}|{probe.First16}";
          if (!groups.TryGetValue(signatureKey, out var group))
          {
            group = new AssetSignatureAccumulator(detected.Extension, probe.First4, probe.First8, probe.First16, probe.MagicLabel);
            groups.Add(signatureKey, group);
          }

          group.Count++;
          group.MinSize = Math.Min(group.MinSize, payload.Bytes.Length);
          group.MaxSize = Math.Max(group.MaxSize, payload.Bytes.Length);
          foreach (var category in probe.SemanticCategories)
          {
            IncrementCount(group.SemanticCategoryCounts, category);
          }

          foreach (var tag in probe.XmlTagCounts)
          {
            AddCount(group.XmlTagCounts, tag.Value, tag.Count);
          }

          foreach (var attribute in probe.XmlAttributeCounts)
          {
            AddCount(group.XmlAttributeCounts, attribute.Value, attribute.Count);
          }

          if (probe.XmlParseStatus is not null)
          {
            IncrementCount(group.XmlParseStatusCounts, probe.XmlParseStatus);
          }

          if (probe.XmlParseWarning is not null)
          {
            IncrementCount(group.XmlParseWarningCounts, probe.XmlParseWarning);
          }

          if (group.Samples.Count < 10)
          {
            group.Samples.Add(new AssetSignatureSample(
                ArchiveName: archiveName,
                EntryIndex: archiveEntry.Index,
                IdPrefix: archiveEntry.IdPrefix,
                Size: payload.Bytes.Length,
                ManifestEntryIndex: manifestEntry?.Index,
                FilenameFnv1Hash: manifestEntry?.FilenameFnv1Hash,
                PakIndex: manifestEntry?.PakIndex,
                PakOffset: manifestEntry?.PakOffset,
                SemanticCategories: probe.SemanticCategories.Take(8).ToList(),
                NameCandidates: probe.NameCandidates.Take(5).ToList()));
          }

          if (includeEntries)
          {
            entries.Add(new AssetSemanticIndexEntry(
                AssetIdPrefix: archiveEntry.IdPrefix,
                ArchiveName: archiveName,
                EntryIndex: archiveEntry.Index,
                ManifestEntryIndex: manifestEntry?.Index,
                FilenameFnv1Hash: manifestEntry?.FilenameFnv1Hash,
                PakIndex: manifestEntry?.PakIndex,
                PakOffset: manifestEntry?.PakOffset,
                CompressedSize: archiveEntry.Size,
                UnpackedSize: payload.Bytes.Length,
                Compression: archiveEntry.Compression,
                DetectedType: detected.Extension,
                Format: detected.Format,
                RiffType: detected.RiffType,
                Width: detected.Width,
                Height: detected.Height,
                MipMapCount: detected.MipMapCount,
                First4: probe.First4,
                First8: probe.First8,
                First16: probe.First16,
                MagicLabel: probe.MagicLabel,
                SemanticCategories: probe.SemanticCategories,
                NameCandidates: probe.NameCandidates,
                ReferenceSamples: probe.ReferenceSamples,
                XmlTagCounts: probe.XmlTagCounts,
                XmlAttributeCounts: probe.XmlAttributeCounts,
                XmlParseStatus: probe.XmlParseStatus,
                XmlParseWarning: probe.XmlParseWarning,
                XmlParseLineNumber: probe.XmlParseLineNumber,
                XmlParseLinePosition: probe.XmlParseLinePosition,
                XmlParsedElementCount: probe.XmlParsedElementCount,
                XmlParsedAttributeNameCount: probe.XmlParsedAttributeNameCount,
                TextSnippetSamples: probe.TextSnippetSamples));
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    var report = new AssetSemanticIndexReport(
        SchemaVersion: "asset-semantic-index/v1",
        GeneratedOutputNotice: "Generated from local copied RIFT assets. Keep under ignored Exports/ unless separately reviewed and redacted.",
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        SemanticCategoryFilters: options.SemanticCategoryFilters,
        InspectedPayloads: inspected,
        Failed: failed,
        TypeCounts: ToTopStringCounts(typeCounts, take: 64),
        SemanticCategoryCounts: ToTopStringCounts(semanticCategoryCounts, take: 64),
        SignatureGroups: groups.Values
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.Type)
            .ThenBy(static g => g.First16)
            .Select(static g => new AssetSignatureGroup(
                Type: g.Type,
                First4: g.First4,
                First8: g.First8,
                First16: g.First16,
                MagicLabel: g.MagicLabel,
                Count: g.Count,
                MinSize: g.MinSize == int.MaxValue ? 0 : g.MinSize,
                MaxSize: g.MaxSize,
                SemanticCategoryCounts: ToTopStringCounts(g.SemanticCategoryCounts, take: 32),
                XmlTagCounts: ToTopStringCounts(g.XmlTagCounts, take: 32),
                XmlAttributeCounts: ToTopStringCounts(g.XmlAttributeCounts, take: 32),
                XmlParseStatusCounts: ToTopStringCounts(g.XmlParseStatusCounts, take: 16),
                XmlParseWarningCounts: ToTopStringCounts(g.XmlParseWarningCounts, take: 16),
                Samples: g.Samples))
            .ToList(),
        Entries: includeEntries ? entries : []);

    var defaultFileName = includeEntries ? "asset-semantic-index.json" : "asset-signature-inventory.json";
    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, defaultFileName);
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"Failed: {failed:N0}");
    Console.WriteLine($"Types: {FormatCounts(typeCounts)}");
    Console.WriteLine($"Semantic categories: {FormatCounts(semanticCategoryCounts)}");
    foreach (var group in report.SignatureGroups.Take(10))
    {
      Console.WriteLine($"- {group.Type} {group.First16}: count={group.Count:N0} size={group.MinSize:N0}..{group.MaxSize:N0} magic={group.MagicLabel}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryBinarySignatures(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var groups = new Dictionary<string, BinarySignatureGroup>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var failed = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (inspected >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          var detected = DetectFileType(payload.Bytes);
          if (detected.Extension != "bin" || !filter.TypeMatches("bin"))
          {
            continue;
          }

          inspected++;
          var probe = BuildBinaryProbe(payload.Bytes);
          var key = probe.First16;
          if (!groups.TryGetValue(key, out var group))
          {
            group = new BinarySignatureGroup(
                First4: probe.First4,
                First8: probe.First8,
                First16: probe.First16,
                Count: 0,
                MinSize: payload.Bytes.Length,
                MaxSize: payload.Bytes.Length,
                SizeModuloCounts: new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase),
                Samples: []);
            groups.Add(key, group);
          }

          group.Count++;
          group.MinSize = Math.Min(group.MinSize, payload.Bytes.Length);
          group.MaxSize = Math.Max(group.MaxSize, payload.Bytes.Length);
          foreach (var stride in probe.StrideCandidates)
          {
            IncrementCount(group.SizeModuloCounts, stride.Stride.ToString());
          }

          if (group.Samples.Count < 10)
          {
            group.Samples.Add(new BinarySignatureSample(
                archiveName,
                entry.Index,
                entry.IdPrefix,
                payload.Bytes.Length,
                manifestEntry?.Index,
                manifestEntry?.FilenameFnv1Hash,
                manifestEntry?.PakIndex,
                ClassifyBinaryCandidate(probe, payload.Bytes.Length)));
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    var report = new BinarySignatureInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedBinPayloads: inspected,
        Failed: failed,
        Groups: groups.Values.OrderByDescending(static g => g.Count).ThenBy(static g => g.First16).ToList());
    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "binary-signatures.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected bin payloads: {inspected:N0}");
    Console.WriteLine($"Groups: {report.Groups.Count:N0}");
    foreach (var group in report.Groups.Take(10))
    {
      Console.WriteLine($"- {group.First16}: count={group.Count} size={group.MinSize:N0}..{group.MaxSize:N0} class={group.Samples.FirstOrDefault()?.Classification}");
    }
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int ProbeBinary(AppOptions options)
  {
    byte[] payload;
    BinaryAssetSource source;
    var rootDirectory = Path.GetFullPath(options.RootDirectory);

    if (!string.IsNullOrWhiteSpace(options.InputPath))
    {
      var inputPath = Path.GetFullPath(options.InputPath);
      payload = File.ReadAllBytes(inputPath);
      source = new BinaryAssetSource(InputPath: inputPath);
    }
    else
    {
      var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
      var lookup = ReadManifestLookup(manifestPath);
      var target = ResolveTargetEntry(options, lookup);
      var found = FindPayloadForId(rootDirectory, lookup, target.IdPrefix, options);
      if (found is null)
      {
        Console.Error.WriteLine($"ERROR: target asset {target.IdPrefix} was not found in copied archives.");
        return 1;
      }

      payload = found.Payload;
      source = new BinaryAssetSource(
          ArchiveName: found.ArchiveName,
          EntryIndex: found.EntryIndex,
          IdPrefix: target.IdPrefix,
          ManifestEntryIndex: target.Index,
          FilenameFnv1Hash: target.FilenameFnv1Hash,
          PakIndex: target.PakIndex,
          PakOffset: target.PakOffset);
    }

    var detected = DetectFileType(payload);
    var probe = BuildBinaryProbe(payload);
    var report = new BinaryProbeReport(
        Source: source,
        Type: detected.Extension,
        Length: payload.Length,
        Classification: detected.Extension == "bin" ? ClassifyBinaryCandidate(probe, payload.Length) : detected.Extension,
        First64: ToHex(payload.AsSpan(0, Math.Min(64, payload.Length))),
        First4: probe.First4,
        First8: probe.First8,
        First16: probe.First16,
        UInt32Values: probe.UInt32Values,
        Int32Values: probe.Int32Values,
        Float32Values: probe.Float32Values,
        StrideCandidates: probe.StrideCandidates);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "binary-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Type: {report.Type}");
    Console.WriteLine($"Length: {report.Length:N0}");
    Console.WriteLine($"Classification: {report.Classification}");
    Console.WriteLine($"First16: {report.First16}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int ProbeNif(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var report = new NifProbeReport(
        Source: source,
        Length: payload.Length,
        First64: ToHex(payload.AsSpan(0, Math.Min(64, payload.Length))),
        Header: header);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF: {header.HeaderString}");
    Console.WriteLine($"Version: {header.VersionText} ({header.VersionHex}) endian={(header.IsLittleEndian ? "little" : "big/unknown")} userVersion={header.UserVersion}");
    Console.WriteLine($"Blocks: {header.BlockCount:N0}; block types: {header.BlockTypeCount:N0}; parsed types: {header.BlockTypes.Count:N0}");
    Console.WriteLine($"Block data: offset={header.BlockDataOffset} totalSize={header.TotalBlockDataSize} delta={header.BlockSizePayloadDelta}");
    Console.WriteLine($"Strings: {header.StringCount:N0}; references: {header.References.Count:N0}");
    Console.WriteLine($"Top block usage: {string.Join(", ", header.BlockTypes.OrderByDescending(static t => t.UsageCount).ThenBy(static t => t.Index).Take(8).Select(FormatBlockTypeUsage))}");
    if (header.Blocks.Count > 0)
    {
      Console.WriteLine($"Block map samples: {string.Join(" | ", header.Blocks.Take(8).Select(static b => $"#{b.Index}:{b.TypeName} size={b.Size} off={b.DataOffset}"))}");
      var meshDataStreamLinks = header.Blocks
          .Where(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase))
          .Select(static b => $"#{b.Index}->{string.Join(",", b.DataStreamReferenceCandidates.Take(4).Select(static r => $"@{r.PayloadOffset}:#{r.TargetBlockIndex}{(r.MaybeStringIndex ? "?" : string.Empty)}"))}")
          .Where(static text => !text.EndsWith("->", StringComparison.Ordinal))
          .Take(6)
          .ToList();
      if (meshDataStreamLinks.Count > 0)
      {
        Console.WriteLine($"Mesh data-stream candidates: {string.Join(" | ", meshDataStreamLinks)}");
      }

      var stringLinkedBlocks = header.Blocks.Where(static b => b.StringSamples.Count > 0).Take(5).ToList();
      if (stringLinkedBlocks.Count > 0)
      {
        Console.WriteLine($"String-linked blocks: {string.Join(" | ", stringLinkedBlocks.Select(static b => $"#{b.Index}:{b.TypeName}->{string.Join(",", b.StringSamples.Take(2).Select(static s => TruncateForConsole(s, 48)))}"))}");
      }
    }
    if (header.References.Count > 0)
    {
      Console.WriteLine($"Reference samples: {string.Join(" | ", header.References.Take(5).Select(static r => TruncateForConsole(r.Value, 96)))}");
    }
    if (header.Warnings.Count > 0)
    {
      Console.WriteLine($"Warnings: {string.Join("; ", header.Warnings)}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static int ProbeNifStreams(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var meshes = new List<NifMeshStreamProbe>();
    foreach (var meshBlock in header.Blocks.Where(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase)))
    {
      if (options.MeshBlockFilter is not null && meshBlock.Index != options.MeshBlockFilter.Value)
      {
        continue;
      }

      var meshPayload = SliceNifBlockPayload(payload, meshBlock);
      var streamCandidates = new List<NifStreamTargetProbe>();
      foreach (var candidate in meshBlock.DataStreamReferenceCandidates.OrderBy(static c => c.PayloadOffset).ThenBy(static c => c.TargetBlockIndex))
      {
        var targetBlock = header.Blocks.FirstOrDefault(b => b.Index == candidate.TargetBlockIndex);
        if (targetBlock is null)
        {
          continue;
        }

        var targetPayload = SliceNifBlockPayload(payload, targetBlock);
        uint? declaredPayloadBytes = targetPayload.Length >= 4
            ? BinaryPrimitives.ReadUInt32LittleEndian(targetPayload[..4])
            : null;
        var declaredPayloadOffset = declaredPayloadBytes is not null && declaredPayloadBytes.Value <= targetPayload.Length
            ? targetPayload.Length - checked((int)declaredPayloadBytes.Value)
            : (int?)null;
        streamCandidates.Add(new NifStreamTargetProbe(
            MeshPayloadOffset: candidate.PayloadOffset,
            TargetBlockIndex: candidate.TargetBlockIndex,
            TargetTypeName: candidate.TargetTypeName,
            TargetDataOffset: targetBlock.DataOffset,
            TargetSize: candidate.TargetSize,
            TargetFirst64: ToHex(targetPayload[..Math.Min(64, targetPayload.Length)]),
            UInt16Prefix: ReadUInt16Prefix(targetPayload, maxValues: 16),
            UInt32Prefix: ReadUInt32Prefix(targetPayload, maxValues: 12),
            Int32Prefix: ReadInt32Prefix(targetPayload, maxValues: 12),
            Float32Prefix: ReadFloat32Prefix(targetPayload, maxValues: 12),
            WholeBlockStrideCandidates: FindWholeBlockStrideCandidates(targetPayload.Length),
            BodyStrideCandidates: FindBodyStrideCandidates(targetPayload.Length).Take(24).ToList(),
            DeclaredPayloadBytes: declaredPayloadBytes,
            DeclaredPayloadOffset: declaredPayloadOffset,
            DeclaredPayloadStrideCandidates: declaredPayloadBytes is not null && declaredPayloadOffset is not null
                ? FindWholeBlockStrideCandidates(checked((int)declaredPayloadBytes.Value))
                : [],
            MaybeStringIndex: candidate.MaybeStringIndex,
            StringValue: candidate.StringValue));
      }

      meshes.Add(new NifMeshStreamProbe(
          MeshBlockIndex: meshBlock.Index,
          MeshSize: meshBlock.Size,
          MeshDataOffset: meshBlock.DataOffset,
          MeshFirst64: ToHex(meshPayload[..Math.Min(64, meshPayload.Length)]),
          UInt32Prefix: meshBlock.UInt32Prefix,
          Int32Prefix: ReadInt32Prefix(meshPayload, maxValues: 12),
          Float32Prefix: meshBlock.Float32Prefix,
          StringSamples: meshBlock.StringSamples,
          StreamCandidates: streamCandidates));
    }

    var report = new NifStreamProbeReport(
        Source: source,
        Length: payload.Length,
        NifVersion: header.VersionText,
        MeshBlockCount: header.Blocks.Count(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase)),
        MeshesEmitted: meshes.Count,
        CandidateLinks: meshes.Sum(static m => m.StreamCandidates.Count),
        HeaderWarnings: header.Warnings,
        Meshes: meshes);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-stream-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF stream probe: version={header.VersionText} meshes={report.MeshBlockCount:N0} emitted={report.MeshesEmitted:N0} candidateLinks={report.CandidateLinks:N0}");
    foreach (var mesh in meshes.Take(8))
    {
      Console.WriteLine($"Mesh #{mesh.MeshBlockIndex} size={mesh.MeshSize:N0} refs={string.Join(", ", mesh.StreamCandidates.Take(8).Select(static c => $"@{c.MeshPayloadOffset}->#{c.TargetBlockIndex}{(c.MaybeStringIndex ? "?" : string.Empty)} size={c.TargetSize:N0}"))}");
      foreach (var stream in mesh.StreamCandidates.Take(4))
      {
        var strideHint = stream.BodyStrideCandidates.FirstOrDefault();
        var strideText = strideHint is null ? "none" : $"header={strideHint.HeaderBytes} stride={strideHint.Stride} count={strideHint.Count}";
        var declaredStrideText = stream.DeclaredPayloadStrideCandidates.Count == 0
            ? "none"
            : FormatPreferredStrideSummary(stream.DeclaredPayloadStrideCandidates, max: 6);
        Console.WriteLine($"  stream #{stream.TargetBlockIndex} first16={stream.TargetFirst64[..Math.Min(32, stream.TargetFirst64.Length)]} declaredPayload={stream.DeclaredPayloadBytes} declaredOffset={stream.DeclaredPayloadOffset} declaredStrides={declaredStrideText} bodyStride={strideText}");
      }
    }

    if (header.Warnings.Count > 0)
    {
      Console.WriteLine($"Warnings: {string.Join("; ", header.Warnings)}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static int ProbeNifMesh(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var meshes = new List<NifMeshProbe>();
    var allMeshBlocks = header.Blocks
        .Where(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase))
        .OrderBy(static b => b.Index)
        .ToList();
    foreach (var meshBlock in allMeshBlocks)
    {
      if (options.MeshBlockFilter is not null && meshBlock.Index != options.MeshBlockFilter.Value)
      {
        continue;
      }

      var meshPayload = SliceNifBlockPayload(payload, meshBlock);
      var streamSummaries = BuildNifMeshBoundStreamSummaries(payload, header, meshBlock);
      var pairings = FindNifMeshProbePairings(streamSummaries);
      var attributeSets = FindNifMeshAttributeSets(null, null, null, meshBlock, streamSummaries);
      var payloadWindows = FindNifMeshPayloadRoleWindows(
          meshPayload,
          pairings.Select(static p => p.VertexCount)
              .Concat(attributeSets.Select(static s => s.VertexCount))
              .Distinct()
              .OrderBy(static c => c)
              .ToList());
      meshes.Add(new NifMeshProbe(
          MeshBlockIndex: meshBlock.Index,
          MeshSize: meshBlock.Size,
          MeshDataOffset: meshBlock.DataOffset,
          MeshFirst64: ToHex(meshPayload[..Math.Min(64, meshPayload.Length)]),
          UInt32Prefix: meshBlock.UInt32Prefix,
          Int32Prefix: ReadInt32Prefix(meshPayload, maxValues: 16),
          Float32Prefix: meshBlock.Float32Prefix,
          StringSamples: meshBlock.StringSamples,
          Streams: streamSummaries,
          Pairings: pairings,
          AttributeSets: attributeSets,
          PayloadWindows: payloadWindows));
    }

    if (options.MeshBlockFilter is not null && meshes.Count == 0)
    {
      Console.Error.WriteLine($"ERROR: NiMesh block #{options.MeshBlockFilter.Value} was not found.");
      return 1;
    }

    var report = new NifMeshProbeReport(
        Source: source,
        Length: payload.Length,
        NifVersion: header.VersionText,
        MeshBlockCount: allMeshBlocks.Count,
        MeshesEmitted: meshes.Count,
        CandidateLinks: meshes.Sum(static m => m.Streams.Count),
        Pairings: meshes.Sum(static m => m.Pairings.Count),
        AttributeSets: meshes.Sum(static m => m.AttributeSets.Count),
        HeaderWarnings: header.Warnings,
        Meshes: meshes);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-mesh-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF mesh probe: version={header.VersionText} meshes={report.MeshBlockCount:N0} emitted={report.MeshesEmitted:N0} candidateLinks={report.CandidateLinks:N0} pairings={report.Pairings:N0} attributeSets={report.AttributeSets:N0}");
    foreach (var mesh in meshes.Take(8))
    {
      Console.WriteLine($"Mesh #{mesh.MeshBlockIndex} size={mesh.MeshSize:N0} refs={string.Join(", ", mesh.Streams.Take(8).Select(static s => $"@{s.MeshPayloadOffset}->#{s.TargetBlockIndex}{(s.MaybeStringIndex ? "?" : string.Empty)}{FormatNifDataStreamUsageAccessInline(s.DataStreamUsage, s.DataStreamAccess)} payload={s.DeclaredPayloadBytes} role={s.RoleStats.PrimaryRole} c={s.RoleStats.Confidence}"))}");
      foreach (var pairing in mesh.Pairings.Take(5))
      {
        Console.WriteLine($"  pairing index@{pairing.IndexMeshPayloadOffset}/#{pairing.IndexBlockIndex}{FormatNifDataStreamUsageAccessInline(pairing.IndexDataStreamUsage, pairing.IndexDataStreamAccess)} {pairing.IndexRole} max={pairing.IndexMax} -> stream@{pairing.VertexMeshPayloadOffset}/#{pairing.VertexBlockIndex}{FormatNifDataStreamUsageAccessInline(pairing.VertexDataStreamUsage, pairing.VertexDataStreamAccess)} {pairing.VertexRole} vertexCount={pairing.VertexCount} coverage={pairing.IndexCoverageRatio:0.####} meta={pairing.DataStreamMetadataScore} confidence={pairing.Confidence}");
      }

      foreach (var attributeSet in mesh.AttributeSets.Take(3))
      {
        Console.WriteLine($"  attributes position@{attributeSet.PositionMeshPayloadOffset}/#{attributeSet.PositionBlockIndex}{FormatNifDataStreamUsageAccessInline(attributeSet.PositionDataStreamUsage, attributeSet.PositionDataStreamAccess)} normal@{attributeSet.NormalMeshPayloadOffset}/#{attributeSet.NormalBlockIndex}{FormatNifDataStreamUsageAccessInline(attributeSet.NormalDataStreamUsage, attributeSet.NormalDataStreamAccess)} uv@{attributeSet.UvMeshPayloadOffset}/#{attributeSet.UvBlockIndex}{FormatNifDataStreamUsageAccessInline(attributeSet.UvDataStreamUsage, attributeSet.UvDataStreamAccess)} vertexCount={attributeSet.VertexCount} meta={attributeSet.DataStreamMetadataScore} confidence={attributeSet.Confidence} topology={FormatNifAttributeTopologySummary(attributeSet.Topology)}");
        foreach (var extra in attributeSet.ExtraStreams.Take(3))
        {
          Console.WriteLine($"    extra @{extra.MeshPayloadOffset}/#{extra.BlockIndex}{FormatNifDataStreamUsageAccessInline(extra.DataStreamUsage, extra.DataStreamAccess)} payload={extra.DeclaredPayloadBytes} role={extra.Role} c={extra.RoleConfidence} fit={extra.FitSummary}");
        }
      }

      foreach (var window in mesh.PayloadWindows.Take(3))
      {
        Console.WriteLine($"  mesh-payload window @{window.PayloadOffset} bytes={window.ByteLength} role={window.Role} vertexCount={window.VertexCount} confidence={window.Confidence} first16={window.First16}");
      }
    }

    if (header.Warnings.Count > 0)
    {
      Console.WriteLine($"Warnings: {string.Join("; ", header.Warnings)}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static int DecodeNifGeometry(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    if (options.MeshBlockFilter is null)
    {
      Console.Error.WriteLine("ERROR: decode-nif-geometry requires --mesh-block <n>.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var meshBlock = header.Blocks.FirstOrDefault(b =>
        string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase) &&
        b.Index == options.MeshBlockFilter.Value);
    if (meshBlock is null)
    {
      Console.Error.WriteLine($"ERROR: NiMesh block #{options.MeshBlockFilter.Value} was not found.");
      return 1;
    }

    var meshPayload = SliceNifBlockPayload(payload, meshBlock);
    var streamSummaries = BuildNifMeshBoundStreamSummaries(payload, header, meshBlock);
    var attributeSets = FindNifMeshAttributeSets(null, null, null, meshBlock, streamSummaries);
    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);

    var objVertices = new List<string>();
    var objNormals = new List<string>();
    var objTexCoords = new List<string>();
    var objFaces = new List<string>();
    var totalPositions = 0;
    var totalNormals = 0;
    var totalUvs = 0;
    var objVertexBase = 0;

    if (attributeSets.Count == 0)
    {
      if (options.ExperimentalPositionSource)
      {
        Console.WriteLine("  [*] ExperimentalPositionSource mode: scanning linked streams for position candidates...");
        var linkedCandidates = ScanNifLinkedStreamPositionCandidates(payload, header, streamSummaries);
        Console.WriteLine($"    linked stream candidates: {linkedCandidates.Count}");
        var float32Candidates = linkedCandidates.Where(static c => c.PositionType == "float32").ToList();
        if (float32Candidates.Count > 0)
        {
          Console.WriteLine($"    float32 position candidates: {float32Candidates.Count}");
          foreach (var candidate in float32Candidates.Take(4))
          {
            Console.WriteLine($"      #{candidate.BlockIndex} offset=@{candidate.MeshPayloadOffset} type={candidate.PositionType} vertexCount={candidate.VertexCount} role={candidate.Role}");
          }

          // Decode positions from the first float32 candidate
          var leadCandidate = float32Candidates[0];
          var vertexCount = leadCandidate.VertexCount;
          var vertexIndices = Enumerable.Range(0, vertexCount).ToList();
          var positionSamples = BuildNifAttributeFloatVertexSamples(
              payload, blocksByIndex, leadCandidate.BlockIndex,
              "position", leadCandidate.Role, components: 3, vertexIndices);
          Console.WriteLine($"    decoded positions: {positionSamples.Count}/{vertexCount}");

          // Print sample vertices
          var sampleCount = Math.Min(4, vertexCount);
          if (positionSamples.Count > 0)
          {
            Console.WriteLine($"    position samples ({sampleCount}):");
            for (var i = 0; i < sampleCount && i < positionSamples.Count; i++)
            {
              var s = positionSamples[i];
              Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)}, {FormatNullableDouble(s.Z)}) prevDist={FormatNullableDouble(s.PreviousDistance)} nextDist={FormatNullableDouble(s.NextDistance)}");
            }
          }

          // Build OBJ data
          if (options.WriteObj || options.ExportObj)
          {
            for (var i = 0; i < positionSamples.Count; i++)
            {
              var s = positionSamples[i];
              if (s.X.HasValue && s.Y.HasValue && s.Z.HasValue)
              {
                objVertices.Add($"v {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Z.Value.ToString("F6", CultureInfo.InvariantCulture)}");
              }
            }
          }

          totalPositions += positionSamples.Count;

          // Decode normals from linked streams
          var normalCandidates = float32Candidates
              .Where(static c => c.Role.StartsWith("normal-", StringComparison.OrdinalIgnoreCase))
              .ToList();
          if (normalCandidates.Count > 0)
          {
            var normalCandidate = normalCandidates[0];
            var normalSamples = BuildNifAttributeFloatVertexSamples(
                payload, blocksByIndex, normalCandidate.BlockIndex,
                "normal", normalCandidate.Role, components: 3, vertexIndices);
            Console.WriteLine($"    decoded normals: {normalSamples.Count}/{vertexCount}");

            if (normalSamples.Count > 0)
            {
              var normalSampleCount = Math.Min(sampleCount, normalSamples.Count);
              Console.WriteLine($"    normal samples ({normalSampleCount}):");
              for (var i = 0; i < normalSampleCount && i < normalSamples.Count; i++)
              {
                var s = normalSamples[i];
                Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)}, {FormatNullableDouble(s.Z)}) len={FormatNullableDouble(s.VectorLength)}");
              }
            }

            if (options.WriteObj || options.ExportObj)
            {
              for (var i = 0; i < normalSamples.Count; i++)
              {
                var s = normalSamples[i];
                if (s.X.HasValue && s.Y.HasValue && s.Z.HasValue)
                {
                  objNormals.Add($"vn {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Z.Value.ToString("F6", CultureInfo.InvariantCulture)}");
                }
              }
            }

            totalNormals += normalSamples.Count;
          }

          // Decode UVs from linked streams
          var uvCandidates = float32Candidates
              .Where(static c => c.Role.StartsWith("uv-", StringComparison.OrdinalIgnoreCase))
              .ToList();
          if (uvCandidates.Count > 0)
          {
            var uvCandidate = uvCandidates[0];
            var uvSamples = BuildNifAttributeFloatVertexSamples(
                payload, blocksByIndex, uvCandidate.BlockIndex,
                "uv", uvCandidate.Role, components: 2, vertexIndices);
            Console.WriteLine($"    decoded uvs: {uvSamples.Count}/{vertexCount}");

            if (options.WriteObj || options.ExportObj)
            {
              for (var i = 0; i < uvSamples.Count; i++)
              {
                var s = uvSamples[i];
                if (s.X.HasValue && s.Y.HasValue)
                {
                  objTexCoords.Add($"vt {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)}");
                }
              }
            }

            totalUvs += uvSamples.Count;
          }

          // Generate triangle faces from paired index streams (ExperimentalPositionSource fallback)
          if ((options.WriteObj || options.ExportObj) && objVertices.Count > 0)
          {
            var pairings = FindNifMeshProbePairings(streamSummaries);
            var confidentPairings = pairings
                .Where(static p => p.Confidence >= 80 && p.IndexMax < ushort.MaxValue)
                .OrderByDescending(static p => p.Confidence)
                .ThenByDescending(static p => p.IndexCoverageRatio)
                .ToList();

            Console.WriteLine($"    index-vertex pairings: {pairings.Count} total, {confidentPairings.Count} confident (minimum 80)");

            if (confidentPairings.Count > 0)
            {
              var bestPairing = confidentPairings[0];
              Console.WriteLine($"    best pairing: index=#{bestPairing.IndexBlockIndex} role={bestPairing.IndexRole} max={bestPairing.IndexMax} vertexCount={bestPairing.VertexCount} coverage={bestPairing.IndexCoverageRatio:0.####} confidence={bestPairing.Confidence}");

              if (blocksByIndex.TryGetValue(bestPairing.IndexBlockIndex, out var indexStreamBlock))
              {
                var indexPayload = SliceNifBlockPayload(payload, indexStreamBlock);
                if (indexPayload.Length >= 4)
                {
                  var indexDeclaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(indexPayload[..4]);
                  if (indexDeclaredBytes > 0 && indexDeclaredBytes <= indexPayload.Length - 4)
                  {
                    var indexHeaderLen = indexPayload.Length - checked((int)indexDeclaredBytes);
                    var indexBody = indexPayload.Slice(indexHeaderLen, checked((int)indexDeclaredBytes));
                    var indices = ReadUInt16BigEndianValues(indexBody);

                    if (indices.Count >= 3)
                    {
                      var vc = vertexCount;
                      var facesGenerated = 0;
                      for (var w = 0; w < indices.Count - 2; w++)
                      {
                        var a = (int)indices[w];
                        var b = (int)indices[w + 1];
                        var c = (int)indices[w + 2];
                        // Skip degenerate triangles (any two equal vertices)
                        if (a == b || a == c || b == c)
                          continue;
                        // Skip out-of-range indices
                        if (a >= vc || b >= vc || c >= vc)
                          continue;
                        var oa = objVertexBase + a + 1;
                        var ob = objVertexBase + b + 1;
                        var oc = objVertexBase + c + 1;
                        if ((w & 1) == 0)
                          objFaces.Add($"f {oa}/{oa}/{oa} {ob}/{ob}/{ob} {oc}/{oc}/{oc}");
                        else
                          objFaces.Add($"f {oa}/{oa}/{oa} {oc}/{oc}/{oc} {ob}/{ob}/{ob}");
                        facesGenerated++;
                      }

                      if (facesGenerated > 0)
                        Console.WriteLine($"    paired strip faces: {facesGenerated} (indices={indices.Count}, vertexBase={objVertexBase})");
                      else
                        Console.WriteLine("    paired strip produced 0 non-degenerate faces");
                    }
                    else
                    {
                      Console.WriteLine($"    index stream #{bestPairing.IndexBlockIndex} has only {indices.Count} indices (need minimum 3)");
                    }
                  }
                  else
                  {
                    Console.WriteLine($"    index stream #{bestPairing.IndexBlockIndex}: declared bytes {indexDeclaredBytes} out of range");
                  }
                }
                else
                {
                  Console.WriteLine($"    index stream #{bestPairing.IndexBlockIndex}: payload too short ({indexPayload.Length} bytes)");
                }
              }
              else
              {
                Console.WriteLine($"    index stream block #{bestPairing.IndexBlockIndex} not found in block map");
              }
            }
            else if (pairings.Count > 0)
            {
              Console.WriteLine($"    all {pairings.Count} pairings below confidence 80; top confidence={pairings[0].Confidence}");
            }
            else
            {
              Console.WriteLine("    no index-vertex pairings found; OBJ will have vertices but no faces");
            }
          }

        }
        else
        {
          Console.Error.WriteLine("ERROR: no float32 position candidates found in linked streams.");
          Console.WriteLine($"  Found {linkedCandidates.Count} non-float32 candidates: {string.Join(", ", linkedCandidates.Select(static c => c.PositionType).Distinct())}");
        }
      }
      else
      {
        Console.Error.WriteLine("ERROR: no attribute sets found for this mesh. Use --experimental-position-source to probe linked streams.");
      }

      if (objVertices.Count == 0)
      {
        return 1;
      }
    }

    Console.WriteLine($"NIF geometry decode: version={header.VersionText} mesh=#{meshBlock.Index}");
    Console.WriteLine($"Attribute sets: {attributeSets.Count}");
    Console.WriteLine();

    for (var setIndex = 0; setIndex < attributeSets.Count; setIndex++)
    {
      var set = attributeSets[setIndex];
      var vertexCount = set.VertexCount;
      var vertexIndices = Enumerable.Range(0, vertexCount).ToList();

      Console.WriteLine($"  Attribute set {setIndex}: vertexCount={vertexCount} confidence={set.Confidence}");
      Console.WriteLine($"    position @{set.PositionMeshPayloadOffset}/#{set.PositionBlockIndex} role={set.PositionRole}");
      Console.WriteLine($"    normal   @{set.NormalMeshPayloadOffset}/#{set.NormalBlockIndex} role={set.NormalRole}");
      Console.WriteLine($"    uv       @{set.UvMeshPayloadOffset}/#{set.UvBlockIndex} role={set.UvRole}");

      // Decode positions (float32)
      var positionSamples = BuildNifAttributeFloatVertexSamples(
          payload, blocksByIndex, set.PositionBlockIndex,
          "position", set.PositionRole, components: 3, vertexIndices);

      // Decode normals (float32)
      var normalSamples = BuildNifAttributeFloatVertexSamples(
          payload, blocksByIndex, set.NormalBlockIndex,
          "normal", set.NormalRole, components: 3, vertexIndices);

      // Decode UVs (float32)
      var uvSamples = BuildNifAttributeFloatVertexSamples(
          payload, blocksByIndex, set.UvBlockIndex,
          "uv", set.UvRole, components: 2, vertexIndices);

      Console.WriteLine($"    decoded positions: {positionSamples.Count}/{vertexCount}");
      Console.WriteLine($"    decoded normals:   {normalSamples.Count}/{vertexCount}");
      Console.WriteLine($"    decoded uvs:       {uvSamples.Count}/{vertexCount}");

      // Print sample vertices
      var sampleCount = Math.Min(4, vertexCount);
      if (positionSamples.Count > 0)
      {
        Console.WriteLine($"    position samples ({sampleCount}):");
        for (var i = 0; i < sampleCount && i < positionSamples.Count; i++)
        {
          var s = positionSamples[i];
          Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)}, {FormatNullableDouble(s.Z)}) prevDist={FormatNullableDouble(s.PreviousDistance)} nextDist={FormatNullableDouble(s.NextDistance)}");
        }
      }

      if (normalSamples.Count > 0)
      {
        Console.WriteLine($"    normal samples ({sampleCount}):");
        for (var i = 0; i < sampleCount && i < normalSamples.Count; i++)
        {
          var s = normalSamples[i];
          Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)}, {FormatNullableDouble(s.Z)}) len={FormatNullableDouble(s.VectorLength)}");
        }
      }

      if (uvSamples.Count > 0)
      {
        Console.WriteLine($"    uv samples ({sampleCount}):");
        for (var i = 0; i < sampleCount && i < uvSamples.Count; i++)
        {
          var s = uvSamples[i];
          Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)})");
        }
      }

      // Experimental: UInt16-packed position decode
      if (options.Experimental)
      {
        Console.WriteLine();
        Console.WriteLine("  [*] Experimental mode: scanning for UInt16-packed position streams...");

        var u16PositionVertices = new List<NifAttributeVertexSample>();
        foreach (var stream in streamSummaries)
        {
          if (!blocksByIndex.TryGetValue(stream.TargetBlockIndex, out var streamBlock))
            continue;

          var blockPayload = SliceNifBlockPayload(payload, streamBlock);
          if (blockPayload.Length < 4)
            continue;

          var declaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
          if (declaredBytes > blockPayload.Length)
            continue;

          var headerLen = blockPayload.Length - checked((int)declaredBytes);
          var body = blockPayload.Slice(headerLen, checked((int)declaredBytes));

          var triplesPrefix = ReadUInt16BigEndianTriplesPrefix(body, maxValues: 16);
          var structure = AnalyzeNifUInt16TriplesStructure(triplesPrefix);

          if (structure.Magic43606Found && structure.MetadataSentinelPattern)
          {
            Console.WriteLine($"    Stream #{stream.TargetBlockIndex} @{stream.MeshPayloadOffset}: magic=43606 structure={structure.StructuralFamily}");
            var u16Vertices = BuildNifAttributeUInt16VertexSamples(
                payload, blocksByIndex, stream.TargetBlockIndex, maxVertices: vertexCount);

            if (u16Vertices.Count > 0)
            {
              u16PositionVertices.AddRange(u16Vertices);
              Console.WriteLine($"      decoded {u16Vertices.Count} UInt16-packed position vertices");
              var u16Sample = Math.Min(4, u16Vertices.Count);
              for (var i = 0; i < u16Sample; i++)
              {
                var s = u16Vertices[i];
                Console.WriteLine($"      v{s.Index}: ({FormatNullableDouble(s.X)}, {FormatNullableDouble(s.Y)})");
              }
            }
          }
        }

        if (u16PositionVertices.Count == 0)
        {
          Console.WriteLine("    No magic-43606 UInt16-packed position streams found.");
        }
        else if (options.WriteObj)
        {
          // Use UInt16 positions for OBJ
          objVertices.Clear();
          foreach (var v in u16PositionVertices.OrderBy(v => v.Index))
          {
            // 2D u16-packed positions; Z coordinate is not present in this encoding
            objVertices.Add($"v {(v.X ?? 0.0).ToString("F6", CultureInfo.InvariantCulture)} {(v.Y ?? 0.0).ToString("F6", CultureInfo.InvariantCulture)} 0.000000");
          }
        }
      }

      // Build OBJ data for float32 decode
      if ((options.WriteObj || options.ExportObj) && !options.Experimental)
      {
        for (var i = 0; i < positionSamples.Count; i++)
        {
          var s = positionSamples[i];
          if (s.X.HasValue && s.Y.HasValue && s.Z.HasValue)
          {
            objVertices.Add($"v {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Z.Value.ToString("F6", CultureInfo.InvariantCulture)}");
          }
        }
        for (var i = 0; i < normalSamples.Count; i++)
        {
          var s = normalSamples[i];
          if (s.X.HasValue && s.Y.HasValue && s.Z.HasValue)
          {
            objNormals.Add($"vn {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Z.Value.ToString("F6", CultureInfo.InvariantCulture)}");
          }
        }
        for (var i = 0; i < uvSamples.Count; i++)
        {
          var s = uvSamples[i];
          if (s.X.HasValue && s.Y.HasValue)
          {
            objTexCoords.Add($"vt {s.X.Value.ToString("F6", CultureInfo.InvariantCulture)} {s.Y.Value.ToString("F6", CultureInfo.InvariantCulture)}");
          }
        }
      }

      totalPositions += positionSamples.Count;
      totalNormals += normalSamples.Count;
      totalUvs += uvSamples.Count;

      // Generate triangle faces from UInt16 big-endian index strip at @264 extra stream
      if ((options.WriteObj || options.ExportObj) && !options.Experimental)
      {
        var extra264Found = false;
        var extra264Skipped = 0;
        foreach (var extra in set.ExtraStreams)
        {
          if (extra.MeshPayloadOffset != 264)
            continue;
          if (extra264Found)
          {
            extra264Skipped++;
            continue;
          }
          if (!blocksByIndex.TryGetValue(extra.BlockIndex, out var extraBlock))
            continue;
          var extraPayload = SliceNifBlockPayload(payload, extraBlock);
          if (extraPayload.Length < 4)
            continue;
          var declaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(extraPayload[..4]);
          if (declaredBytes > extraPayload.Length)
            continue;
          var headerLen = extraPayload.Length - checked((int)declaredBytes);
          var body = extraPayload.Slice(headerLen, checked((int)declaredBytes));
          var indices = ReadUInt16BigEndianValues(body);
          if (indices.Count < 3)
            continue;

          // Walk as degenerate-bridge triangle strip (raw-zero-based mapping)
          var vc = set.VertexCount;
          var pairCount = indices.Count - 1;
          var windowCount = Math.Max(0, pairCount - 1);
          var facesGenerated = 0;
          for (var w = 0; w < windowCount; w++)
          {
            var a = (int)indices[w];
            var b = (int)indices[w + 1];
            var c = (int)indices[w + 2];
            // Skip degenerate triangles (any two equal vertices) — closes the strip segment
            if (a == b || a == c || b == c)
              continue;
            // Skip out-of-range indices
            if (a >= vc || b >= vc || c >= vc)
              continue;
            // OBJ uses 1-based indices; raw-zero-based strip indices match OBJ vertex order
            var oa = objVertexBase + a + 1;
            var ob = objVertexBase + b + 1;
            var oc = objVertexBase + c + 1;
            // Even windows maintain winding (a,b,c), odd windows flip (a,c,b) for strip consistency
            if ((w & 1) == 0)
              objFaces.Add($"f {oa}/{oa}/{oa} {ob}/{ob}/{ob} {oc}/{oc}/{oc}");
            else
              objFaces.Add($"f {oa}/{oa}/{oa} {oc}/{oc}/{oc} {ob}/{ob}/{ob}");
            facesGenerated++;
          }

          if (facesGenerated > 0)
            Console.WriteLine($"    @264 strip faces: {facesGenerated} (indices={indices.Count}, windows={windowCount}, vertexBase={objVertexBase})");
          break; // Use first @264 extra stream found
        }
      }

      objVertexBase = objVertices.Count;
    }

    // Write OBJ file
    if (options.WriteObj || options.ExportObj)
    {
      var outDir = ResolveOutputPath(rootDirectory, options.OutDirectory, "decode-nif-geometry");
      Directory.CreateDirectory(outDir);
      var objPath = Path.Combine(outDir, $"decode-nif-geometry-mesh{meshBlock.Index}.obj");
      using var writer = new StreamWriter(objPath, false, Encoding.ASCII);
      writer.WriteLine($"# RiftAssetDumper decode-nif-geometry");
      writer.WriteLine($"# NIF version: {header.VersionText}");
      writer.WriteLine($"# Mesh block: #{meshBlock.Index}");
      writer.WriteLine($"# Positions: {objVertices.Count}  Normals: {objNormals.Count}  UVs: {objTexCoords.Count}");
      writer.WriteLine($"# Faces: {objFaces.Count}  (degenerate-bridge UInt16BE strip)");
      writer.WriteLine();
      foreach (var v in objVertices)
        writer.WriteLine(v);
      foreach (var vn in objNormals)
        writer.WriteLine(vn);
      foreach (var vt in objTexCoords)
        writer.WriteLine(vt);
      if (objFaces.Count > 0)
      {
        writer.WriteLine();
        foreach (var f in objFaces)
          writer.WriteLine(f);
      }
      writer.WriteLine();
      writer.WriteLine($"# End of file. {objVertices.Count} vertices, {objFaces.Count} faces.");
      Console.WriteLine();
      Console.WriteLine($"OBJ written: {DisplayPath(options, objPath)}");
      Console.WriteLine($"  Vertices: {objVertices.Count}");
      Console.WriteLine($"  Normals:  {objNormals.Count}");
      Console.WriteLine($"  TexCoords: {objTexCoords.Count}");
      Console.WriteLine($"  Faces: {objFaces.Count}");
    }

    var sourceLabel = attributeSets.Count > 0 ? $"{attributeSets.Count} attribute sets" : "linked-stream fallback";
    Console.WriteLine();
    Console.WriteLine($"Summary: {totalPositions} positions, {totalNormals} normals, {totalUvs} UVs across {sourceLabel}");

    return 0;
  }

  private static int ValidateUInt16Positions(AppOptions options)
  {
    if (options.IdFilter is null)
    {
      Console.Error.WriteLine("ERROR: validate-uint16-positions requires --id <16hex>.");
      return 1;
    }

    if (options.MeshBlockFilter is null)
    {
      Console.Error.WriteLine("ERROR: validate-uint16-positions requires --mesh-block <n>.");
      return 1;
    }

    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var meshBlock = header.Blocks.FirstOrDefault(b =>
        string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase) &&
        b.Index == options.MeshBlockFilter.Value);
    if (meshBlock is null)
    {
      Console.Error.WriteLine($"ERROR: NiMesh block #{options.MeshBlockFilter.Value} was not found.");
      return 1;
    }

    var meshPayload = SliceNifBlockPayload(payload, meshBlock);
    var streamSummaries = BuildNifMeshBoundStreamSummaries(payload, header, meshBlock);
    var attributeSets = FindNifMeshAttributeSets(null, null, null, meshBlock, streamSummaries);
    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);

    if (attributeSets.Count == 0)
    {
      Console.Error.WriteLine("ERROR: no attribute sets found for this mesh.");
      return 1;
    }

    Console.WriteLine($"NIF packed positions cross-validation: version={header.VersionText} mesh=#{meshBlock.Index}");
    Console.WriteLine($"Attribute sets: {attributeSets.Count}");
    Console.WriteLine();

    for (var setIndex = 0; setIndex < attributeSets.Count; setIndex++)
    {
      var set = attributeSets[setIndex];
      var vertexCount = set.VertexCount;
      var vertexIndices = Enumerable.Range(0, vertexCount).ToList();

      // Decode Float32 Positions
      var float32Samples = BuildNifAttributeFloatVertexSamples(
          payload, blocksByIndex, set.PositionBlockIndex,
          "position", set.PositionRole, components: 3, vertexIndices);

      // Decode experimental UInt16 Positions
      List<NifAttributeVertexSample>? u16Samples = null;
      var u16BlockIndex = -1;
      foreach (var stream in streamSummaries)
      {
        if (!blocksByIndex.TryGetValue(stream.TargetBlockIndex, out var streamBlock))
          continue;

        var blockPayload = SliceNifBlockPayload(payload, streamBlock);
        if (blockPayload.Length < 4)
          continue;

        var declaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
        if (declaredBytes > blockPayload.Length)
          continue;

        var headerLen = blockPayload.Length - checked((int)declaredBytes);
        var body = blockPayload.Slice(headerLen, checked((int)declaredBytes));

        var triplesPrefix = ReadUInt16BigEndianTriplesPrefix(body, maxValues: 16);
        var structure = AnalyzeNifUInt16TriplesStructure(triplesPrefix);

        if (structure.Magic43606Found && structure.MetadataSentinelPattern)
        {
          u16Samples = BuildNifAttributeUInt16VertexSamples(
              payload, blocksByIndex, stream.TargetBlockIndex, maxVertices: vertexCount);
          u16BlockIndex = stream.TargetBlockIndex;
          break;
        }
      }

      if (float32Samples.Count == 0 || u16Samples == null || u16Samples.Count == 0)
      {
        Console.WriteLine($"[WARNING] Attribute set {setIndex}: missing one or both position streams.");
        continue;
      }

      if (float32Samples.Count != u16Samples.Count)
      {
        Console.WriteLine($"[WARNING] Attribute set {setIndex}: vertex count mismatch! Float32 count = {float32Samples.Count}, UInt16 count = {u16Samples.Count}");
        continue;
      }

      // OLS Fitting helper
      static UInt16ValidationFitStats FitDimension(List<double> u, List<double> f)
      {
        var N = u.Count;
        double sumU = 0, sumF = 0, sumUU = 0, sumFF = 0, sumUF = 0;
        var minF = double.MaxValue;
        var maxF = double.MinValue;
        for (var i = 0; i < N; i++)
        {
          var ui = u[i];
          var fi = f[i];
          sumU += ui;
          sumF += fi;
          sumUU += ui * ui;
          sumFF += fi * fi;
          sumUF += ui * fi;
          if (fi < minF) minF = fi;
          if (fi > maxF) maxF = fi;
        }

        var span = maxF - minF;
        var meanF = sumF / N;

        double a, b;
        var denominator = N * sumUU - sumU * sumU;
        if (Math.Abs(denominator) < 1e-12)
        {
          a = 1.0;
          b = 0.0;
        }
        else
        {
          a = (N * sumUF - sumU * sumF) / denominator;
          b = (sumF - a * sumU) / N;
        }

        double sse = 0;
        double sst = 0;
        double maxError = 0;
        for (var i = 0; i < N; i++)
        {
          var ui = u[i];
          var fi = f[i];
          var fit = a * ui + b;
          var error = fit - fi;
          sse += error * error;
          sst += (fi - meanF) * (fi - meanF);
          var absErr = Math.Abs(error);
          if (absErr > maxError)
            maxError = absErr;
        }

        var rms = Math.Sqrt(sse / N);
        var r2 = 1.0;
        if (sst > 1e-12)
        {
          r2 = 1.0 - (sse / sst);
        }
        else
        {
          r2 = Math.Abs(sse) < 1e-12 ? 1.0 : 0.0;
        }

        var threshold = 0.001 * span;
        if (threshold < 1e-6) threshold = 1e-6;

        var outliers = 0;
        for (var i = 0; i < N; i++)
        {
          var fit = a * u[i] + b;
          if (Math.Abs(fit - f[i]) > threshold)
          {
            outliers++;
          }
        }

        return new UInt16ValidationFitStats(
            Scale: a,
            Translation: b,
            RSquared: r2,
            RmsError: rms,
            MaxError: maxError,
            Span: span,
            OutlierThreshold: threshold,
            OutlierCount: outliers);
      }

      var uX = u16Samples.Select(s => s.X ?? 0.0).ToList();
      var uY = u16Samples.Select(s => s.Y ?? 0.0).ToList();
      var fX = float32Samples.Select(s => s.X ?? 0.0).ToList();
      var fY = float32Samples.Select(s => s.Y ?? 0.0).ToList();

      var statsX = FitDimension(uX, fX);
      var statsY = FitDimension(uY, fY);

      // Display Table
      Console.WriteLine("==========================================================================");
      Console.WriteLine("          UInt16-Packed Position Cross-Validation Summary                 ");
      Console.WriteLine("==========================================================================");
      Console.WriteLine($"Asset ID:      {options.IdFilter}");
      Console.WriteLine($"Mesh Block:    #{options.MeshBlockFilter.Value}");
      Console.WriteLine($"Vertex Count:  {vertexCount}");
      Console.WriteLine($"Float32 Block: #{set.PositionBlockIndex}  Role: {set.PositionRole}");
      Console.WriteLine($"UInt16 Block:  #{u16BlockIndex}  Role: position-u16-packed-experimental");
      Console.WriteLine("--------------------------------------------------------------------------");
      Console.WriteLine(" Dimension |    Scale   |  Translate |    R²    | RMS Error  | Outliers / Total");
      Console.WriteLine("--------------------------------------------------------------------------");
      Console.WriteLine($"     X     | {statsX.Scale,10:F4} | {statsX.Translation,10:F4} | {statsX.RSquared,8:F6} | {statsX.RmsError,10:F6} | {statsX.OutlierCount,3} / {vertexCount}");
      Console.WriteLine($"     Y     | {statsY.Scale,10:F4} | {statsY.Translation,10:F4} | {statsY.RSquared,8:F6} | {statsY.RmsError,10:F6} | {statsY.OutlierCount,3} / {vertexCount}");
      Console.WriteLine("==========================================================================");
      Console.WriteLine();

      // Prepare Vertices detailed list
      var vertices = new List<UInt16ValidationVertex>();
      for (var i = 0; i < vertexCount; i++)
      {
        var f32 = float32Samples[i];
        var u16 = u16Samples[i];
        var fitX = statsX.Scale * (u16.X ?? 0.0) + statsX.Translation;
        var fitY = statsY.Scale * (u16.Y ?? 0.0) + statsY.Translation;
        var errX = fitX - (f32.X ?? 0.0);
        var errY = fitY - (f32.Y ?? 0.0);
        var isOut = Math.Abs(errX) > statsX.OutlierThreshold || Math.Abs(errY) > statsY.OutlierThreshold;

        vertices.Add(new UInt16ValidationVertex(
            Index: i,
            Float32: new UInt16ValidationCoordinate3D(f32.X ?? 0.0, f32.Y ?? 0.0, f32.Z ?? 0.0),
            UInt16Normalized: new UInt16ValidationCoordinate2D(u16.X ?? 0.0, u16.Y ?? 0.0),
            Fitted: new UInt16ValidationCoordinate2D(fitX, fitY),
            Delta: new UInt16ValidationCoordinate2D(errX, errY),
            IsOutlier: isOut));
      }

      var fitSuccess = statsX.RSquared >= 0.99 && statsY.RSquared >= 0.99 && statsX.OutlierCount == 0 && statsY.OutlierCount == 0;

      var report = new UInt16ValidationReport(
          AssetId: options.IdFilter,
          MeshBlock: options.MeshBlockFilter.Value,
          VertexCount: vertexCount,
          AttributeSetIndex: setIndex,
          Float32BlockIndex: set.PositionBlockIndex,
          UInt16BlockIndex: u16BlockIndex,
          FitResults: new Dictionary<string, UInt16ValidationFitStats>
          {
                    { "X", statsX },
                    { "Y", statsY }
          },
          Overall: new UInt16ValidationOverallStats(
              TotalOutliers: statsX.OutlierCount + statsY.OutlierCount,
              FitSuccess: fitSuccess),
          Vertices: vertices);

      // Write report JSON
      var defaultName = $"uint16-validation-{options.IdFilter}-mesh{options.MeshBlockFilter.Value}.json";
      var defaultDirName = Path.Combine("discovery-plan", "stage1", "validation", defaultName);
      var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, defaultDirName);

      Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
      File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);
      Console.WriteLine($"Detailed validation report saved: {DisplayPath(options, outPath)}");
    }

    return 0;
  }

  private static int ProbeNifAttributeExtra(AppOptions options)
  {
    if (options.MeshBlockFilter is null)
    {
      Console.Error.WriteLine("ERROR: probe-nif-attribute-extra requires --mesh-block <n>.");
      return 1;
    }

    if (options.ExtraOffsetFilter is null)
    {
      Console.Error.WriteLine("ERROR: probe-nif-attribute-extra requires --extra-offset <n>.");
      return 1;
    }

    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var meshBlock = header.Blocks.FirstOrDefault(b =>
        string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase) &&
        b.Index == options.MeshBlockFilter.Value);
    if (meshBlock is null)
    {
      Console.Error.WriteLine($"ERROR: NiMesh block #{options.MeshBlockFilter.Value} was not found.");
      return 1;
    }

    var meshPayload = SliceNifBlockPayload(payload, meshBlock);
    var streamSummaries = BuildNifMeshBoundStreamSummaries(payload, header, meshBlock);
    var attributeSets = FindNifMeshAttributeSets(null, null, null, meshBlock, streamSummaries);
    var matches = new List<NifAttributeExtraProbeMatch>();
    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);

    for (var attributeSetIndex = 0; attributeSetIndex < attributeSets.Count; attributeSetIndex++)
    {
      var attributeSet = attributeSets[attributeSetIndex];
      foreach (var extra in attributeSet.ExtraStreams.Where(e => e.MeshPayloadOffset == options.ExtraOffsetFilter.Value))
      {
        var extraSummary = streamSummaries.FirstOrDefault(s =>
            s.MeshPayloadOffset == extra.MeshPayloadOffset &&
            s.TargetBlockIndex == extra.BlockIndex);
        var roleStats = extraSummary?.RoleStats;
        var isIndexRole = roleStats?.IndexStats is not null;
        blocksByIndex.TryGetValue(extra.BlockIndex, out var extraBlock);
        var blockPayload = extraBlock is null
            ? ReadOnlySpan<byte>.Empty
            : SliceNifBlockPayload(payload, extraBlock);
        uint? declaredPayloadBytes = null;
        int? headerBytes = null;
        ReadOnlySpan<byte> body = ReadOnlySpan<byte>.Empty;
        NifStreamBodyStats? bodyStats = null;
        if (blockPayload.Length >= 4)
        {
          declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
          if (declaredPayloadBytes.Value <= blockPayload.Length)
          {
            headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes.Value);
            body = blockPayload.Slice(headerBytes.Value, checked((int)declaredPayloadBytes.Value));
            bodyStats = AnalyzeNifStreamBody(body);
          }
        }

        var indexCompatibility = isIndexRole ? BuildNifAttributeExtraIndexCompatibility(attributeSet.VertexCount, roleStats?.IndexStats, body) : null;
        var vertexSampleIndices = BuildNifAttributeVertexSampleIndices(attributeSet.VertexCount, indexCompatibility);
        var positionVertexSamples = BuildNifAttributeFloatVertexSamples(
            payload,
            blocksByIndex,
            attributeSet.PositionBlockIndex,
            "position",
            attributeSet.PositionRole,
            components: 3,
            vertexSampleIndices);
        var normalVertexSamples = BuildNifAttributeFloatVertexSamples(
            payload,
            blocksByIndex,
            attributeSet.NormalBlockIndex,
            "normal",
            attributeSet.NormalRole,
            components: 3,
            vertexSampleIndices);
        var uvVertexSamples = BuildNifAttributeFloatVertexSamples(
            payload,
            blocksByIndex,
            attributeSet.UvBlockIndex,
            "uv",
            attributeSet.UvRole,
            components: 2,
            vertexSampleIndices);
        var mappingPositionFitness = BuildNifAttributeMappingPositionFitness(
            payload,
            blocksByIndex,
            attributeSet,
            body,
            indexCompatibility);

        matches.Add(new NifAttributeExtraProbeMatch(
            AttributeSetIndex: attributeSetIndex,
            VertexCount: attributeSet.VertexCount,
            Topology: attributeSet.Topology,
            PositionMeshPayloadOffset: attributeSet.PositionMeshPayloadOffset,
            PositionBlockIndex: attributeSet.PositionBlockIndex,
            PositionDeclaredPayloadBytes: attributeSet.PositionDeclaredPayloadBytes,
            PositionRole: attributeSet.PositionRole,
            NormalMeshPayloadOffset: attributeSet.NormalMeshPayloadOffset,
            NormalBlockIndex: attributeSet.NormalBlockIndex,
            NormalDeclaredPayloadBytes: attributeSet.NormalDeclaredPayloadBytes,
            NormalRole: attributeSet.NormalRole,
            UvMeshPayloadOffset: attributeSet.UvMeshPayloadOffset,
            UvBlockIndex: attributeSet.UvBlockIndex,
            UvDeclaredPayloadBytes: attributeSet.UvDeclaredPayloadBytes,
            UvRole: attributeSet.UvRole,
            ExtraMeshPayloadOffset: extra.MeshPayloadOffset,
            ExtraBlockIndex: extra.BlockIndex,
            ExtraTargetTypeName: extraBlock?.TypeName ?? "missing-block",
            ExtraBlockSize: extraBlock?.Size,
            ExtraDeclaredPayloadBytes: declaredPayloadBytes,
            HeaderBytes: headerBytes,
            BodyOffset: headerBytes,
            Role: extra.Role,
            RoleConfidence: extra.RoleConfidence,
            FitSummary: extra.FitSummary,
            BlockFirst64: ToHex(blockPayload[..Math.Min(64, blockPayload.Length)]),
            BodyFirst64: ToHex(body[..Math.Min(64, body.Length)]),
            BodyFirst128: ToHex(body[..Math.Min(128, body.Length)]),
            BodyStats: bodyStats,
            RoleCandidates: roleStats?.RoleCandidates ?? [],
            RoleEvidence: roleStats?.Evidence ?? [],
            VertexCountCandidates: roleStats?.VertexCountCandidates ?? [],
            IndexMax: isIndexRole ? roleStats?.IndexMax : null,
            IndexPairCount: isIndexRole ? roleStats?.IndexPairCount : null,
            IndexStats: isIndexRole ? roleStats?.IndexStats : null,
            IndexCompatibility: indexCompatibility,
            PositionVertexSamples: positionVertexSamples,
            NormalVertexSamples: normalVertexSamples,
            UvVertexSamples: uvVertexSamples,
            MappingPositionFitness: mappingPositionFitness,
            UInt8Prefix: body[..Math.Min(64, body.Length)].ToArray().ToList(),
            ByteHistogramTop: BuildByteHistogram(body, maxEntries: 16),
            UInt16LittleEndianPrefix: ReadUInt16Prefix(body, maxValues: 32),
            UInt16BigEndianPrefix: ReadUInt16BigEndianPrefix(body, maxValues: 32),
            UInt32LittleEndianPrefix: ReadUInt32Prefix(body, maxValues: 24),
            UInt32BigEndianPrefix: ReadUInt32BigEndianPrefix(body, maxValues: 24),
            Float32LittleEndianPrefix: ReadFloat32Prefix(body, maxValues: 24),
            Float32BigEndianPrefix: ReadFloat32BigEndianPrefix(body, maxValues: 24),
            Repeated2BytePatterns: FindRepeatedFixedWidthPatterns(body, width: 2, maxEntries: 12),
            Repeated4BytePatterns: FindRepeatedFixedWidthPatterns(body, width: 4, maxEntries: 12),
            GroupedViews: BuildNifAttributeExtraGroupedViews(body, attributeSet)));
      }
    }

    if (matches.Count == 0)
    {
      var available = attributeSets
          .SelectMany(static a => a.ExtraStreams)
          .OrderBy(static e => e.MeshPayloadOffset)
          .ThenBy(static e => e.BlockIndex)
          .Select(static e => $"@{e.MeshPayloadOffset}/#{e.BlockIndex}")
          .Distinct(StringComparer.Ordinal)
          .Take(16)
          .ToList();
      var suffix = available.Count == 0
          ? " No attribute extra streams were found for this mesh."
          : $" Available extras: {string.Join(", ", available)}.";
      Console.Error.WriteLine($"ERROR: no attribute extra stream was found at mesh payload offset @{options.ExtraOffsetFilter.Value} on NiMesh #{meshBlock.Index}.{suffix}");
      return 1;
    }

    var report = new NifAttributeExtraProbeReport(
        Source: source,
        Length: payload.Length,
        NifVersion: header.VersionText,
        MeshBlockIndex: meshBlock.Index,
        MeshSize: meshBlock.Size,
        MeshDataOffset: meshBlock.DataOffset,
        MeshFirst64: ToHex(meshPayload[..Math.Min(64, meshPayload.Length)]),
        AttributeSets: attributeSets.Count,
        ExtraMeshPayloadOffset: options.ExtraOffsetFilter.Value,
        Matches: matches.Count,
        HeaderWarnings: header.Warnings,
        ExtraStreams: matches);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-attribute-extra-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF attribute extra probe: version={header.VersionText} mesh=#{meshBlock.Index} size={meshBlock.Size:N0} attributeSets={attributeSets.Count:N0} matches={matches.Count:N0}");
    foreach (var match in matches.Take(8))
    {
      var topBytes = match.ByteHistogramTop.Count == 0
          ? "none"
          : string.Join(",", match.ByteHistogramTop.Take(6).Select(static h => $"{h.Hex}x{h.Count}"));
      Console.WriteLine($"Extra @{match.ExtraMeshPayloadOffset}/#{match.ExtraBlockIndex} payload={match.ExtraDeclaredPayloadBytes} header={match.HeaderBytes} role={match.Role} c={match.RoleConfidence} fit={match.FitSummary}");
      Console.WriteLine($"  first64={match.BodyFirst64}");
      Console.WriteLine($"  top bytes={topBytes}");
      Console.WriteLine($"  u16le={string.Join(",", match.UInt16LittleEndianPrefix.Take(12))}");
      Console.WriteLine($"  u16be={string.Join(",", match.UInt16BigEndianPrefix.Take(12))}");
      Console.WriteLine($"  u32le={string.Join(",", match.UInt32LittleEndianPrefix.Take(8))}");
      Console.WriteLine($"  u32be={string.Join(",", match.UInt32BigEndianPrefix.Take(8))}");
      Console.WriteLine($"  f32le={string.Join(",", match.Float32LittleEndianPrefix.Take(8).Select(static f => f?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"))}");
      Console.WriteLine($"  f32be={string.Join(",", match.Float32BigEndianPrefix.Take(8).Select(static f => f?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"))}");
      if (match.IndexCompatibility is not null)
      {
        Console.WriteLine($"  index {match.IndexCompatibility.CandidateTopology}: min={match.IndexCompatibility.MinIndex} max={match.IndexCompatibility.MaxIndex} distinct={match.IndexCompatibility.DistinctIndexCount} withinVertexCount={match.IndexCompatibility.MaxIndexWithinVertexCount} maxCoverage={match.IndexCompatibility.MaxIndexCoverageRatio:0.####} distinctCoverage={match.IndexCompatibility.DistinctIndexCoverageRatio:0.####}");
        Console.WriteLine($"  index baseHint={match.IndexCompatibility.IndexBaseHint} usesZero={match.IndexCompatibility.UsesZeroIndex}");
        Console.WriteLine($"  index stripNonDegenerate={match.IndexCompatibility.TriangleStripNonDegenerateWindowCount}/{match.IndexCompatibility.TriangleStripWindowCount} stripDegenerate={match.IndexCompatibility.TriangleStripDegenerateRatio:0.####} tripleDegenerate={match.IndexCompatibility.DegenerateTriangleRatio:0.####} first={string.Join(",", match.IndexCompatibility.FirstIndices.Take(16))}");
        Console.WriteLine($"  strip structure={match.IndexCompatibility.StripStructure.Hint} degRuns={match.IndexCompatibility.StripStructure.DegenerateRunCount} maxDegRun={match.IndexCompatibility.StripStructure.MaxDegenerateRunLength} nonDegRuns={match.IndexCompatibility.StripStructure.NonDegenerateRunCount} maxNonDegRun={match.IndexCompatibility.StripStructure.MaxNonDegenerateRunLength} adjacentRepeats={match.IndexCompatibility.StripStructure.AdjacentRepeatCount} mirroredBridges={match.IndexCompatibility.StripStructure.MirroredAdjacentRepeatBridgeCount} sentinels={match.IndexCompatibility.StripStructure.SentinelRestartValueCount} zeroValues={match.IndexCompatibility.StripStructure.ZeroIndexValueCount}");
        var previewText = string.Join(
            " | ",
            match.IndexCompatibility.FirstStripTriangles.Take(6).Select(static t => $"{t.Index}:{t.A},{t.B},{t.C}{(t.Degenerate ? "*" : string.Empty)}"));
        Console.WriteLine($"  strip preview={previewText}");
        foreach (var mapping in match.IndexCompatibility.MappingCandidates.Take(2))
        {
          var missing = mapping.MissingVertexSamples.Count == 0 ? "none" : string.Join(",", mapping.MissingVertexSamples.Take(8));
          Console.WriteLine($"  mapping {mapping.Name}: offset={mapping.IndexOffset} valid={mapping.ValidForVertexCount} range={FormatNullableInt(mapping.MappedMinIndex)}..{FormatNullableInt(mapping.MappedMaxIndex)} outOfRange={mapping.OutOfRangeIndexCount} referenced={mapping.ReferencedVertexCount}/{match.IndexCompatibility.VertexCount} missing={mapping.MissingVertexCount} sampleMissing={missing} first={string.Join(",", mapping.FirstMappedIndices.Take(12))}");
        }
      }

      if (match.PositionVertexSamples.Count > 0)
      {
        Console.WriteLine($"  position samples={string.Join(" | ", match.PositionVertexSamples.Take(6).Select(FormatNifAttributeVertexSample))}");
      }

      if (match.NormalVertexSamples.Count > 0)
      {
        Console.WriteLine($"  normal samples={string.Join(" | ", match.NormalVertexSamples.Take(6).Select(FormatNifAttributeVertexSample))}");
      }

      if (match.UvVertexSamples.Count > 0)
      {
        Console.WriteLine($"  uv samples={string.Join(" | ", match.UvVertexSamples.Take(6).Select(FormatNifAttributeVertexSample))}");
      }

      foreach (var fitness in match.MappingPositionFitness.Take(2))
      {
        var worst = fitness.WorstTriangles.Count == 0
            ? "none"
            : string.Join(" | ", fitness.WorstTriangles.Take(3).Select(static t => $"{t.StripWindowIndex}:{t.A},{t.B},{t.C} max={t.MaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"}"));
        var firstSegmentTriangles = fitness.FirstSegmentTriangles.Count == 0
            ? "none"
            : string.Join(" | ", fitness.FirstSegmentTriangles.Take(3).Select(static t => $"{t.StripWindowIndex}:{t.A},{t.B},{t.C} pos={t.MaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} n={t.NormalMaxDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} uv={t.UvMaxDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} area={t.Area?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} {t.DominantAreaPlane}:{t.DominantSignedArea?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} parity={t.StripWindingParity}"));
        var review = fitness.FirstSegmentProofReview;
        var reviewFlags = review.ReviewFlags.Count == 0 ? "none" : string.Join(",", review.ReviewFlags);
        var dominantPlanes = review.DominantPlaneCounts.Count == 0
            ? "none"
            : string.Join(",", review.DominantPlaneCounts.Take(3).Select(static c => $"{c.Value}:{c.Count}"));
        Console.WriteLine($"  position fit {fitness.MappingName}: finite={fitness.FiniteTriangleWindowCount}/{fitness.NonDegenerateTriangleWindowCount} medianMaxEdge={fitness.MedianMaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} p95MaxEdge={fitness.P95MaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} maxEdge={fitness.MaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} segments={fitness.SegmentCount} segFinite={fitness.SegmentedFiniteTriangleWindowCount}/{fitness.SegmentedTriangleWindowCount} segMedian={fitness.SegmentedMedianMaxEdge?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} normMedian={fitness.SegmentedMedianNormalDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} uvMedian={fitness.SegmentedMedianUvDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} areaMedian={fitness.SegmentedMedianTriangleArea?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"} nearZeroArea={fitness.SegmentedNearZeroTriangleAreaCount} proofFlags={reviewFlags} planes={dominantPlanes} sign=+{review.PositiveDominantSignedAreaCount}/-{review.NegativeDominantSignedAreaCount}/0{review.ZeroDominantSignedAreaCount} parityBreaks={review.NonAlternatingParityTransitionCount} droppedDeg={fitness.DroppedDegenerateWindowCount} droppedCross={fitness.DroppedCrossSegmentWindowCount} firstSeg={firstSegmentTriangles} worst={worst}");
      }

      foreach (var view in match.GroupedViews.Take(4))
      {
        var firstSlot = view.PrefixSlots.Count == 0 ? "none" : view.PrefixSlots[0].Hex;
        var exact = view.ExactFit ? "exact" : $"remainder={view.RemainderBytes}";
        Console.WriteLine($"  view {view.Name}: slots={view.SlotCount} bytesPerSlot={view.BytesPerSlot} {exact} first={firstSlot}");
      }
    }

    if (header.Warnings.Count > 0)
    {
      Console.WriteLine($"Warnings: {string.Join("; ", header.Warnings)}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static int ProbeNifPositionSource(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var allMeshBlocks = header.Blocks
        .Where(static b => b.TypeName is "NiMesh" or "NiMorphMesh")
        .OrderBy(static b => b.Index)
        .ToList();

    if (options.MeshBlockFilter is not null)
    {
      allMeshBlocks = allMeshBlocks.Where(b => b.Index == options.MeshBlockFilter.Value).ToList();
      if (allMeshBlocks.Count == 0)
      {
        Console.Error.WriteLine($"ERROR: NiMesh block #{options.MeshBlockFilter.Value} was not found.");
        return 1;
      }
    }

    var meshes = new List<NifPositionSourceMeshProbe>();

    foreach (var meshBlock in allMeshBlocks)
    {
      var meshPayload = SliceNifBlockPayload(payload, meshBlock);
      var streamSummaries = BuildNifMeshBoundStreamSummaries(payload, header, meshBlock);

      var inlineCandidates = FindNifInlinePositionCandidates(meshPayload, streamSummaries);
      var orphanCandidates = FindNifOrphanPositionCandidates(payload, header, meshBlock, streamSummaries);
      var linkedCandidates = ScanNifLinkedStreamPositionCandidates(payload, header, streamSummaries);

      meshes.Add(new NifPositionSourceMeshProbe(
          MeshBlockIndex: meshBlock.Index,
          MeshSize: meshBlock.Size,
          MeshDataOffset: meshBlock.DataOffset,
          InlinePositionCandidates: inlineCandidates,
          OrphanPositionCandidates: orphanCandidates,
          LinkedStreamPositionCandidates: linkedCandidates));
    }

    var report = new NifPositionSourceProbeReport(
        Source: source,
        Length: payload.Length,
        NifVersion: header.VersionText,
        MeshBlockCount: allMeshBlocks.Count,
        MeshesEmitted: meshes.Count,
        Meshes: meshes);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-position-source.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF position source probe: version={header.VersionText} meshes={report.MeshBlockCount:N0} emitted={report.MeshesEmitted:N0}");
    foreach (var mesh in meshes.Take(8))
    {
      var inlineSummary = string.Join(", ", mesh.InlinePositionCandidates.Take(4).Select(static c => $"@{c.Offset}+{c.Stride} float[{c.FloatCount}]"));
      var orphanSummary = string.Join(", ", mesh.OrphanPositionCandidates.Take(4).Select(static c => $"#{c.BlockIndex} @{c.Offset}+{c.Stride}"));
      var linkedSummary = string.Join(", ", mesh.LinkedStreamPositionCandidates.Take(4).Select(static c => $"#{c.BlockIndex} type={c.PositionType} verts={c.VertexCount} role={c.Role}"));
      Console.WriteLine($"  Mesh #{mesh.MeshBlockIndex} size={mesh.MeshSize:N0} inline=[{inlineSummary}] orphan=[{orphanSummary}] linked=[{linkedSummary}]");
    }

    if (header.Warnings.Count > 0)
    {
      Console.Error.WriteLine($"Header warnings ({header.Warnings.Count}):");
      foreach (var w in header.Warnings.Take(10))
      {
        Console.Error.WriteLine($"  {w}");
      }
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static List<NifInlinePositionCandidate> FindNifInlinePositionCandidates(
      ReadOnlySpan<byte> meshPayload,
      List<NifMeshBoundStreamSummary> streamSummaries)
  {
    var candidates = new List<NifInlinePositionCandidate>();

    // We look for spans of mesh payload bytes that are not claimed by known stream references
    // and contain plausible float3 position data: vertexCount * 12 bytes, non-NaN, bounded range.
    var claimedOffsets = new HashSet<int>();
    foreach (var stream in streamSummaries)
    {
      if (stream.MeshPayloadOffset >= 0)
      {
        for (var i = 0; i < 64 && stream.MeshPayloadOffset + i < meshPayload.Length; i++)
        {
          claimedOffsets.Add(stream.MeshPayloadOffset + i);
        }
      }
    }

    // Scan for plausible inline float3 blocks
    var minVertexCount = 3;
    var maxVertexCount = 65535;
    var stride = 12; // 3 floats * 4 bytes

    for (var offset = 0; offset <= meshPayload.Length - stride * minVertexCount; offset += 4)
    {
      // Skip if any byte in this span is claimed
      var unclaimed = true;
      for (var j = 0; j < stride * maxVertexCount && offset + j < meshPayload.Length; j++)
      {
        if (claimedOffsets.Contains(offset + j))
        {
          unclaimed = false;
          break;
        }
      }
      if (!unclaimed) continue;

      // How many consecutive float3 values fit?
      var maxFit = (meshPayload.Length - offset) / stride;
      if (maxFit < minVertexCount) continue;
      var vertexCount = Math.Min(maxFit, maxVertexCount);

      // Validate first few float3s are non-NaN, finite, plausible
      var valid = true;
      var sampleCount = Math.Min(5, vertexCount);
      for (var vi = 0; vi < sampleCount; vi++)
      {
        var f0 = BitConverter.ToSingle(meshPayload.Slice(offset + vi * stride + 0, 4));
        var f1 = BitConverter.ToSingle(meshPayload.Slice(offset + vi * stride + 4, 4));
        var f2 = BitConverter.ToSingle(meshPayload.Slice(offset + vi * stride + 8, 4));
        if (float.IsNaN(f0) || float.IsNaN(f1) || float.IsNaN(f2) ||
            float.IsInfinity(f0) || float.IsInfinity(f1) || float.IsInfinity(f2))
        {
          valid = false;
          break;
        }
      }
      if (!valid) continue;

      candidates.Add(new NifInlinePositionCandidate(
          Offset: offset,
          Stride: stride,
          FloatCount: vertexCount * 3,
          VertexCount: vertexCount,
          FirstFloat3: ToHex(meshPayload.Slice(offset, Math.Min(12, meshPayload.Length - offset)))));

      // Skip past this block
      offset += stride * vertexCount - stride;
    }

    return candidates;
  }

  private static List<NifOrphanPositionCandidate> FindNifOrphanPositionCandidates(
      byte[] payload,
      NifHeaderInfo header,
      NifBlockInfo meshBlock,
      List<NifMeshBoundStreamSummary> streamSummaries)
  {
    var candidates = new List<NifOrphanPositionCandidate>();

    // Build set of referenced stream block indices
    var referencedBlocks = new HashSet<int>();
    foreach (var s in streamSummaries)
    {
      referencedBlocks.Add(s.TargetBlockIndex);
    }

    // Look at unlinked NiDataStream blocks that are near the mesh block
    var neighborBlocks = header.Blocks
        .Where(static b => b.TypeName is "NiDataStream" or "NiBinaryStream")
        .Where(b => !referencedBlocks.Contains(b.Index))
        .Where(b => Math.Abs(b.Index - meshBlock.Index) <= 8)
        .OrderBy(static b => b.Index)
        .ToList();

    foreach (var candidate in neighborBlocks)
    {
      var blockPayload = SliceNifBlockPayload(payload, candidate);
      if (blockPayload.Length < 16) continue;

      // Read declared payload size from first 4 bytes (LE uint32)
      var declaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
      if (declaredBytes > blockPayload.Length || declaredBytes < 12) continue;

      var headerBytes = blockPayload.Length - (int)declaredBytes;
      if (headerBytes < 4) continue;

      var body = blockPayload.Slice(headerBytes, (int)declaredBytes);
      if (body.Length < 36) continue; // need at least 3 float3s

      // Try to identify float3 positions: bound data evenly divisible by 12
      var vertexCount = body.Length / 12;
      if (body.Length % 12 != 0) continue;
      if (vertexCount < 3 || vertexCount > 65535) continue;

      // Validate first few float3s
      var valid = true;
      var sampleCount = Math.Min(3, vertexCount);
      for (var vi = 0; vi < sampleCount; vi++)
      {
        var f0 = BitConverter.ToSingle(body.Slice(vi * 12 + 0, 4));
        var f1 = BitConverter.ToSingle(body.Slice(vi * 12 + 4, 4));
        var f2 = BitConverter.ToSingle(body.Slice(vi * 12 + 8, 4));
        if (float.IsNaN(f0) || float.IsNaN(f1) || float.IsNaN(f2) ||
            float.IsInfinity(f0) || float.IsInfinity(f1) || float.IsInfinity(f2))
        {
          valid = false;
          break;
        }
      }
      if (!valid) continue;

      candidates.Add(new NifOrphanPositionCandidate(
          BlockIndex: candidate.Index,
          BlockSize: candidate.Size,
          Offset: headerBytes,
          Stride: 12,
          DeclaredPayloadBytes: declaredBytes,
          FloatCount: body.Length / 4,
          VertexCount: vertexCount,
          FirstFloat3: ToHex(body[..Math.Min(12, body.Length)]),
          BlockTypeName: candidate.TypeName));
    }

    return candidates;
  }

  private static List<NifLinkedStreamPositionCandidate> ScanNifLinkedStreamPositionCandidates(
      byte[] payload,
      NifHeaderInfo header,
      List<NifMeshBoundStreamSummary> streamSummaries)
  {
    var candidates = new List<NifLinkedStreamPositionCandidate>();
    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);

    foreach (var stream in streamSummaries)
    {
      if (!blocksByIndex.TryGetValue(stream.TargetBlockIndex, out var streamBlock))
        continue;

      var blockPayload = SliceNifBlockPayload(payload, streamBlock);
      if (blockPayload.Length < 4)
        continue;

      var declaredBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
      if (declaredBytes > blockPayload.Length)
        continue;

      var headerBytes = blockPayload.Length - checked((int)declaredBytes);
      var body = blockPayload.Slice(headerBytes, checked((int)declaredBytes));
      if (body.Length < 12)
        continue;

      // Float32 position candidate: body evenly divisible by 12, valid non-NaN float3s
      if (body.Length % 12 == 0 && body.Length >= 36)
      {
        var vertexCount = body.Length / 12;
        if (vertexCount >= 3 && vertexCount <= 65535)
        {
          // Skip float32 validation for streams identified as uint16-compatible
          // (body bytes look like valid-but-tiny floats when interpreted as float32)
          var valid = true;
          if (stream.RoleStats?.PrimaryRole?.Contains("uint16", StringComparison.OrdinalIgnoreCase) != true)
          {
            var sampleCount = Math.Min(3, vertexCount);
            for (var vi = 0; vi < sampleCount; vi++)
            {
              var f0 = BitConverter.ToSingle(body.Slice(vi * 12 + 0, 4));
              var f1 = BitConverter.ToSingle(body.Slice(vi * 12 + 4, 4));
              var f2 = BitConverter.ToSingle(body.Slice(vi * 12 + 8, 4));
              if (float.IsNaN(f0) || float.IsNaN(f1) || float.IsNaN(f2) ||
                  float.IsInfinity(f0) || float.IsInfinity(f1) || float.IsInfinity(f2))
              {
                valid = false;
                break;
              }
            }
          }
          else
          {
            valid = false;
          }
          if (valid)
          {
            candidates.Add(new NifLinkedStreamPositionCandidate(
                MeshPayloadOffset: stream.MeshPayloadOffset,
                BlockIndex: stream.TargetBlockIndex,
                PositionType: "float32",
                Stride: 12,
                FloatCount: body.Length / 4,
                VertexCount: vertexCount,
                BodyFirst16: ToHex(body[..Math.Min(16, body.Length)]),
                DataStreamUsage: stream.DataStreamUsage,
                DataStreamAccess: stream.DataStreamAccess,
                Role: stream.RoleStats.PrimaryRole,
                FirstFloat3: ToHex(body[..Math.Min(12, body.Length)])));
            continue;
          }
        }
      }

      // UInt16-packed position candidate: magic 43606 pattern
      if (body.Length >= 24)
      {
        var triplesPrefix = ReadUInt16BigEndianTriplesPrefix(body, maxValues: 16);
        var structure = AnalyzeNifUInt16TriplesStructure(triplesPrefix);
        if (structure.Magic43606Found)
        {
          var bytesPerVertex = 12;
          var vertexCount = body.Length / bytesPerVertex;
          if (vertexCount >= 3 && vertexCount <= 65535)
          {
            candidates.Add(new NifLinkedStreamPositionCandidate(
                MeshPayloadOffset: stream.MeshPayloadOffset,
                BlockIndex: stream.TargetBlockIndex,
                PositionType: "uint16-magic43606",
                Stride: bytesPerVertex,
                FloatCount: vertexCount * 3,
                VertexCount: vertexCount,
                BodyFirst16: ToHex(body[..Math.Min(16, body.Length)]),
                DataStreamUsage: stream.DataStreamUsage,
                DataStreamAccess: stream.DataStreamAccess,
                Role: stream.RoleStats.PrimaryRole,
                FirstFloat3: ToHex(body[..Math.Min(12, body.Length)])));
          }
        }
      }
    }

    return candidates;
  }

  private static int ProbeNifStreamBody(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var (payload, source) = LoadPayloadForProbe(options, rootDirectory);
    var detected = DetectFileType(payload);
    if (detected.Extension != "nif")
    {
      Console.Error.WriteLine($"ERROR: target payload is detected as '{detected.Extension}', not 'nif'.");
      return 1;
    }

    var header = ParseNifHeader(payload);
    var allStreamBlocks = header.Blocks
        .Where(static b => b.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase))
        .OrderBy(static b => b.Index)
        .ToList();
    var emitLimit = options.StreamBlockFilter is null
        ? (options.Limit > 0 ? options.Limit : 12)
        : int.MaxValue;
    var streamBodies = new List<NifStreamBodyProbe>();
    foreach (var block in allStreamBlocks)
    {
      if (options.StreamBlockFilter is not null && block.Index != options.StreamBlockFilter.Value)
      {
        continue;
      }

      if (streamBodies.Count >= emitLimit)
      {
        break;
      }

      var blockPayload = SliceNifBlockPayload(payload, block);
      uint? declaredPayloadBytes = null;
      int? headerBytes = null;
      ReadOnlySpan<byte> body = ReadOnlySpan<byte>.Empty;
      NifStreamBodyStats? stats = null;
      if (blockPayload.Length >= 4)
      {
        declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
        if (declaredPayloadBytes.Value <= blockPayload.Length)
        {
          headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes.Value);
          body = blockPayload.Slice(headerBytes.Value, checked((int)declaredPayloadBytes.Value));
          stats = AnalyzeNifStreamBody(body);
        }
      }

      var bodyTriplesPrefix = ReadUInt16BigEndianTriplesPrefix(body, maxValues: 16);
      streamBodies.Add(new NifStreamBodyProbe(
          BlockIndex: block.Index,
          TypeName: block.TypeName,
          DataOffset: block.DataOffset,
          BlockSize: block.Size,
          BlockFirst64: ToHex(blockPayload[..Math.Min(64, blockPayload.Length)]),
          DeclaredPayloadBytes: declaredPayloadBytes,
          HeaderBytes: headerBytes,
          BodyOffset: headerBytes,
          BodyFirst128: ToHex(body[..Math.Min(128, body.Length)]),
          Stats: stats,
          UInt16Prefix: ReadUInt16Prefix(body, maxValues: 32),
          UInt16BigEndianPrefix: ReadUInt16BigEndianPrefix(body, maxValues: 32),
          UInt32Prefix: ReadUInt32Prefix(body, maxValues: 24),
          Float32Prefix: ReadFloat32Prefix(body, maxValues: 24),
          Float2Prefix: ReadFloat2Prefix(body, maxValues: 12),
          Float3Prefix: ReadFloat3Prefix(body, maxValues: 12),
          UInt16TriplesPrefix: bodyTriplesPrefix,
          UInt16BigEndianTriplesPrefix: bodyTriplesPrefix,
          UInt16TriplesStructure: AnalyzeNifUInt16TriplesStructure(bodyTriplesPrefix),
          PreferredStrideCandidates: stats is null ? []
              : stats.PayloadStrideCandidates
                  .OrderBy(static c => PreferredStrideRank(c.Stride))
                  .ThenBy(static c => c.Stride)
                  .Take(12)
                  .ToList()));
    }

    if (options.StreamBlockFilter is not null && streamBodies.Count == 0)
    {
      Console.Error.WriteLine($"ERROR: NiDataStream block #{options.StreamBlockFilter.Value} was not found.");
      return 1;
    }

    var report = new NifStreamBodyProbeReport(
        Source: source,
        Length: payload.Length,
        NifVersion: header.VersionText,
        DataStreamBlocks: allStreamBlocks.Count,
        StreamBodiesEmitted: streamBodies.Count,
        HeaderWarnings: header.Warnings,
        StreamBodies: streamBodies);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-stream-body-probe.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"NIF stream body probe: version={header.VersionText} streams={allStreamBlocks.Count:N0} emitted={streamBodies.Count:N0}");
    foreach (var stream in streamBodies.Take(8))
    {
      var strideText = stream.PreferredStrideCandidates.Count == 0
          ? "none"
          : FormatPreferredStrideSummary(stream.PreferredStrideCandidates, max: 6);
      Console.WriteLine($"Stream #{stream.BlockIndex} size={stream.BlockSize:N0} payload={stream.DeclaredPayloadBytes} header={stream.HeaderBytes} class={stream.Stats?.Classification ?? "invalid"} strides={strideText}");
      Console.WriteLine($"  body first16={stream.BodyFirst128[..Math.Min(32, stream.BodyFirst128.Length)]}");
      Console.WriteLine($"  u16le={string.Join(",", stream.UInt16Prefix.Take(12))}");
      Console.WriteLine($"  u16be={string.Join(",", stream.UInt16BigEndianPrefix.Take(12))}");
      Console.WriteLine($"  f32={string.Join(",", stream.Float32Prefix.Take(8).Select(static f => f?.ToString("g6", CultureInfo.InvariantCulture) ?? "null"))}");
    }

    if (header.Warnings.Count > 0)
    {
      Console.WriteLine($"Warnings: {string.Join("; ", header.Warnings)}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return header.Warnings.Count == 0 ? 0 : 2;
  }

  private static int InventoryNif(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var groups = new Dictionary<string, NifInventoryGroup>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          var key = $"{header.VersionText}|{string.Join('|', header.BlockTypes.Select(static t => $"{t.Name}:{t.UsageCount}"))}";
          if (!groups.TryGetValue(key, out var group))
          {
            group = new NifInventoryGroup(
                VersionText: header.VersionText,
                VersionHex: header.VersionHex,
                HeaderString: header.HeaderString,
                BlockTypeCount: header.BlockTypeCount,
                BlockTypes: header.BlockTypes.Select(static t => t.DisplayName).ToList(),
                BlockTypeUsage: header.BlockTypes
                    .Where(static t => t.UsageCount > 0)
                    .ToDictionary(static t => t.DisplayName, static t => t.UsageCount, StringComparer.OrdinalIgnoreCase),
                Count: 0,
                MinSize: payload.Bytes.Length,
                MaxSize: payload.Bytes.Length,
                MinStringCount: checked((int)(header.StringCount ?? 0)),
                MaxStringCount: checked((int)(header.StringCount ?? 0)),
                ReferenceCount: 0,
                Samples: [],
                ReferenceSamples: []);
            groups.Add(key, group);
          }

          group.Count++;
          group.MinSize = Math.Min(group.MinSize, payload.Bytes.Length);
          group.MaxSize = Math.Max(group.MaxSize, payload.Bytes.Length);
          var stringCount = checked((int)(header.StringCount ?? 0));
          group.MinStringCount = Math.Min(group.MinStringCount, stringCount);
          group.MaxStringCount = Math.Max(group.MaxStringCount, stringCount);
          group.ReferenceCount += header.References.Count;
          if (group.Samples.Count < 10)
          {
            group.Samples.Add(new NifInventorySample(
                archiveName,
                entry.Index,
                entry.IdPrefix,
                payload.Bytes.Length,
                manifestEntry?.Index,
                manifestEntry?.FilenameFnv1Hash,
                manifestEntry?.PakIndex,
                header.BlockCount,
                header.StringCount,
                header.References.Count));
          }

          foreach (var reference in header.References)
          {
            if (group.ReferenceSamples.Count >= 20)
            {
              break;
            }

            group.ReferenceSamples.Add(new NifReferenceSample(
                archiveName,
                entry.Index,
                entry.IdPrefix,
                reference.StringIndex,
                reference.Value));
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    var report = new NifInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        Groups: groups.Values.OrderByDescending(static g => g.Count).ThenBy(static g => g.VersionText).ToList());
    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"Groups: {report.Groups.Count:N0}");
    foreach (var group in report.Groups.Take(10))
    {
      Console.WriteLine($"- {group.VersionText}: count={group.Count:N0} size={group.MinSize:N0}..{group.MaxSize:N0} blockTypes={group.BlockTypeCount:N0} strings={group.MinStringCount:N0}..{group.MaxStringCount:N0} refs={group.ReferenceCount:N0} first={string.Join(", ", group.BlockTypes.Take(5))}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifBlocks(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var typeGroups = new Dictionary<string, NifBlockTypeAccumulator>(StringComparer.OrdinalIgnoreCase);
    var families = new Dictionary<string, NifBlockFamilyAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var totalBlocks = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          totalBlocks += header.Blocks.Count;
          var seenTypesInNif = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

          foreach (var block in header.Blocks)
          {
            if (!typeGroups.TryGetValue(block.TypeName, out var typeGroup))
            {
              typeGroup = new NifBlockTypeAccumulator(block.TypeName);
              typeGroups.Add(block.TypeName, typeGroup);
            }

            typeGroup.BlockCount++;
            typeGroup.MinBlockSize = Math.Min(typeGroup.MinBlockSize, block.Size);
            typeGroup.MaxBlockSize = Math.Max(typeGroup.MaxBlockSize, block.Size);
            typeGroup.First16Values.Add(block.First16);
            if (seenTypesInNif.Add(block.TypeName))
            {
              typeGroup.NifPayloadCount++;
            }

            var sample = new NifBlockInventorySample(
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                BlockIndex: block.Index,
                DataOffset: block.DataOffset,
                Size: block.Size,
                First16: block.First16,
                StringSamples: block.StringSamples.Take(6).ToList());
            if (typeGroup.Samples.Count < 12)
            {
              typeGroup.Samples.Add(sample);
            }

            var familyKey = $"{block.TypeName}|{block.Size}|{block.First16}";
            if (!families.TryGetValue(familyKey, out var family))
            {
              family = new NifBlockFamilyAccumulator(block.TypeName, block.Size, block.First16);
              families.Add(familyKey, family);
            }

            family.Count++;
            family.NifIds.Add(entry.IdPrefix);
            foreach (var stringSample in block.StringSamples.Take(6))
            {
              family.StringSamples.Add(stringSample);
            }

            if (family.Samples.Count < 12)
            {
              family.Samples.Add(sample);
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static NifBlockTypeInventoryGroup toTypeRecord(NifBlockTypeAccumulator group)
    {
      return new NifBlockTypeInventoryGroup(
          TypeName: group.TypeName,
          NifPayloads: group.NifPayloadCount,
          BlockCount: group.BlockCount,
          MinBlockSize: group.MinBlockSize == uint.MaxValue ? 0 : group.MinBlockSize,
          MaxBlockSize: group.MaxBlockSize,
          DistinctFirst16: group.First16Values.Count,
          Samples: group.Samples);
    }

    static NifBlockPayloadFamily toFamilyRecord(NifBlockFamilyAccumulator family)
    {
      return new NifBlockPayloadFamily(
          TypeName: family.TypeName,
          Size: family.Size,
          First16: family.First16,
          Count: family.Count,
          NifPayloads: family.NifIds.Count,
          StringSamples: family.StringSamples.Take(12).ToList(),
          Samples: family.Samples);
    }

    var familyRecords = families.Values
        .Select(toFamilyRecord)
        .OrderByDescending(static f => f.Count)
        .ThenBy(static f => f.TypeName, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static f => f.Size)
        .ToList();
    var report = new NifBlockInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        TotalBlocks: totalBlocks,
        BlockTypes: typeGroups.Values
            .Select(toTypeRecord)
            .OrderByDescending(static g => g.BlockCount)
            .ThenBy(static g => g.TypeName, StringComparer.OrdinalIgnoreCase)
            .ToList(),
        MeshFamilies: familyRecords.Where(static f => string.Equals(f.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase)).ToList(),
        DataStreamFamilies: familyRecords.Where(static f => f.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase)).ToList(),
        TopFamilies: familyRecords.Take(options.Limit > 0 ? options.Limit : 100).ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-block-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"Total blocks: {totalBlocks:N0}");
    Console.WriteLine($"Block types: {report.BlockTypes.Count:N0}");
    Console.WriteLine($"Mesh families: {report.MeshFamilies.Count:N0}");
    Console.WriteLine($"DataStream families: {report.DataStreamFamilies.Count:N0}");
    Console.WriteLine($"Top block types: {string.Join(", ", report.BlockTypes.Take(8).Select(static g => $"{g.TypeName}={g.BlockCount:N0}"))}");
    Console.WriteLine($"Top mesh families: {string.Join(", ", report.MeshFamilies.Take(5).Select(static f => $"size={f.Size} count={f.Count:N0}"))}");
    Console.WriteLine($"Top data stream families: {string.Join(", ", report.DataStreamFamilies.Take(5).Select(static f => $"{f.TypeName}/size={f.Size} count={f.Count:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifMeshStreams(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var offsetGroups = new Dictionary<int, NifMeshStreamOffsetAccumulator>();
    var patternGroups = new Dictionary<string, NifMeshStreamPatternAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var meshBlockCount = 0;
    var candidateLinkCount = 0;
    var ambiguousCandidateLinkCount = 0;
    var meshBlocksWithCandidates = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var meshBlock in header.Blocks.Where(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase)))
          {
            meshBlockCount++;
            var candidates = meshBlock.DataStreamReferenceCandidates
                .OrderBy(static c => c.PayloadOffset)
                .ThenBy(static c => c.TargetBlockIndex)
                .ToList();
            if (candidates.Count == 0)
            {
              continue;
            }

            meshBlocksWithCandidates++;
            var patternKey = string.Join("|", candidates.Take(16).Select(static c => $"@{c.PayloadOffset}:size={c.TargetSize}{(c.MaybeStringIndex ? "?" : string.Empty)}"));
            if (!patternGroups.TryGetValue(patternKey, out var patternGroup))
            {
              patternGroup = new NifMeshStreamPatternAccumulator(patternKey, meshBlock.Size, meshBlock.First16);
              patternGroups.Add(patternKey, patternGroup);
            }

            patternGroup.Count++;
            patternGroup.NifIds.Add(entry.IdPrefix);

            foreach (var candidate in candidates)
            {
              candidateLinkCount++;
              if (candidate.MaybeStringIndex)
              {
                ambiguousCandidateLinkCount++;
              }

              var sample = new NifMeshStreamSample(
                  ArchiveName: archiveName,
                  EntryIndex: entry.Index,
                  IdPrefix: entry.IdPrefix,
                  ManifestEntryIndex: manifestEntry?.Index,
                  MeshBlockIndex: meshBlock.Index,
                  MeshSize: meshBlock.Size,
                  MeshFirst16: meshBlock.First16,
                  PayloadOffset: candidate.PayloadOffset,
                  TargetBlockIndex: candidate.TargetBlockIndex,
                  TargetTypeName: candidate.TargetTypeName,
                  TargetSize: candidate.TargetSize,
                  TargetFirst16: candidate.TargetFirst16,
                  MaybeStringIndex: candidate.MaybeStringIndex,
                  StringValue: candidate.StringValue);

              if (patternGroup.Samples.Count < 12)
              {
                patternGroup.Samples.Add(sample);
              }

              if (!offsetGroups.TryGetValue(candidate.PayloadOffset, out var offsetGroup))
              {
                offsetGroup = new NifMeshStreamOffsetAccumulator(candidate.PayloadOffset);
                offsetGroups.Add(candidate.PayloadOffset, offsetGroup);
              }

              offsetGroup.Count++;
              if (candidate.MaybeStringIndex)
              {
                offsetGroup.AmbiguousCount++;
              }

              offsetGroup.TargetSizeCounts[candidate.TargetSize] = offsetGroup.TargetSizeCounts.GetValueOrDefault(candidate.TargetSize) + 1;
              offsetGroup.MeshSizeCounts[meshBlock.Size] = offsetGroup.MeshSizeCounts.GetValueOrDefault(meshBlock.Size) + 1;
              if (offsetGroup.Samples.Count < 12)
              {
                offsetGroup.Samples.Add(sample);
              }
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static NifMeshStreamOffsetGroup toOffsetRecord(NifMeshStreamOffsetAccumulator group)
    {
      return new NifMeshStreamOffsetGroup(
          PayloadOffset: group.PayloadOffset,
          Count: group.Count,
          AmbiguousCount: group.AmbiguousCount,
          TargetSizes: group.TargetSizeCounts
              .OrderByDescending(static kvp => kvp.Value)
              .ThenBy(static kvp => kvp.Key)
              .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
              .ToList(),
          MeshSizes: group.MeshSizeCounts
              .OrderByDescending(static kvp => kvp.Value)
              .ThenBy(static kvp => kvp.Key)
              .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
              .ToList(),
          Samples: group.Samples);
    }

    static NifMeshStreamPatternGroup toPatternRecord(NifMeshStreamPatternAccumulator group)
    {
      return new NifMeshStreamPatternGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          MeshFirst16: group.MeshFirst16,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          Samples: group.Samples);
    }

    var report = new NifMeshStreamInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        MeshBlocks: meshBlockCount,
        MeshBlocksWithCandidates: meshBlocksWithCandidates,
        CandidateLinks: candidateLinkCount,
        AmbiguousCandidateLinks: ambiguousCandidateLinkCount,
        OffsetGroups: offsetGroups.Values
            .Select(toOffsetRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.PayloadOffset)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopPatterns: patternGroups.Values
            .Select(toPatternRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.Pattern, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-mesh-stream-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiMesh blocks: {meshBlockCount:N0}");
    Console.WriteLine($"Mesh blocks with candidates: {meshBlocksWithCandidates:N0}");
    Console.WriteLine($"Candidate stream links: {candidateLinkCount:N0}");
    Console.WriteLine($"Ambiguous candidate links: {ambiguousCandidateLinkCount:N0}");
    Console.WriteLine($"Top offsets: {string.Join(", ", report.OffsetGroups.Take(8).Select(static g => $"@{g.PayloadOffset}={g.Count:N0}"))}");
    Console.WriteLine($"Top patterns: {string.Join(" | ", report.TopPatterns.Take(5).Select(static g => $"meshSize={g.MeshSize} count={g.Count:N0} {g.Pattern}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifMeshBindings(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var roleGroups = new Dictionary<string, NifMeshBindingRoleAccumulator>(StringComparer.OrdinalIgnoreCase);
    var usageAccessRoleGroups = new Dictionary<string, NifMeshBindingUsageAccessRoleAccumulator>(StringComparer.OrdinalIgnoreCase);
    var patternGroups = new Dictionary<string, NifMeshBindingPatternAccumulator>(StringComparer.OrdinalIgnoreCase);
    var pairingGroups = new Dictionary<string, NifMeshBindingPairingAccumulator>(StringComparer.OrdinalIgnoreCase);
    var positionSourceSiblingGroups = new Dictionary<string, NifPositionSourceSiblingAccumulator>(StringComparer.OrdinalIgnoreCase);
    var residualTargetGroups = new Dictionary<uint, NifMeshResidualTargetAccumulator>();
    var residualStreamGroups = new Dictionary<string, NifMeshResidualStreamAccumulator>(StringComparer.OrdinalIgnoreCase);
    var attributeSetGroups = new Dictionary<string, NifMeshAttributeSetAccumulator>(StringComparer.OrdinalIgnoreCase);
    var attributeTopologyGroups = new Dictionary<string, NifAttributeTopologyAccumulator>(StringComparer.OrdinalIgnoreCase);
    var attributeExtraGroups = new Dictionary<string, NifAttributeExtraStreamAccumulator>(StringComparer.OrdinalIgnoreCase);
    var attributeExtraMappingFitnessGroups = new Dictionary<string, NifAttributeExtraMappingFitnessAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var meshBlockCount = 0;
    var meshBlocksWithCandidates = 0;
    var candidateLinkCount = 0;
    var validDeclaredStreamBodies = 0;
    var invalidDeclaredStreamBodies = 0;
    var pairCompatibleMeshes = 0;
    var pairCompatibleLinks = 0;
    var attributeCompatibleMeshes = 0;
    var attributeCompatibleSets = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);
          foreach (var meshBlock in header.Blocks.Where(static b => string.Equals(b.TypeName, "NiMesh", StringComparison.OrdinalIgnoreCase)))
          {
            meshBlockCount++;
            var candidates = meshBlock.DataStreamReferenceCandidates
                .OrderBy(static c => c.PayloadOffset)
                .ThenBy(static c => c.TargetBlockIndex)
                .ToList();
            if (candidates.Count == 0)
            {
              continue;
            }

            meshBlocksWithCandidates++;
            var streamSummaries = new List<NifMeshBoundStreamSummary>(candidates.Count);
            NifMeshResidualTargetAccumulator? residualTargetGroup = null;
            if (IsNifMeshResidualTargetSize(meshBlock.Size))
            {
              if (!residualTargetGroups.TryGetValue(meshBlock.Size, out residualTargetGroup))
              {
                residualTargetGroup = new NifMeshResidualTargetAccumulator(meshBlock.Size);
                residualTargetGroups.Add(meshBlock.Size, residualTargetGroup);
              }

              residualTargetGroup.MeshBlockCount++;
              residualTargetGroup.NifIds.Add(entry.IdPrefix);
            }

            foreach (var candidate in candidates)
            {
              candidateLinkCount++;
              blocksByIndex.TryGetValue(candidate.TargetBlockIndex, out var targetBlock);
              ReadOnlySpan<byte> targetPayload = targetBlock is null
                  ? ReadOnlySpan<byte>.Empty
                  : SliceNifBlockPayload(payload.Bytes, targetBlock);
              uint? declaredPayloadBytes = null;
              int? headerBytes = null;
              var bodyFirst16 = string.Empty;
              NifMeshStreamRoleStats roleStats;
              if (targetPayload.Length >= 4)
              {
                declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(targetPayload[..4]);
                if (declaredPayloadBytes.Value <= targetPayload.Length)
                {
                  headerBytes = targetPayload.Length - checked((int)declaredPayloadBytes.Value);
                  var body = targetPayload.Slice(headerBytes.Value, checked((int)declaredPayloadBytes.Value));
                  bodyFirst16 = ToHex(body[..Math.Min(16, body.Length)]);
                  roleStats = AnalyzeNifMeshBoundStreamRole(body);
                  validDeclaredStreamBodies++;
                }
                else
                {
                  roleStats = NifMeshStreamRoleStats.Invalid("declared-payload-past-block");
                  invalidDeclaredStreamBodies++;
                }
              }
              else
              {
                roleStats = NifMeshStreamRoleStats.Invalid("stream-block-too-small");
                invalidDeclaredStreamBodies++;
              }

              var summary = new NifMeshBoundStreamSummary(
                  MeshPayloadOffset: candidate.PayloadOffset,
                  TargetBlockIndex: candidate.TargetBlockIndex,
                  TargetTypeName: candidate.TargetTypeName,
                  DataStreamUsage: candidate.TargetDataStreamUsage,
                  DataStreamAccess: candidate.TargetDataStreamAccess,
                  TargetSize: candidate.TargetSize,
                  TargetFirst16: candidate.TargetFirst16,
                  DeclaredPayloadBytes: declaredPayloadBytes,
                  HeaderBytes: headerBytes,
                  BodyFirst16: bodyFirst16,
                  MaybeStringIndex: candidate.MaybeStringIndex,
                  StringValue: candidate.StringValue,
                  RoleStats: roleStats);
              streamSummaries.Add(summary);

              if (!roleGroups.TryGetValue(roleStats.PrimaryRole, out var roleGroup))
              {
                roleGroup = new NifMeshBindingRoleAccumulator(roleStats.PrimaryRole);
                roleGroups.Add(roleStats.PrimaryRole, roleGroup);
              }

              roleGroup.Count++;
              var usageAccessKey = FormatNifDataStreamUsageAccessKey(summary.DataStreamUsage, summary.DataStreamAccess);
              roleGroup.UsageAccessCounts[usageAccessKey] = roleGroup.UsageAccessCounts.GetValueOrDefault(usageAccessKey) + 1;
              if (roleStats.Confidence >= 70)
              {
                roleGroup.HighConfidenceCount++;
              }

              roleGroup.MeshSizeCounts[meshBlock.Size] = roleGroup.MeshSizeCounts.GetValueOrDefault(meshBlock.Size) + 1;
              if (declaredPayloadBytes is not null)
              {
                roleGroup.DeclaredPayloadSizeCounts[declaredPayloadBytes.Value] = roleGroup.DeclaredPayloadSizeCounts.GetValueOrDefault(declaredPayloadBytes.Value) + 1;
              }

              if (roleGroup.Samples.Count < 16)
              {
                roleGroup.Samples.Add(new NifMeshBindingStreamSample(
                    ArchiveName: archiveName,
                    EntryIndex: entry.Index,
                    IdPrefix: entry.IdPrefix,
                    ManifestEntryIndex: manifestEntry?.Index,
                    MeshBlockIndex: meshBlock.Index,
                    MeshSize: meshBlock.Size,
                    Stream: summary));
              }

              if (declaredPayloadBytes is not null &&
                  roleStats.PrimaryRole.StartsWith("position-float3", StringComparison.OrdinalIgnoreCase))
              {
                var positionSiblingKey = $"id={entry.IdPrefix}|target=#{summary.TargetBlockIndex}|payload={declaredPayloadBytes.Value}:{FormatNifDataStreamUsageAccessKey(summary.DataStreamUsage, summary.DataStreamAccess)}|role={roleStats.PrimaryRole}";
                if (!positionSourceSiblingGroups.TryGetValue(positionSiblingKey, out var positionSiblingGroup))
                {
                  positionSiblingGroup = new NifPositionSourceSiblingAccumulator(
                      positionSiblingKey,
                      entry.IdPrefix,
                      summary.TargetBlockIndex,
                      declaredPayloadBytes,
                      summary.DataStreamUsage,
                      summary.DataStreamAccess,
                      roleStats.PrimaryRole);
                  positionSourceSiblingGroups.Add(positionSiblingKey, positionSiblingGroup);
                }

                positionSiblingGroup.Count++;
                positionSiblingGroup.NifIds.Add(entry.IdPrefix);
                positionSiblingGroup.MeshBlockIndices.Add(meshBlock.Index);
                positionSiblingGroup.MeshPayloadOffsets.Add(summary.MeshPayloadOffset);
                positionSiblingGroup.MeshSizeCounts[meshBlock.Size] = positionSiblingGroup.MeshSizeCounts.GetValueOrDefault(meshBlock.Size) + 1;
                if (positionSiblingGroup.Samples.Count < 16)
                {
                  positionSiblingGroup.Samples.Add(new NifMeshBindingStreamSample(
                      ArchiveName: archiveName,
                      EntryIndex: entry.Index,
                      IdPrefix: entry.IdPrefix,
                      ManifestEntryIndex: manifestEntry?.Index,
                      MeshBlockIndex: meshBlock.Index,
                      MeshSize: meshBlock.Size,
                      Stream: summary));
                }
              }

              var usageAccessRoleKey = $"{usageAccessKey}|role={roleStats.PrimaryRole}";
              if (!usageAccessRoleGroups.TryGetValue(usageAccessRoleKey, out var usageAccessRoleGroup))
              {
                usageAccessRoleGroup = new NifMeshBindingUsageAccessRoleAccumulator(
                    roleStats.PrimaryRole,
                    summary.DataStreamUsage,
                    summary.DataStreamAccess);
                usageAccessRoleGroups.Add(usageAccessRoleKey, usageAccessRoleGroup);
              }

              usageAccessRoleGroup.Count++;
              if (roleStats.Confidence >= 70)
              {
                usageAccessRoleGroup.HighConfidenceCount++;
              }

              usageAccessRoleGroup.MeshSizeCounts[meshBlock.Size] = usageAccessRoleGroup.MeshSizeCounts.GetValueOrDefault(meshBlock.Size) + 1;
              if (declaredPayloadBytes is not null)
              {
                usageAccessRoleGroup.DeclaredPayloadSizeCounts[declaredPayloadBytes.Value] = usageAccessRoleGroup.DeclaredPayloadSizeCounts.GetValueOrDefault(declaredPayloadBytes.Value) + 1;
              }

              if (usageAccessRoleGroup.Samples.Count < 16)
              {
                usageAccessRoleGroup.Samples.Add(new NifMeshBindingStreamSample(
                    ArchiveName: archiveName,
                    EntryIndex: entry.Index,
                    IdPrefix: entry.IdPrefix,
                    ManifestEntryIndex: manifestEntry?.Index,
                    MeshBlockIndex: meshBlock.Index,
                    MeshSize: meshBlock.Size,
                    Stream: summary));
              }
            }

            foreach (var residual in streamSummaries.Where(s => IsNifMeshResidualStreamCandidate(meshBlock.Size, s)))
            {
              var residualKey = $"meshSize={meshBlock.Size}|stream@{residual.MeshPayloadOffset}:size={residual.TargetSize}:payload={residual.DeclaredPayloadBytes}:{FormatNifDataStreamUsageAccessKey(residual.DataStreamUsage, residual.DataStreamAccess)}:role={residual.RoleStats.PrimaryRole}:body={residual.BodyFirst16}:string={residual.StringValue}";
              if (!residualStreamGroups.TryGetValue(residualKey, out var residualGroup))
              {
                residualGroup = new NifMeshResidualStreamAccumulator(
                    residualKey,
                    meshBlock.Size,
                    residual.MeshPayloadOffset,
                    residual.TargetSize,
                    residual.DeclaredPayloadBytes,
                    residual.DataStreamUsage,
                    residual.DataStreamAccess,
                    residual.RoleStats.PrimaryRole,
                    residual.RoleStats.Confidence,
                    residual.BodyFirst16,
                    residual.StringValue,
                    residual.RoleStats.RotatedFloat3Stats?.VectorCount,
                    residual.RoleStats.RotatedFloat3Stats?.FiniteVectorRatio,
                    residual.RoleStats.RotatedFloat3Stats?.PlausibleValueRatio,
                    residual.RoleStats.RotatedFloat3Stats?.NonZeroVectorRatio,
                    residual.RoleStats.RotatedFloat3Stats?.MaxExtent,
                    residual.RoleStats.RotatedFloat3Stats?.Prefix);
                residualStreamGroups.Add(residualKey, residualGroup);
              }

              residualGroup.Count++;
              residualGroup.NifIds.Add(entry.IdPrefix);
              if (residualTargetGroup is not null)
              {
                residualTargetGroup.ResidualStreamCount++;
                residualTargetGroup.ResidualPatternKeys.Add(residualKey);
                if (residualTargetGroup.Samples.Count < 16)
                {
                  residualTargetGroup.Samples.Add(new NifMeshBindingStreamSample(
                      ArchiveName: archiveName,
                      EntryIndex: entry.Index,
                      IdPrefix: entry.IdPrefix,
                      ManifestEntryIndex: manifestEntry?.Index,
                      MeshBlockIndex: meshBlock.Index,
                      MeshSize: meshBlock.Size,
                      Stream: residual));
                }
              }

              if (residualGroup.Samples.Count < 16)
              {
                residualGroup.Samples.Add(new NifMeshBindingStreamSample(
                    ArchiveName: archiveName,
                    EntryIndex: entry.Index,
                    IdPrefix: entry.IdPrefix,
                    ManifestEntryIndex: manifestEntry?.Index,
                    MeshBlockIndex: meshBlock.Index,
                    MeshSize: meshBlock.Size,
                    Stream: residual));
              }
            }

            var pairings = FindNifMeshBindingPairings(
                archiveName,
                entry,
                manifestEntry,
                meshBlock,
                streamSummaries);
            var attributeSets = FindNifMeshAttributeSets(
                archiveName,
                entry,
                manifestEntry,
                meshBlock,
                streamSummaries);
            if (pairings.Count > 0)
            {
              pairCompatibleMeshes++;
              pairCompatibleLinks += pairings.Count;
            }

            if (attributeSets.Count > 0)
            {
              attributeCompatibleMeshes++;
              attributeCompatibleSets += attributeSets.Count;
            }

            var patternKey = string.Join("|", streamSummaries.Take(16).Select(static s => $"@{s.MeshPayloadOffset}:size={s.TargetSize}:payload={s.DeclaredPayloadBytes?.ToString(CultureInfo.InvariantCulture) ?? "?"}:role={s.RoleStats.PrimaryRole}{(s.MaybeStringIndex ? "?" : string.Empty)}"));
            if (!patternGroups.TryGetValue(patternKey, out var patternGroup))
            {
              patternGroup = new NifMeshBindingPatternAccumulator(patternKey, meshBlock.Size, meshBlock.First16);
              patternGroups.Add(patternKey, patternGroup);
            }

            patternGroup.Count++;
            patternGroup.NifIds.Add(entry.IdPrefix);
            if (pairings.Count > 0)
            {
              patternGroup.PairCompatibleCount++;
            }

            if (patternGroup.Samples.Count < 12)
            {
              patternGroup.Samples.Add(new NifMeshBindingMeshSample(
                  ArchiveName: archiveName,
                  EntryIndex: entry.Index,
                  IdPrefix: entry.IdPrefix,
                  ManifestEntryIndex: manifestEntry?.Index,
                  MeshBlockIndex: meshBlock.Index,
                  MeshSize: meshBlock.Size,
                  MeshFirst16: meshBlock.First16,
                  PairingCount: pairings.Count,
                  Streams: streamSummaries.Take(16).ToList()));
            }

            foreach (var attributeSet in attributeSets)
            {
              var key = $"meshSize={meshBlock.Size}|position@{attributeSet.PositionMeshPayloadOffset}:payload={attributeSet.PositionDeclaredPayloadBytes}|normal@{attributeSet.NormalMeshPayloadOffset}:payload={attributeSet.NormalDeclaredPayloadBytes}|uv@{attributeSet.UvMeshPayloadOffset}:payload={attributeSet.UvDeclaredPayloadBytes}|count={attributeSet.VertexCount}|topology={attributeSet.Topology.PrimaryTopology}";
              if (!attributeSetGroups.TryGetValue(key, out var attributeSetGroup))
              {
                attributeSetGroup = new NifMeshAttributeSetAccumulator(
                    key,
                    meshBlock.Size,
                    attributeSet.PositionDeclaredPayloadBytes,
                    attributeSet.NormalDeclaredPayloadBytes,
                    attributeSet.UvDeclaredPayloadBytes,
                    attributeSet.VertexCount,
                    attributeSet.Topology);
                attributeSetGroups.Add(key, attributeSetGroup);
              }

              attributeSetGroup.Count++;
              attributeSetGroup.NifIds.Add(entry.IdPrefix);
              attributeSetGroup.ConfidenceTotal += attributeSet.Confidence;
              if (attributeSetGroup.Samples.Count < 16)
              {
                attributeSetGroup.Samples.Add(attributeSet);
              }

              var topologyKey = $"{attributeSet.Topology.PrimaryTopology}|vertexCount={attributeSet.VertexCount}|list={attributeSet.Topology.TriangleListTriangleCount}|strip={attributeSet.Topology.TriangleStripTriangleCount}|quad={attributeSet.Topology.QuadListQuadCount}";
              if (!attributeTopologyGroups.TryGetValue(topologyKey, out var topologyGroup))
              {
                topologyGroup = new NifAttributeTopologyAccumulator(
                    attributeSet.Topology.PrimaryTopology,
                    attributeSet.VertexCount,
                    attributeSet.Topology.TriangleListTriangleCount,
                    attributeSet.Topology.TriangleStripTriangleCount,
                    attributeSet.Topology.QuadListQuadCount);
                attributeTopologyGroups.Add(topologyKey, topologyGroup);
              }

              topologyGroup.Count++;
              topologyGroup.NifIds.Add(entry.IdPrefix);
              topologyGroup.ConfidenceTotal += attributeSet.Topology.Confidence;
              if (topologyGroup.Samples.Count < 16)
              {
                topologyGroup.Samples.Add(attributeSet);
              }

              foreach (var extra in attributeSet.ExtraStreams)
              {
                var extraKey = $"topology={attributeSet.Topology.PrimaryTopology}|vertexCount={attributeSet.VertexCount}|extra@{extra.MeshPayloadOffset}:payload={extra.DeclaredPayloadBytes}:role={extra.Role}:bpv={extra.BytesPerVertex}:btri={extra.BytesPerTriangleListTriangle}:bstrip={extra.BytesPerStripOrFanTriangle}:bquad={extra.BytesPerQuad}";
                if (!attributeExtraGroups.TryGetValue(extraKey, out var extraGroup))
                {
                  extraGroup = new NifAttributeExtraStreamAccumulator(
                      attributeSet.Topology.PrimaryTopology,
                      attributeSet.VertexCount,
                      extra.MeshPayloadOffset,
                      extra.Role,
                      extra.DeclaredPayloadBytes,
                      extra.BytesPerVertex,
                      extra.BytesPerTriangleListTriangle,
                      extra.BytesPerStripOrFanTriangle,
                      extra.BytesPerQuad,
                      extra.FitSummary);
                  attributeExtraGroups.Add(extraKey, extraGroup);
                }

                extraGroup.Count++;
                extraGroup.NifIds.Add(entry.IdPrefix);
                if (extraGroup.Samples.Count < 16)
                {
                  extraGroup.Samples.Add(attributeSet);
                }

                var extraSummary = streamSummaries.FirstOrDefault(s =>
                    s.MeshPayloadOffset == extra.MeshPayloadOffset &&
                    s.TargetBlockIndex == extra.BlockIndex);
                if (extraSummary?.RoleStats.IndexStats is not null &&
                    blocksByIndex.TryGetValue(extra.BlockIndex, out var extraBlock))
                {
                  var extraPayload = SliceNifBlockPayload(payload.Bytes, extraBlock);
                  if (extraPayload.Length >= 4)
                  {
                    var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(extraPayload[..4]);
                    if (declaredPayloadBytes <= extraPayload.Length)
                    {
                      var headerBytes = extraPayload.Length - checked((int)declaredPayloadBytes);
                      var extraBody = extraPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));
                      var indexCompatibility = BuildNifAttributeExtraIndexCompatibility(attributeSet.VertexCount, extraSummary.RoleStats.IndexStats, extraBody);
                      var positionFitness = BuildNifAttributeMappingPositionFitness(payload.Bytes, blocksByIndex, attributeSet, extraBody, indexCompatibility);
                      var rawFitness = positionFitness.FirstOrDefault(static f => string.Equals(f.MappingName, "raw-zero-based", StringComparison.OrdinalIgnoreCase));
                      var subtractOneFitness = positionFitness.FirstOrDefault(static f => string.Equals(f.MappingName, "subtract-one", StringComparison.OrdinalIgnoreCase));
                      var preferredMapping = GetNifAttributeMappingFitnessPreference(rawFitness, subtractOneFitness);

                      var fitnessKey = $"meshSize={meshBlock.Size}|topology={attributeSet.Topology.PrimaryTopology}|vertexCount={attributeSet.VertexCount}|extra@{extra.MeshPayloadOffset}:payload={extra.DeclaredPayloadBytes}:role={extra.Role}";
                      if (!attributeExtraMappingFitnessGroups.TryGetValue(fitnessKey, out var fitnessGroup))
                      {
                        fitnessGroup = new NifAttributeExtraMappingFitnessAccumulator(
                            fitnessKey,
                            meshBlock.Size,
                            attributeSet.Topology.PrimaryTopology,
                            attributeSet.VertexCount,
                            extra.MeshPayloadOffset,
                            extra.Role,
                            extra.DeclaredPayloadBytes);
                        attributeExtraMappingFitnessGroups.Add(fitnessKey, fitnessGroup);
                      }

                      fitnessGroup.Count++;
                      fitnessGroup.NifIds.Add(entry.IdPrefix);
                      fitnessGroup.AddFitness(rawFitness, subtractOneFitness, preferredMapping);
                      if (indexCompatibility?.StripStructure is not null)
                      {
                        fitnessGroup.AddStripStructure(indexCompatibility.StripStructure);
                      }

                      if (fitnessGroup.Samples.Count < 16)
                      {
                        fitnessGroup.Samples.Add(new NifAttributeExtraMappingFitnessSample(
                            ArchiveName: archiveName,
                            EntryIndex: entry.Index,
                            IdPrefix: entry.IdPrefix,
                            ManifestEntryIndex: manifestEntry?.Index,
                            MeshBlockIndex: meshBlock.Index,
                            MeshSize: meshBlock.Size,
                            VertexCount: attributeSet.VertexCount,
                            ExtraMeshPayloadOffset: extra.MeshPayloadOffset,
                            ExtraBlockIndex: extra.BlockIndex,
                            ExtraRole: extra.Role,
                            RawMedianMaxEdge: rawFitness?.MedianMaxEdge,
                            SubtractOneMedianMaxEdge: subtractOneFitness?.MedianMaxEdge,
                            RawSegmentedMedianMaxEdge: rawFitness?.SegmentedMedianMaxEdge,
                            SubtractOneSegmentedMedianMaxEdge: subtractOneFitness?.SegmentedMedianMaxEdge,
                            RawSegmentedMedianNormalDelta: rawFitness?.SegmentedMedianNormalDelta,
                            SubtractOneSegmentedMedianNormalDelta: subtractOneFitness?.SegmentedMedianNormalDelta,
                            RawSegmentedMedianUvDelta: rawFitness?.SegmentedMedianUvDelta,
                            SubtractOneSegmentedMedianUvDelta: subtractOneFitness?.SegmentedMedianUvDelta,
                            RawSegmentedMedianTriangleArea: rawFitness?.SegmentedMedianTriangleArea,
                            SubtractOneSegmentedMedianTriangleArea: subtractOneFitness?.SegmentedMedianTriangleArea,
                            RawFirstSegmentProofFlags: rawFitness is null ? [] : rawFitness.FirstSegmentProofReview.ReviewFlags,
                            SubtractOneFirstSegmentProofFlags: subtractOneFitness is null ? [] : subtractOneFitness.FirstSegmentProofReview.ReviewFlags,
                            RawFirstSegmentDominantPlaneSwitchCount: rawFitness?.FirstSegmentProofReview.DominantPlaneSwitchCount,
                            SubtractOneFirstSegmentDominantPlaneSwitchCount: subtractOneFitness?.FirstSegmentProofReview.DominantPlaneSwitchCount,
                            RawFirstSegmentDominantSignedAreaSignSwitchCount: rawFitness?.FirstSegmentProofReview.DominantSignedAreaSignSwitchCount,
                            SubtractOneFirstSegmentDominantSignedAreaSignSwitchCount: subtractOneFitness?.FirstSegmentProofReview.DominantSignedAreaSignSwitchCount,
                            RawFirstSegmentNonAlternatingParityTransitionCount: rawFitness?.FirstSegmentProofReview.NonAlternatingParityTransitionCount,
                            SubtractOneFirstSegmentNonAlternatingParityTransitionCount: subtractOneFitness?.FirstSegmentProofReview.NonAlternatingParityTransitionCount,
                            RawP95MaxEdge: rawFitness?.P95MaxEdge,
                            SubtractOneP95MaxEdge: subtractOneFitness?.P95MaxEdge,
                            SegmentCount: rawFitness?.SegmentCount ?? subtractOneFitness?.SegmentCount,
                            SegmentedTriangleWindowCount: rawFitness?.SegmentedTriangleWindowCount ?? subtractOneFitness?.SegmentedTriangleWindowCount,
                            DroppedDegenerateWindowCount: rawFitness?.DroppedDegenerateWindowCount ?? subtractOneFitness?.DroppedDegenerateWindowCount,
                            DroppedCrossSegmentWindowCount: rawFitness?.DroppedCrossSegmentWindowCount ?? subtractOneFitness?.DroppedCrossSegmentWindowCount,
                            PreferredMapping: preferredMapping));
                      }
                    }
                  }
                }
              }
            }

            foreach (var pairing in pairings)
            {
              var key = $"meshSize={meshBlock.Size}|index@{pairing.IndexMeshPayloadOffset}:payload={pairing.IndexDeclaredPayloadBytes}:{FormatNifDataStreamUsageAccessKey(pairing.IndexDataStreamUsage, pairing.IndexDataStreamAccess)}:role={pairing.IndexRole}|vertex@{pairing.VertexMeshPayloadOffset}:payload={pairing.VertexDeclaredPayloadBytes}:{FormatNifDataStreamUsageAccessKey(pairing.VertexDataStreamUsage, pairing.VertexDataStreamAccess)}:role={pairing.VertexRole}:count={pairing.VertexCount}";
              if (!pairingGroups.TryGetValue(key, out var pairingGroup))
              {
                pairingGroup = new NifMeshBindingPairingAccumulator(
                    key,
                    meshBlock.Size,
                    pairing.IndexRole,
                    pairing.VertexRole,
                    pairing.IndexDeclaredPayloadBytes,
                    pairing.VertexDeclaredPayloadBytes,
                    pairing.IndexPairCount,
                    pairing.IndexDataStreamUsage,
                    pairing.IndexDataStreamAccess,
                    pairing.VertexDataStreamUsage,
                    pairing.VertexDataStreamAccess,
                    pairing.VertexCount);
                pairingGroups.Add(key, pairingGroup);
              }

              pairingGroup.Count++;
              pairingGroup.NifIds.Add(entry.IdPrefix);
              pairingGroup.MaxIndexObserved = Math.Max(pairingGroup.MaxIndexObserved, pairing.IndexMax);
              pairingGroup.ConfidenceTotal += pairing.Confidence;
              pairingGroup.IndexCoverageRatioTotal += pairing.IndexCoverageRatio;
              if (pairingGroup.Samples.Count < 16)
              {
                pairingGroup.Samples.Add(pairing);
              }
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static List<NifSizeCount> topSizeCounts(Dictionary<uint, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static List<NifStringCount> topStringCounts(Dictionary<string, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
          .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static NifMeshBindingRoleGroup toRoleRecord(NifMeshBindingRoleAccumulator group)
    {
      return new NifMeshBindingRoleGroup(
          Role: group.Role,
          Count: group.Count,
          HighConfidenceCount: group.HighConfidenceCount,
          UsageAccessCounts: topStringCounts(group.UsageAccessCounts),
          MeshSizes: topSizeCounts(group.MeshSizeCounts),
          DeclaredPayloadSizes: topSizeCounts(group.DeclaredPayloadSizeCounts),
          Samples: group.Samples);
    }

    static NifMeshBindingUsageAccessRoleGroup toUsageAccessRoleRecord(NifMeshBindingUsageAccessRoleAccumulator group)
    {
      return new NifMeshBindingUsageAccessRoleGroup(
          Role: group.Role,
          DataStreamUsage: group.DataStreamUsage,
          DataStreamAccess: group.DataStreamAccess,
          Count: group.Count,
          HighConfidenceCount: group.HighConfidenceCount,
          MeshSizes: topSizeCounts(group.MeshSizeCounts),
          DeclaredPayloadSizes: topSizeCounts(group.DeclaredPayloadSizeCounts),
          Samples: group.Samples);
    }

    static NifPositionSourceSiblingGroup toPositionSourceSiblingRecord(NifPositionSourceSiblingAccumulator group)
    {
      return new NifPositionSourceSiblingGroup(
          Pattern: group.Pattern,
          IdPrefix: group.IdPrefix,
          TargetBlockIndex: group.TargetBlockIndex,
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          DataStreamUsage: group.DataStreamUsage,
          DataStreamAccess: group.DataStreamAccess,
          Role: group.Role,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          DistinctMeshBlocks: group.MeshBlockIndices.Count,
          MeshBlockIndices: group.MeshBlockIndices.Order().ToList(),
          MeshSizes: topSizeCounts(group.MeshSizeCounts),
          MeshPayloadOffsets: group.MeshPayloadOffsets.Order().ToList(),
          Samples: group.Samples);
    }

    static NifMeshBindingPatternGroup toPatternRecord(NifMeshBindingPatternAccumulator group)
    {
      return new NifMeshBindingPatternGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          MeshFirst16: group.MeshFirst16,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          PairCompatibleCount: group.PairCompatibleCount,
          Samples: group.Samples);
    }

    static NifMeshBindingPairingGroup toPairingRecord(NifMeshBindingPairingAccumulator group)
    {
      return new NifMeshBindingPairingGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          IndexRole: group.IndexRole,
          VertexRole: group.VertexRole,
          IndexDeclaredPayloadBytes: group.IndexDeclaredPayloadBytes,
          VertexDeclaredPayloadBytes: group.VertexDeclaredPayloadBytes,
          IndexPairCount: group.IndexPairCount,
          TriangleListTriangleCount: group.TriangleListTriangleCount,
          TriangleStripWindowCount: group.TriangleStripWindowCount,
          MaxIndexCoverageRatio: group.VertexCount == 0 ? 0 : Math.Round((group.MaxIndexObserved + 1) / (double)group.VertexCount, 4),
          IndexDataStreamUsage: group.IndexDataStreamUsage,
          IndexDataStreamAccess: group.IndexDataStreamAccess,
          VertexDataStreamUsage: group.VertexDataStreamUsage,
          VertexDataStreamAccess: group.VertexDataStreamAccess,
          VertexCount: group.VertexCount,
          MaxIndexObserved: group.MaxIndexObserved,
          AverageConfidence: group.Count == 0 ? 0 : Math.Round(group.ConfidenceTotal / group.Count, 2),
          AverageIndexCoverageRatio: group.Count == 0 ? 0 : Math.Round(group.IndexCoverageRatioTotal / group.Count, 4),
          Samples: group.Samples);
    }

    static NifMeshResidualTargetGroup toResidualTargetRecord(NifMeshResidualTargetAccumulator group)
    {
      return new NifMeshResidualTargetGroup(
          MeshSize: group.MeshSize,
          MeshBlockCount: group.MeshBlockCount,
          NifPayloads: group.NifIds.Count,
          ResidualStreamCount: group.ResidualStreamCount,
          ResidualPatternCount: group.ResidualPatternKeys.Count,
          Samples: group.Samples);
    }

    static NifMeshResidualStreamGroup toResidualStreamRecord(NifMeshResidualStreamAccumulator group)
    {
      return new NifMeshResidualStreamGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          MeshPayloadOffset: group.MeshPayloadOffset,
          TargetSize: group.TargetSize,
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          DataStreamUsage: group.DataStreamUsage,
          DataStreamAccess: group.DataStreamAccess,
          Role: group.Role,
          RoleConfidence: group.RoleConfidence,
          BodyFirst16: group.BodyFirst16,
          StringValue: group.StringValue,
          RotatedFloat3VectorCount: group.RotatedFloat3VectorCount,
          RotatedFloat3FiniteVectorRatio: group.RotatedFloat3FiniteVectorRatio,
          RotatedFloat3PlausibleValueRatio: group.RotatedFloat3PlausibleValueRatio,
          RotatedFloat3NonZeroVectorRatio: group.RotatedFloat3NonZeroVectorRatio,
          RotatedFloat3MaxExtent: group.RotatedFloat3MaxExtent,
          RotatedFloat3Prefix: group.RotatedFloat3Prefix,
          StrictRotatedFloat3PositionClassifierReview: BuildNifResidualPositionClassifierReview(
              group.RotatedFloat3VectorCount,
              group.RotatedFloat3FiniteVectorRatio,
              group.RotatedFloat3PlausibleValueRatio,
              group.RotatedFloat3NonZeroVectorRatio,
              group.RotatedFloat3MaxExtent),
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          Samples: group.Samples);
    }

    static NifMeshAttributeSetGroup toAttributeSetRecord(NifMeshAttributeSetAccumulator group)
    {
      return new NifMeshAttributeSetGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          PositionDeclaredPayloadBytes: group.PositionDeclaredPayloadBytes,
          NormalDeclaredPayloadBytes: group.NormalDeclaredPayloadBytes,
          UvDeclaredPayloadBytes: group.UvDeclaredPayloadBytes,
          VertexCount: group.VertexCount,
          Topology: group.Topology,
          AverageConfidence: group.Count == 0 ? 0 : Math.Round(group.ConfidenceTotal / group.Count, 2),
          Samples: group.Samples);
    }

    static NifAttributeTopologyGroup toAttributeTopologyRecord(NifAttributeTopologyAccumulator group)
    {
      return new NifAttributeTopologyGroup(
          Topology: group.Topology,
          VertexCount: group.VertexCount,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          TriangleListTriangleCount: group.TriangleListTriangleCount,
          TriangleStripTriangleCount: group.TriangleStripTriangleCount,
          QuadListQuadCount: group.QuadListQuadCount,
          AverageTopologyConfidence: group.Count == 0 ? 0 : Math.Round(group.ConfidenceTotal / group.Count, 2),
          Samples: group.Samples);
    }

    static NifAttributeExtraStreamGroup toAttributeExtraRecord(NifAttributeExtraStreamAccumulator group)
    {
      return new NifAttributeExtraStreamGroup(
          Topology: group.Topology,
          VertexCount: group.VertexCount,
          ExtraMeshPayloadOffset: group.ExtraMeshPayloadOffset,
          ExtraRole: group.ExtraRole,
          ExtraDeclaredPayloadBytes: group.ExtraDeclaredPayloadBytes,
          BytesPerVertex: group.BytesPerVertex,
          BytesPerTriangleListTriangle: group.BytesPerTriangleListTriangle,
          BytesPerStripOrFanTriangle: group.BytesPerStripOrFanTriangle,
          BytesPerQuad: group.BytesPerQuad,
          FitSummary: group.FitSummary,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          Samples: group.Samples);
    }

    static NifAttributeExtraMappingFitnessGroup toAttributeExtraMappingFitnessRecord(NifAttributeExtraMappingFitnessAccumulator group)
    {
      var averageRawMedian = group.RawMedianMaxEdgeCount == 0 ? (double?)null : Math.Round(group.RawMedianMaxEdgeTotal / group.RawMedianMaxEdgeCount, 6);
      var averageSubtractOneMedian = group.SubtractOneMedianMaxEdgeCount == 0 ? (double?)null : Math.Round(group.SubtractOneMedianMaxEdgeTotal / group.SubtractOneMedianMaxEdgeCount, 6);
      var averageRawSegmentedMedian = group.RawSegmentedMedianMaxEdgeCount == 0 ? (double?)null : Math.Round(group.RawSegmentedMedianMaxEdgeTotal / group.RawSegmentedMedianMaxEdgeCount, 6);
      var averageSubtractOneSegmentedMedian = group.SubtractOneSegmentedMedianMaxEdgeCount == 0 ? (double?)null : Math.Round(group.SubtractOneSegmentedMedianMaxEdgeTotal / group.SubtractOneSegmentedMedianMaxEdgeCount, 6);
      var averageRawSegmentedNormalMedian = group.RawSegmentedMedianNormalDeltaCount == 0 ? (double?)null : Math.Round(group.RawSegmentedMedianNormalDeltaTotal / group.RawSegmentedMedianNormalDeltaCount, 6);
      var averageSubtractOneSegmentedNormalMedian = group.SubtractOneSegmentedMedianNormalDeltaCount == 0 ? (double?)null : Math.Round(group.SubtractOneSegmentedMedianNormalDeltaTotal / group.SubtractOneSegmentedMedianNormalDeltaCount, 6);
      var averageRawSegmentedUvMedian = group.RawSegmentedMedianUvDeltaCount == 0 ? (double?)null : Math.Round(group.RawSegmentedMedianUvDeltaTotal / group.RawSegmentedMedianUvDeltaCount, 6);
      var averageSubtractOneSegmentedUvMedian = group.SubtractOneSegmentedMedianUvDeltaCount == 0 ? (double?)null : Math.Round(group.SubtractOneSegmentedMedianUvDeltaTotal / group.SubtractOneSegmentedMedianUvDeltaCount, 6);
      var averageRawSegmentedAreaMedian = group.RawSegmentedMedianTriangleAreaCount == 0 ? (double?)null : Math.Round(group.RawSegmentedMedianTriangleAreaTotal / group.RawSegmentedMedianTriangleAreaCount, 6);
      var averageSubtractOneSegmentedAreaMedian = group.SubtractOneSegmentedMedianTriangleAreaCount == 0 ? (double?)null : Math.Round(group.SubtractOneSegmentedMedianTriangleAreaTotal / group.SubtractOneSegmentedMedianTriangleAreaCount, 6);
      return new NifAttributeExtraMappingFitnessGroup(
          Pattern: group.Pattern,
          MeshSize: group.MeshSize,
          Topology: group.Topology,
          VertexCount: group.VertexCount,
          ExtraMeshPayloadOffset: group.ExtraMeshPayloadOffset,
          ExtraRole: group.ExtraRole,
          ExtraDeclaredPayloadBytes: group.ExtraDeclaredPayloadBytes,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          RawZeroBasedPreferredCount: group.RawZeroBasedPreferredCount,
          SubtractOnePreferredCount: group.SubtractOnePreferredCount,
          TieCount: group.TieCount,
          AverageRawMedianMaxEdge: averageRawMedian,
          AverageSubtractOneMedianMaxEdge: averageSubtractOneMedian,
          AverageMedianMaxEdgeDelta: averageRawMedian is null || averageSubtractOneMedian is null ? null : Math.Round(averageSubtractOneMedian.Value - averageRawMedian.Value, 6),
          AverageRawSegmentedMedianMaxEdge: averageRawSegmentedMedian,
          AverageSubtractOneSegmentedMedianMaxEdge: averageSubtractOneSegmentedMedian,
          AverageSegmentedMedianMaxEdgeDelta: averageRawSegmentedMedian is null || averageSubtractOneSegmentedMedian is null ? null : Math.Round(averageSubtractOneSegmentedMedian.Value - averageRawSegmentedMedian.Value, 6),
          AverageRawSegmentedMedianNormalDelta: averageRawSegmentedNormalMedian,
          AverageSubtractOneSegmentedMedianNormalDelta: averageSubtractOneSegmentedNormalMedian,
          AverageSegmentedMedianNormalDeltaGap: averageRawSegmentedNormalMedian is null || averageSubtractOneSegmentedNormalMedian is null ? null : Math.Round(averageSubtractOneSegmentedNormalMedian.Value - averageRawSegmentedNormalMedian.Value, 6),
          AverageRawSegmentedMedianUvDelta: averageRawSegmentedUvMedian,
          AverageSubtractOneSegmentedMedianUvDelta: averageSubtractOneSegmentedUvMedian,
          AverageSegmentedMedianUvDeltaGap: averageRawSegmentedUvMedian is null || averageSubtractOneSegmentedUvMedian is null ? null : Math.Round(averageSubtractOneSegmentedUvMedian.Value - averageRawSegmentedUvMedian.Value, 6),
          AverageRawSegmentedMedianTriangleArea: averageRawSegmentedAreaMedian,
          AverageSubtractOneSegmentedMedianTriangleArea: averageSubtractOneSegmentedAreaMedian,
          AverageSegmentedMedianTriangleAreaGap: averageRawSegmentedAreaMedian is null || averageSubtractOneSegmentedAreaMedian is null ? null : Math.Round(averageSubtractOneSegmentedAreaMedian.Value - averageRawSegmentedAreaMedian.Value, 6),
          AverageRawFirstSegmentNearZeroAreaCount: group.RawFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.RawFirstSegmentNearZeroAreaCountTotal / group.RawFirstSegmentProofReviewCount, 2),
          AverageSubtractOneFirstSegmentNearZeroAreaCount: group.SubtractOneFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.SubtractOneFirstSegmentNearZeroAreaCountTotal / group.SubtractOneFirstSegmentProofReviewCount, 2),
          AverageRawFirstSegmentDominantPlaneSwitchCount: group.RawFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.RawFirstSegmentDominantPlaneSwitchCountTotal / group.RawFirstSegmentProofReviewCount, 2),
          AverageSubtractOneFirstSegmentDominantPlaneSwitchCount: group.SubtractOneFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.SubtractOneFirstSegmentDominantPlaneSwitchCountTotal / group.SubtractOneFirstSegmentProofReviewCount, 2),
          AverageRawFirstSegmentDominantSignedAreaSignSwitchCount: group.RawFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.RawFirstSegmentDominantSignedAreaSignSwitchCountTotal / group.RawFirstSegmentProofReviewCount, 2),
          AverageSubtractOneFirstSegmentDominantSignedAreaSignSwitchCount: group.SubtractOneFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.SubtractOneFirstSegmentDominantSignedAreaSignSwitchCountTotal / group.SubtractOneFirstSegmentProofReviewCount, 2),
          AverageRawFirstSegmentNonContiguousWindowTransitionCount: group.RawFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.RawFirstSegmentNonContiguousWindowTransitionCountTotal / group.RawFirstSegmentProofReviewCount, 2),
          AverageSubtractOneFirstSegmentNonContiguousWindowTransitionCount: group.SubtractOneFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.SubtractOneFirstSegmentNonContiguousWindowTransitionCountTotal / group.SubtractOneFirstSegmentProofReviewCount, 2),
          AverageRawFirstSegmentNonAlternatingParityTransitionCount: group.RawFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.RawFirstSegmentNonAlternatingParityTransitionCountTotal / group.RawFirstSegmentProofReviewCount, 2),
          AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount: group.SubtractOneFirstSegmentProofReviewCount == 0 ? null : Math.Round(group.SubtractOneFirstSegmentNonAlternatingParityTransitionCountTotal / group.SubtractOneFirstSegmentProofReviewCount, 2),
          AverageSegmentCount: group.Count == 0 ? null : Math.Round(group.SegmentCountTotal / group.Count, 2),
          AverageSegmentedTriangleWindowCount: group.Count == 0 ? null : Math.Round(group.SegmentedTriangleWindowCountTotal / group.Count, 2),
          AverageDroppedDegenerateWindowCount: group.Count == 0 ? null : Math.Round(group.DroppedDegenerateWindowCountTotal / group.Count, 2),
          AverageDroppedCrossSegmentWindowCount: group.Count == 0 ? null : Math.Round(group.DroppedCrossSegmentWindowCountTotal / group.Count, 2),
          DominantStripStructureHint: group.StripStructureHintCounts.Count == 0
              ? "unknown"
              : group.StripStructureHintCounts
                  .OrderByDescending(static kvp => kvp.Value)
                  .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
                  .First()
                  .Key,
          AverageAdjacentRepeatCount: group.StripStructureCount == 0 ? null : Math.Round(group.AdjacentRepeatCountTotal / group.StripStructureCount, 2),
          AverageMirroredBridgeCount: group.StripStructureCount == 0 ? null : Math.Round(group.MirroredBridgeCountTotal / group.StripStructureCount, 2),
          AverageDegenerateRunCount: group.StripStructureCount == 0 ? null : Math.Round(group.DegenerateRunCountTotal / group.StripStructureCount, 2),
          AverageMaxDegenerateRunLength: group.StripStructureCount == 0 ? null : Math.Round(group.MaxDegenerateRunLengthTotal / group.StripStructureCount, 2),
          AverageNonDegenerateRunCount: group.StripStructureCount == 0 ? null : Math.Round(group.NonDegenerateRunCountTotal / group.StripStructureCount, 2),
          AverageMaxNonDegenerateRunLength: group.StripStructureCount == 0 ? null : Math.Round(group.MaxNonDegenerateRunLengthTotal / group.StripStructureCount, 2),
          SentinelRestartValueCountTotal: group.SentinelRestartValueCountTotal,
          ZeroIndexValueCountTotal: group.ZeroIndexValueCountTotal,
          PreferredMapping: group.RawZeroBasedPreferredCount > group.SubtractOnePreferredCount
              ? "raw-zero-based"
              : group.SubtractOnePreferredCount > group.RawZeroBasedPreferredCount
                  ? "subtract-one"
                  : "tie",
          Samples: group.Samples);
    }

    var report = new NifMeshBindingInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        MeshBlocks: meshBlockCount,
        MeshBlocksWithCandidates: meshBlocksWithCandidates,
        CandidateLinks: candidateLinkCount,
        ValidDeclaredStreamBodies: validDeclaredStreamBodies,
        InvalidDeclaredStreamBodies: invalidDeclaredStreamBodies,
        PairCompatibleMeshes: pairCompatibleMeshes,
        PairCompatibleLinks: pairCompatibleLinks,
        AttributeCompatibleMeshes: attributeCompatibleMeshes,
        AttributeCompatibleSets: attributeCompatibleSets,
        RoleGroups: roleGroups.Values
            .Select(toRoleRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.Role, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopUsageAccessRoles: usageAccessRoleGroups.Values
            .Select(toUsageAccessRoleRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.DataStreamUsage, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static g => g.DataStreamAccess, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static g => g.Role, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopPositionSourceSiblings: positionSourceSiblingGroups.Values
            .Where(static g => g.MeshBlockIndices.Count >= 2)
            .Select(toPositionSourceSiblingRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.DistinctMeshBlocks)
            .ThenBy(static g => g.IdPrefix, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static g => g.TargetBlockIndex)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        ResidualTargetMeshSizes: residualTargetGroups.Values
            .Select(toResidualTargetRecord)
            .OrderByDescending(static g => g.ResidualStreamCount)
            .ThenByDescending(static g => g.MeshBlockCount)
            .ThenBy(static g => g.MeshSize)
            .ToList(),
        TopResidualStreams: residualStreamGroups.Values
            .Select(toResidualStreamRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.MeshPayloadOffset)
            .ThenBy(static g => g.Role, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopPatterns: patternGroups.Values
            .Select(toPatternRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.PairCompatibleCount)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.Pattern, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopPairings: pairingGroups.Values
            .Select(toPairingRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.AverageConfidence)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.Pattern, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopAttributeSets: attributeSetGroups.Values
            .Select(toAttributeSetRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.AverageConfidence)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.Pattern, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopAttributeTopologies: attributeTopologyGroups.Values
            .Select(toAttributeTopologyRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.AverageTopologyConfidence)
            .ThenBy(static g => g.VertexCount)
            .ThenBy(static g => g.Topology, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopAttributeExtraStreams: attributeExtraGroups.Values
            .Select(toAttributeExtraRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.VertexCount)
            .ThenBy(static g => g.ExtraMeshPayloadOffset)
            .ThenBy(static g => g.ExtraRole, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopAttributeExtraMappingFitness: attributeExtraMappingFitnessGroups.Values
            .Select(toAttributeExtraMappingFitnessRecord)
            .OrderByDescending(static g => g.Count)
            .ThenByDescending(static g => g.RawZeroBasedPreferredCount)
            .ThenByDescending(static g => g.AverageMedianMaxEdgeDelta ?? double.MinValue)
            .ThenBy(static g => g.MeshSize)
            .ThenBy(static g => g.ExtraMeshPayloadOffset)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-mesh-binding-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiMesh blocks: {meshBlockCount:N0}");
    Console.WriteLine($"Mesh blocks with candidates: {meshBlocksWithCandidates:N0}");
    Console.WriteLine($"Candidate stream links: {candidateLinkCount:N0}");
    Console.WriteLine($"Valid declared stream bodies: {validDeclaredStreamBodies:N0}");
    Console.WriteLine($"Invalid declared stream bodies: {invalidDeclaredStreamBodies:N0}");
    Console.WriteLine($"Pair-compatible meshes: {pairCompatibleMeshes:N0}");
    Console.WriteLine($"Pair-compatible links: {pairCompatibleLinks:N0}");
    Console.WriteLine($"Attribute-compatible meshes: {attributeCompatibleMeshes:N0}");
    Console.WriteLine($"Attribute-compatible sets: {attributeCompatibleSets:N0}");
    Console.WriteLine($"Top roles: {string.Join(", ", report.RoleGroups.Take(8).Select(static g => $"{g.Role}={g.Count:N0}"))}");
    Console.WriteLine($"Top usage/access roles: {string.Join(" | ", report.TopUsageAccessRoles.Take(8).Select(static g => $"{FormatNifDataStreamUsageAccessKey(g.DataStreamUsage, g.DataStreamAccess)} {g.Role}={g.Count:N0}"))}");
    Console.WriteLine($"Top position source sibling groups: {string.Join(" | ", report.TopPositionSourceSiblings.Take(5).Select(static g => $"{g.IdPrefix} block#{g.TargetBlockIndex} payload={g.DeclaredPayloadBytes?.ToString(CultureInfo.InvariantCulture) ?? "-"} {FormatNifDataStreamUsageAccessKey(g.DataStreamUsage, g.DataStreamAccess)} count={g.Count:N0} meshes={string.Join(",", g.MeshBlockIndices.Take(4).Select(static i => $"#{i}"))} offsets={string.Join(",", g.MeshPayloadOffsets.Take(4))}"))}");
    Console.WriteLine($"Residual target mesh sizes: {string.Join(" | ", report.ResidualTargetMeshSizes.Select(static g => $"meshSize={g.MeshSize} meshes={g.MeshBlockCount:N0} residuals={g.ResidualStreamCount:N0} patterns={g.ResidualPatternCount:N0}"))}");
    Console.WriteLine($"Top residual streams (target mesh sizes, known geometry/sentinel roles removed): {string.Join(" | ", report.TopResidualStreams.Take(5).Select(static g => $"meshSize={g.MeshSize} count={g.Count:N0} stream@{g.MeshPayloadOffset} payload={g.DeclaredPayloadBytes?.ToString(CultureInfo.InvariantCulture) ?? "-"} {FormatNifDataStreamUsageAccessKey(g.DataStreamUsage, g.DataStreamAccess)} {g.Role} c={g.RoleConfidence} string={g.StringValue ?? "-"} ror3=v{g.RotatedFloat3VectorCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} finite={g.RotatedFloat3FiniteVectorRatio?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} plausible={g.RotatedFloat3PlausibleValueRatio?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} extent={g.RotatedFloat3MaxExtent?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} first16={g.BodyFirst16}"))}");
    Console.WriteLine($"Top pairings: {string.Join(" | ", report.TopPairings.Take(5).Select(static g => $"meshSize={g.MeshSize} count={g.Count:N0} index[{FormatNifDataStreamUsageAccessKey(g.IndexDataStreamUsage, g.IndexDataStreamAccess)}] {g.IndexRole}->vertex[{FormatNifDataStreamUsageAccessKey(g.VertexDataStreamUsage, g.VertexDataStreamAccess)}] {g.VertexRole} v={g.VertexCount} maxIndex={g.MaxIndexObserved} pairs={g.IndexPairCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} list={g.TriangleListTriangleCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} strip={g.TriangleStripWindowCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} cov={g.MaxIndexCoverageRatio.ToString("g6", CultureInfo.InvariantCulture)}"))}");
    Console.WriteLine($"Top attribute sets: {string.Join(" | ", report.TopAttributeSets.Take(5).Select(static g => $"meshSize={g.MeshSize} count={g.Count:N0} p={g.PositionDeclaredPayloadBytes}/n={g.NormalDeclaredPayloadBytes}/uv={g.UvDeclaredPayloadBytes} v={g.VertexCount} topology={g.Topology.PrimaryTopology}"))}");
    Console.WriteLine($"Top attribute topologies: {string.Join(" | ", report.TopAttributeTopologies.Take(5).Select(static g => $"{g.Topology} v={g.VertexCount} count={g.Count:N0} list={g.TriangleListTriangleCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} strip={g.TriangleStripTriangleCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} quad={g.QuadListQuadCount?.ToString(CultureInfo.InvariantCulture) ?? "-"}"))}");
    Console.WriteLine($"Top attribute extras: {string.Join(" | ", report.TopAttributeExtraStreams.Take(5).Select(static g => $"{g.Topology} v={g.VertexCount} extra@{g.ExtraMeshPayloadOffset} payload={g.ExtraDeclaredPayloadBytes} {g.ExtraRole} count={g.Count:N0} fit={g.FitSummary}"))}");
    Console.WriteLine($"Top attribute extra mapping fitness: {string.Join(" | ", report.TopAttributeExtraMappingFitness.Take(5).Select(static g => $"meshSize={g.MeshSize} v={g.VertexCount} extra@{g.ExtraMeshPayloadOffset} {g.ExtraRole} count={g.Count:N0} prefer={g.PreferredMapping} raw={g.RawZeroBasedPreferredCount:N0} sub1={g.SubtractOnePreferredCount:N0} avgDelta={g.AverageMedianMaxEdgeDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} segDelta={g.AverageSegmentedMedianMaxEdgeDelta?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} normGap={g.AverageSegmentedMedianNormalDeltaGap?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} uvGap={g.AverageSegmentedMedianUvDeltaGap?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} areaGap={g.AverageSegmentedMedianTriangleAreaGap?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} proofSwitches={g.AverageRawFirstSegmentDominantPlaneSwitchCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"}/{g.AverageSubtractOneFirstSegmentDominantPlaneSwitchCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} signSwitches={g.AverageRawFirstSegmentDominantSignedAreaSignSwitchCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"}/{g.AverageSubtractOneFirstSegmentDominantSignedAreaSignSwitchCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} parityBreaks={g.AverageRawFirstSegmentNonAlternatingParityTransitionCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"}/{g.AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} segments={g.AverageSegmentCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} droppedCross={g.AverageDroppedCrossSegmentWindowCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} strip={g.DominantStripStructureHint} bridges={g.AverageMirroredBridgeCount?.ToString("g6", CultureInfo.InvariantCulture) ?? "-"} sentinels={g.SentinelRestartValueCountTotal:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifStreamHeaders(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var headerGroups = new Dictionary<int, NifStreamHeaderAccumulator>();
    var familyGroups = new Dictionary<string, NifStreamHeaderFamilyAccumulator>(StringComparer.OrdinalIgnoreCase);
    var usageAccessGroups = new Dictionary<string, NifDataStreamUsageAccessAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var dataStreamBlocks = 0;
    var declaredPayloadBlocks = 0;
    var validDeclaredPayloadBlocks = 0;
    var invalidDeclaredPayloadBlocks = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var block in header.Blocks.Where(static b => b.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase)))
          {
            dataStreamBlocks++;
            var blockPayload = SliceNifBlockPayload(payload.Bytes, block);
            if (blockPayload.Length < 4)
            {
              continue;
            }

            declaredPayloadBlocks++;
            var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
            if (declaredPayloadBytes > blockPayload.Length)
            {
              invalidDeclaredPayloadBlocks++;
              continue;
            }

            validDeclaredPayloadBlocks++;
            var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);
            var declaredPayloadOffset = headerBytes;
            var declaredPayload = blockPayload.Slice(declaredPayloadOffset, checked((int)declaredPayloadBytes));
            var strideCandidates = FindWholeBlockStrideCandidates(declaredPayload.Length);
            var usageAccessKey = FormatNifDataStreamUsageAccessKey(block.DataStreamUsage, block.DataStreamAccess);
            var sample = new NifStreamHeaderSample(
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                BlockIndex: block.Index,
                TypeName: block.TypeName,
                DataStreamUsage: block.DataStreamUsage,
                DataStreamAccess: block.DataStreamAccess,
                DataOffset: block.DataOffset,
                BlockSize: block.Size,
                First16: block.First16,
                DeclaredPayloadBytes: declaredPayloadBytes,
                HeaderBytes: headerBytes,
                PayloadFirst16: ToHex(declaredPayload[..Math.Min(16, declaredPayload.Length)]),
                PayloadStrideCandidates: strideCandidates);

            if (!headerGroups.TryGetValue(headerBytes, out var headerGroup))
            {
              headerGroup = new NifStreamHeaderAccumulator(headerBytes);
              headerGroups.Add(headerBytes, headerGroup);
            }

            headerGroup.Count++;
            headerGroup.TypeCounts[block.TypeName] = headerGroup.TypeCounts.GetValueOrDefault(block.TypeName) + 1;
            headerGroup.UsageAccessCounts[usageAccessKey] = headerGroup.UsageAccessCounts.GetValueOrDefault(usageAccessKey) + 1;
            headerGroup.BlockSizeCounts[block.Size] = headerGroup.BlockSizeCounts.GetValueOrDefault(block.Size) + 1;
            headerGroup.DeclaredPayloadSizeCounts[declaredPayloadBytes] = headerGroup.DeclaredPayloadSizeCounts.GetValueOrDefault(declaredPayloadBytes) + 1;
            foreach (var strideCandidate in strideCandidates)
            {
              headerGroup.PayloadStrideCounts[strideCandidate.Stride] = headerGroup.PayloadStrideCounts.GetValueOrDefault(strideCandidate.Stride) + 1;
            }

            if (headerGroup.Samples.Count < 16)
            {
              headerGroup.Samples.Add(sample);
            }

            if (!usageAccessGroups.TryGetValue(usageAccessKey, out var usageAccessGroup))
            {
              usageAccessGroup = new NifDataStreamUsageAccessAccumulator(block.DataStreamUsage, block.DataStreamAccess);
              usageAccessGroups.Add(usageAccessKey, usageAccessGroup);
            }

            usageAccessGroup.Count++;

            var familyKey = $"{block.TypeName}|{usageAccessKey}|size={block.Size}|payload={declaredPayloadBytes}|header={headerBytes}|first16={block.First16}";
            if (!familyGroups.TryGetValue(familyKey, out var familyGroup))
            {
              familyGroup = new NifStreamHeaderFamilyAccumulator(block.TypeName, block.DataStreamUsage, block.DataStreamAccess, block.Size, declaredPayloadBytes, headerBytes, block.First16, sample.PayloadFirst16);
              familyGroups.Add(familyKey, familyGroup);
            }

            familyGroup.Count++;
            familyGroup.NifIds.Add(entry.IdPrefix);
            foreach (var strideCandidate in strideCandidates)
            {
              familyGroup.PayloadStrideCounts[strideCandidate.Stride] = familyGroup.PayloadStrideCounts.GetValueOrDefault(strideCandidate.Stride) + 1;
            }

            if (familyGroup.Samples.Count < 16)
            {
              familyGroup.Samples.Add(sample);
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static List<NifSizeCount> topSizeCounts(Dictionary<uint, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static List<NifIntCount> topIntCounts(Dictionary<int, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifIntCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static List<NifStringCount> topStringCounts(Dictionary<string, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
          .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static NifStreamHeaderGroup toHeaderRecord(NifStreamHeaderAccumulator group)
    {
      return new NifStreamHeaderGroup(
          HeaderBytes: group.HeaderBytes,
          Count: group.Count,
          TypeCounts: group.TypeCounts
              .OrderByDescending(static kvp => kvp.Value)
              .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
              .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
              .ToList(),
          UsageAccessCounts: topStringCounts(group.UsageAccessCounts),
          BlockSizes: topSizeCounts(group.BlockSizeCounts),
          DeclaredPayloadSizes: topSizeCounts(group.DeclaredPayloadSizeCounts),
          PayloadStrides: topIntCounts(group.PayloadStrideCounts),
          Samples: group.Samples);
    }

    static NifStreamHeaderFamilyGroup toFamilyRecord(NifStreamHeaderFamilyAccumulator family)
    {
      return new NifStreamHeaderFamilyGroup(
          TypeName: family.TypeName,
          DataStreamUsage: family.DataStreamUsage,
          DataStreamAccess: family.DataStreamAccess,
          BlockSize: family.BlockSize,
          DeclaredPayloadBytes: family.DeclaredPayloadBytes,
          HeaderBytes: family.HeaderBytes,
          First16: family.First16,
          PayloadFirst16: family.PayloadFirst16,
          Count: family.Count,
          NifPayloads: family.NifIds.Count,
          PayloadStrides: topIntCounts(family.PayloadStrideCounts),
          Samples: family.Samples);
    }

    var report = new NifStreamHeaderInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        DataStreamBlocks: dataStreamBlocks,
        DeclaredPayloadBlocks: declaredPayloadBlocks,
        ValidDeclaredPayloadBlocks: validDeclaredPayloadBlocks,
        InvalidDeclaredPayloadBlocks: invalidDeclaredPayloadBlocks,
        UsageAccessGroups: usageAccessGroups.Values
            .Select(static g => new NifDataStreamUsageAccessGroup(g.DataStreamUsage, g.DataStreamAccess, g.Count))
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.DataStreamUsage, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static g => g.DataStreamAccess, StringComparer.OrdinalIgnoreCase)
            .ToList(),
        HeaderGroups: headerGroups.Values
            .Select(toHeaderRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.HeaderBytes)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopFamilies: familyGroups.Values
            .Select(toFamilyRecord)
            .OrderByDescending(static f => f.Count)
            .ThenBy(static f => f.BlockSize)
            .ThenBy(static f => f.DeclaredPayloadBytes)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-stream-header-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiDataStream blocks: {dataStreamBlocks:N0}");
    Console.WriteLine($"Declared payload blocks: {declaredPayloadBlocks:N0}");
    Console.WriteLine($"Valid declared payload blocks: {validDeclaredPayloadBlocks:N0}");
    Console.WriteLine($"Invalid declared payload blocks: {invalidDeclaredPayloadBlocks:N0}");
    Console.WriteLine($"Top usage/access: {string.Join(", ", report.UsageAccessGroups.Take(8).Select(static g => $"{FormatNifDataStreamUsageAccessKey(g.DataStreamUsage, g.DataStreamAccess)}={g.Count:N0}"))}");
    Console.WriteLine($"Top header byte counts: {string.Join(", ", report.HeaderGroups.Take(8).Select(static g => $"{g.HeaderBytes}={g.Count:N0}"))}");
    Console.WriteLine($"Top stream families: {string.Join(" | ", report.TopFamilies.Take(5).Select(static f => $"size={f.BlockSize}/payload={f.DeclaredPayloadBytes}/header={f.HeaderBytes}{FormatNifDataStreamUsageAccessInline(f.DataStreamUsage, f.DataStreamAccess)} count={f.Count:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifStreamBodies(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var sizeGroups = new Dictionary<uint, NifStreamBodySizeAccumulator>();
    var signatureGroups = new Dictionary<string, NifStreamBodySignatureAccumulator>(StringComparer.OrdinalIgnoreCase);
    var usageAccessGroups = new Dictionary<string, NifDataStreamUsageAccessAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var dataStreamBlocks = 0;
    var validStreamBodies = 0;
    var invalidStreamBodies = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var block in header.Blocks.Where(static b => b.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase)))
          {
            dataStreamBlocks++;
            var blockPayload = SliceNifBlockPayload(payload.Bytes, block);
            if (blockPayload.Length < 4)
            {
              invalidStreamBodies++;
              continue;
            }

            var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
            if (declaredPayloadBytes > blockPayload.Length)
            {
              invalidStreamBodies++;
              continue;
            }

            var bodyOffset = blockPayload.Length - checked((int)declaredPayloadBytes);
            var body = blockPayload.Slice(bodyOffset, checked((int)declaredPayloadBytes));
            var stats = AnalyzeNifStreamBody(body);
            var usageAccessKey = FormatNifDataStreamUsageAccessKey(block.DataStreamUsage, block.DataStreamAccess);
            validStreamBodies++;

            var sample = new NifStreamBodySample(
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                BlockIndex: block.Index,
                TypeName: block.TypeName,
                DataStreamUsage: block.DataStreamUsage,
                DataStreamAccess: block.DataStreamAccess,
                BlockSize: block.Size,
                HeaderBytes: bodyOffset,
                DeclaredPayloadBytes: declaredPayloadBytes,
                PayloadFirst16: stats.First16,
                Stats: stats);

            if (!sizeGroups.TryGetValue(declaredPayloadBytes, out var sizeGroup))
            {
              sizeGroup = new NifStreamBodySizeAccumulator(declaredPayloadBytes);
              sizeGroups.Add(declaredPayloadBytes, sizeGroup);
            }

            sizeGroup.Count++;
            sizeGroup.ClassificationCounts[stats.Classification] = sizeGroup.ClassificationCounts.GetValueOrDefault(stats.Classification) + 1;
            sizeGroup.UsageAccessCounts[usageAccessKey] = sizeGroup.UsageAccessCounts.GetValueOrDefault(usageAccessKey) + 1;
            sizeGroup.BlockSizeCounts[block.Size] = sizeGroup.BlockSizeCounts.GetValueOrDefault(block.Size) + 1;
            sizeGroup.NonZeroByteTotal += stats.NonZeroBytes;
            if (stats.AllZero)
            {
              sizeGroup.AllZeroCount++;
            }

            foreach (var strideCandidate in stats.PayloadStrideCandidates)
            {
              sizeGroup.PayloadStrideCounts[strideCandidate.Stride] = sizeGroup.PayloadStrideCounts.GetValueOrDefault(strideCandidate.Stride) + 1;
            }

            if (sizeGroup.Samples.Count < 16)
            {
              sizeGroup.Samples.Add(sample);
            }

            if (!usageAccessGroups.TryGetValue(usageAccessKey, out var usageAccessGroup))
            {
              usageAccessGroup = new NifDataStreamUsageAccessAccumulator(block.DataStreamUsage, block.DataStreamAccess);
              usageAccessGroups.Add(usageAccessKey, usageAccessGroup);
            }

            usageAccessGroup.Count++;

            var signatureKey = $"{declaredPayloadBytes}|{usageAccessKey}|{stats.First16}";
            if (!signatureGroups.TryGetValue(signatureKey, out var signatureGroup))
            {
              signatureGroup = new NifStreamBodySignatureAccumulator(declaredPayloadBytes, block.DataStreamUsage, block.DataStreamAccess, stats.First16);
              signatureGroups.Add(signatureKey, signatureGroup);
            }

            signatureGroup.Count++;
            signatureGroup.NifIds.Add(entry.IdPrefix);
            signatureGroup.ClassificationCounts[stats.Classification] = signatureGroup.ClassificationCounts.GetValueOrDefault(stats.Classification) + 1;
            foreach (var strideCandidate in stats.PayloadStrideCandidates)
            {
              signatureGroup.PayloadStrideCounts[strideCandidate.Stride] = signatureGroup.PayloadStrideCounts.GetValueOrDefault(strideCandidate.Stride) + 1;
            }

            if (signatureGroup.Samples.Count < 16)
            {
              signatureGroup.Samples.Add(sample);
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static List<NifSizeCount> topSizeCounts(Dictionary<uint, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static List<NifIntCount> topIntCounts(Dictionary<int, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifIntCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static List<NifStringCount> topStringCounts(Dictionary<string, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
          .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static NifStreamBodySizeGroup toSizeRecord(NifStreamBodySizeAccumulator group)
    {
      return new NifStreamBodySizeGroup(
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          Count: group.Count,
          AllZeroCount: group.AllZeroCount,
          AverageNonZeroBytes: group.Count == 0 ? 0 : Math.Round(group.NonZeroByteTotal / (double)group.Count, 2),
          ClassificationCounts: topStringCounts(group.ClassificationCounts),
          UsageAccessCounts: topStringCounts(group.UsageAccessCounts),
          BlockSizes: topSizeCounts(group.BlockSizeCounts),
          PayloadStrides: topIntCounts(group.PayloadStrideCounts),
          Samples: group.Samples);
    }

    static NifStreamBodySignatureGroup toSignatureRecord(NifStreamBodySignatureAccumulator group)
    {
      return new NifStreamBodySignatureGroup(
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          DataStreamUsage: group.DataStreamUsage,
          DataStreamAccess: group.DataStreamAccess,
          PayloadFirst16: group.PayloadFirst16,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          ClassificationCounts: topStringCounts(group.ClassificationCounts),
          PayloadStrides: topIntCounts(group.PayloadStrideCounts),
          Samples: group.Samples);
    }

    var report = new NifStreamBodyInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        DataStreamBlocks: dataStreamBlocks,
        ValidStreamBodies: validStreamBodies,
        InvalidStreamBodies: invalidStreamBodies,
        UsageAccessGroups: usageAccessGroups.Values
            .Select(static g => new NifDataStreamUsageAccessGroup(g.DataStreamUsage, g.DataStreamAccess, g.Count))
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.DataStreamUsage, StringComparer.OrdinalIgnoreCase)
            .ThenBy(static g => g.DataStreamAccess, StringComparer.OrdinalIgnoreCase)
            .ToList(),
        PayloadSizeGroups: sizeGroups.Values
            .Select(toSizeRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.DeclaredPayloadBytes)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopBodySignatures: signatureGroups.Values
            .Select(toSignatureRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.DeclaredPayloadBytes)
            .ThenBy(static g => g.PayloadFirst16, StringComparer.OrdinalIgnoreCase)
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-stream-body-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiDataStream blocks: {dataStreamBlocks:N0}");
    Console.WriteLine($"Valid stream bodies: {validStreamBodies:N0}");
    Console.WriteLine($"Invalid stream bodies: {invalidStreamBodies:N0}");
    Console.WriteLine($"Top usage/access: {string.Join(", ", report.UsageAccessGroups.Take(8).Select(static g => $"{FormatNifDataStreamUsageAccessKey(g.DataStreamUsage, g.DataStreamAccess)}={g.Count:N0}"))}");
    Console.WriteLine($"Top payload sizes: {string.Join(", ", report.PayloadSizeGroups.Take(8).Select(static g => $"{g.DeclaredPayloadBytes}={g.Count:N0}"))}");
    Console.WriteLine($"Top body signatures: {string.Join(" | ", report.TopBodySignatures.Take(5).Select(static g => $"payload={g.DeclaredPayloadBytes}{FormatNifDataStreamUsageAccessInline(g.DataStreamUsage, g.DataStreamAccess)} first16={g.PayloadFirst16} count={g.Count:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifStreamEndianness(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var classGroups = new Dictionary<string, NifStreamEndianClassAccumulator>(StringComparer.OrdinalIgnoreCase);
    var signatureGroups = new Dictionary<string, NifStreamEndianSignatureAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var dataStreamBlocks = 0;
    var validStreamBodies = 0;
    var evenLengthBodies = 0;
    var invalidStreamBodies = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var block in header.Blocks.Where(static b => b.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase)))
          {
            dataStreamBlocks++;
            var blockPayload = SliceNifBlockPayload(payload.Bytes, block);
            if (blockPayload.Length < 4)
            {
              invalidStreamBodies++;
              continue;
            }

            var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
            if (declaredPayloadBytes > blockPayload.Length)
            {
              invalidStreamBodies++;
              continue;
            }

            validStreamBodies++;
            var bodyOffset = blockPayload.Length - checked((int)declaredPayloadBytes);
            var body = blockPayload.Slice(bodyOffset, checked((int)declaredPayloadBytes));
            if (body.Length % 2 != 0)
            {
              continue;
            }

            evenLengthBodies++;
            var stats = AnalyzeNifStreamEndian(body);
            var sample = new NifStreamEndianSample(
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                BlockIndex: block.Index,
                TypeName: block.TypeName,
                BlockSize: block.Size,
                HeaderBytes: bodyOffset,
                DeclaredPayloadBytes: declaredPayloadBytes,
                PayloadFirst16: stats.First16,
                Stats: stats);

            if (!classGroups.TryGetValue(stats.Classification, out var classGroup))
            {
              classGroup = new NifStreamEndianClassAccumulator(stats.Classification);
              classGroups.Add(stats.Classification, classGroup);
            }

            classGroup.Count++;
            classGroup.PayloadSizeCounts[declaredPayloadBytes] = classGroup.PayloadSizeCounts.GetValueOrDefault(declaredPayloadBytes) + 1;
            classGroup.BlockSizeCounts[block.Size] = classGroup.BlockSizeCounts.GetValueOrDefault(block.Size) + 1;
            classGroup.BigEndianLowValueRatioTotal += stats.BigEndianLowValueRatio;
            classGroup.LittleEndianLowValueRatioTotal += stats.LittleEndianLowValueRatio;
            if (classGroup.Samples.Count < 16)
            {
              classGroup.Samples.Add(sample);
            }

            var signatureKey = $"{stats.Classification}|{declaredPayloadBytes}|{stats.First16}";
            if (!signatureGroups.TryGetValue(signatureKey, out var signatureGroup))
            {
              signatureGroup = new NifStreamEndianSignatureAccumulator(stats.Classification, declaredPayloadBytes, stats.First16);
              signatureGroups.Add(signatureKey, signatureGroup);
            }

            signatureGroup.Count++;
            signatureGroup.NifIds.Add(entry.IdPrefix);
            if (signatureGroup.Samples.Count < 16)
            {
              signatureGroup.Samples.Add(sample);
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static List<NifSizeCount> topSizeCounts(Dictionary<uint, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static NifStreamEndianClassGroup toClassRecord(NifStreamEndianClassAccumulator group)
    {
      return new NifStreamEndianClassGroup(
          Classification: group.Classification,
          Count: group.Count,
          AverageBigEndianLowValueRatio: group.Count == 0 ? 0 : Math.Round(group.BigEndianLowValueRatioTotal / group.Count, 4),
          AverageLittleEndianLowValueRatio: group.Count == 0 ? 0 : Math.Round(group.LittleEndianLowValueRatioTotal / group.Count, 4),
          PayloadSizes: topSizeCounts(group.PayloadSizeCounts),
          BlockSizes: topSizeCounts(group.BlockSizeCounts),
          Samples: group.Samples);
    }

    static NifStreamEndianSignatureGroup toSignatureRecord(NifStreamEndianSignatureAccumulator group)
    {
      return new NifStreamEndianSignatureGroup(
          Classification: group.Classification,
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          PayloadFirst16: group.PayloadFirst16,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          Samples: group.Samples);
    }

    var signatureRecords = signatureGroups.Values
        .Select(toSignatureRecord)
        .OrderByDescending(static g => g.Count)
        .ThenBy(static g => g.Classification, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static g => g.DeclaredPayloadBytes)
        .ThenBy(static g => g.PayloadFirst16, StringComparer.OrdinalIgnoreCase)
        .ToList();
    var report = new NifStreamEndiannessInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        DataStreamBlocks: dataStreamBlocks,
        ValidStreamBodies: validStreamBodies,
        EvenLengthBodies: evenLengthBodies,
        InvalidStreamBodies: invalidStreamBodies,
        ClassGroups: classGroups.Values
            .Select(toClassRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.Classification, StringComparer.OrdinalIgnoreCase)
            .ToList(),
        TopBigEndianSignatures: signatureRecords
            .Where(static g => g.Classification.Contains("big-endian", StringComparison.OrdinalIgnoreCase))
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopSignatures: signatureRecords.Take(options.Limit > 0 ? options.Limit : 100).ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-stream-endianness-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiDataStream blocks: {dataStreamBlocks:N0}");
    Console.WriteLine($"Valid stream bodies: {validStreamBodies:N0}");
    Console.WriteLine($"Even-length stream bodies: {evenLengthBodies:N0}");
    Console.WriteLine($"Invalid stream bodies: {invalidStreamBodies:N0}");
    Console.WriteLine($"Endianness classes: {string.Join(", ", report.ClassGroups.Take(8).Select(static g => $"{g.Classification}={g.Count:N0}"))}");
    Console.WriteLine($"Top big-endian signatures: {string.Join(" | ", report.TopBigEndianSignatures.Take(5).Select(static g => $"payload={g.DeclaredPayloadBytes} first16={g.PayloadFirst16} count={g.Count:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int InventoryNifIndexCandidates(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var classGroups = new Dictionary<string, NifIndexCandidateClassAccumulator>(StringComparer.OrdinalIgnoreCase);
    var signatureGroups = new Dictionary<string, NifIndexCandidateSignatureAccumulator>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;
    var dataStreamBlocks = 0;
    var validStreamBodies = 0;
    var evenLengthBodies = 0;
    var bigEndianLeadBodies = 0;
    var bigEndianTriangleAlignedBodies = 0;
    var ambiguousTriangleAlignedBodies = 0;
    var triangleStripLessDegenerateBodies = 0;
    var invalidStreamBodies = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var block in header.Blocks.Where(static b => b.TypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase)))
          {
            dataStreamBlocks++;
            var blockPayload = SliceNifBlockPayload(payload.Bytes, block);
            if (blockPayload.Length < 4)
            {
              invalidStreamBodies++;
              continue;
            }

            var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
            if (declaredPayloadBytes > blockPayload.Length)
            {
              invalidStreamBodies++;
              continue;
            }

            validStreamBodies++;
            var bodyOffset = blockPayload.Length - checked((int)declaredPayloadBytes);
            var body = blockPayload.Slice(bodyOffset, checked((int)declaredPayloadBytes));
            if (body.Length % 2 != 0)
            {
              continue;
            }

            evenLengthBodies++;
            var endianStats = AnalyzeNifStreamEndian(body);
            var indexStats = AnalyzeNifUInt16BeIndex(body);
            var classification = ClassifyNifIndexCandidate(endianStats, indexStats);
            if (endianStats.Classification == "big-endian-u16-lead")
            {
              bigEndianLeadBodies++;
              if (indexStats.TriangleAligned)
              {
                bigEndianTriangleAlignedBodies++;
              }
            }

            if (endianStats.Classification == "ambiguous-small-u16" && indexStats.TriangleAligned)
            {
              ambiguousTriangleAlignedBodies++;
            }

            if (indexStats.TriangleStripLessDegenerateThanTriples)
            {
              triangleStripLessDegenerateBodies++;
            }

            var sample = new NifIndexCandidateSample(
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                BlockIndex: block.Index,
                TypeName: block.TypeName,
                BlockSize: block.Size,
                HeaderBytes: bodyOffset,
                DeclaredPayloadBytes: declaredPayloadBytes,
                PayloadFirst16: endianStats.First16,
                EndianStats: endianStats,
                IndexStats: indexStats,
                Classification: classification);

            if (!classGroups.TryGetValue(classification, out var classGroup))
            {
              classGroup = new NifIndexCandidateClassAccumulator(classification);
              classGroups.Add(classification, classGroup);
            }

            classGroup.Count++;
            if (indexStats.TriangleAligned)
            {
              classGroup.TriangleAlignedCount++;
            }

            classGroup.PayloadSizeCounts[declaredPayloadBytes] = classGroup.PayloadSizeCounts.GetValueOrDefault(declaredPayloadBytes) + 1;
            classGroup.MaxIndexTotal += indexStats.BigEndianMaxIndex;
            classGroup.TriangleCountTotal += indexStats.TriangleCount;
            classGroup.DegenerateTriangleRatioTotal += indexStats.DegenerateTriangleRatio;
            classGroup.TriangleStripWindowCountTotal += indexStats.TriangleStripWindowCount;
            classGroup.TriangleStripDegenerateRatioTotal += indexStats.TriangleStripDegenerateRatio;
            if (indexStats.TriangleStripLessDegenerateThanTriples)
            {
              classGroup.TriangleStripLessDegenerateThanTriplesCount++;
            }

            if (classGroup.Samples.Count < 16)
            {
              classGroup.Samples.Add(sample);
            }

            var signatureKey = $"{classification}|{declaredPayloadBytes}|{endianStats.First16}";
            if (!signatureGroups.TryGetValue(signatureKey, out var signatureGroup))
            {
              signatureGroup = new NifIndexCandidateSignatureAccumulator(classification, declaredPayloadBytes, endianStats.First16);
              signatureGroups.Add(signatureKey, signatureGroup);
            }

            signatureGroup.Count++;
            signatureGroup.NifIds.Add(entry.IdPrefix);
            signatureGroup.MaxObservedIndex = Math.Max(signatureGroup.MaxObservedIndex, indexStats.BigEndianMaxIndex);
            signatureGroup.MinObservedMaxIndex = signatureGroup.MinObservedMaxIndex is null
                ? indexStats.BigEndianMaxIndex
                : Math.Min(signatureGroup.MinObservedMaxIndex.Value, indexStats.BigEndianMaxIndex);
            if (indexStats.TriangleAligned)
            {
              signatureGroup.TriangleAlignedCount++;
            }

            signatureGroup.TriangleCountTotal += indexStats.TriangleCount;
            signatureGroup.DegenerateTriangleRatioTotal += indexStats.DegenerateTriangleRatio;
            signatureGroup.TriangleStripWindowCountTotal += indexStats.TriangleStripWindowCount;
            signatureGroup.TriangleStripDegenerateRatioTotal += indexStats.TriangleStripDegenerateRatio;
            if (indexStats.TriangleStripLessDegenerateThanTriples)
            {
              signatureGroup.TriangleStripLessDegenerateThanTriplesCount++;
            }

            if (signatureGroup.Samples.Count < 16)
            {
              signatureGroup.Samples.Add(sample);
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    static List<NifSizeCount> topSizeCounts(Dictionary<uint, int> counts)
    {
      return counts
          .OrderByDescending(static kvp => kvp.Value)
          .ThenBy(static kvp => kvp.Key)
          .Select(static kvp => new NifSizeCount(kvp.Key, kvp.Value))
          .ToList();
    }

    static NifIndexCandidateClassGroup toClassRecord(NifIndexCandidateClassAccumulator group)
    {
      return new NifIndexCandidateClassGroup(
          Classification: group.Classification,
          Count: group.Count,
          TriangleAlignedCount: group.TriangleAlignedCount,
          AverageTriangleCount: group.Count == 0 ? 0 : Math.Round(group.TriangleCountTotal / (double)group.Count, 2),
          AverageMaxIndex: group.Count == 0 ? 0 : Math.Round(group.MaxIndexTotal / (double)group.Count, 2),
          AverageDegenerateTriangleRatio: group.Count == 0 ? 0 : Math.Round(group.DegenerateTriangleRatioTotal / group.Count, 4),
          TriangleStripLessDegenerateThanTriplesCount: group.TriangleStripLessDegenerateThanTriplesCount,
          AverageTriangleStripWindowCount: group.Count == 0 ? 0 : Math.Round(group.TriangleStripWindowCountTotal / (double)group.Count, 2),
          AverageTriangleStripDegenerateRatio: group.Count == 0 ? 0 : Math.Round(group.TriangleStripDegenerateRatioTotal / group.Count, 4),
          PayloadSizes: topSizeCounts(group.PayloadSizeCounts),
          Samples: group.Samples);
    }

    static NifIndexCandidateSignatureGroup toSignatureRecord(NifIndexCandidateSignatureAccumulator group)
    {
      return new NifIndexCandidateSignatureGroup(
          Classification: group.Classification,
          DeclaredPayloadBytes: group.DeclaredPayloadBytes,
          PayloadFirst16: group.PayloadFirst16,
          Count: group.Count,
          NifPayloads: group.NifIds.Count,
          TriangleAlignedCount: group.TriangleAlignedCount,
          AverageTriangleCount: group.Count == 0 ? 0 : Math.Round(group.TriangleCountTotal / (double)group.Count, 2),
          AverageDegenerateTriangleRatio: group.Count == 0 ? 0 : Math.Round(group.DegenerateTriangleRatioTotal / group.Count, 4),
          TriangleStripLessDegenerateThanTriplesCount: group.TriangleStripLessDegenerateThanTriplesCount,
          AverageTriangleStripWindowCount: group.Count == 0 ? 0 : Math.Round(group.TriangleStripWindowCountTotal / (double)group.Count, 2),
          AverageTriangleStripDegenerateRatio: group.Count == 0 ? 0 : Math.Round(group.TriangleStripDegenerateRatioTotal / group.Count, 4),
          MaxObservedIndex: group.MaxObservedIndex,
          MinObservedMaxIndex: group.MinObservedMaxIndex,
          Samples: group.Samples);
    }

    var signatureRecords = signatureGroups.Values
        .Select(toSignatureRecord)
        .OrderByDescending(static g => g.Count)
        .ThenBy(static g => g.Classification, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static g => g.DeclaredPayloadBytes)
        .ThenBy(static g => g.PayloadFirst16, StringComparer.OrdinalIgnoreCase)
        .ToList();
    var report = new NifIndexCandidateInventoryReport(
        RootDirectory: rootDirectory,
        ManifestPath: manifestPath,
        InspectedPayloads: inspected,
        NifPayloads: nifCount,
        Failed: failed,
        DataStreamBlocks: dataStreamBlocks,
        ValidStreamBodies: validStreamBodies,
        EvenLengthBodies: evenLengthBodies,
        BigEndianLeadBodies: bigEndianLeadBodies,
        BigEndianTriangleAlignedBodies: bigEndianTriangleAlignedBodies,
        AmbiguousTriangleAlignedBodies: ambiguousTriangleAlignedBodies,
        TriangleStripLessDegenerateBodies: triangleStripLessDegenerateBodies,
        InvalidStreamBodies: invalidStreamBodies,
        ClassGroups: classGroups.Values
            .Select(toClassRecord)
            .OrderByDescending(static g => g.Count)
            .ThenBy(static g => g.Classification, StringComparer.OrdinalIgnoreCase)
            .ToList(),
        TopBigEndianIndexSignatures: signatureRecords
            .Where(static g => g.Classification.StartsWith("uint16be", StringComparison.OrdinalIgnoreCase))
            .Take(options.Limit > 0 ? options.Limit : 100)
            .ToList(),
        TopSignatures: signatureRecords.Take(options.Limit > 0 ? options.Limit : 100).ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-index-candidate-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NiDataStream blocks: {dataStreamBlocks:N0}");
    Console.WriteLine($"Valid stream bodies: {validStreamBodies:N0}");
    Console.WriteLine($"Even-length stream bodies: {evenLengthBodies:N0}");
    Console.WriteLine($"Big-endian uint16 lead bodies: {bigEndianLeadBodies:N0}");
    Console.WriteLine($"Big-endian triangle-aligned bodies: {bigEndianTriangleAlignedBodies:N0}");
    Console.WriteLine($"Triangle-strip less-degenerate bodies: {triangleStripLessDegenerateBodies:N0}");
    Console.WriteLine($"Index candidate classes: {string.Join(", ", report.ClassGroups.Take(8).Select(static g => $"{g.Classification}={g.Count:N0}"))}");
    Console.WriteLine($"Top uint16be signatures: {string.Join(" | ", report.TopBigEndianIndexSignatures.Take(5).Select(static g => $"payload={g.DeclaredPayloadBytes} first16={g.PayloadFirst16} count={g.Count:N0}"))}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int MineNifReferences(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var records = new List<NifReferenceMineRecord>();
    var uniqueCandidates = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
    var inspected = 0;
    var nifCount = 0;
    var failed = 0;

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      if (nifCount >= options.MaxTotalOrUnlimited())
      {
        break;
      }

      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry);
        if (!filter.EntryMatches(entry, manifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var reference in header.References)
          {
            var candidate = NormalizeNifReferenceCandidate(reference.Value);
            if (candidate.Length == 0)
            {
              continue;
            }

            uniqueCandidates.Add(candidate);
            records.Add(new NifReferenceMineRecord(
                Reference: reference.Value,
                Candidate: candidate,
                ArchiveName: archiveName,
                EntryIndex: entry.Index,
                IdPrefix: entry.IdPrefix,
                ManifestEntryIndex: manifestEntry?.Index,
                FilenameFnv1Hash: manifestEntry?.FilenameFnv1Hash,
                PakIndex: manifestEntry?.PakIndex,
                PakOffset: manifestEntry?.PakOffset,
                StringIndex: reference.StringIndex,
                NifVersion: header.VersionText,
                NifStringCount: header.StringCount));
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-references.jsonl");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    if (string.Equals(Path.GetExtension(outPath), ".txt", StringComparison.OrdinalIgnoreCase))
    {
      File.WriteAllLines(outPath, uniqueCandidates, Encoding.UTF8);
    }
    else
    {
      var orderedRecords = records
          .OrderBy(static r => r.Candidate, StringComparer.OrdinalIgnoreCase)
          .ThenBy(static r => r.ArchiveName, StringComparer.OrdinalIgnoreCase)
          .ThenBy(static r => r.EntryIndex)
          .ThenBy(static r => r.StringIndex);
      WriteJsonLines(outPath, options.Limit > 0 ? orderedRecords.Take(options.Limit) : orderedRecords, options.RedactPaths);
    }

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"Reference records: {records.Count:N0}");
    Console.WriteLine($"Unique candidates: {uniqueCandidates.Count:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int LinkNifTextures(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: Assets directory does not exist: {DisplayPath(options, assetsDirectory)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var filter = BuildExtractionFilter(options, lookup);
    var links = new List<NifTextureLinkRecord>();
    var inspected = 0;
    var nifCount = 0;
    var referenceCount = 0;
    var textureCandidateCount = 0;
    var failed = 0;
    var seenEdges = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      if (nifCount >= options.MaxTotalOrUnlimited())
      {
        break;
      }

      var archiveName = Path.GetFileName(archivePath);
      if (!filter.ArchiveMatches(archiveName))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (nifCount >= options.MaxTotalOrUnlimited())
        {
          break;
        }

        if (entry.IsNull)
        {
          continue;
        }

        lookup.Table1ById.TryGetValue(entry.IdPrefix, out var modelManifestEntry);
        if (!filter.EntryMatches(entry, modelManifestEntry))
        {
          continue;
        }

        try
        {
          inspected++;
          var packed = ReadArchivePayload(stream, entry, archiveName);
          var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
          if (DetectFileType(payload.Bytes).Extension != "nif")
          {
            continue;
          }

          nifCount++;
          var header = ParseNifHeader(payload.Bytes);
          foreach (var reference in header.References)
          {
            referenceCount++;
            foreach (var candidate in BuildTextureCandidateVariants(reference.Value))
            {
              textureCandidateCount++;
              if (!TryMatchRecoveredNameCandidate(lookup, candidate.Candidate, out var textureEntry, out var hash, out var byteLength, out var collisionCount))
              {
                continue;
              }

              var edgeKey = $"{entry.IdPrefix}|{textureEntry.IdPrefix}|{candidate.Candidate}";
              if (!seenEdges.Add(edgeKey))
              {
                continue;
              }

              links.Add(new NifTextureLinkRecord(
                  ModelArchiveName: archiveName,
                  ModelEntryIndex: entry.Index,
                  ModelIdPrefix: entry.IdPrefix,
                  ModelManifestEntryIndex: modelManifestEntry?.Index,
                  ModelFilenameFnv1Hash: modelManifestEntry?.FilenameFnv1Hash,
                  ModelPakIndex: modelManifestEntry?.PakIndex,
                  ModelPakOffset: modelManifestEntry?.PakOffset,
                  NifVersion: header.VersionText,
                  Reference: reference.Value,
                  ReferenceStringIndex: reference.StringIndex,
                  Candidate: candidate.Candidate,
                  CandidateKind: candidate.Kind,
                  Algorithm: "fnv1",
                  Hash: hash,
                  Length: byteLength,
                  Confidence: 100,
                  CollisionCount: collisionCount,
                  TextureManifestEntryIndex: textureEntry.Index,
                  TextureIdPrefix: textureEntry.IdPrefix,
                  TextureFilenameFnv1Hash: textureEntry.FilenameFnv1Hash,
                  TexturePakIndex: textureEntry.PakIndex,
                  TexturePakOffset: textureEntry.PakOffset,
                  TextureCompressedSize: textureEntry.CompressedSize,
                  TextureSize: textureEntry.Size,
                  TextureNameLength: textureEntry.NameLength));
            }
          }
        }
        catch
        {
          failed++;
        }
      }
    }

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-texture-links.jsonl");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    var orderedLinks = links
        .OrderBy(static l => l.ModelArchiveName, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static l => l.ModelEntryIndex)
        .ThenBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static l => l.TextureManifestEntryIndex);
    WriteJsonLines(outPath, options.Limit > 0 ? orderedLinks.Take(options.Limit) : orderedLinks, options.RedactPaths);

    Console.WriteLine($"Inspected payloads: {inspected:N0}");
    Console.WriteLine($"NIF payloads: {nifCount:N0}");
    Console.WriteLine($"NIF references: {referenceCount:N0}");
    Console.WriteLine($"Texture candidates: {textureCandidateCount:N0}");
    Console.WriteLine($"Recovered texture links: {links.Count:N0}");
    Console.WriteLine($"Unique models linked: {links.Select(static l => l.ModelIdPrefix).Distinct(StringComparer.OrdinalIgnoreCase).Count():N0}");
    Console.WriteLine($"Unique textures linked: {links.Select(static l => l.TextureIdPrefix).Distinct(StringComparer.OrdinalIgnoreCase).Count():N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int ExtractLinkedTextures(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var outDirectory = Path.GetFullPath(options.OutDirectory ?? Path.Combine(rootDirectory, "..", "Extracted", "linked-textures"));
    var linksPath = string.IsNullOrWhiteSpace(options.InputPath)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", "nif-texture-links.jsonl"))
        : Path.GetFullPath(options.InputPath);
    if (!File.Exists(linksPath))
    {
      Console.Error.WriteLine($"ERROR: link JSONL does not exist: {DisplayPath(options, linksPath)}");
      return 1;
    }

    var links = ReadJsonLines<NifTextureLinkRecord>(linksPath)
        .Where(l => string.IsNullOrWhiteSpace(options.IdFilter) || string.Equals(l.ModelIdPrefix, options.IdFilter, StringComparison.OrdinalIgnoreCase))
        .GroupBy(static l => l.TextureIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Select(static g => g.OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase).First())
        .OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase)
        .ToList();
    var payloadLookup = BuildPayloadLookup(rootDirectory, options, links.Select(static l => l.TextureIdPrefix));

    Directory.CreateDirectory(outDirectory);
    var samples = new List<LinkedTextureExtractSample>();
    var attempted = 0;
    var written = 0;
    var writtenFromCopied = 0;
    var writtenFromLive = 0;
    var missingFromCopied = 0;
    var missingFromSelectedSources = 0;
    var typeMismatch = 0;
    var failed = 0;

    foreach (var link in links)
    {
      if (options.MaxTotal > 0 && written >= options.MaxTotal)
      {
        break;
      }

      attempted++;
      try
      {
        var found = payloadLookup.Find(link.TextureIdPrefix, options.Lzma2Mode);
        if (found is null)
        {
          missingFromCopied++;
          missingFromSelectedSources++;
          continue;
        }

        var foundInLiveFallback = string.Equals(found.SourceKind, "live", StringComparison.OrdinalIgnoreCase);
        if (foundInLiveFallback)
        {
          missingFromCopied++;
        }

        var detected = DetectFileType(found.Payload);
        if (!RecoveredNameMatchesDetectedType(link.Candidate, detected.Extension))
        {
          typeMismatch++;
          continue;
        }

        var outputPath = BuildRecoveredOutputPath(outDirectory, link.Candidate, link.TextureIdPrefix, detected.Extension);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.WriteAllBytes(outputPath, found.Payload);
        written++;
        if (foundInLiveFallback)
        {
          writtenFromLive++;
        }
        else
        {
          writtenFromCopied++;
        }

        if (samples.Count < 50)
        {
          samples.Add(new LinkedTextureExtractSample(
              ModelIdPrefix: link.ModelIdPrefix,
              TextureIdPrefix: link.TextureIdPrefix,
              Candidate: link.Candidate,
              ArchiveName: found.ArchiveName,
              EntryIndex: found.EntryIndex,
              SourceKind: found.SourceKind,
              Type: detected.Extension,
              Width: detected.Width,
              Height: detected.Height,
              Format: detected.Format,
              RelativePath: Path.GetRelativePath(outDirectory, outputPath)));
        }
      }
      catch
      {
        failed++;
      }
    }

    var report = new LinkedTextureExtractReport(
        RootDirectory: rootDirectory,
        LinksPath: linksPath,
        OutputDirectory: outDirectory,
        ModelIdFilter: options.IdFilter,
        IndexedPayloads: payloadLookup.IndexedPayloads,
        CopiedArchivesScanned: payloadLookup.CopiedArchivesScanned,
        LiveFallbackArchivesScanned: payloadLookup.LiveArchivesScanned,
        UniqueTextureLinks: links.Count,
        Attempted: attempted,
        Written: written,
        WrittenFromCopiedArchives: writtenFromCopied,
        WrittenFromLiveArchives: writtenFromLive,
        MissingFromCopiedArchives: missingFromCopied,
        MissingFromSelectedSources: missingFromSelectedSources,
        TypeMismatches: typeMismatch,
        Failed: failed,
        Samples: samples);
    var reportPath = Path.Combine(outDirectory, "linked-texture-extract-report.json");
    File.WriteAllText(reportPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Indexed payload IDs: {payloadLookup.IndexedPayloads:N0}");
    Console.WriteLine($"Copied archives scanned: {payloadLookup.CopiedArchivesScanned:N0}");
    Console.WriteLine($"Live fallback archives scanned: {payloadLookup.LiveArchivesScanned:N0}");
    Console.WriteLine($"Links: {links.Count:N0}");
    Console.WriteLine($"Attempted: {attempted:N0}");
    Console.WriteLine($"Written: {written:N0}");
    Console.WriteLine($"Written from copied archives: {writtenFromCopied:N0}");
    Console.WriteLine($"Written from live fallback: {writtenFromLive:N0}");
    Console.WriteLine($"Missing from copied archives: {missingFromCopied:N0}");
    Console.WriteLine($"Missing from selected sources: {missingFromSelectedSources:N0}");
    Console.WriteLine($"Type mismatches: {typeMismatch:N0}");
    Console.WriteLine($"Failed: {failed:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outDirectory)}");
    Console.WriteLine($"Report: {DisplayPath(options, reportPath)}");
    return failed == 0 ? 0 : 2;
  }

  private static int ExtractNifBundle(AppOptions options)
  {
    if (string.IsNullOrWhiteSpace(options.IdFilter))
    {
      Console.Error.WriteLine("ERROR: extract-nif-bundle requires --id <nif asset id>.");
      return 1;
    }

    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var outDirectory = Path.GetFullPath(options.OutDirectory ?? Path.Combine(rootDirectory, "..", "Extracted", "nif-bundles", options.IdFilter));
    var linksPath = string.IsNullOrWhiteSpace(options.InputPath)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", "nif-texture-links.jsonl"))
        : Path.GetFullPath(options.InputPath);
    if (!File.Exists(linksPath))
    {
      Console.Error.WriteLine($"ERROR: link JSONL does not exist: {DisplayPath(options, linksPath)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var modelId = options.IdFilter.Trim().ToLowerInvariant();
    var links = ReadJsonLines<NifTextureLinkRecord>(linksPath)
        .Where(l => string.Equals(l.ModelIdPrefix, modelId, StringComparison.OrdinalIgnoreCase))
        .GroupBy(static l => l.TextureIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Select(static g => g.OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase).First())
        .OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase)
        .ToList();
    var payloadLookup = BuildPayloadLookup(rootDirectory, options, links.Select(static l => l.TextureIdPrefix).Append(modelId));

    NifBundleExtractReport report;
    try
    {
      report = WriteNifBundle(rootDirectory, linksPath, outDirectory, modelId, links, lookup, payloadLookup, options);
    }
    catch (InvalidOperationException ex)
    {
      Console.Error.WriteLine($"ERROR: {ex.Message}");
      return 1;
    }

    Console.WriteLine($"Model: {modelId}");
    Console.WriteLine($"NIF version: {report.Model.NifVersion}");
    Console.WriteLine($"Indexed payload IDs: {report.IndexedPayloads:N0}");
    Console.WriteLine($"Copied archives scanned: {report.CopiedArchivesScanned:N0}");
    Console.WriteLine($"Live fallback archives scanned: {report.LiveFallbackArchivesScanned:N0}");
    Console.WriteLine($"Texture links: {report.UniqueTextureLinks:N0}");
    Console.WriteLine($"Textures written: {report.TextureWritten:N0}");
    Console.WriteLine($"Textures written from copied archives: {report.TextureWrittenFromCopiedArchives:N0}");
    Console.WriteLine($"Textures written from live fallback: {report.TextureWrittenFromLiveArchives:N0}");
    Console.WriteLine($"Textures missing from copied archives: {report.TextureMissingFromCopiedArchives:N0}");
    Console.WriteLine($"Textures missing from selected sources: {report.TextureMissingFromSelectedSources:N0}");
    Console.WriteLine($"Texture type mismatches: {report.TextureTypeMismatches:N0}");
    Console.WriteLine($"Texture failures: {report.TextureFailed:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outDirectory)}");
    Console.WriteLine($"Report: {DisplayPath(options, Path.Combine(outDirectory, "nif-bundle-report.json"))}");
    return report.TextureFailed == 0 ? 0 : 2;
  }

  private static int ExtractNifBundles(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var outDirectory = Path.GetFullPath(options.OutDirectory ?? Path.Combine(rootDirectory, "..", "Extracted", "nif-bundles-batch"));
    var linksPath = string.IsNullOrWhiteSpace(options.InputPath)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", "nif-texture-links.jsonl"))
        : Path.GetFullPath(options.InputPath);
    if (!File.Exists(linksPath))
    {
      Console.Error.WriteLine($"ERROR: link JSONL does not exist: {DisplayPath(options, linksPath)}");
      return 1;
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var requestedLimit = options.Limit > 0 ? options.Limit : 10;
    var allLinks = ReadJsonLines<NifTextureLinkRecord>(linksPath).ToList();
    var selected = allLinks
        .Where(l => string.IsNullOrWhiteSpace(options.IdFilter) || string.Equals(l.ModelIdPrefix, options.IdFilter, StringComparison.OrdinalIgnoreCase))
        .GroupBy(static l => l.ModelIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Select(static g =>
        {
          var uniqueLinks = g
                  .GroupBy(static l => l.TextureIdPrefix, StringComparer.OrdinalIgnoreCase)
                  .Select(static textureGroup => textureGroup.OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase).First())
                  .OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase)
                  .ToList();
          return new NifBundleBatchSelection(g.Key, uniqueLinks, uniqueLinks.Count, g.Count());
        })
        .OrderByDescending(static s => s.UniqueTextureCount)
        .ThenByDescending(static s => s.LinkCount)
        .ThenBy(static s => s.ModelIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Take(requestedLimit)
        .ToList();

    if (selected.Count == 0)
    {
      Console.Error.WriteLine("ERROR: no NIF bundle candidates matched the selected filters.");
      return 1;
    }

    var targetIds = selected
        .Select(static s => s.ModelIdPrefix)
        .Concat(selected.SelectMany(static s => s.Links.Select(static l => l.TextureIdPrefix)));
    var payloadLookup = BuildPayloadLookup(rootDirectory, options, targetIds);
    Directory.CreateDirectory(outDirectory);

    var samples = new List<NifBundleBatchExtractSample>();
    var modelAttempted = 0;
    var modelWritten = 0;
    var completeBundles = 0;
    var failedBundles = 0;

    foreach (var selection in selected)
    {
      modelAttempted++;
      var bundleOutDirectory = Path.Combine(outDirectory, selection.ModelIdPrefix);
      try
      {
        var bundleReport = WriteNifBundle(rootDirectory, linksPath, bundleOutDirectory, selection.ModelIdPrefix, selection.Links, lookup, payloadLookup, options);
        modelWritten++;
        var isComplete = bundleReport.TextureMissingFromSelectedSources == 0 &&
            bundleReport.TextureTypeMismatches == 0 &&
            bundleReport.TextureFailed == 0;
        if (isComplete)
        {
          completeBundles++;
        }

        samples.Add(new NifBundleBatchExtractSample(
            ModelIdPrefix: selection.ModelIdPrefix,
            RelativeOutputDirectory: Path.GetRelativePath(outDirectory, bundleOutDirectory),
            ModelArchiveName: bundleReport.Model.ArchiveName,
            ModelSourceKind: bundleReport.Model.SourceKind,
            UniqueTextureLinks: bundleReport.UniqueTextureLinks,
            TexturesWritten: bundleReport.TextureWritten,
            TexturesWrittenFromCopiedArchives: bundleReport.TextureWrittenFromCopiedArchives,
            TexturesWrittenFromLiveArchives: bundleReport.TextureWrittenFromLiveArchives,
            TexturesMissingFromCopiedArchives: bundleReport.TextureMissingFromCopiedArchives,
            TexturesMissingFromSelectedSources: bundleReport.TextureMissingFromSelectedSources,
            TextureTypeMismatches: bundleReport.TextureTypeMismatches,
            TextureFailures: bundleReport.TextureFailed,
            IsComplete: isComplete,
            Error: null));
      }
      catch (Exception ex) when (ex is InvalidOperationException or IOException or InvalidDataException)
      {
        failedBundles++;
        samples.Add(new NifBundleBatchExtractSample(
            ModelIdPrefix: selection.ModelIdPrefix,
            RelativeOutputDirectory: Path.GetRelativePath(outDirectory, bundleOutDirectory),
            ModelArchiveName: null,
            ModelSourceKind: null,
            UniqueTextureLinks: selection.UniqueTextureCount,
            TexturesWritten: 0,
            TexturesWrittenFromCopiedArchives: 0,
            TexturesWrittenFromLiveArchives: 0,
            TexturesMissingFromCopiedArchives: 0,
            TexturesMissingFromSelectedSources: selection.UniqueTextureCount,
            TextureTypeMismatches: 0,
            TextureFailures: 1,
            IsComplete: false,
            Error: ex.Message));
      }
    }

    var report = new NifBundleBatchExtractReport(
        RootDirectory: rootDirectory,
        LinksPath: linksPath,
        OutputDirectory: outDirectory,
        RequestedModelLimit: requestedLimit,
        SelectedModels: selected.Count,
        IndexedPayloads: payloadLookup.IndexedPayloads,
        CopiedArchivesScanned: payloadLookup.CopiedArchivesScanned,
        LiveFallbackArchivesScanned: payloadLookup.LiveArchivesScanned,
        ModelsAttempted: modelAttempted,
        ModelsWritten: modelWritten,
        CompleteBundles: completeBundles,
        FailedBundles: failedBundles,
        TotalTextureLinks: samples.Sum(static s => s.UniqueTextureLinks),
        TotalTexturesWritten: samples.Sum(static s => s.TexturesWritten),
        TotalTexturesWrittenFromCopiedArchives: samples.Sum(static s => s.TexturesWrittenFromCopiedArchives),
        TotalTexturesWrittenFromLiveArchives: samples.Sum(static s => s.TexturesWrittenFromLiveArchives),
        TotalTexturesMissingFromSelectedSources: samples.Sum(static s => s.TexturesMissingFromSelectedSources),
        Samples: samples);

    var reportPath = Path.Combine(outDirectory, "nif-bundles-report.json");
    File.WriteAllText(reportPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Selected models: {selected.Count:N0}");
    Console.WriteLine($"Indexed payload IDs: {payloadLookup.IndexedPayloads:N0}");
    Console.WriteLine($"Copied archives scanned: {payloadLookup.CopiedArchivesScanned:N0}");
    Console.WriteLine($"Live fallback archives scanned: {payloadLookup.LiveArchivesScanned:N0}");
    Console.WriteLine($"Models attempted: {modelAttempted:N0}");
    Console.WriteLine($"Models written: {modelWritten:N0}");
    Console.WriteLine($"Complete bundles: {completeBundles:N0}");
    Console.WriteLine($"Failed bundles: {failedBundles:N0}");
    Console.WriteLine($"Texture links: {report.TotalTextureLinks:N0}");
    Console.WriteLine($"Textures written: {report.TotalTexturesWritten:N0}");
    Console.WriteLine($"Textures written from copied archives: {report.TotalTexturesWrittenFromCopiedArchives:N0}");
    Console.WriteLine($"Textures written from live fallback: {report.TotalTexturesWrittenFromLiveArchives:N0}");
    Console.WriteLine($"Textures missing from selected sources: {report.TotalTexturesMissingFromSelectedSources:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outDirectory)}");
    Console.WriteLine($"Report: {DisplayPath(options, reportPath)}");
    return failedBundles == 0 ? 0 : 2;
  }

  private static NifBundleExtractReport WriteNifBundle(
      string rootDirectory,
      string linksPath,
      string outDirectory,
      string modelId,
      List<NifTextureLinkRecord> links,
      ManifestLookup lookup,
      ArchivePayloadLookup payloadLookup,
      AppOptions options)
  {
    if (!lookup.Table1ById.TryGetValue(modelId, out var modelManifestEntry))
    {
      throw new InvalidOperationException($"model ID was not found in manifest Table 1: {modelId}");
    }

    var foundModel = payloadLookup.Find(modelId, options.Lzma2Mode);
    if (foundModel is null)
    {
      throw new InvalidOperationException($"model payload was not found in selected archive sources: {modelId}");
    }

    var modelDetected = DetectFileType(foundModel.Payload);
    if (modelDetected.Extension != "nif")
    {
      throw new InvalidOperationException($"model payload is detected as '{modelDetected.Extension}', not 'nif'.");
    }

    Directory.CreateDirectory(outDirectory);
    var modelDirectory = Path.Combine(outDirectory, "model");
    Directory.CreateDirectory(modelDirectory);
    var modelFileName = $"{foundModel.EntryIndex:D6}_m{modelManifestEntry.Index:D6}_fnv{modelManifestEntry.FilenameFnv1Hash:x8}_pak{modelManifestEntry.PakIndex:D4}_off{modelManifestEntry.PakOffset}_{modelId}.nif";
    var modelPath = Path.Combine(modelDirectory, modelFileName);
    File.WriteAllBytes(modelPath, foundModel.Payload);
    var modelHeader = ParseNifHeader(foundModel.Payload);

    var textureRoot = Path.Combine(outDirectory, "textures");
    Directory.CreateDirectory(textureRoot);
    var samples = new List<LinkedTextureExtractSample>();
    var attempted = 0;
    var written = 0;
    var writtenFromCopied = 0;
    var writtenFromLive = 0;
    var missingFromCopied = 0;
    var missingFromSelectedSources = 0;
    var typeMismatch = 0;
    var failed = 0;

    foreach (var link in links)
    {
      attempted++;
      try
      {
        var found = payloadLookup.Find(link.TextureIdPrefix, options.Lzma2Mode);
        if (found is null)
        {
          missingFromCopied++;
          missingFromSelectedSources++;
          continue;
        }

        var foundInLiveFallback = string.Equals(found.SourceKind, "live", StringComparison.OrdinalIgnoreCase);
        if (foundInLiveFallback)
        {
          missingFromCopied++;
        }

        var detected = DetectFileType(found.Payload);
        if (!RecoveredNameMatchesDetectedType(link.Candidate, detected.Extension))
        {
          typeMismatch++;
          continue;
        }

        var outputPath = BuildRecoveredOutputPath(textureRoot, link.Candidate, link.TextureIdPrefix, detected.Extension);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.WriteAllBytes(outputPath, found.Payload);
        written++;
        if (foundInLiveFallback)
        {
          writtenFromLive++;
        }
        else
        {
          writtenFromCopied++;
        }

        if (samples.Count < 100)
        {
          samples.Add(new LinkedTextureExtractSample(
              ModelIdPrefix: link.ModelIdPrefix,
              TextureIdPrefix: link.TextureIdPrefix,
              Candidate: link.Candidate,
              ArchiveName: found.ArchiveName,
              EntryIndex: found.EntryIndex,
              SourceKind: found.SourceKind,
              Type: detected.Extension,
              Width: detected.Width,
              Height: detected.Height,
              Format: detected.Format,
              RelativePath: Path.GetRelativePath(outDirectory, outputPath)));
        }
      }
      catch
      {
        failed++;
      }
    }

    var report = new NifBundleExtractReport(
        RootDirectory: rootDirectory,
        LinksPath: linksPath,
        OutputDirectory: outDirectory,
        Model: new NifBundleModelSample(
            IdPrefix: modelId,
            ArchiveName: foundModel.ArchiveName,
            EntryIndex: foundModel.EntryIndex,
            ManifestEntryIndex: modelManifestEntry.Index,
            FilenameFnv1Hash: modelManifestEntry.FilenameFnv1Hash,
            PakIndex: modelManifestEntry.PakIndex,
            PakOffset: modelManifestEntry.PakOffset,
            NifVersion: modelHeader.VersionText,
            BlockCount: modelHeader.BlockCount,
            StringCount: modelHeader.StringCount,
            SourceKind: foundModel.SourceKind,
            RelativePath: Path.GetRelativePath(outDirectory, modelPath)),
        IndexedPayloads: payloadLookup.IndexedPayloads,
        CopiedArchivesScanned: payloadLookup.CopiedArchivesScanned,
        LiveFallbackArchivesScanned: payloadLookup.LiveArchivesScanned,
        UniqueTextureLinks: links.Count,
        TextureAttempted: attempted,
        TextureWritten: written,
        TextureWrittenFromCopiedArchives: writtenFromCopied,
        TextureWrittenFromLiveArchives: writtenFromLive,
        TextureMissingFromCopiedArchives: missingFromCopied,
        TextureMissingFromSelectedSources: missingFromSelectedSources,
        TextureTypeMismatches: typeMismatch,
        TextureFailed: failed,
        Textures: samples);
    var reportPath = Path.Combine(outDirectory, "nif-bundle-report.json");
    File.WriteAllText(reportPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);
    return report;
  }

  private static int InventoryNifBundles(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var linksPath = string.IsNullOrWhiteSpace(options.InputPath)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", "nif-texture-links.jsonl"))
        : Path.GetFullPath(options.InputPath);
    if (!File.Exists(linksPath))
    {
      Console.Error.WriteLine($"ERROR: link JSONL does not exist: {DisplayPath(options, linksPath)}");
      return 1;
    }

    var copiedIds = ReadCopiedArchiveIds(rootDirectory);
    var links = ReadJsonLines<NifTextureLinkRecord>(linksPath).ToList();
    var samples = links
        .GroupBy(static l => l.ModelIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Select(g =>
        {
          var orderedLinks = g.OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase).ToList();
          var uniqueTextureIds = orderedLinks.Select(static l => l.TextureIdPrefix).Distinct(StringComparer.OrdinalIgnoreCase).ToList();
          var presentTextureIds = uniqueTextureIds.Where(copiedIds.Contains).ToList();
          var missingTextureIds = uniqueTextureIds.Where(id => !copiedIds.Contains(id)).ToList();
          return new NifBundleInventorySample(
                  ModelIdPrefix: g.Key,
                  ModelArchiveName: orderedLinks[0].ModelArchiveName,
                  ModelEntryIndex: orderedLinks[0].ModelEntryIndex,
                  ModelManifestEntryIndex: orderedLinks[0].ModelManifestEntryIndex,
                  ModelPakIndex: orderedLinks[0].ModelPakIndex,
                  ModelPresentInCopiedArchives: copiedIds.Contains(g.Key),
                  LinkCount: orderedLinks.Count,
                  UniqueTextureCount: uniqueTextureIds.Count,
                  PresentTextureCount: presentTextureIds.Count,
                  MissingTextureCount: missingTextureIds.Count,
                  IsComplete: copiedIds.Contains(g.Key) && missingTextureIds.Count == 0,
                  PresentTextureSamples: orderedLinks
                      .Where(l => copiedIds.Contains(l.TextureIdPrefix))
                      .Select(static l => l.Candidate)
                      .Distinct(StringComparer.OrdinalIgnoreCase)
                      .Take(10)
                      .ToList(),
                  MissingTextureSamples: orderedLinks
                      .Where(l => !copiedIds.Contains(l.TextureIdPrefix))
                      .Select(static l => l.Candidate)
                      .Distinct(StringComparer.OrdinalIgnoreCase)
                      .Take(10)
                      .ToList());
        })
        .OrderByDescending(static s => s.IsComplete)
        .ThenByDescending(static s => s.PresentTextureCount)
        .ThenBy(static s => s.ModelArchiveName, StringComparer.OrdinalIgnoreCase)
        .ThenBy(static s => s.ModelEntryIndex)
        .ToList();

    var complete = samples.Count(static s => s.IsComplete);
    var modelPresent = samples.Count(static s => s.ModelPresentInCopiedArchives);
    var report = new NifBundleInventoryReport(
        RootDirectory: rootDirectory,
        LinksPath: linksPath,
        CopiedAssetIds: copiedIds.Count,
        GraphLinks: links.Count,
        GraphModels: samples.Count,
        ModelsPresentInCopiedArchives: modelPresent,
        CompleteBundles: complete,
        IncompleteBundles: samples.Count - complete,
        TotalUniqueTextureRefs: samples.Sum(static s => s.UniqueTextureCount),
        PresentTextureRefs: samples.Sum(static s => s.PresentTextureCount),
        MissingTextureRefs: samples.Sum(static s => s.MissingTextureCount),
        Samples: options.Limit > 0 ? samples.Take(options.Limit).ToList() : samples);

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-bundle-inventory.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Graph links: {links.Count:N0}");
    Console.WriteLine($"Graph models: {samples.Count:N0}");
    Console.WriteLine($"Copied asset IDs: {copiedIds.Count:N0}");
    Console.WriteLine($"Models present in copied archives: {modelPresent:N0}");
    Console.WriteLine($"Complete bundles: {complete:N0}");
    Console.WriteLine($"Incomplete bundles: {samples.Count - complete:N0}");
    Console.WriteLine($"Present texture refs: {report.PresentTextureRefs:N0}");
    Console.WriteLine($"Missing texture refs: {report.MissingTextureRefs:N0}");
    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static int PlanNifBundleArchives(AppOptions options)
  {
    var rootDirectory = Path.GetFullPath(options.RootDirectory);
    var linksPath = string.IsNullOrWhiteSpace(options.InputPath)
        ? Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", "nif-texture-links.jsonl"))
        : Path.GetFullPath(options.InputPath);
    if (!File.Exists(linksPath))
    {
      Console.Error.WriteLine($"ERROR: link JSONL does not exist: {DisplayPath(options, linksPath)}");
      return 1;
    }

    var copiedIds = ReadCopiedArchiveIds(rootDirectory);
    var links = ReadJsonLines<NifTextureLinkRecord>(linksPath).ToList();
    var modelGroups = links
        .GroupBy(static l => l.ModelIdPrefix, StringComparer.OrdinalIgnoreCase)
        .Select(g =>
        {
          var orderedLinks = g.OrderBy(static l => l.Candidate, StringComparer.OrdinalIgnoreCase).ToList();
          var uniqueTextureIds = orderedLinks.Select(static l => l.TextureIdPrefix).Distinct(StringComparer.OrdinalIgnoreCase).ToHashSet(StringComparer.OrdinalIgnoreCase);
          var missingTextureIds = uniqueTextureIds.Where(id => !copiedIds.Contains(id)).ToHashSet(StringComparer.OrdinalIgnoreCase);
          return new NifBundleArchiveModelState(
                  ModelIdPrefix: g.Key,
                  IsModelPresentInCopiedArchives: copiedIds.Contains(g.Key),
                  MissingTextureIds: missingTextureIds,
                  CandidateSamples: orderedLinks
                      .Where(l => missingTextureIds.Contains(l.TextureIdPrefix))
                      .Select(static l => l.Candidate)
                      .Distinct(StringComparer.OrdinalIgnoreCase)
                      .Take(10)
                      .ToList());
        })
        .ToList();

    var missingTextureIds = modelGroups
        .SelectMany(static m => m.MissingTextureIds)
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .ToHashSet(StringComparer.OrdinalIgnoreCase);
    var textureLinkCounts = links
        .Where(l => missingTextureIds.Contains(l.TextureIdPrefix))
        .GroupBy(static l => l.TextureIdPrefix, StringComparer.OrdinalIgnoreCase)
        .ToDictionary(static g => g.Key, static g => g.Count(), StringComparer.OrdinalIgnoreCase);
    var textureCandidates = links
        .Where(l => missingTextureIds.Contains(l.TextureIdPrefix))
        .GroupBy(static l => l.TextureIdPrefix, StringComparer.OrdinalIgnoreCase)
        .ToDictionary(
            static g => g.Key,
            static g => g.Select(static l => l.Candidate).Distinct(StringComparer.OrdinalIgnoreCase).OrderBy(static c => c, StringComparer.OrdinalIgnoreCase).ToList(),
            StringComparer.OrdinalIgnoreCase);

    var scanRoot = Path.GetFullPath(string.IsNullOrWhiteSpace(options.LiveRoot) ? rootDirectory : options.LiveRoot);
    var liveAssetsDirectory = ResolveAssetsDirectory(scanRoot);
    if (!Directory.Exists(liveAssetsDirectory))
    {
      Console.Error.WriteLine($"ERROR: live/candidate assets directory does not exist: {DisplayPath(options, liveAssetsDirectory)}");
      return 1;
    }

    var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);
    var archiveToMissingTextureIds = new Dictionary<string, HashSet<string>>(StringComparer.OrdinalIgnoreCase);
    var missingTextureToArchiveNames = new Dictionary<string, List<string>>(StringComparer.OrdinalIgnoreCase);
    var archivesScanned = 0;
    var entriesScanned = 0;
    var matchedEntries = 0;

    foreach (var archivePath in Directory.EnumerateFiles(liveAssetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (archiveFilter is not null && !string.Equals(archiveName, archiveFilter, StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      archivesScanned++;
      foreach (var entry in entries)
      {
        if (entry.IsNull)
        {
          continue;
        }

        entriesScanned++;
        if (!missingTextureIds.Contains(entry.IdPrefix))
        {
          continue;
        }

        matchedEntries++;
        if (!archiveToMissingTextureIds.TryGetValue(archiveName, out var archiveTextureIds))
        {
          archiveTextureIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
          archiveToMissingTextureIds.Add(archiveName, archiveTextureIds);
        }

        archiveTextureIds.Add(entry.IdPrefix);
        if (!missingTextureToArchiveNames.TryGetValue(entry.IdPrefix, out var archiveNames))
        {
          archiveNames = [];
          missingTextureToArchiveNames.Add(entry.IdPrefix, archiveNames);
        }

        if (!archiveNames.Contains(archiveName, StringComparer.OrdinalIgnoreCase))
        {
          archiveNames.Add(archiveName);
        }
      }
    }

    var foundTextureIds = missingTextureToArchiveNames.Keys.ToHashSet(StringComparer.OrdinalIgnoreCase);
    var notFoundTextureIds = missingTextureIds.Where(id => !foundTextureIds.Contains(id)).OrderBy(static id => id, StringComparer.OrdinalIgnoreCase).ToList();
    var recommendations = archiveToMissingTextureIds
        .Select(kvp =>
        {
          var archiveName = kvp.Key;
          var archiveTextureIds = kvp.Value;
          var affectedModels = modelGroups.Count(m => m.MissingTextureIds.Overlaps(archiveTextureIds));
          var completesBundlesAlone = modelGroups.Count(m => m.IsModelPresentInCopiedArchives && m.MissingTextureIds.Count > 0 && m.MissingTextureIds.IsSubsetOf(archiveTextureIds));
          var sampleNames = archiveTextureIds
                  .SelectMany(id => textureCandidates.TryGetValue(id, out var candidates) ? candidates : [])
                  .Distinct(StringComparer.OrdinalIgnoreCase)
                  .OrderBy(static c => c, StringComparer.OrdinalIgnoreCase)
                  .Take(10)
                  .ToList();

          return new NifBundleArchiveRecommendation(
                  ArchiveName: archiveName,
                  MissingTextureAssets: archiveTextureIds.Count,
                  MissingTextureLinks: archiveTextureIds.Sum(id => textureLinkCounts.TryGetValue(id, out var count) ? count : 0),
                  AffectedModels: affectedModels,
                  CompletesBundlesAlone: completesBundlesAlone,
                  SampleTextureIds: archiveTextureIds.OrderBy(static id => id, StringComparer.OrdinalIgnoreCase).Take(10).ToList(),
                  SampleTextureNames: sampleNames);
        })
        .OrderByDescending(static r => r.CompletesBundlesAlone)
        .ThenByDescending(static r => r.MissingTextureAssets)
        .ThenByDescending(static r => r.MissingTextureLinks)
        .ThenBy(static r => r.ArchiveName, StringComparer.OrdinalIgnoreCase)
        .ToList();

    var greedyPlan = BuildNifBundleArchiveGreedyPlan(modelGroups, archiveToMissingTextureIds, textureCandidates, options.Limit > 0 ? options.Limit : 25);
    var report = new NifBundleArchivePlanReport(
        RootDirectory: rootDirectory,
        LinksPath: linksPath,
        LiveRoot: scanRoot,
        LiveAssetsDirectory: liveAssetsDirectory,
        ArchivesScanned: archivesScanned,
        ArchiveEntriesScanned: entriesScanned,
        MatchingArchiveEntries: matchedEntries,
        CopiedAssetIds: copiedIds.Count,
        GraphLinks: links.Count,
        GraphModels: modelGroups.Count,
        ModelsPresentInCopiedArchives: modelGroups.Count(static m => m.IsModelPresentInCopiedArchives),
        MissingTextureAssetIds: missingTextureIds.Count,
        MissingTextureAssetIdsFoundInLive: foundTextureIds.Count,
        MissingTextureAssetIdsNotFoundInLive: notFoundTextureIds.Count,
        ArchiveRecommendations: recommendations,
        GreedyPlan: greedyPlan,
        MissingTextureIdsNotFoundInLiveSamples: notFoundTextureIds.Take(50).ToList());

    var outPath = ResolveOutputPath(rootDirectory, options.OutDirectory, "nif-bundle-archive-plan.json");
    Directory.CreateDirectory(Path.GetDirectoryName(outPath)!);
    File.WriteAllText(outPath, JsonSerializer.Serialize(report, JsonOptions(options.RedactPaths)) + Environment.NewLine, Encoding.UTF8);

    Console.WriteLine($"Graph links: {links.Count:N0}");
    Console.WriteLine($"Graph models: {modelGroups.Count:N0}");
    Console.WriteLine($"Copied asset IDs: {copiedIds.Count:N0}");
    Console.WriteLine($"Missing texture assets: {missingTextureIds.Count:N0}");
    Console.WriteLine($"Live/candidate assets directory: {DisplayPath(options, liveAssetsDirectory)}");
    Console.WriteLine($"Archives scanned: {archivesScanned:N0}");
    Console.WriteLine($"Found missing texture assets in live archives: {foundTextureIds.Count:N0}");
    Console.WriteLine($"Missing texture assets not found in live archives: {notFoundTextureIds.Count:N0}");
    Console.WriteLine($"Archive recommendations: {recommendations.Count:N0}");
    if (recommendations.Count > 0)
    {
      var top = recommendations[0];
      Console.WriteLine($"Top archive: {top.ArchiveName} covers {top.MissingTextureAssets:N0} missing texture assets, affects {top.AffectedModels:N0} models, completes {top.CompletesBundlesAlone:N0} bundles alone");
    }

    if (greedyPlan.Count > 0)
    {
      var firstStep = greedyPlan[0];
      Console.WriteLine($"Greedy first step: {firstStep.ArchiveName} adds {firstStep.NewTextureAssets:N0} texture assets and completes {firstStep.NewlyCompletedBundles:N0} bundles");
      Console.WriteLine($"Greedy selected archives: {greedyPlan.Count:N0}; cumulative completed bundles: {greedyPlan[^1].CumulativeCompletedBundles:N0}");
    }

    Console.WriteLine($"Output: {DisplayPath(options, outPath)}");
    return 0;
  }

  private static List<NifBundleArchiveGreedyStep> BuildNifBundleArchiveGreedyPlan(
      List<NifBundleArchiveModelState> modelGroups,
      Dictionary<string, HashSet<string>> archiveToMissingTextureIds,
      Dictionary<string, List<string>> textureCandidates,
      int maxSteps)
  {
    var remainingArchives = archiveToMissingTextureIds.Keys.ToHashSet(StringComparer.OrdinalIgnoreCase);
    var selectedTextureIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var completedModels = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var eligibleMissingModels = modelGroups
        .Where(static m => m.IsModelPresentInCopiedArchives && m.MissingTextureIds.Count > 0)
        .ToList();
    var plan = new List<NifBundleArchiveGreedyStep>();

    while (remainingArchives.Count > 0 && plan.Count < maxSteps)
    {
      var best = remainingArchives
          .Select(archiveName =>
          {
            var newTextureIds = archiveToMissingTextureIds[archiveName]
                      .Where(id => !selectedTextureIds.Contains(id))
                      .ToHashSet(StringComparer.OrdinalIgnoreCase);
            var newlyCompleted = eligibleMissingModels.Count(m =>
                      !completedModels.Contains(m.ModelIdPrefix) &&
                      m.MissingTextureIds.All(id => selectedTextureIds.Contains(id) || newTextureIds.Contains(id)));
            return new { ArchiveName = archiveName, NewTextureIds = newTextureIds, NewlyCompleted = newlyCompleted };
          })
          .Where(static c => c.NewTextureIds.Count > 0)
          .OrderByDescending(static c => c.NewlyCompleted)
          .ThenByDescending(static c => c.NewTextureIds.Count)
          .ThenBy(static c => c.ArchiveName, StringComparer.OrdinalIgnoreCase)
          .FirstOrDefault();

      if (best is null)
      {
        break;
      }

      foreach (var textureId in best.NewTextureIds)
      {
        selectedTextureIds.Add(textureId);
      }

      foreach (var model in eligibleMissingModels)
      {
        if (!completedModels.Contains(model.ModelIdPrefix) &&
            model.MissingTextureIds.All(selectedTextureIds.Contains))
        {
          completedModels.Add(model.ModelIdPrefix);
        }
      }

      var sampleNames = best.NewTextureIds
          .SelectMany(id => textureCandidates.TryGetValue(id, out var candidates) ? candidates : [])
          .Distinct(StringComparer.OrdinalIgnoreCase)
          .OrderBy(static c => c, StringComparer.OrdinalIgnoreCase)
          .Take(10)
          .ToList();
      plan.Add(new NifBundleArchiveGreedyStep(
          Step: plan.Count + 1,
          ArchiveName: best.ArchiveName,
          NewTextureAssets: best.NewTextureIds.Count,
          NewlyCompletedBundles: best.NewlyCompleted,
          CumulativeCompletedBundles: completedModels.Count,
          RemainingIncompleteBundles: eligibleMissingModels.Count - completedModels.Count,
          SampleTextureNames: sampleNames));
      remainingArchives.Remove(best.ArchiveName);
    }

    return plan;
  }

  private static (byte[] Payload, BinaryAssetSource Source) LoadPayloadForProbe(AppOptions options, string rootDirectory)
  {
    if (!string.IsNullOrWhiteSpace(options.InputPath))
    {
      var inputPath = Path.GetFullPath(options.InputPath);
      return (File.ReadAllBytes(inputPath), new BinaryAssetSource(InputPath: inputPath));
    }

    var manifestPath = ResolveManifestPath(rootDirectory, options.ManifestPath);
    var lookup = ReadManifestLookup(manifestPath);
    var target = ResolveTargetEntry(options, lookup);
    var found = FindPayloadForId(rootDirectory, lookup, target.IdPrefix, options)
        ?? throw new InvalidOperationException($"target asset {target.IdPrefix} was not found in selected archive sources.");

    return (found.Payload, new BinaryAssetSource(
        ArchiveName: found.ArchiveName,
        EntryIndex: found.EntryIndex,
        SourceKind: found.SourceKind,
        IdPrefix: target.IdPrefix,
        ManifestEntryIndex: target.Index,
        FilenameFnv1Hash: target.FilenameFnv1Hash,
        PakIndex: target.PakIndex,
        PakOffset: target.PakOffset));
  }

  private static NifHeaderInfo ParseNifHeader(byte[] payload)
  {
    var warnings = new List<string>();
    var data = payload.AsSpan();
    var searchLength = Math.Min(data.Length, 256);
    var newline = data[..searchLength].IndexOf((byte)'\n');

    static NifHeaderInfo InvalidHeader(string headerString, int parsedBytes, string warning)
    {
      return new NifHeaderInfo(
          HeaderString: headerString,
          Version: null,
          VersionHex: null,
          VersionText: "unknown",
          Endian: null,
          IsLittleEndian: false,
          UserVersion: null,
          BlockCount: null,
          BlockTypeCount: null,
          HeaderBytesParsed: parsedBytes,
          BlockDataOffset: null,
          TotalBlockDataSize: null,
          MinBlockDataSize: null,
          MaxBlockDataSize: null,
          RemainingAfterBlockDataOffset: null,
          BlockSizePayloadDelta: null,
          StringCount: null,
          MaxStringLength: null,
          GroupCount: null,
          BlockTypes: [],
          Strings: [],
          References: [],
          Blocks: [],
          Warnings: [warning]);
    }

    if (newline < 0)
    {
      return InvalidHeader("", 0, "NIF header line terminator was not found in first 256 bytes.");
    }

    var headerString = Encoding.ASCII.GetString(data[..newline]).TrimEnd('\r', '\0');
    var offset = newline + 1;
    if (offset + 15 > data.Length)
    {
      return InvalidHeader(headerString, offset, "NIF header is truncated before version/endian/block-count fields.");
    }

    var version = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
    offset += 4;
    var endian = data[offset++];
    var isLittleEndian = endian == 1;
    if (!isLittleEndian)
    {
      warnings.Add($"Unexpected endian marker {endian}; parser currently assumes little-endian RIFT samples.");
    }

    var userVersion = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
    offset += 4;
    var blockCount = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
    offset += 4;
    var blockTypeCount = BinaryPrimitives.ReadUInt16LittleEndian(data.Slice(offset, 2));
    offset += 2;

    var blockTypeNames = new List<NifBlockTypeNameInfo>(blockTypeCount);
    for (var i = 0; i < blockTypeCount; i++)
    {
      if (offset + 4 > data.Length)
      {
        warnings.Add($"Block type table ended before length field for type {i}.");
        break;
      }

      var length = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
      offset += 4;
      if (length > 1024)
      {
        warnings.Add($"Block type {i} length {length} is implausibly large.");
        break;
      }

      if (offset + length > data.Length)
      {
        warnings.Add($"Block type {i} length {length} extends past payload end.");
        break;
      }

      var name = Encoding.ASCII.GetString(data.Slice(offset, checked((int)length)));
      offset += checked((int)length);
      blockTypeNames.Add(BuildNifBlockTypeNameInfo(i, name));
    }

    var usageCounts = new int[blockTypeNames.Count];
    var blockTypeIndices = new List<int>();
    var blockIndexTableParsed = false;
    if (blockCount > 1_000_000)
    {
      warnings.Add($"Block count {blockCount:N0} is too large for the lightweight NIF header probe.");
    }
    else if (blockTypeNames.Count == blockTypeCount)
    {
      var blockCountInt = checked((int)blockCount);
      var indexBytes = checked(blockCountInt * 2);
      if (offset + indexBytes <= data.Length)
      {
        var allIndicesValid = true;
        blockTypeIndices = new List<int>(blockCountInt);
        for (var i = 0; i < blockCountInt; i++)
        {
          var typeIndex = BinaryPrimitives.ReadUInt16LittleEndian(data.Slice(offset + (i * 2), 2));
          if (typeIndex >= usageCounts.Length)
          {
            allIndicesValid = false;
            warnings.Add($"Block {i} references out-of-range block type index {typeIndex}.");
            break;
          }

          blockTypeIndices.Add(typeIndex);
          usageCounts[typeIndex]++;
        }

        offset += indexBytes;
        if (!allIndicesValid)
        {
          usageCounts = new int[blockTypeNames.Count];
          blockTypeIndices.Clear();
        }
        else
        {
          blockIndexTableParsed = true;
        }
      }
      else
      {
        warnings.Add("NIF header ended before the block type index table.");
      }
    }

    ulong? totalBlockDataSize = null;
    uint? minBlockDataSize = null;
    uint? maxBlockDataSize = null;
    var blockSizes = new List<uint>();
    var blockSizeTableParsed = false;
    if (blockIndexTableParsed && blockCount <= 1_000_000)
    {
      var blockCountInt = checked((int)blockCount);
      var blockSizeBytes = checked(blockCountInt * 4);
      if (offset + blockSizeBytes <= data.Length)
      {
        ulong total = 0;
        uint min = uint.MaxValue;
        uint max = 0;
        blockSizes = new List<uint>(blockCountInt);
        for (var i = 0; i < blockCountInt; i++)
        {
          var blockSize = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset + (i * 4), 4));
          blockSizes.Add(blockSize);
          total += blockSize;
          min = Math.Min(min, blockSize);
          max = Math.Max(max, blockSize);
        }

        offset += blockSizeBytes;
        totalBlockDataSize = total;
        minBlockDataSize = blockCountInt > 0 ? min : 0;
        maxBlockDataSize = blockCountInt > 0 ? max : 0;
        blockSizeTableParsed = true;
      }
      else
      {
        warnings.Add("NIF header ended before the block size table.");
      }
    }
    else if (!blockIndexTableParsed)
    {
      warnings.Add("Skipping block size and string table parsing because the block type index table was not parsed.");
    }

    uint? stringCount = null;
    uint? maxStringLength = null;
    var strings = new List<NifStringInfo>();
    var references = new List<NifReferenceInfo>();
    if (blockSizeTableParsed && offset + 8 <= data.Length)
    {
      stringCount = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
      offset += 4;
      maxStringLength = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
      offset += 4;

      if (stringCount > 1_000_000)
      {
        warnings.Add($"NIF string count {stringCount:N0} is too large for the lightweight probe.");
        stringCount = null;
        maxStringLength = null;
      }
      else
      {
        for (var i = 0; i < stringCount; i++)
        {
          if (offset + 4 > data.Length)
          {
            warnings.Add($"String table ended before length field for string {i}.");
            break;
          }

          var length = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
          offset += 4;
          if (length > 1_000_000)
          {
            warnings.Add($"String {i} length {length:N0} is too large for the lightweight probe.");
            break;
          }

          if (offset + length > data.Length)
          {
            warnings.Add($"String {i} length {length:N0} extends past payload end.");
            break;
          }

          var value = DecodeNifString(data.Slice(offset, checked((int)length)));
          offset += checked((int)length);
          var stringInfo = new NifStringInfo(checked((int)i), value);
          strings.Add(stringInfo);
          references.AddRange(ExtractNifReferences(stringInfo));
        }
      }
    }
    else if (blockSizeTableParsed)
    {
      warnings.Add("NIF header ended before the string table count fields.");
    }

    uint? groupCount = null;
    if (blockSizeTableParsed && offset + 4 <= data.Length)
    {
      var candidateGroupCount = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset, 4));
      if (candidateGroupCount <= 1_000_000 && (ulong)offset + 4UL + (candidateGroupCount * 4UL) <= (ulong)data.Length)
      {
        groupCount = candidateGroupCount;
        offset += 4 + checked((int)(candidateGroupCount * 4));
      }
      else
      {
        warnings.Add($"NIF group count candidate {candidateGroupCount:N0} is implausible at offset {offset}.");
      }
    }

    var blockDataOffset = offset;
    var remainingAfterBlockDataOffset = data.Length - blockDataOffset;
    long? blockSizePayloadDelta = totalBlockDataSize is null
        ? null
        : remainingAfterBlockDataOffset - checked((long)totalBlockDataSize.Value);
    var blockTypes = blockTypeNames
        .Select(t => new NifBlockTypeInfo(
            Index: t.Index,
            Name: t.Name,
            DisplayName: t.DisplayName,
            NormalizedName: t.NormalizedName,
            DataStreamUsage: t.DataStreamUsage,
            DataStreamAccess: t.DataStreamAccess,
            UsageCount: t.Index < usageCounts.Length ? usageCounts[t.Index] : 0))
        .ToList();
    var blockInfos = BuildNifBlockInfos(data, blockDataOffset, blockTypeIndices, blockSizes, blockTypeNames, strings);

    references = references
        .DistinctBy(static r => (r.StringIndex, r.Value), EqualityComparer<(int, string)>.Default)
        .ToList();

    return new NifHeaderInfo(
        HeaderString: headerString,
        Version: version,
        VersionHex: $"0x{version:x8}",
        VersionText: FormatNifVersion(version),
        Endian: endian,
        IsLittleEndian: isLittleEndian,
        UserVersion: userVersion,
        BlockCount: blockCount,
        BlockTypeCount: blockTypeCount,
        HeaderBytesParsed: offset,
        BlockDataOffset: blockDataOffset,
        TotalBlockDataSize: totalBlockDataSize,
        MinBlockDataSize: minBlockDataSize,
        MaxBlockDataSize: maxBlockDataSize,
        RemainingAfterBlockDataOffset: remainingAfterBlockDataOffset,
        BlockSizePayloadDelta: blockSizePayloadDelta,
        StringCount: stringCount,
        MaxStringLength: maxStringLength,
        GroupCount: groupCount,
        BlockTypes: blockTypes,
        Strings: strings,
        References: references,
        Blocks: blockInfos,
        Warnings: warnings);
  }

  private static List<NifBlockInfo> BuildNifBlockInfos(
      ReadOnlySpan<byte> data,
      int blockDataOffset,
      List<int> blockTypeIndices,
      List<uint> blockSizes,
      List<NifBlockTypeNameInfo> blockTypeNames,
      List<NifStringInfo> strings)
  {
    var blockCount = Math.Min(blockTypeIndices.Count, blockSizes.Count);
    var blocks = new List<NifBlockInfo>(blockCount);
    var blockOffsets = new List<int>(blockCount);
    var offset = blockDataOffset;
    for (var i = 0; i < blockCount; i++)
    {
      blockOffsets.Add(offset);
      offset += checked((int)Math.Min(blockSizes[i], int.MaxValue));
      if (offset > data.Length)
      {
        break;
      }
    }

    offset = blockDataOffset;
    for (var i = 0; i < blockCount; i++)
    {
      var size = blockSizes[i];
      var safeSize = checked((int)Math.Min(size, (uint)Math.Max(0, data.Length - offset)));
      var payload = safeSize > 0 ? data.Slice(offset, safeSize) : ReadOnlySpan<byte>.Empty;
      var typeIndex = blockTypeIndices[i];
      var typeInfo = typeIndex >= 0 && typeIndex < blockTypeNames.Count
          ? blockTypeNames[typeIndex]
          : null;
      var typeName = typeInfo?.NormalizedName ?? $"type-index-{typeIndex}";
      var typeDisplayName = typeInfo?.DisplayName ?? typeName;
      var stringIndexCandidates = FindNifStringIndexCandidates(payload, strings.Count);
      var stringSamples = stringIndexCandidates
          .Take(8)
          .Select(index => strings[index].Value)
          .Distinct(StringComparer.OrdinalIgnoreCase)
          .Take(8)
          .ToList();

      blocks.Add(new NifBlockInfo(
          Index: i,
          TypeIndex: typeIndex,
          TypeName: typeName,
          TypeDisplayName: typeDisplayName,
          DataStreamUsage: typeInfo?.DataStreamUsage,
          DataStreamAccess: typeInfo?.DataStreamAccess,
          Size: size,
          DataOffset: offset,
          First16: ToHex(payload[..Math.Min(16, payload.Length)]),
          UInt32Prefix: ReadUInt32Prefix(payload, maxValues: 8),
          Float32Prefix: ReadFloat32Prefix(payload, maxValues: 8),
          StringIndexCandidates: stringIndexCandidates.Take(32).ToList(),
          StringSamples: stringSamples,
          DataStreamReferenceCandidates: FindNifDataStreamReferenceCandidates(data, payload, blockOffsets, blockTypeIndices, blockSizes, blockTypeNames, strings).Take(32).ToList()));
      offset += checked((int)Math.Min(size, int.MaxValue));
      if (offset > data.Length)
      {
        break;
      }
    }

    return blocks;
  }

  private static List<NifBlockReferenceCandidate> FindNifDataStreamReferenceCandidates(
      ReadOnlySpan<byte> data,
      ReadOnlySpan<byte> payload,
      List<int> blockOffsets,
      List<int> blockTypeIndices,
      List<uint> blockSizes,
      List<NifBlockTypeNameInfo> blockTypeNames,
      List<NifStringInfo> strings)
  {
    var candidates = new List<NifBlockReferenceCandidate>();
    var seen = new HashSet<(int Offset, int Target)>();
    var blockCount = Math.Min(blockTypeIndices.Count, blockSizes.Count);
    for (var offset = 0; offset + 4 <= payload.Length; offset += 4)
    {
      var targetBlockIndex = BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(offset, 4));
      if (targetBlockIndex < 0 || targetBlockIndex >= blockCount || !seen.Add((offset, targetBlockIndex)))
      {
        continue;
      }

      var targetTypeIndex = blockTypeIndices[targetBlockIndex];
      var targetTypeInfo = targetTypeIndex >= 0 && targetTypeIndex < blockTypeNames.Count
          ? blockTypeNames[targetTypeIndex]
          : null;
      var targetTypeName = targetTypeInfo?.NormalizedName ?? $"type-index-{targetTypeIndex}";
      if (!targetTypeName.StartsWith("NiDataStream", StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      var targetOffset = targetBlockIndex < blockOffsets.Count ? blockOffsets[targetBlockIndex] : data.Length;
      var safeTargetSize = targetOffset < data.Length
          ? Math.Min(checked((int)Math.Min(blockSizes[targetBlockIndex], int.MaxValue)), data.Length - targetOffset)
          : 0;
      var targetPayload = safeTargetSize > 0 ? data.Slice(targetOffset, safeTargetSize) : ReadOnlySpan<byte>.Empty;
      var targetFirst16 = ToHex(targetPayload[..Math.Min(16, targetPayload.Length)]);
      var maybeStringIndex = targetBlockIndex >= 0 && targetBlockIndex < strings.Count;
      candidates.Add(new NifBlockReferenceCandidate(
          PayloadOffset: offset,
          TargetBlockIndex: targetBlockIndex,
          TargetTypeName: targetTypeName,
          TargetDataStreamUsage: targetTypeInfo?.DataStreamUsage,
          TargetDataStreamAccess: targetTypeInfo?.DataStreamAccess,
          TargetSize: blockSizes[targetBlockIndex],
          TargetFirst16: targetFirst16,
          MaybeStringIndex: maybeStringIndex,
          StringValue: maybeStringIndex ? strings[targetBlockIndex].Value : null));
    }

    return candidates;
  }

  private static List<uint> ReadUInt32Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 4);
    var values = new List<uint>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadUInt32LittleEndian(payload.Slice(i * 4, 4)));
    }

    return values;
  }

  private static List<uint> ReadUInt32BigEndianPrefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 4);
    var values = new List<uint>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadUInt32BigEndian(payload.Slice(i * 4, 4)));
    }

    return values;
  }

  private static List<int> ReadInt32Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 4);
    var values = new List<int>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(i * 4, 4)));
    }

    return values;
  }

  private static List<ushort> ReadUInt16Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 2);
    var values = new List<ushort>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(i * 2, 2)));
    }

    return values;
  }

  private static List<ushort> ReadUInt16BigEndianPrefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 2);
    var values = new List<ushort>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadUInt16BigEndian(payload.Slice(i * 2, 2)));
    }

    return values;
  }

  private static List<NifFloat2> ReadFloat2Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 8);
    var values = new List<NifFloat2>(count);
    for (var i = 0; i < count; i++)
    {
      var offset = i * 8;
      values.Add(new NifFloat2(
          Index: i,
          X: ReadFiniteFloat32(payload.Slice(offset, 4)),
          Y: ReadFiniteFloat32(payload.Slice(offset + 4, 4))));
    }

    return values;
  }

  private static List<NifFloat3> ReadFloat3Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 12);
    var values = new List<NifFloat3>(count);
    for (var i = 0; i < count; i++)
    {
      var offset = i * 12;
      values.Add(new NifFloat3(
          Index: i,
          X: ReadFiniteFloat32(payload.Slice(offset, 4)),
          Y: ReadFiniteFloat32(payload.Slice(offset + 4, 4)),
          Z: ReadFiniteFloat32(payload.Slice(offset + 8, 4))));
    }

    return values;
  }

  private static List<NifUInt16Triple> ReadUInt16BigEndianTriplesPrefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 6);
    var values = new List<NifUInt16Triple>(count);
    for (var i = 0; i < count; i++)
    {
      var offset = i * 6;
      values.Add(new NifUInt16Triple(
          Index: i,
          A: BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(offset, 2)),
          B: BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(offset + 2, 2)),
          C: BinaryPrimitives.ReadUInt16LittleEndian(payload.Slice(offset + 4, 2))));
    }

    return values;
  }

  private static NifUInt16TriplesStructure AnalyzeNifUInt16TriplesStructure(List<NifUInt16Triple> triples)
  {
    if (triples.Count < 4)
    {
      return new NifUInt16TriplesStructure(
          TriplesCount: triples.Count,
          AlternationDetected: false,
          EvenIndexCConstant: false,
          EvenCValueSet: [],
          OddIndexAConstant: false,
          OddAValueSet: [],
          Magic43606Found: false,
          MetadataSentinelPattern: false,
          StructuralFamily: "unknown",
          Interpretation: "too few triples for structural analysis");
    }

    var evenTriples = new List<NifUInt16Triple>();
    var oddTriples = new List<NifUInt16Triple>();
    for (var i = 0; i < triples.Count; i++)
    {
      if (i % 2 == 0)
        evenTriples.Add(triples[i]);
      else
        oddTriples.Add(triples[i]);
    }

    if (evenTriples.Count < 2 || oddTriples.Count < 2)
    {
      return new NifUInt16TriplesStructure(
          TriplesCount: triples.Count,
          AlternationDetected: false,
          EvenIndexCConstant: false,
          EvenCValueSet: [],
          OddIndexAConstant: false,
          OddAValueSet: [],
          Magic43606Found: false,
          MetadataSentinelPattern: false,
          StructuralFamily: "unknown",
          Interpretation: "insufficient even/odd split for alternation analysis");
    }

    var evenCVals = evenTriples.Select(t => t.C).ToList();
    var evenCSet = evenCVals.Distinct().OrderBy(v => v).ToList();
    var evenCConstant = evenCSet.Count == 1 && evenTriples.Count >= 2;
    var magic43606 = evenCConstant && evenCSet[0] == 43606;

    var oddAVals = oddTriples.Select(t => t.A).ToList();
    var oddASet = oddAVals.Distinct().OrderBy(v => v).ToList();
    var oddAConstant = oddASet.Count == 1 && oddTriples.Count >= 2;

    var oddBVals = oddTriples.Select(t => t.B).Distinct().OrderBy(v => v).ToList();
    var oddCVals = oddTriples.Select(t => t.C).Distinct().OrderBy(v => v).ToList();
    var metadataSentinel = oddBVals.Count <= 2 && oddCVals.Count <= 2 && oddBVals.Count > 0 && oddCVals.Count > 0;

    string structuralFamily;
    string interpretation;
    if (magic43606 && evenCConstant && metadataSentinel)
    {
      structuralFamily = "magic-43606-u16-ternary-alternating";
      interpretation = "Magic constant 43606 (0xAA56) on even-C with alternating metadata layer. Typical of packed uint16 positions with vertex-type tag.";
    }
    else if (evenCConstant && metadataSentinel)
    {
      structuralFamily = "u16-ternary-alternating";
      interpretation = "Alternating [position_triple, metadata_pair] structure with constant even-C. Packed/quantized position hypothesis.";
    }
    else if (evenCSet.Count > 1)
    {
      structuralFamily = "u16-ternary-mixed-c";
      interpretation = "Alternating structure with varying even-C values. May indicate multi-attribute or interleaved multi-mesh data.";
    }
    else
    {
      structuralFamily = "unstructured-u16";
      interpretation = "No clear even/odd alternation or constant-C pattern detected. Requires deeper analysis.";
    }

    return new NifUInt16TriplesStructure(
        TriplesCount: triples.Count,
        AlternationDetected: true,
        EvenIndexCConstant: evenCConstant,
        EvenCValueSet: evenCSet,
        OddIndexAConstant: oddAConstant,
        OddAValueSet: oddASet,
        Magic43606Found: magic43606,
        MetadataSentinelPattern: metadataSentinel,
        StructuralFamily: structuralFamily,
        Interpretation: interpretation);
  }


  private static float? ReadFiniteFloat32(ReadOnlySpan<byte> bytes)
  {
    var value = BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(bytes));
    return float.IsFinite(value) ? value : null;
  }

  private static List<float?> ReadFloat32Prefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 4);
    var values = new List<float?>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(ReadFiniteFloat32(payload.Slice(i * 4, 4)));
    }

    return values;
  }

  private static List<float?> ReadFloat32BigEndianPrefix(ReadOnlySpan<byte> payload, int maxValues)
  {
    var count = Math.Min(maxValues, payload.Length / 4);
    var values = new List<float?>(count);
    for (var i = 0; i < count; i++)
    {
      var value = BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32BigEndian(payload.Slice(i * 4, 4)));
      values.Add(float.IsFinite(value) ? value : null);
    }

    return values;
  }

  private static List<NifByteHistogramEntry> BuildByteHistogram(ReadOnlySpan<byte> payload, int maxEntries)
  {
    var counts = new int[256];
    foreach (var value in payload)
    {
      counts[value]++;
    }

    var entries = new List<NifByteHistogramEntry>();
    for (var value = 0; value < counts.Length; value++)
    {
      var count = counts[value];
      if (count == 0)
      {
        continue;
      }

      entries.Add(new NifByteHistogramEntry(
          Value: value,
          Hex: $"0x{value:x2}",
          Count: count,
          Ratio: payload.Length == 0 ? 0 : Math.Round(count / (double)payload.Length, 6)));
    }

    return entries
        .OrderByDescending(static e => e.Count)
        .ThenBy(static e => e.Value)
        .Take(maxEntries)
        .ToList();
  }

  private static List<NifRepeatedBodyPattern> FindRepeatedFixedWidthPatterns(ReadOnlySpan<byte> payload, int width, int maxEntries)
  {
    if (width <= 0 || payload.Length < width)
    {
      return [];
    }

    var groups = new Dictionary<string, NifRepeatedBodyPatternAccumulator>(StringComparer.OrdinalIgnoreCase);
    var count = payload.Length / width;
    for (var i = 0; i < count; i++)
    {
      var offset = i * width;
      var hex = ToHex(payload.Slice(offset, width));
      if (!groups.TryGetValue(hex, out var group))
      {
        group = new NifRepeatedBodyPatternAccumulator(hex, width);
        groups.Add(hex, group);
      }

      group.Count++;
      if (group.Offsets.Count < 16)
      {
        group.Offsets.Add(offset);
      }
    }

    return groups.Values
        .Where(static g => g.Count > 1)
        .OrderByDescending(static g => g.Count)
        .ThenBy(static g => g.Hex, StringComparer.OrdinalIgnoreCase)
        .Take(maxEntries)
        .Select(static g => new NifRepeatedBodyPattern(g.Hex, g.Width, g.Count, g.Offsets))
        .ToList();
  }

  private static List<NifAttributeExtraGroupedView> BuildNifAttributeExtraGroupedViews(ReadOnlySpan<byte> body, NifMeshAttributeSetSample attributeSet)
  {
    var views = new List<NifAttributeExtraGroupedView>
        {
            BuildNifAttributeExtraGroupedView("per-vertex", body, attributeSet.VertexCount),
        };

    if (attributeSet.Topology.TriangleListTriangleCount is not null)
    {
      views.Add(BuildNifAttributeExtraGroupedView("per-triangle-list-triangle", body, attributeSet.Topology.TriangleListTriangleCount.Value));
    }

    if (attributeSet.Topology.TriangleStripTriangleCount is not null)
    {
      views.Add(BuildNifAttributeExtraGroupedView("per-strip-or-fan-triangle", body, attributeSet.Topology.TriangleStripTriangleCount.Value));
    }

    if (attributeSet.Topology.QuadListQuadCount is not null)
    {
      views.Add(BuildNifAttributeExtraGroupedView("per-quad", body, attributeSet.Topology.QuadListQuadCount.Value));
    }

    return views;
  }

  private static NifAttributeExtraIndexCompatibility? BuildNifAttributeExtraIndexCompatibility(
      int vertexCount,
      NifUInt16BeIndexStats? indexStats,
      ReadOnlySpan<byte> body)
  {
    if (indexStats is null || vertexCount <= 0)
    {
      return null;
    }

    var maxIndexWithinVertexCount = indexStats.BigEndianMaxIndex < vertexCount;
    var maxCoverageRatio = Math.Round((indexStats.BigEndianMaxIndex + 1) / (double)vertexCount, 4);
    var distinctCoverageRatio = Math.Round(indexStats.BigEndianDistinctIndexCount / (double)vertexCount, 4);
    string candidateTopology;
    var evidence = new List<string>
        {
            $"max-index={indexStats.BigEndianMaxIndex.ToString(CultureInfo.InvariantCulture)} vertex-count={vertexCount.ToString(CultureInfo.InvariantCulture)}",
            $"distinct-indices={indexStats.BigEndianDistinctIndexCount.ToString(CultureInfo.InvariantCulture)}",
        };

    if (!maxIndexWithinVertexCount)
    {
      candidateTopology = "index-out-of-range";
      evidence.Add("max index is not within the attribute vertex count");
    }
    else if (indexStats.TriangleStripLessDegenerateThanTriples)
    {
      candidateTopology = "explicit-index-strip-lead";
      evidence.Add($"strip windows are less degenerate than fixed triples ({indexStats.TriangleStripDegenerateRatio:0.####} < {indexStats.DegenerateTriangleRatio:0.####})");
    }
    else if (indexStats.TriangleAligned && indexStats.DegenerateTriangleRatio <= 0.25)
    {
      candidateTopology = "explicit-index-list-lead";
      evidence.Add($"fixed triples are low-degenerate ({indexStats.DegenerateTriangleRatio:0.####})");
    }
    else
    {
      candidateTopology = "explicit-index-topology-unknown";
      evidence.Add("index range is compatible but topology remains ambiguous");
    }

    if (indexStats.BigEndianMinIndex > 0)
    {
      evidence.Add("zero index is absent from the sampled stream; check for 1-based or reserved-zero semantics before export");
    }

    var indexBaseHint = GetNifAttributeExtraIndexBaseHint(vertexCount, indexStats);
    var allIndices = ReadUInt16BigEndianValues(body);
    var mappingCandidates = BuildNifAttributeExtraIndexMappingCandidates(vertexCount, allIndices);
    var stripStructure = BuildNifTriangleStripStructureStats(allIndices);
    evidence.Add($"index-base-hint={indexBaseHint}");
    evidence.Add($"strip-structure={stripStructure.Hint}; mirrored-bridges={stripStructure.MirroredAdjacentRepeatBridgeCount.ToString(CultureInfo.InvariantCulture)} sentinel-restarts={stripStructure.SentinelRestartValueCount.ToString(CultureInfo.InvariantCulture)} zero-values={stripStructure.ZeroIndexValueCount.ToString(CultureInfo.InvariantCulture)}");

    return new NifAttributeExtraIndexCompatibility(
        CandidateTopology: candidateTopology,
        VertexCount: vertexCount,
        PairCount: indexStats.PairCount,
        TriangleAligned: indexStats.TriangleAligned,
        TriangleCount: indexStats.TriangleCount,
        MinIndex: indexStats.BigEndianMinIndex,
        MaxIndex: indexStats.BigEndianMaxIndex,
        DistinctIndexCount: indexStats.BigEndianDistinctIndexCount,
        MaxIndexWithinVertexCount: maxIndexWithinVertexCount,
        MaxIndexCoverageRatio: maxCoverageRatio,
        DistinctIndexCoverageRatio: distinctCoverageRatio,
        UsesZeroIndex: indexStats.BigEndianMinIndex == 0,
        DegenerateTriangleRatio: indexStats.DegenerateTriangleRatio,
        TriangleStripWindowCount: indexStats.TriangleStripWindowCount,
        TriangleStripNonDegenerateWindowCount: indexStats.TriangleStripNonDegenerateWindowCount,
        TriangleStripDegenerateRatio: indexStats.TriangleStripDegenerateRatio,
        TriangleStripLessDegenerateThanTriples: indexStats.TriangleStripLessDegenerateThanTriples,
        IndexBaseHint: indexBaseHint,
        FirstIndices: indexStats.FirstBigEndianIndices,
        FirstTriples: indexStats.FirstBigEndianTriples,
        FirstStripTriangles: BuildNifTriangleStripPreview(indexStats.FirstBigEndianIndices, maxTriangles: 16),
        MappingCandidates: mappingCandidates,
        StripStructure: stripStructure,
        Evidence: evidence);
  }

  private static List<ushort> ReadUInt16BigEndianValues(ReadOnlySpan<byte> payload)
  {
    var count = payload.Length / 2;
    var values = new List<ushort>(count);
    for (var i = 0; i < count; i++)
    {
      values.Add(BinaryPrimitives.ReadUInt16BigEndian(payload.Slice(i * 2, 2)));
    }

    return values;
  }

  private static List<NifAttributeExtraIndexMappingCandidate> BuildNifAttributeExtraIndexMappingCandidates(int vertexCount, List<ushort> indices)
  {
    return
    [
        BuildNifAttributeExtraIndexMappingCandidate("raw-zero-based", 0, vertexCount, indices),
            BuildNifAttributeExtraIndexMappingCandidate("subtract-one", -1, vertexCount, indices)
    ];
  }

  private static NifAttributeExtraIndexMappingCandidate BuildNifAttributeExtraIndexMappingCandidate(
      string name,
      int indexOffset,
      int vertexCount,
      List<ushort> indices)
  {
    var referenced = new HashSet<int>();
    var mappedPrefix = new List<int>(Math.Min(indices.Count, 32));
    var outOfRange = 0;
    int? mappedMin = null;
    int? mappedMax = null;

    foreach (var sourceIndex in indices)
    {
      var mapped = sourceIndex + indexOffset;
      if (mappedPrefix.Count < 32)
      {
        mappedPrefix.Add(mapped);
      }

      if (mapped < 0 || mapped >= vertexCount)
      {
        outOfRange++;
        continue;
      }

      referenced.Add(mapped);
      mappedMin = mappedMin is null ? mapped : Math.Min(mappedMin.Value, mapped);
      mappedMax = mappedMax is null ? mapped : Math.Max(mappedMax.Value, mapped);
    }

    var missingSamples = new List<int>();
    for (var vertex = 0; vertex < vertexCount && missingSamples.Count < 16; vertex++)
    {
      if (!referenced.Contains(vertex))
      {
        missingSamples.Add(vertex);
      }
    }

    var missingVertexCount = Math.Max(0, vertexCount - referenced.Count);
    var valid = outOfRange == 0;
    var evidence = new List<string>
        {
            valid ? "all mapped indices are within the attribute vertex count" : $"{outOfRange.ToString(CultureInfo.InvariantCulture)} mapped index value(s) are out of range",
            $"referenced-vertices={referenced.Count.ToString(CultureInfo.InvariantCulture)}/{vertexCount.ToString(CultureInfo.InvariantCulture)}",
        };
    if (missingSamples.Count > 0)
    {
      evidence.Add($"first-missing-vertices={string.Join(",", missingSamples)}");
    }

    return new NifAttributeExtraIndexMappingCandidate(
        Name: name,
        IndexOffset: indexOffset,
        ValidForVertexCount: valid,
        OutOfRangeIndexCount: outOfRange,
        ReferencedVertexCount: referenced.Count,
        ReferencedVertexCoverageRatio: vertexCount == 0 ? 0 : Math.Round(referenced.Count / (double)vertexCount, 4),
        MissingVertexCount: missingVertexCount,
        MissingVertexSamples: missingSamples,
        MappedMinIndex: mappedMin,
        MappedMaxIndex: mappedMax,
        FirstMappedIndices: mappedPrefix,
        FirstMappedStripTriangles: BuildMappedTriangleStripPreview(mappedPrefix, vertexCount, maxTriangles: 16),
        Evidence: evidence);
  }

  private static List<NifMappedTriangleStripPreviewTriangle> BuildMappedTriangleStripPreview(List<int> mappedIndices, int vertexCount, int maxTriangles)
  {
    var triangles = new List<NifMappedTriangleStripPreviewTriangle>();
    for (var i = 0; i + 2 < mappedIndices.Count && triangles.Count < maxTriangles; i++)
    {
      var a = mappedIndices[i];
      var b = mappedIndices[i + 1];
      var c = mappedIndices[i + 2];
      var outOfRange = a < 0 || a >= vertexCount || b < 0 || b >= vertexCount || c < 0 || c >= vertexCount;
      var degenerate = a == b || a == c || b == c;
      triangles.Add(new NifMappedTriangleStripPreviewTriangle(
          Index: i,
          A: a,
          B: b,
          C: c,
          WindingParity: (i % 2) == 0 ? "even" : "odd",
          Degenerate: degenerate,
          OutOfRange: outOfRange));
    }

    return triangles;
  }

  private static List<int> BuildNifAttributeVertexSampleIndices(int vertexCount, NifAttributeExtraIndexCompatibility? indexCompatibility)
  {
    var samples = new List<int>();
    void add(int index)
    {
      if (index >= 0 && index < vertexCount && !samples.Contains(index))
      {
        samples.Add(index);
      }
    }

    void addNeighborhood(int index)
    {
      add(index);
      add(index - 1);
      add(index + 1);
    }

    add(0);
    add(1);
    add(vertexCount - 2);
    add(vertexCount - 1);
    if (indexCompatibility is not null)
    {
      foreach (var mapping in indexCompatibility.MappingCandidates)
      {
        foreach (var missing in mapping.MissingVertexSamples.Take(4))
        {
          addNeighborhood(missing);
        }
      }

      foreach (var index in indexCompatibility.FirstIndices.Take(4))
      {
        addNeighborhood(index);
      }
    }

    return samples.Take(16).ToList();
  }

  private static List<NifAttributeVertexSample> BuildNifAttributeFloatVertexSamples(
      byte[] payload,
      IReadOnlyDictionary<int, NifBlockInfo> blocksByIndex,
      int blockIndex,
      string attributeName,
      string role,
      int components,
      List<int> vertexIndices)
  {
    if (components is < 2 or > 3 || vertexIndices.Count == 0 || !blocksByIndex.TryGetValue(blockIndex, out var streamBlock))
    {
      return [];
    }

    var blockPayload = SliceNifBlockPayload(payload, streamBlock);
    if (blockPayload.Length < 4)
    {
      return [];
    }

    var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
    if (declaredPayloadBytes > blockPayload.Length)
    {
      return [];
    }

    var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);
    var body = blockPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));
    var bytesPerVector = checked(components * 4);
    var vectorCount = body.Length / bytesPerVector;
    var transform = role.Contains("ror1", StringComparison.OrdinalIgnoreCase)
        ? NifFloatByteTransform.RotateRight1
        : NifFloatByteTransform.LittleEndian;
    var samples = new List<NifAttributeVertexSample>();
    foreach (var vertexIndex in vertexIndices)
    {
      if (vertexIndex < 0 || vertexIndex >= vectorCount)
      {
        continue;
      }

      var values = DecodeNifAttributeVector(body, components, transform, vertexIndex);
      samples.Add(new NifAttributeVertexSample(
          Index: vertexIndex,
          Attribute: attributeName,
          Role: role,
          Transform: FormatNifFloatTransformSuffix(transform),
          Components: components,
          X: values[0],
          Y: values[1],
          Z: components > 2 ? values[2] : null,
          VectorLength: ComputeNifAttributeVectorLength(values, components),
          PreviousDistance: vertexIndex > 0 ? ComputeNifAttributeVectorDistance(body, components, transform, vertexIndex - 1, vertexIndex) : null,
          NextDistance: vertexIndex + 1 < vectorCount ? ComputeNifAttributeVectorDistance(body, components, transform, vertexIndex, vertexIndex + 1) : null));
    }

    return samples;
  }

  private static List<NifAttributeVertexSample> BuildNifAttributeUInt16VertexSamples(
          byte[] payload,
          IReadOnlyDictionary<int, NifBlockInfo> blocksByIndex,
          int blockIndex,
          int maxVertices)
  {
    if (maxVertices <= 0 || !blocksByIndex.TryGetValue(blockIndex, out var streamBlock))
    {
      return [];
    }

    var blockPayload = SliceNifBlockPayload(payload, streamBlock);
    if (blockPayload.Length < 4)
    {
      return [];
    }

    var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
    if (declaredPayloadBytes > blockPayload.Length)
    {
      return [];
    }

    var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);
    var body = blockPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));

    // UInt16-packed position: alternating even/odd triples, 12 bytes per vertex
    // Even triple: (posA_lo, posA_hi), (posB_lo, posB_hi), (magic_43606_lo, magic_43606_hi)
    // Odd triple:  (metaA_lo, metaA_hi), (metaB_lo, metaB_hi), (metaC_lo, metaC_hi)
    // Position components span across even-triple A and B as a 32-bit value
    var bytesPerVertex = 12;
    var vertexCount = Math.Min(maxVertices, body.Length / bytesPerVertex);
    var samples = new List<NifAttributeVertexSample>(vertexCount);

    for (var i = 0; i < vertexCount; i++)
    {
      var offset = i * bytesPerVertex;
      if (offset + bytesPerVertex > body.Length)
        break;

      // Read even triple for this vertex (offset + 0 to offset + 5)
      var posA = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offset, 2)) / 65535.0;
      var posB = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offset + 2, 2)) / 65535.0;

      samples.Add(new NifAttributeVertexSample(
          Index: i,
          Attribute: "position",
          Role: "position-u16-packed-experimental",
          Transform: "u16-le-normalized",
          Components: 2,
          X: posA,
          Y: posB,
          Z: null,
          VectorLength: null,
          PreviousDistance: i > 0 ? ComputeNifAttributeUInt16Distance(body, i - 1, i, bytesPerVertex) : null,
          NextDistance: i + 1 < vertexCount ? ComputeNifAttributeUInt16Distance(body, i, i + 1, bytesPerVertex) : null));
    }

    return samples;
  }

  private static double? ComputeNifAttributeUInt16Distance(ReadOnlySpan<byte> body, int indexA, int indexB, int bytesPerVertex)
  {
    var offsetA = indexA * bytesPerVertex;
    var offsetB = indexB * bytesPerVertex;
    if (offsetA + 4 > body.Length || offsetB + 4 > body.Length)
      return null;

    var aX = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offsetA, 2)) / 65535.0;
    var aY = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offsetA + 2, 2)) / 65535.0;
    var bX = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offsetB, 2)) / 65535.0;
    var bY = (double)BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offsetB + 2, 2)) / 65535.0;

    var dx = aX - bX;
    var dy = aY - bY;
    return Math.Sqrt(dx * dx + dy * dy);
  }

  private static double?[] DecodeNifAttributeVector(ReadOnlySpan<byte> body, int components, NifFloatByteTransform transform, int vertexIndex)
  {
    var values = new double?[3];
    var bytesPerVector = checked(components * 4);
    var offset = checked(vertexIndex * bytesPerVector);
    if (offset < 0 || offset + bytesPerVector > body.Length)
    {
      return values;
    }

    for (var component = 0; component < components; component++)
    {
      values[component] = ToNullableDouble(ReadFiniteFloat32(body.Slice(offset + (component * 4), 4), transform));
    }

    return values;
  }

  private static double? ComputeNifAttributeVectorLength(double?[] values, int components)
  {
    double sum = 0;
    for (var component = 0; component < components; component++)
    {
      if (values[component] is null)
      {
        return null;
      }

      sum += values[component]!.Value * values[component]!.Value;
    }

    return Math.Round(Math.Sqrt(sum), 6);
  }

  private static double? ComputeNifAttributeVectorDistance(
      ReadOnlySpan<byte> body,
      int components,
      NifFloatByteTransform transform,
      int fromVertexIndex,
      int toVertexIndex)
  {
    var from = DecodeNifAttributeVector(body, components, transform, fromVertexIndex);
    var to = DecodeNifAttributeVector(body, components, transform, toVertexIndex);
    double sum = 0;
    for (var component = 0; component < components; component++)
    {
      if (from[component] is null || to[component] is null)
      {
        return null;
      }

      var delta = to[component]!.Value - from[component]!.Value;
      sum += delta * delta;
    }

    return Math.Round(Math.Sqrt(sum), 6);
  }

  private static double? ComputeNifAttributeTriangleMaxDistance(
      ReadOnlySpan<byte> body,
      int components,
      NifFloatByteTransform transform,
      int a,
      int b,
      int c)
  {
    if (components is < 2 or > 3 || body.IsEmpty)
    {
      return null;
    }

    var ab = ComputeNifAttributeVectorDistance(body, components, transform, a, b);
    var bc = ComputeNifAttributeVectorDistance(body, components, transform, b, c);
    var ca = ComputeNifAttributeVectorDistance(body, components, transform, c, a);
    if (ab is null || bc is null || ca is null)
    {
      return null;
    }

    return Math.Max(ab.Value, Math.Max(bc.Value, ca.Value));
  }

  private static NifAttributeTriangleShape? ComputeNifPositionTriangleShape(
      ReadOnlySpan<byte> body,
      NifFloatByteTransform transform,
      int a,
      int b,
      int c)
  {
    var va = DecodeNifAttributeVector(body, components: 3, transform, a);
    var vb = DecodeNifAttributeVector(body, components: 3, transform, b);
    var vc = DecodeNifAttributeVector(body, components: 3, transform, c);
    if (va[0] is null || va[1] is null || va[2] is null ||
        vb[0] is null || vb[1] is null || vb[2] is null ||
        vc[0] is null || vc[1] is null || vc[2] is null)
    {
      return null;
    }

    var ux = vb[0]!.Value - va[0]!.Value;
    var uy = vb[1]!.Value - va[1]!.Value;
    var uz = vb[2]!.Value - va[2]!.Value;
    var vx = vc[0]!.Value - va[0]!.Value;
    var vy = vc[1]!.Value - va[1]!.Value;
    var vz = vc[2]!.Value - va[2]!.Value;
    var crossX = (uy * vz) - (uz * vy);
    var crossY = (uz * vx) - (ux * vz);
    var crossZ = (ux * vy) - (uy * vx);
    var area = 0.5 * Math.Sqrt((crossX * crossX) + (crossY * crossY) + (crossZ * crossZ));
    var absX = Math.Abs(crossX);
    var absY = Math.Abs(crossY);
    var absZ = Math.Abs(crossZ);
    var (dominantPlane, dominantSignedArea) = absZ >= absX && absZ >= absY
        ? ("xy", 0.5 * crossZ)
        : absY >= absX && absY >= absZ
            ? ("xz", 0.5 * crossY)
            : ("yz", 0.5 * crossX);

    return new NifAttributeTriangleShape(
        Area: Math.Round(area, 6),
        DominantPlane: dominantPlane,
        DominantSignedArea: Math.Round(dominantSignedArea, 6));
  }

  private static List<NifAttributeExtraMappingPositionFitness> BuildNifAttributeMappingPositionFitness(
      byte[] payload,
      IReadOnlyDictionary<int, NifBlockInfo> blocksByIndex,
      NifMeshAttributeSetSample attributeSet,
      ReadOnlySpan<byte> indexBody,
      NifAttributeExtraIndexCompatibility? indexCompatibility)
  {
    if (indexCompatibility is null ||
        indexBody.Length < 6 ||
        !TryGetNifAttributeFloatBody(payload, blocksByIndex, attributeSet.PositionBlockIndex, attributeSet.PositionRole, components: 3, out var positionBody, out var positionTransform))
    {
      return [];
    }

    var hasNormalBody = TryGetNifAttributeFloatBody(payload, blocksByIndex, attributeSet.NormalBlockIndex, attributeSet.NormalRole, components: 3, out var normalBody, out var normalTransform);
    var hasUvBody = TryGetNifAttributeFloatBody(payload, blocksByIndex, attributeSet.UvBlockIndex, attributeSet.UvRole, components: 2, out var uvBody, out var uvTransform);
    var indices = ReadUInt16BigEndianValues(indexBody);

    var fitness = new List<NifAttributeExtraMappingPositionFitness>();
    foreach (var mapping in indexCompatibility.MappingCandidates)
    {
      fitness.Add(BuildNifAttributeMappingPositionFitnessCandidate(
          mapping,
          indices,
          positionBody,
          positionTransform,
          hasNormalBody ? normalBody : ReadOnlySpan<byte>.Empty,
          hasNormalBody ? normalTransform : NifFloatByteTransform.LittleEndian,
          hasNormalBody ? 3 : 0,
          hasUvBody ? uvBody : ReadOnlySpan<byte>.Empty,
          hasUvBody ? uvTransform : NifFloatByteTransform.LittleEndian,
          hasUvBody ? 2 : 0,
          attributeSet.VertexCount,
          indexCompatibility.StripStructure.Hint));
    }

    return fitness;
  }

  private static bool TryGetNifAttributeFloatBody(
      byte[] payload,
      IReadOnlyDictionary<int, NifBlockInfo> blocksByIndex,
      int blockIndex,
      string role,
      int components,
      out ReadOnlySpan<byte> body,
      out NifFloatByteTransform transform)
  {
    body = ReadOnlySpan<byte>.Empty;
    transform = role.Contains("ror1", StringComparison.OrdinalIgnoreCase)
        ? NifFloatByteTransform.RotateRight1
        : NifFloatByteTransform.LittleEndian;
    if (components is < 2 or > 3 || !blocksByIndex.TryGetValue(blockIndex, out var streamBlock))
    {
      return false;
    }

    var blockPayload = SliceNifBlockPayload(payload, streamBlock);
    if (blockPayload.Length < 4)
    {
      return false;
    }

    var declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(blockPayload[..4]);
    if (declaredPayloadBytes > blockPayload.Length)
    {
      return false;
    }

    var headerBytes = blockPayload.Length - checked((int)declaredPayloadBytes);
    body = blockPayload.Slice(headerBytes, checked((int)declaredPayloadBytes));
    return body.Length >= components * 4;
  }

  private static NifAttributeExtraMappingPositionFitness BuildNifAttributeMappingPositionFitnessCandidate(
      NifAttributeExtraIndexMappingCandidate mapping,
      List<ushort> indices,
      ReadOnlySpan<byte> positionBody,
      NifFloatByteTransform positionTransform,
      ReadOnlySpan<byte> normalBody,
      NifFloatByteTransform normalTransform,
      int normalComponents,
      ReadOnlySpan<byte> uvBody,
      NifFloatByteTransform uvTransform,
      int uvComponents,
      int vertexCount,
      string restartModeHypothesis)
  {
    var triangleWindowCount = Math.Max(0, indices.Count - 2);
    var nonDegenerateTriangleWindowCount = 0;
    var outOfRangeTriangleWindowCount = 0;
    var finiteMaxEdges = new List<double>(triangleWindowCount);
    var triangleSamples = new List<NifAttributeExtraMappingPositionTriangleSample>();
    var segmentedTriangleWindowCount = 0;
    var segmentedMaxEdges = new List<double>(triangleWindowCount);
    var segmentedNormalDeltas = new List<double>(triangleWindowCount);
    var segmentedUvDeltas = new List<double>(triangleWindowCount);
    var segmentedAreas = new List<double>(triangleWindowCount);
    var segmentedNearZeroAreaCount = 0;
    var segmentedTriangleSamples = new List<NifAttributeExtraMappingPositionTriangleSample>();
    var firstSegmentTriangleSamples = new List<NifAttributeExtraMappingPositionTriangleSample>();
    var segmentSamples = new List<NifAttributeExtraMappingPositionSegmentSample>();
    int? segmentStartWindow = null;
    int segmentTriangleWindowCount = 0;
    int segmentFiniteTriangleWindowCount = 0;
    int segmentStartA = 0;
    int segmentStartB = 0;
    int segmentEndB = 0;
    int segmentEndC = 0;
    var segmentMaxEdges = new List<double>();

    for (var i = 0; i + 2 < indices.Count; i++)
    {
      var a = indices[i] + mapping.IndexOffset;
      var b = indices[i + 1] + mapping.IndexOffset;
      var c = indices[i + 2] + mapping.IndexOffset;
      if (a == b || a == c || b == c)
      {
        closeSegment();
        continue;
      }

      nonDegenerateTriangleWindowCount++;
      if (a < 0 || a >= vertexCount || b < 0 || b >= vertexCount || c < 0 || c >= vertexCount)
      {
        outOfRangeTriangleWindowCount++;
        closeSegment();
        continue;
      }

      if (segmentStartWindow is null)
      {
        segmentStartWindow = i;
        segmentStartA = a;
        segmentStartB = b;
        segmentMaxEdges.Clear();
        segmentTriangleWindowCount = 0;
        segmentFiniteTriangleWindowCount = 0;
      }

      segmentedTriangleWindowCount++;
      segmentTriangleWindowCount++;
      segmentEndB = b;
      segmentEndC = c;
      var ab = ComputeNifAttributeVectorDistance(positionBody, components: 3, positionTransform, a, b);
      var bc = ComputeNifAttributeVectorDistance(positionBody, components: 3, positionTransform, b, c);
      var ca = ComputeNifAttributeVectorDistance(positionBody, components: 3, positionTransform, c, a);
      if (ab is null || bc is null || ca is null)
      {
        continue;
      }

      var maxEdge = Math.Max(ab.Value, Math.Max(bc.Value, ca.Value));
      var normalMaxDelta = ComputeNifAttributeTriangleMaxDistance(normalBody, normalComponents, normalTransform, a, b, c);
      var uvMaxDelta = ComputeNifAttributeTriangleMaxDistance(uvBody, uvComponents, uvTransform, a, b, c);
      var shape = ComputeNifPositionTriangleShape(positionBody, positionTransform, a, b, c);
      finiteMaxEdges.Add(maxEdge);
      segmentedMaxEdges.Add(maxEdge);
      if (normalMaxDelta is not null)
      {
        segmentedNormalDeltas.Add(normalMaxDelta.Value);
      }

      if (uvMaxDelta is not null)
      {
        segmentedUvDeltas.Add(uvMaxDelta.Value);
      }

      if (shape is not null)
      {
        segmentedAreas.Add(shape.Area);
        if (shape.Area <= 0.000001)
        {
          segmentedNearZeroAreaCount++;
        }
      }

      segmentMaxEdges.Add(maxEdge);
      segmentFiniteTriangleWindowCount++;
      var triangleSample = new NifAttributeExtraMappingPositionTriangleSample(
          StripWindowIndex: i,
          A: a,
          B: b,
          C: c,
          AB: ab,
          BC: bc,
          CA: ca,
          MaxEdge: maxEdge,
          NormalMaxDelta: normalMaxDelta,
          UvMaxDelta: uvMaxDelta,
          Area: shape?.Area,
          DominantAreaPlane: shape?.DominantPlane,
          DominantSignedArea: shape?.DominantSignedArea,
          StripWindingParity: (i & 1) == 0 ? "even" : "odd");
      triangleSamples.Add(triangleSample);
      segmentedTriangleSamples.Add(triangleSample);
      if (firstSegmentTriangleSamples.Count < 24)
      {
        firstSegmentTriangleSamples.Add(triangleSample);
      }
    }

    closeSegment();
    var sortedEdges = finiteMaxEdges.OrderBy(static e => e).ToList();
    var sortedSegmentedEdges = segmentedMaxEdges.OrderBy(static e => e).ToList();
    var sortedSegmentedNormalDeltas = segmentedNormalDeltas.OrderBy(static e => e).ToList();
    var sortedSegmentedUvDeltas = segmentedUvDeltas.OrderBy(static e => e).ToList();
    var sortedSegmentedAreas = segmentedAreas.OrderBy(static e => e).ToList();
    var segmentedMedian = GetPercentile(sortedSegmentedEdges, 0.50);
    var continuousMedian = GetPercentile(sortedEdges, 0.50);
    return new NifAttributeExtraMappingPositionFitness(
        MappingName: mapping.Name,
        IndexOffset: mapping.IndexOffset,
        RestartModeHypothesis: restartModeHypothesis,
        TriangleWindowCount: triangleWindowCount,
        NonDegenerateTriangleWindowCount: nonDegenerateTriangleWindowCount,
        OutOfRangeTriangleWindowCount: outOfRangeTriangleWindowCount,
        FiniteTriangleWindowCount: finiteMaxEdges.Count,
        AverageMaxEdge: finiteMaxEdges.Count == 0 ? null : Math.Round(finiteMaxEdges.Average(), 6),
        MedianMaxEdge: continuousMedian,
        P95MaxEdge: GetPercentile(sortedEdges, 0.95),
        MaxEdge: sortedEdges.Count == 0 ? null : Math.Round(sortedEdges[^1], 6),
        SegmentCount: segmentSamples.Count,
        SegmentedTriangleWindowCount: segmentedTriangleWindowCount,
        DroppedDegenerateWindowCount: triangleWindowCount - nonDegenerateTriangleWindowCount,
        DroppedCrossSegmentWindowCount: Math.Max(0, nonDegenerateTriangleWindowCount - segmentedTriangleWindowCount - outOfRangeTriangleWindowCount),
        SegmentedFiniteTriangleWindowCount: segmentedMaxEdges.Count,
        SegmentedAverageMaxEdge: segmentedMaxEdges.Count == 0 ? null : Math.Round(segmentedMaxEdges.Average(), 6),
        SegmentedMedianMaxEdge: segmentedMedian,
        SegmentedP95MaxEdge: GetPercentile(sortedSegmentedEdges, 0.95),
        SegmentedMaxEdge: sortedSegmentedEdges.Count == 0 ? null : Math.Round(sortedSegmentedEdges[^1], 6),
        SegmentedFiniteNormalTriangleWindowCount: segmentedNormalDeltas.Count,
        SegmentedMedianNormalDelta: GetPercentile(sortedSegmentedNormalDeltas, 0.50),
        SegmentedP95NormalDelta: GetPercentile(sortedSegmentedNormalDeltas, 0.95),
        SegmentedMaxNormalDelta: sortedSegmentedNormalDeltas.Count == 0 ? null : Math.Round(sortedSegmentedNormalDeltas[^1], 6),
        SegmentedFiniteUvTriangleWindowCount: segmentedUvDeltas.Count,
        SegmentedMedianUvDelta: GetPercentile(sortedSegmentedUvDeltas, 0.50),
        SegmentedP95UvDelta: GetPercentile(sortedSegmentedUvDeltas, 0.95),
        SegmentedMaxUvDelta: sortedSegmentedUvDeltas.Count == 0 ? null : Math.Round(sortedSegmentedUvDeltas[^1], 6),
        SegmentedFiniteAreaTriangleWindowCount: segmentedAreas.Count,
        SegmentedMedianTriangleArea: GetPercentile(sortedSegmentedAreas, 0.50),
        SegmentedMinTriangleArea: sortedSegmentedAreas.Count == 0 ? null : Math.Round(sortedSegmentedAreas[0], 6),
        SegmentedNearZeroTriangleAreaCount: segmentedNearZeroAreaCount,
        ContinuousToSegmentedMedianDelta: continuousMedian is null || segmentedMedian is null ? null : Math.Round(continuousMedian.Value - segmentedMedian.Value, 6),
        WorstTriangles: triangleSamples
            .OrderByDescending(static t => t.MaxEdge ?? -1)
            .ThenBy(static t => t.StripWindowIndex)
            .Take(8)
            .ToList(),
        WorstSegmentedTriangles: segmentedTriangleSamples
            .OrderByDescending(static t => t.MaxEdge ?? -1)
            .ThenBy(static t => t.StripWindowIndex)
            .Take(8)
            .ToList(),
        FirstSegmentProofReview: BuildNifAttributeExtraFirstSegmentProofReview(firstSegmentTriangleSamples),
        FirstSegmentTriangles: firstSegmentTriangleSamples,
        FirstSegments: segmentSamples.Take(16)
            .ToList());

    void closeSegment()
    {
      if (segmentStartWindow is null || segmentTriangleWindowCount <= 0)
      {
        segmentStartWindow = null;
        segmentTriangleWindowCount = 0;
        segmentFiniteTriangleWindowCount = 0;
        segmentMaxEdges.Clear();
        return;
      }

      var sortedSegmentEdges = segmentMaxEdges.OrderBy(static e => e).ToList();
      segmentSamples.Add(new NifAttributeExtraMappingPositionSegmentSample(
          StartWindow: segmentStartWindow.Value,
          EndWindow: segmentStartWindow.Value + segmentTriangleWindowCount - 1,
          TriangleWindowCount: segmentTriangleWindowCount,
          FiniteTriangleWindowCount: segmentFiniteTriangleWindowCount,
          StartA: segmentStartA,
          StartB: segmentStartB,
          EndB: segmentEndB,
          EndC: segmentEndC,
          MedianMaxEdge: GetPercentile(sortedSegmentEdges, 0.50),
          MaxEdge: sortedSegmentEdges.Count == 0 ? null : Math.Round(sortedSegmentEdges[^1], 6)));

      segmentStartWindow = null;
      segmentTriangleWindowCount = 0;
      segmentFiniteTriangleWindowCount = 0;
      segmentMaxEdges.Clear();
    }
  }

  private static NifAttributeExtraFirstSegmentProofReview BuildNifAttributeExtraFirstSegmentProofReview(
      List<NifAttributeExtraMappingPositionTriangleSample> samples)
  {
    const double areaEpsilon = 0.000001;
    var nearZeroAreaCount = 0;
    var positiveSignedAreaCount = 0;
    var negativeSignedAreaCount = 0;
    var zeroSignedAreaCount = 0;
    var dominantPlaneSwitchCount = 0;
    var dominantSignedAreaSignSwitchCount = 0;
    var contiguousWindowTransitionCount = 0;
    var nonContiguousWindowTransitionCount = 0;
    var nonAlternatingParityTransitionCount = 0;
    var planeCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

    for (var i = 0; i < samples.Count; i++)
    {
      var sample = samples[i];
      var plane = string.IsNullOrWhiteSpace(sample.DominantAreaPlane)
          ? "unknown"
          : sample.DominantAreaPlane;
      planeCounts[plane] = planeCounts.GetValueOrDefault(plane) + 1;

      if (sample.Area is null || Math.Abs(sample.Area.Value) <= areaEpsilon)
      {
        nearZeroAreaCount++;
      }

      var sign = GetDominantSignedAreaSign(sample, areaEpsilon);
      switch (sign)
      {
        case > 0:
          positiveSignedAreaCount++;
          break;
        case < 0:
          negativeSignedAreaCount++;
          break;
        default:
          zeroSignedAreaCount++;
          break;
      }

      if (i == 0)
      {
        continue;
      }

      var previous = samples[i - 1];
      if (sample.StripWindowIndex == previous.StripWindowIndex + 1)
      {
        contiguousWindowTransitionCount++;
        if (string.Equals(sample.StripWindingParity, previous.StripWindingParity, StringComparison.OrdinalIgnoreCase))
        {
          nonAlternatingParityTransitionCount++;
        }
      }
      else
      {
        nonContiguousWindowTransitionCount++;
      }

      if (!string.IsNullOrWhiteSpace(sample.DominantAreaPlane) &&
          !string.IsNullOrWhiteSpace(previous.DominantAreaPlane) &&
          !string.Equals(sample.DominantAreaPlane, previous.DominantAreaPlane, StringComparison.OrdinalIgnoreCase))
      {
        dominantPlaneSwitchCount++;
      }

      var previousSign = GetDominantSignedAreaSign(previous, areaEpsilon);
      if (previousSign != 0 && sign != 0 && previousSign != sign)
      {
        dominantSignedAreaSignSwitchCount++;
      }
    }

    var reviewFlags = new List<string>();
    if (samples.Count == 0)
    {
      reviewFlags.Add("no-first-segment-triangle-samples");
    }

    if (nearZeroAreaCount > 0)
    {
      reviewFlags.Add($"near-zero-area={nearZeroAreaCount.ToString(CultureInfo.InvariantCulture)}");
    }

    if (nonContiguousWindowTransitionCount > 0)
    {
      reviewFlags.Add($"non-contiguous-windows={nonContiguousWindowTransitionCount.ToString(CultureInfo.InvariantCulture)}");
    }

    if (nonAlternatingParityTransitionCount > 0)
    {
      reviewFlags.Add($"non-alternating-parity={nonAlternatingParityTransitionCount.ToString(CultureInfo.InvariantCulture)}");
    }

    if (dominantPlaneSwitchCount > 0)
    {
      reviewFlags.Add($"dominant-plane-switches={dominantPlaneSwitchCount.ToString(CultureInfo.InvariantCulture)}");
    }

    if (dominantSignedAreaSignSwitchCount > 0)
    {
      reviewFlags.Add($"dominant-sign-switches={dominantSignedAreaSignSwitchCount.ToString(CultureInfo.InvariantCulture)}");
    }

    if (reviewFlags.Count == 0)
    {
      reviewFlags.Add("none");
    }

    return new NifAttributeExtraFirstSegmentProofReview(
        TriangleSampleCount: samples.Count,
        NearZeroAreaCount: nearZeroAreaCount,
        DominantPlaneCounts: planeCounts
            .OrderByDescending(static kvp => kvp.Value)
            .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
            .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
            .ToList(),
        PositiveDominantSignedAreaCount: positiveSignedAreaCount,
        NegativeDominantSignedAreaCount: negativeSignedAreaCount,
        ZeroDominantSignedAreaCount: zeroSignedAreaCount,
        DominantPlaneSwitchCount: dominantPlaneSwitchCount,
        DominantSignedAreaSignSwitchCount: dominantSignedAreaSignSwitchCount,
        ContiguousWindowTransitionCount: contiguousWindowTransitionCount,
        NonContiguousWindowTransitionCount: nonContiguousWindowTransitionCount,
        NonAlternatingParityTransitionCount: nonAlternatingParityTransitionCount,
        ReviewFlags: reviewFlags);

    static int GetDominantSignedAreaSign(NifAttributeExtraMappingPositionTriangleSample sample, double epsilon)
    {
      if (sample.DominantSignedArea is null || Math.Abs(sample.DominantSignedArea.Value) <= epsilon)
      {
        return 0;
      }

      return sample.DominantSignedArea.Value > 0 ? 1 : -1;
    }
  }

  private static double? GetPercentile(List<double> sortedValues, double percentile)
  {
    if (sortedValues.Count == 0)
    {
      return null;
    }

    var index = Math.Clamp((int)Math.Ceiling(percentile * sortedValues.Count) - 1, 0, sortedValues.Count - 1);
    return Math.Round(sortedValues[index], 6);
  }

  private static string GetNifAttributeMappingFitnessPreference(
      NifAttributeExtraMappingPositionFitness? rawFitness,
      NifAttributeExtraMappingPositionFitness? subtractOneFitness)
  {
    var rawMedian = rawFitness?.SegmentedMedianMaxEdge ?? rawFitness?.MedianMaxEdge;
    var subtractOneMedian = subtractOneFitness?.SegmentedMedianMaxEdge ?? subtractOneFitness?.MedianMaxEdge;
    if (rawMedian is null || subtractOneMedian is null)
    {
      return "insufficient";
    }

    var delta = subtractOneMedian.Value - rawMedian.Value;
    if (Math.Abs(delta) <= 0.000001)
    {
      return "tie";
    }

    return delta > 0 ? "raw-zero-based" : "subtract-one";
  }

  private static double? ToNullableDouble(float? value) => value is null ? null : (double)value.Value;

  private static string FormatNifAttributeVertexSample(NifAttributeVertexSample sample)
  {
    var components = sample.Components > 2
        ? $"{FormatNullableDouble(sample.X)},{FormatNullableDouble(sample.Y)},{FormatNullableDouble(sample.Z)}"
        : $"{FormatNullableDouble(sample.X)},{FormatNullableDouble(sample.Y)}";
    var metrics = sample.Attribute.Equals("normal", StringComparison.OrdinalIgnoreCase)
        ? $" len={FormatNullableDouble(sample.VectorLength)}"
        : $" prev={FormatNullableDouble(sample.PreviousDistance)} next={FormatNullableDouble(sample.NextDistance)}";
    return $"v{sample.Index}=({components}){metrics}";
  }

  private static string FormatNullableDouble(double? value)
  {
    return value?.ToString("g6", CultureInfo.InvariantCulture) ?? "null";
  }

  private static string FormatNullableInt(int? value)
  {
    return value?.ToString(CultureInfo.InvariantCulture) ?? "null";
  }

  private static string GetNifAttributeExtraIndexBaseHint(int vertexCount, NifUInt16BeIndexStats indexStats)
  {
    if (indexStats.BigEndianMinIndex == 0 && indexStats.BigEndianMaxIndex < vertexCount)
    {
      return "zero-based-compatible";
    }

    if (indexStats.BigEndianMinIndex == 1 && indexStats.BigEndianMaxIndex == vertexCount - 1)
    {
      return "one-based-or-reserved-zero-ambiguous";
    }

    if (indexStats.BigEndianMinIndex > 0 && indexStats.BigEndianMaxIndex < vertexCount)
    {
      return "zero-index-absent-compatible";
    }

    return "index-range-incompatible";
  }

  private static List<NifTriangleStripPreviewTriangle> BuildNifTriangleStripPreview(List<ushort> indices, int maxTriangles)
  {
    var triangles = new List<NifTriangleStripPreviewTriangle>();
    for (var i = 0; i + 2 < indices.Count && triangles.Count < maxTriangles; i++)
    {
      var a = indices[i];
      var b = indices[i + 1];
      var c = indices[i + 2];
      var degenerate = a == b || a == c || b == c;
      triangles.Add(new NifTriangleStripPreviewTriangle(
          Index: i,
          A: a,
          B: b,
          C: c,
          WindingParity: (i % 2) == 0 ? "even" : "odd",
          Degenerate: degenerate));
    }

    return triangles;
  }

  private static NifTriangleStripStructureStats BuildNifTriangleStripStructureStats(List<ushort> indices)
  {
    var triangleWindowCount = Math.Max(0, indices.Count - 2);
    var degenerateRuns = new List<NifTriangleStripWindowRunSample>();
    var nonDegenerateRuns = new List<NifTriangleStripWindowRunSample>();
    var sentinelRestartValueCount = 0;
    var zeroIndexValueCount = 0;
    var adjacentRepeatCount = 0;
    var mirroredAdjacentRepeatBridgeCount = 0;

    foreach (var index in indices)
    {
      if (index == 0)
      {
        zeroIndexValueCount++;
      }

      if (index == ushort.MaxValue)
      {
        sentinelRestartValueCount++;
      }
    }

    for (var i = 0; i + 1 < indices.Count; i++)
    {
      if (indices[i] == indices[i + 1])
      {
        adjacentRepeatCount++;
      }
    }

    for (var i = 1; i + 2 < indices.Count; i++)
    {
      if (indices[i] == indices[i + 1] &&
          indices[i - 1] == indices[i + 2] &&
          indices[i - 1] != indices[i])
      {
        mirroredAdjacentRepeatBridgeCount++;
      }
    }

    var degenerateWindowCount = 0;
    var runStart = 0;
    bool? currentDegenerate = null;
    for (var window = 0; window < triangleWindowCount; window++)
    {
      var a = indices[window];
      var b = indices[window + 1];
      var c = indices[window + 2];
      var degenerate = a == b || a == c || b == c;
      if (degenerate)
      {
        degenerateWindowCount++;
      }

      if (currentDegenerate is null)
      {
        currentDegenerate = degenerate;
        runStart = window;
        continue;
      }

      if (currentDegenerate.Value != degenerate)
      {
        addRun(currentDegenerate.Value, runStart, window - runStart);
        currentDegenerate = degenerate;
        runStart = window;
      }
    }

    if (currentDegenerate is not null)
    {
      addRun(currentDegenerate.Value, runStart, triangleWindowCount - runStart);
    }

    var hint = sentinelRestartValueCount > 0
        ? "sentinel-restart-markers-present"
        : mirroredAdjacentRepeatBridgeCount > 0
            ? "degenerate-bridge-stitch-candidate"
            : degenerateWindowCount == 0
                ? "continuous-strip-no-degenerate-markers"
                : "degenerate-markers-no-clear-bridge";

    return new NifTriangleStripStructureStats(
        Hint: hint,
        IndexCount: indices.Count,
        TriangleWindowCount: triangleWindowCount,
        DegenerateWindowCount: degenerateWindowCount,
        NonDegenerateWindowCount: triangleWindowCount - degenerateWindowCount,
        DegenerateRunCount: degenerateRuns.Count,
        MaxDegenerateRunLength: degenerateRuns.Count == 0 ? 0 : degenerateRuns.Max(static r => r.Length),
        NonDegenerateRunCount: nonDegenerateRuns.Count,
        MaxNonDegenerateRunLength: nonDegenerateRuns.Count == 0 ? 0 : nonDegenerateRuns.Max(static r => r.Length),
        AverageNonDegenerateRunLength: nonDegenerateRuns.Count == 0 ? 0 : Math.Round(nonDegenerateRuns.Average(static r => r.Length), 2),
        AdjacentRepeatCount: adjacentRepeatCount,
        MirroredAdjacentRepeatBridgeCount: mirroredAdjacentRepeatBridgeCount,
        SentinelRestartValueCount: sentinelRestartValueCount,
        ZeroIndexValueCount: zeroIndexValueCount,
        FirstDegenerateRuns: degenerateRuns.Take(12).ToList(),
        FirstNonDegenerateRuns: nonDegenerateRuns.Take(12).ToList());

    void addRun(bool degenerate, int startWindow, int length)
    {
      if (length <= 0)
      {
        return;
      }

      var run = new NifTriangleStripWindowRunSample(
          StartWindow: startWindow,
          Length: length,
          EndWindow: startWindow + length - 1);
      if (degenerate)
      {
        degenerateRuns.Add(run);
      }
      else
      {
        nonDegenerateRuns.Add(run);
      }
    }
  }

  private static NifAttributeExtraGroupedView BuildNifAttributeExtraGroupedView(string name, ReadOnlySpan<byte> body, int slotCount)
  {
    if (slotCount <= 0 || body.Length == 0)
    {
      return new NifAttributeExtraGroupedView(
          Name: name,
          SlotCount: Math.Max(0, slotCount),
          BodyBytes: body.Length,
          BytesPerSlot: null,
          ExactFit: false,
          RemainderBytes: body.Length,
          PrefixSlots: [],
          RemainderFirst32: ToHex(body[..Math.Min(32, body.Length)]));
    }

    var bytesPerSlot = body.Length / slotCount;
    var remainderBytes = body.Length % slotCount;
    var prefixSlots = new List<NifAttributeExtraGroupSlot>();
    if (bytesPerSlot > 0)
    {
      var prefixSlotCount = Math.Min(slotCount, 24);
      for (var i = 0; i < prefixSlotCount; i++)
      {
        var offset = i * bytesPerSlot;
        var slot = body.Slice(offset, bytesPerSlot);
        prefixSlots.Add(new NifAttributeExtraGroupSlot(
            Index: i,
            Offset: offset,
            Hex: ToHex(slot),
            UInt16LittleEndianPrefix: ReadUInt16Prefix(slot, maxValues: 8),
            UInt16BigEndianPrefix: ReadUInt16BigEndianPrefix(slot, maxValues: 8),
            UInt32LittleEndianPrefix: ReadUInt32Prefix(slot, maxValues: 4),
            UInt32BigEndianPrefix: ReadUInt32BigEndianPrefix(slot, maxValues: 4),
            Float32LittleEndianPrefix: ReadFloat32Prefix(slot, maxValues: 4),
            Float32BigEndianPrefix: ReadFloat32BigEndianPrefix(slot, maxValues: 4)));
      }
    }

    var remainderOffset = bytesPerSlot * slotCount;
    var remainderFirst32 = remainderBytes > 0 && remainderOffset < body.Length
        ? ToHex(body.Slice(remainderOffset, Math.Min(32, body.Length - remainderOffset)))
        : null;
    return new NifAttributeExtraGroupedView(
        Name: name,
        SlotCount: slotCount,
        BodyBytes: body.Length,
        BytesPerSlot: bytesPerSlot > 0 ? bytesPerSlot : null,
        ExactFit: remainderBytes == 0,
        RemainderBytes: remainderBytes,
        PrefixSlots: prefixSlots,
        RemainderFirst32: remainderFirst32);
  }

  private static ReadOnlySpan<byte> SliceNifBlockPayload(byte[] payload, NifBlockInfo block)
  {
    if (block.DataOffset < 0 || block.DataOffset >= payload.Length)
    {
      return ReadOnlySpan<byte>.Empty;
    }

    var safeSize = Math.Min(checked((int)Math.Min(block.Size, int.MaxValue)), payload.Length - block.DataOffset);
    return payload.AsSpan(block.DataOffset, safeSize);
  }

  private static List<StrideCandidate> FindWholeBlockStrideCandidates(int length)
  {
    var candidates = new List<StrideCandidate>();
    foreach (var stride in CommonStreamStrides())
    {
      if (length >= stride && length % stride == 0)
      {
        candidates.Add(new StrideCandidate(stride, length / stride));
      }
    }

    return candidates;
  }

  private static List<BodyStrideCandidate> FindBodyStrideCandidates(int length)
  {
    var candidates = new List<BodyStrideCandidate>();
    foreach (var headerBytes in new[] { 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 48, 56, 64 })
    {
      var bodyLength = length - headerBytes;
      if (bodyLength <= 0)
      {
        continue;
      }

      foreach (var stride in CommonStreamStrides())
      {
        if (bodyLength >= stride && bodyLength % stride == 0)
        {
          candidates.Add(new BodyStrideCandidate(headerBytes, stride, bodyLength / stride));
        }
      }
    }

    return candidates
        .OrderBy(static c => c.HeaderBytes)
        .ThenBy(static c => c.Stride)
        .ThenByDescending(static c => c.Count)
        .ToList();
  }

  private static int[] CommonStreamStrides() => [2, 4, 6, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64];

  private static NifStreamBodyStats AnalyzeNifStreamBody(ReadOnlySpan<byte> body)
  {
    var first16 = ToHex(body[..Math.Min(16, body.Length)]);
    var nonZeroBytes = 0;
    foreach (var value in body)
    {
      if (value != 0)
      {
        nonZeroBytes++;
      }
    }

    var floatCount = body.Length / 4;
    var finiteFloatCount = 0;
    var plausibleFloatCount = 0;
    double? floatMin = null;
    double? floatMax = null;
    for (var i = 0; i < floatCount; i++)
    {
      var value = BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(body.Slice(i * 4, 4)));
      if (!float.IsFinite(value))
      {
        continue;
      }

      finiteFloatCount++;
      var doubleValue = (double)value;
      floatMin = floatMin is null ? doubleValue : Math.Min(floatMin.Value, doubleValue);
      floatMax = floatMax is null ? doubleValue : Math.Max(floatMax.Value, doubleValue);
      var abs = Math.Abs(doubleValue);
      if (abs == 0 || abs is >= 0.0000001 and <= 1_000_000)
      {
        plausibleFloatCount++;
      }
    }

    var uint16Count = body.Length / 2;
    var uint16Values = new HashSet<ushort>();
    ushort uint16Max = 0;
    for (var i = 0; i < uint16Count; i++)
    {
      var value = BinaryPrimitives.ReadUInt16BigEndian(body.Slice(i * 2, 2));
      uint16Values.Add(value);
      uint16Max = Math.Max(uint16Max, value);
    }

    var uint32Count = body.Length / 4;
    var uint32Values = new HashSet<uint>();
    uint uint32Max = 0;
    for (var i = 0; i < uint32Count; i++)
    {
      var value = BinaryPrimitives.ReadUInt32LittleEndian(body.Slice(i * 4, 4));
      uint32Values.Add(value);
      uint32Max = Math.Max(uint32Max, value);
    }

    var strideCandidates = FindWholeBlockStrideCandidates(body.Length);
    var classification = ClassifyNifStreamBody(
        body.Length,
        nonZeroBytes,
        floatCount,
        finiteFloatCount,
        plausibleFloatCount,
        uint16Values.Count,
        uint16Max,
        uint32Values.Count,
        uint32Max,
        strideCandidates);

    return new NifStreamBodyStats(
        ByteLength: body.Length,
        First16: first16,
        AllZero: nonZeroBytes == 0,
        NonZeroBytes: nonZeroBytes,
        Float32Count: floatCount,
        FiniteFloat32Count: finiteFloatCount,
        PlausibleFloat32Count: plausibleFloatCount,
        Float32Min: floatMin,
        Float32Max: floatMax,
        UInt16Count: uint16Count,
        UInt16Distinct: uint16Values.Count,
        UInt16Max: uint16Max,
        UInt32Count: uint32Count,
        UInt32Distinct: uint32Values.Count,
        UInt32Max: uint32Max,
        PayloadStrideCandidates: strideCandidates,
        Classification: classification);
  }

  private static NifStreamEndianStats AnalyzeNifStreamEndian(ReadOnlySpan<byte> body)
  {
    var first16 = ToHex(body[..Math.Min(16, body.Length)]);
    var pairCount = body.Length / 2;
    var littleValues = new List<ushort>(Math.Min(pairCount, 32));
    var bigValues = new List<ushort>(Math.Min(pairCount, 32));
    var littleDistinct = new HashSet<ushort>();
    var bigDistinct = new HashSet<ushort>();
    ushort littleMax = 0;
    ushort bigMax = 0;
    var littleLowValueCount = 0;
    var bigLowValueCount = 0;
    var littleMultipleOf256Count = 0;
    var bigMultipleOf256Count = 0;
    const ushort lowValueThreshold = 4096;

    for (var i = 0; i < pairCount; i++)
    {
      var pair = body.Slice(i * 2, 2);
      var little = BinaryPrimitives.ReadUInt16LittleEndian(pair);
      var big = BinaryPrimitives.ReadUInt16BigEndian(pair);
      if (littleValues.Count < 32)
      {
        littleValues.Add(little);
        bigValues.Add(big);
      }

      littleDistinct.Add(little);
      bigDistinct.Add(big);
      littleMax = Math.Max(littleMax, little);
      bigMax = Math.Max(bigMax, big);
      if (little <= lowValueThreshold)
      {
        littleLowValueCount++;
      }

      if (big <= lowValueThreshold)
      {
        bigLowValueCount++;
      }

      if (little != 0 && little % 256 == 0)
      {
        littleMultipleOf256Count++;
      }

      if (big != 0 && big % 256 == 0)
      {
        bigMultipleOf256Count++;
      }
    }

    var littleLowRatio = pairCount == 0 ? 0 : littleLowValueCount / (double)pairCount;
    var bigLowRatio = pairCount == 0 ? 0 : bigLowValueCount / (double)pairCount;
    var littleMultipleRatio = pairCount == 0 ? 0 : littleMultipleOf256Count / (double)pairCount;
    var bigMultipleRatio = pairCount == 0 ? 0 : bigMultipleOf256Count / (double)pairCount;
    var classification = ClassifyNifStreamEndian(
        body,
        pairCount,
        littleMax,
        bigMax,
        littleLowRatio,
        bigLowRatio,
        littleMultipleRatio,
        bigMultipleRatio,
        littleDistinct.Count,
        bigDistinct.Count);

    return new NifStreamEndianStats(
        ByteLength: body.Length,
        First16: first16,
        PairCount: pairCount,
        LowValueThreshold: lowValueThreshold,
        LittleEndianPrefix: littleValues,
        BigEndianPrefix: bigValues,
        LittleEndianMax: littleMax,
        BigEndianMax: bigMax,
        LittleEndianDistinct: littleDistinct.Count,
        BigEndianDistinct: bigDistinct.Count,
        LittleEndianLowValueCount: littleLowValueCount,
        BigEndianLowValueCount: bigLowValueCount,
        LittleEndianLowValueRatio: Math.Round(littleLowRatio, 4),
        BigEndianLowValueRatio: Math.Round(bigLowRatio, 4),
        LittleEndianMultipleOf256Count: littleMultipleOf256Count,
        BigEndianMultipleOf256Count: bigMultipleOf256Count,
        LittleEndianMultipleOf256Ratio: Math.Round(littleMultipleRatio, 4),
        BigEndianMultipleOf256Ratio: Math.Round(bigMultipleRatio, 4),
        Classification: classification);
  }

  private static string ClassifyNifStreamEndian(
      ReadOnlySpan<byte> body,
      int pairCount,
      ushort littleMax,
      ushort bigMax,
      double littleLowRatio,
      double bigLowRatio,
      double littleMultipleRatio,
      double bigMultipleRatio,
      int littleDistinct,
      int bigDistinct)
  {
    if (pairCount == 0)
    {
      return "empty-u16-body";
    }

    var allZero = true;
    var allFf = true;
    foreach (var value in body)
    {
      allZero &= value == 0;
      allFf &= value == 0xff;
      if (!allZero && !allFf)
      {
        break;
      }
    }

    if (allZero)
    {
      return "all-zero-u16-body";
    }

    if (allFf)
    {
      return "sentinel-ffff-u16-body";
    }

    var bigRangeAdvantage = bigMax > 0 && littleMax >= bigMax * 8;
    var littleRangeAdvantage = littleMax > 0 && bigMax >= littleMax * 8;
    if (bigLowRatio >= 0.80 && (littleLowRatio <= 0.35 || bigRangeAdvantage || littleMultipleRatio >= 0.50) && bigDistinct > 2)
    {
      return "big-endian-u16-lead";
    }

    if (littleLowRatio >= 0.80 && (bigLowRatio <= 0.35 || littleRangeAdvantage || bigMultipleRatio >= 0.50) && littleDistinct > 2)
    {
      return "little-endian-u16-lead";
    }

    if (bigLowRatio >= 0.80 && littleLowRatio >= 0.80)
    {
      return "ambiguous-small-u16";
    }

    return "mixed-u16-body";
  }

  private static NifUInt16BeIndexStats AnalyzeNifUInt16BeIndex(ReadOnlySpan<byte> body)
  {
    var pairCount = body.Length / 2;
    var triangleAligned = body.Length > 0 && body.Length % 6 == 0;
    var triangleCount = body.Length / 6;
    var values = new ushort[pairCount];
    var distinct = new HashSet<ushort>();
    ushort maxIndex = 0;
    ushort minIndex = ushort.MaxValue;
    var firstIndices = new List<ushort>(Math.Min(pairCount, 32));
    var firstTriples = new List<NifUInt16Triple>(Math.Min(triangleCount, 16));
    var degenerateTriangles = 0;

    for (var i = 0; i < pairCount; i++)
    {
      var value = BinaryPrimitives.ReadUInt16BigEndian(body.Slice(i * 2, 2));
      values[i] = value;
      distinct.Add(value);
      maxIndex = Math.Max(maxIndex, value);
      minIndex = Math.Min(minIndex, value);
      if (firstIndices.Count < 32)
      {
        firstIndices.Add(value);
      }
    }

    for (var i = 0; i < triangleCount; i++)
    {
      var offset = i * 6;
      var a = BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offset, 2));
      var b = BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offset + 2, 2));
      var c = BinaryPrimitives.ReadUInt16BigEndian(body.Slice(offset + 4, 2));
      if (firstTriples.Count < 16)
      {
        firstTriples.Add(new NifUInt16Triple(i, a, b, c));
      }

      if (a == b || b == c || a == c)
      {
        degenerateTriangles++;
      }
    }

    var triangleStripWindowCount = Math.Max(0, pairCount - 2);
    var triangleStripDegenerateWindows = 0;
    for (var i = 0; i < triangleStripWindowCount; i++)
    {
      var a = values[i];
      var b = values[i + 1];
      var c = values[i + 2];
      if (a == b || b == c || a == c)
      {
        triangleStripDegenerateWindows++;
      }
    }

    if (pairCount == 0)
    {
      minIndex = 0;
    }

    var degenerateTriangleRatio = triangleCount == 0 ? 0 : Math.Round(degenerateTriangles / (double)triangleCount, 4);
    var triangleStripDegenerateRatio = triangleStripWindowCount == 0 ? 0 : Math.Round(triangleStripDegenerateWindows / (double)triangleStripWindowCount, 4);

    return new NifUInt16BeIndexStats(
        PairCount: pairCount,
        TriangleAligned: triangleAligned,
        TriangleCount: triangleCount,
        BigEndianMinIndex: minIndex,
        BigEndianMaxIndex: maxIndex,
        BigEndianDistinctIndexCount: distinct.Count,
        DegenerateTriangles: degenerateTriangles,
        DegenerateTriangleRatio: degenerateTriangleRatio,
        TriangleStripWindowCount: triangleStripWindowCount,
        TriangleStripNonDegenerateWindowCount: triangleStripWindowCount - triangleStripDegenerateWindows,
        TriangleStripDegenerateWindows: triangleStripDegenerateWindows,
        TriangleStripDegenerateRatio: triangleStripDegenerateRatio,
        TriangleStripLessDegenerateThanTriples: triangleCount > 0 && triangleStripWindowCount > 0 && triangleStripDegenerateRatio < degenerateTriangleRatio,
        FirstBigEndianIndices: firstIndices,
        FirstBigEndianTriples: firstTriples);
  }

  private static NifMeshStreamRoleStats AnalyzeNifMeshBoundStreamRole(ReadOnlySpan<byte> body)
  {
    var bodyStats = AnalyzeNifStreamBody(body);
    var endianStats = body.Length % 2 == 0 ? AnalyzeNifStreamEndian(body) : null;
    var indexStats = body.Length % 2 == 0 ? AnalyzeNifUInt16BeIndex(body) : null;
    var float2Stats = AnalyzeNifFloatVectors(body, components: 2, NifFloatByteTransform.LittleEndian);
    var float3Stats = AnalyzeNifFloatVectors(body, components: 3, NifFloatByteTransform.LittleEndian);
    var rotatedFloat2Stats = AnalyzeNifFloatVectors(body, components: 2, NifFloatByteTransform.RotateRight1);
    var rotatedFloat3Stats = AnalyzeNifFloatVectors(body, components: 3, NifFloatByteTransform.RotateRight1);
    var vertexCountCandidates = FindWholeBlockStrideCandidates(body.Length)
        .Where(static c => c.Stride is 8 or 12 or 16 or 20 or 24 or 28 or 32 or 36 or 40 or 44 or 48 or 56 or 64)
        .Select(static c => c.Count)
        .Distinct()
        .OrderBy(static c => c)
        .ToList();
    var evidence = new List<string>();
    var roleCandidates = new List<string>();
    var primaryRole = "unknown-stream";
    var confidence = 0;
    ushort? indexMax = null;

    if (bodyStats.AllZero)
    {
      return new NifMeshStreamRoleStats(
          PrimaryRole: "all-zero-stream",
          Confidence: 10,
          RoleCandidates: ["all-zero-stream"],
          Evidence: ["all bytes are zero"],
          VertexCountCandidates: vertexCountCandidates,
          IndexMax: null,
          IndexPairCount: null,
          BodyStats: bodyStats,
          EndianStats: endianStats,
          IndexStats: indexStats,
          Float2Stats: float2Stats,
          Float3Stats: float3Stats,
          RotatedFloat2Stats: rotatedFloat2Stats,
          RotatedFloat3Stats: rotatedFloat3Stats);
    }

    if (bodyStats.Classification is "u32-sentinel-mask-body" or "u32-repeated-pattern-body")
    {
      return new NifMeshStreamRoleStats(
          PrimaryRole: bodyStats.Classification,
          Confidence: 25,
          RoleCandidates: [bodyStats.Classification],
          Evidence: [$"stream body classifier={bodyStats.Classification}; low-variation uint32 body is not promoted to geometry"],
          VertexCountCandidates: vertexCountCandidates,
          IndexMax: null,
          IndexPairCount: null,
          BodyStats: bodyStats,
          EndianStats: endianStats,
          IndexStats: indexStats,
          Float2Stats: float2Stats,
          Float3Stats: float3Stats,
          RotatedFloat2Stats: rotatedFloat2Stats,
          RotatedFloat3Stats: rotatedFloat3Stats);
    }

    if (endianStats?.Classification == "big-endian-u16-lead" && indexStats is not null && indexStats.BigEndianDistinctIndexCount >= 8)
    {
      indexMax = indexStats.BigEndianMaxIndex;
      evidence.Add($"big-endian uint16 lead, maxIndex={indexStats.BigEndianMaxIndex}, distinct={indexStats.BigEndianDistinctIndexCount}");
      if (indexStats.TriangleStripLessDegenerateThanTriples)
      {
        primaryRole = "index-u16be-strip-lead";
        confidence = 85;
        roleCandidates.Add(primaryRole);
        evidence.Add($"strip windows less degenerate than fixed triples ({indexStats.TriangleStripDegenerateRatio:0.####} < {indexStats.DegenerateTriangleRatio:0.####})");
      }
      else if (indexStats.TriangleAligned && indexStats.DegenerateTriangleRatio <= 0.25)
      {
        primaryRole = "index-u16be-list-lead";
        confidence = 80;
        roleCandidates.Add(primaryRole);
        evidence.Add($"fixed triples are low-degenerate ({indexStats.DegenerateTriangleRatio:0.####})");
      }
      else if (indexStats.DegenerateTriangleRatio <= 0.90 || indexStats.TriangleStripDegenerateRatio <= 0.90)
      {
        primaryRole = "index-u16be-lead";
        confidence = 60;
        roleCandidates.Add(primaryRole);
        evidence.Add($"compact big-endian uint16 stream without a proven topology (degRatio={indexStats.DegenerateTriangleRatio:0.####}, stripDegRatio={indexStats.TriangleStripDegenerateRatio:0.####})");
      }
    }

    if (endianStats?.Classification == "ambiguous-small-u16" && indexStats is not null && indexStats.BigEndianDistinctIndexCount >= 8 && indexStats.TriangleAligned && indexStats.DegenerateTriangleRatio <= 0.50)
    {
      indexMax = indexStats.BigEndianMaxIndex;
      evidence.Add($"ambiguous-small-u16 lead, maxIndex={indexStats.BigEndianMaxIndex}, distinct={indexStats.BigEndianDistinctIndexCount}");
      primaryRole = "index-u16be-lead";
      confidence = 55;
      roleCandidates.Add(primaryRole);
      evidence.Add($"ambiguous endianness uint16 stream, triangle-aligned low-degenerate ({indexStats.DegenerateTriangleRatio:0.####})");
    }

    if (endianStats?.Classification == "little-endian-u16-lead" && indexStats is not null && indexStats.BigEndianDistinctIndexCount >= 8 && indexStats.TriangleAligned && indexStats.DegenerateTriangleRatio <= 0.90 && primaryRole == "unknown-stream")
    {
      indexMax = indexStats.BigEndianMaxIndex;
      evidence.Add($"little-endian u16 lead, be-maxIndex={indexStats.BigEndianMaxIndex}, be-distinct={indexStats.BigEndianDistinctIndexCount}");
      primaryRole = "index-u16le-lead";
      confidence = 45;
      roleCandidates.Add(primaryRole);
      evidence.Add($"little-endian uint16 lead with guards; low confidence ({indexStats.DegenerateTriangleRatio:0.####})");
    }

    if (float3Stats.VectorCount >= 3 && float3Stats.FiniteVectorRatio >= 0.95 && float3Stats.PlausibleValueRatio >= 0.95)
    {
      if (float3Stats.NearUnitVectorRatio >= 0.75 && float3Stats.NonZeroVectorRatio >= 0.50)
      {
        roleCandidates.Add("normal-float3-lead");
        evidence.Add($"float3 vectors are mostly unit length ({float3Stats.NearUnitVectorRatio:0.####})");
        if (confidence < 75)
        {
          primaryRole = "normal-float3-lead";
          confidence = 75;
        }
      }
      else if (float3Stats.MaxExtent >= 0.0001 && float3Stats.NonZeroVectorRatio >= 0.50)
      {
        roleCandidates.Add("position-float3-lead");
        evidence.Add($"float3 vectors have finite nonzero bounds, extent={float3Stats.MaxExtent:0.####}");
        if (confidence < 65)
        {
          primaryRole = "position-float3-lead";
          confidence = 65;
        }
      }
      else
      {
        roleCandidates.Add("float3-compatible-lead");
        if (confidence < 45)
        {
          primaryRole = "float3-compatible-lead";
          confidence = 45;
        }
      }
    }

    if (float2Stats.VectorCount >= 3 && float2Stats.FiniteVectorRatio >= 0.95 && float2Stats.UvRangeRatio >= 0.80 && float2Stats.NonZeroVectorRatio >= 0.50)
    {
      roleCandidates.Add("uv-float2-lead");
      evidence.Add($"float2 values are mostly in UV-ish range ({float2Stats.UvRangeRatio:0.####})");
      if (confidence < 55)
      {
        primaryRole = "uv-float2-lead";
        confidence = 55;
      }
    }

    if (rotatedFloat3Stats.VectorCount >= 3 && rotatedFloat3Stats.FiniteVectorRatio >= 0.95 && rotatedFloat3Stats.PlausibleValueRatio >= 0.95)
    {
      if (rotatedFloat3Stats.NearUnitVectorRatio >= 0.75 && rotatedFloat3Stats.NonZeroVectorRatio >= 0.50)
      {
        roleCandidates.Add("normal-float3-ror1-lead");
        evidence.Add($"rotate-right-1 float3 vectors are mostly unit length ({rotatedFloat3Stats.NearUnitVectorRatio:0.####})");
        if (confidence < 85)
        {
          primaryRole = "normal-float3-ror1-lead";
          confidence = 85;
        }
      }
      else if (rotatedFloat3Stats.MaxExtent >= 0.0001 && rotatedFloat3Stats.NonZeroVectorRatio >= 0.50)
      {
        roleCandidates.Add("position-float3-ror1-lead");
        evidence.Add($"rotate-right-1 float3 vectors have finite nonzero bounds, extent={rotatedFloat3Stats.MaxExtent:0.####}");
        if (confidence < 75)
        {
          primaryRole = "position-float3-ror1-lead";
          confidence = 75;
        }
      }
    }

    if (rotatedFloat2Stats.VectorCount >= 3 && rotatedFloat2Stats.FiniteVectorRatio >= 0.95 && rotatedFloat2Stats.UvRangeRatio >= 0.80 && rotatedFloat2Stats.NonZeroVectorRatio >= 0.50)
    {
      roleCandidates.Add("uv-float2-ror1-lead");
      evidence.Add($"rotate-right-1 float2 values are mostly in UV-ish range ({rotatedFloat2Stats.UvRangeRatio:0.####})");
      if (confidence < 80)
      {
        primaryRole = "uv-float2-ror1-lead";
        confidence = 80;
      }
    }

    if (roleCandidates.Count == 0)
    {
      roleCandidates.Add(bodyStats.Classification);
      evidence.Add($"stream body classifier={bodyStats.Classification}");
      primaryRole = bodyStats.Classification;
      confidence = bodyStats.Classification == "empty-body" ? 10 : 25;
    }

    return new NifMeshStreamRoleStats(
        PrimaryRole: primaryRole,
        Confidence: confidence,
        RoleCandidates: roleCandidates.Distinct(StringComparer.OrdinalIgnoreCase).ToList(),
        Evidence: evidence,
        VertexCountCandidates: vertexCountCandidates,
        IndexMax: indexMax,
        IndexPairCount: indexStats?.PairCount,
        BodyStats: bodyStats,
        EndianStats: endianStats,
        IndexStats: indexStats,
        Float2Stats: float2Stats,
        Float3Stats: float3Stats,
        RotatedFloat2Stats: rotatedFloat2Stats,
        RotatedFloat3Stats: rotatedFloat3Stats);
  }

  private static NifFloatVectorStats AnalyzeNifFloatVectors(ReadOnlySpan<byte> body, int components, NifFloatByteTransform transform)
  {
    var bytesPerVector = checked(components * 4);
    var aligned = body.Length > 0 && body.Length % bytesPerVector == 0;
    var vectorCount = body.Length / bytesPerVector;
    var finiteVectors = 0;
    var plausibleValues = 0;
    var totalValues = vectorCount * components;
    var nonZeroVectors = 0;
    var nearUnitVectors = 0;
    var uvRangeValues = 0;
    double? minX = null;
    double? maxX = null;
    double? minY = null;
    double? maxY = null;
    double? minZ = null;
    double? maxZ = null;
    var prefix = new List<NifFloatVectorPrefix>(Math.Min(vectorCount, 12));

    for (var i = 0; i < vectorCount; i++)
    {
      var offset = i * bytesPerVector;
      var values = new double[components];
      var finite = true;
      var nonZero = false;
      for (var component = 0; component < components; component++)
      {
        var value = ReadFiniteFloat32(body.Slice(offset + (component * 4), 4), transform);
        if (value is null)
        {
          finite = false;
          values[component] = double.NaN;
          continue;
        }

        var doubleValue = (double)value.Value;
        values[component] = doubleValue;
        var abs = Math.Abs(doubleValue);
        if (abs > 0.0000001)
        {
          nonZero = true;
        }

        if (abs == 0 || abs is >= 0.0000001 and <= 1_000_000)
        {
          plausibleValues++;
        }

        if (doubleValue is >= -10 and <= 10)
        {
          uvRangeValues++;
        }
      }

      if (prefix.Count < 12)
      {
        prefix.Add(new NifFloatVectorPrefix(
            Index: i,
            X: finite ? values[0] : null,
            Y: finite && components > 1 ? values[1] : null,
            Z: finite && components > 2 ? values[2] : null));
      }

      if (!finite)
      {
        continue;
      }

      finiteVectors++;
      if (nonZero)
      {
        nonZeroVectors++;
      }

      minX = minX is null ? values[0] : Math.Min(minX.Value, values[0]);
      maxX = maxX is null ? values[0] : Math.Max(maxX.Value, values[0]);
      if (components > 1)
      {
        minY = minY is null ? values[1] : Math.Min(minY.Value, values[1]);
        maxY = maxY is null ? values[1] : Math.Max(maxY.Value, values[1]);
      }

      if (components > 2)
      {
        minZ = minZ is null ? values[2] : Math.Min(minZ.Value, values[2]);
        maxZ = maxZ is null ? values[2] : Math.Max(maxZ.Value, values[2]);
      }

      if (components == 3)
      {
        var length = Math.Sqrt((values[0] * values[0]) + (values[1] * values[1]) + (values[2] * values[2]));
        if (length is >= 0.75 and <= 1.25)
        {
          nearUnitVectors++;
        }
      }
    }

    var extentX = minX is null || maxX is null ? 0 : maxX.Value - minX.Value;
    var extentY = minY is null || maxY is null ? 0 : maxY.Value - minY.Value;
    var extentZ = minZ is null || maxZ is null ? 0 : maxZ.Value - minZ.Value;

    return new NifFloatVectorStats(
        Transform: transform.ToString(),
        Components: components,
        Aligned: aligned,
        VectorCount: vectorCount,
        FiniteVectorCount: finiteVectors,
        FiniteVectorRatio: vectorCount == 0 ? 0 : Math.Round(finiteVectors / (double)vectorCount, 4),
        PlausibleValueRatio: totalValues == 0 ? 0 : Math.Round(plausibleValues / (double)totalValues, 4),
        NonZeroVectorCount: nonZeroVectors,
        NonZeroVectorRatio: vectorCount == 0 ? 0 : Math.Round(nonZeroVectors / (double)vectorCount, 4),
        NearUnitVectorCount: nearUnitVectors,
        NearUnitVectorRatio: vectorCount == 0 ? 0 : Math.Round(nearUnitVectors / (double)vectorCount, 4),
        UvRangeRatio: totalValues == 0 ? 0 : Math.Round(uvRangeValues / (double)totalValues, 4),
        MinX: minX,
        MaxX: maxX,
        MinY: minY,
        MaxY: maxY,
        MinZ: minZ,
        MaxZ: maxZ,
        MaxExtent: Math.Round(Math.Max(extentX, Math.Max(extentY, extentZ)), 6),
        Prefix: prefix);
  }

  private static float? ReadFiniteFloat32(ReadOnlySpan<byte> bytes, NifFloatByteTransform transform)
  {
    if (bytes.Length < 4)
    {
      return null;
    }

    var bits = transform switch
    {
      NifFloatByteTransform.LittleEndian => BinaryPrimitives.ReadInt32LittleEndian(bytes),
      NifFloatByteTransform.RotateRight1 => bytes[3] | (bytes[0] << 8) | (bytes[1] << 16) | (bytes[2] << 24),
      _ => BinaryPrimitives.ReadInt32LittleEndian(bytes)
    };
    var value = BitConverter.Int32BitsToSingle(bits);
    return float.IsFinite(value) ? value : null;
  }

  private static List<NifMeshBindingPairingSample> FindNifMeshBindingPairings(
      string archiveName,
      ArchiveEntrySample entry,
      ManifestEntryBrief? manifestEntry,
      NifBlockInfo meshBlock,
      List<NifMeshBoundStreamSummary> streams)
  {
    var pairings = new List<NifMeshBindingPairingSample>();
    var indexStreams = streams
        .Where(static s => s.RoleStats.PrimaryRole.StartsWith("index-", StringComparison.OrdinalIgnoreCase) && s.RoleStats.IndexMax is not null)
        .ToList();
    var vertexStreams = streams
        .Where(static s => !s.RoleStats.PrimaryRole.StartsWith("index-", StringComparison.OrdinalIgnoreCase) && s.RoleStats.VertexCountCandidates.Count > 0)
        .ToList();

    foreach (var indexStream in indexStreams)
    {
      var maxIndex = indexStream.RoleStats.IndexMax!.Value;
      foreach (var vertexStream in vertexStreams)
      {
        if (vertexStream.TargetBlockIndex == indexStream.TargetBlockIndex)
        {
          continue;
        }

        var compatibleVertexCount = vertexStream.RoleStats.VertexCountCandidates
            .Where(count => count > maxIndex)
            .OrderBy(static count => count)
            .FirstOrDefault();
        if (compatibleVertexCount <= 0)
        {
          continue;
        }

        var confidence = Math.Min(indexStream.RoleStats.Confidence, vertexStream.RoleStats.Confidence);
        if (compatibleVertexCount == maxIndex + 1)
        {
          confidence = Math.Min(100, confidence + 10);
        }

        var dataStreamMetadataScore = GetNifDataStreamMetadataScore(indexStream, vertexStream);
        var coverageRatio = compatibleVertexCount == 0 ? 0 : Math.Round((maxIndex + 1) / (double)compatibleVertexCount, 4);
        pairings.Add(new NifMeshBindingPairingSample(
            ArchiveName: archiveName,
            EntryIndex: entry.Index,
            IdPrefix: entry.IdPrefix,
            ManifestEntryIndex: manifestEntry?.Index,
            MeshBlockIndex: meshBlock.Index,
            MeshSize: meshBlock.Size,
            IndexMeshPayloadOffset: indexStream.MeshPayloadOffset,
            IndexBlockIndex: indexStream.TargetBlockIndex,
            IndexDeclaredPayloadBytes: indexStream.DeclaredPayloadBytes,
            IndexDataStreamUsage: indexStream.DataStreamUsage,
            IndexDataStreamAccess: indexStream.DataStreamAccess,
            IndexRole: indexStream.RoleStats.PrimaryRole,
            IndexMax: maxIndex,
            IndexPairCount: indexStream.RoleStats.IndexPairCount,
            VertexMeshPayloadOffset: vertexStream.MeshPayloadOffset,
            VertexBlockIndex: vertexStream.TargetBlockIndex,
            VertexDeclaredPayloadBytes: vertexStream.DeclaredPayloadBytes,
            VertexDataStreamUsage: vertexStream.DataStreamUsage,
            VertexDataStreamAccess: vertexStream.DataStreamAccess,
            VertexRole: vertexStream.RoleStats.PrimaryRole,
            VertexCount: compatibleVertexCount,
            IndexCoverageRatio: coverageRatio,
            DataStreamMetadataScore: dataStreamMetadataScore,
            Confidence: confidence));
      }
    }

    return pairings
        .OrderByDescending(static p => p.Confidence)
        .ThenByDescending(static p => p.IndexCoverageRatio)
        .ThenByDescending(static p => p.DataStreamMetadataScore)
        .ThenBy(static p => p.IndexMeshPayloadOffset)
        .ThenBy(static p => p.VertexMeshPayloadOffset)
        .Take(16)
        .ToList();
  }

  private static int GetNifDataStreamMetadataScore(params NifMeshBoundStreamSummary[] streams)
  {
    var scored = streams
        .Where(static s => !string.IsNullOrWhiteSpace(s.DataStreamUsage) || !string.IsNullOrWhiteSpace(s.DataStreamAccess))
        .ToList();
    var score = scored.Count;
    var accessValues = scored
        .Select(static s => s.DataStreamAccess)
        .Where(static v => !string.IsNullOrWhiteSpace(v))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .Count();
    if (scored.Count > 1 && accessValues == 1)
    {
      score++;
    }

    var usageValues = scored
        .Select(static s => s.DataStreamUsage)
        .Where(static v => !string.IsNullOrWhiteSpace(v))
        .Distinct(StringComparer.OrdinalIgnoreCase)
        .Count();
    if (usageValues > 1)
    {
      score++;
    }

    return score;
  }

  private static List<NifMeshBoundStreamSummary> BuildNifMeshBoundStreamSummaries(
      byte[] payload,
      NifHeaderInfo header,
      NifBlockInfo meshBlock)
  {
    var blocksByIndex = header.Blocks.ToDictionary(static b => b.Index);
    var streamSummaries = new List<NifMeshBoundStreamSummary>();
    foreach (var candidate in meshBlock.DataStreamReferenceCandidates.OrderBy(static c => c.PayloadOffset).ThenBy(static c => c.TargetBlockIndex))
    {
      blocksByIndex.TryGetValue(candidate.TargetBlockIndex, out var targetBlock);
      ReadOnlySpan<byte> targetPayload = targetBlock is null
          ? ReadOnlySpan<byte>.Empty
          : SliceNifBlockPayload(payload, targetBlock);
      uint? declaredPayloadBytes = null;
      int? headerBytes = null;
      var bodyFirst16 = string.Empty;
      NifMeshStreamRoleStats roleStats;
      if (targetPayload.Length >= 4)
      {
        declaredPayloadBytes = BinaryPrimitives.ReadUInt32LittleEndian(targetPayload[..4]);
        if (declaredPayloadBytes.Value <= targetPayload.Length)
        {
          headerBytes = targetPayload.Length - checked((int)declaredPayloadBytes.Value);
          var body = targetPayload.Slice(headerBytes.Value, checked((int)declaredPayloadBytes.Value));
          bodyFirst16 = ToHex(body[..Math.Min(16, body.Length)]);
          roleStats = AnalyzeNifMeshBoundStreamRole(body);
        }
        else
        {
          roleStats = NifMeshStreamRoleStats.Invalid("declared-payload-past-block");
        }
      }
      else
      {
        roleStats = NifMeshStreamRoleStats.Invalid("stream-block-too-small");
      }

      streamSummaries.Add(new NifMeshBoundStreamSummary(
          MeshPayloadOffset: candidate.PayloadOffset,
          TargetBlockIndex: candidate.TargetBlockIndex,
          TargetTypeName: candidate.TargetTypeName,
          DataStreamUsage: candidate.TargetDataStreamUsage,
          DataStreamAccess: candidate.TargetDataStreamAccess,
          TargetSize: candidate.TargetSize,
          TargetFirst16: candidate.TargetFirst16,
          DeclaredPayloadBytes: declaredPayloadBytes,
          HeaderBytes: headerBytes,
          BodyFirst16: bodyFirst16,
          MaybeStringIndex: candidate.MaybeStringIndex,
          StringValue: candidate.StringValue,
          RoleStats: roleStats));
    }

    return streamSummaries;
  }

  private static List<NifMeshProbePairing> FindNifMeshProbePairings(List<NifMeshBoundStreamSummary> streams)
  {
    var pairings = new List<NifMeshProbePairing>();
    var indexStreams = streams
        .Where(static s => s.RoleStats.PrimaryRole.StartsWith("index-", StringComparison.OrdinalIgnoreCase) && s.RoleStats.IndexMax is not null)
        .ToList();
    var vertexStreams = streams
        .Where(static s => !s.RoleStats.PrimaryRole.StartsWith("index-", StringComparison.OrdinalIgnoreCase) && s.RoleStats.VertexCountCandidates.Count > 0)
        .ToList();

    foreach (var indexStream in indexStreams)
    {
      var maxIndex = indexStream.RoleStats.IndexMax!.Value;
      foreach (var vertexStream in vertexStreams)
      {
        if (vertexStream.TargetBlockIndex == indexStream.TargetBlockIndex)
        {
          continue;
        }

        var compatibleVertexCount = vertexStream.RoleStats.VertexCountCandidates
            .Where(count => count > maxIndex)
            .OrderBy(static count => count)
            .FirstOrDefault();
        if (compatibleVertexCount <= 0)
        {
          continue;
        }

        var confidence = Math.Min(indexStream.RoleStats.Confidence, vertexStream.RoleStats.Confidence);
        if (compatibleVertexCount == maxIndex + 1)
        {
          confidence = Math.Min(100, confidence + 10);
        }

        var dataStreamMetadataScore = GetNifDataStreamMetadataScore(indexStream, vertexStream);
        pairings.Add(new NifMeshProbePairing(
            IndexMeshPayloadOffset: indexStream.MeshPayloadOffset,
            IndexBlockIndex: indexStream.TargetBlockIndex,
            IndexDeclaredPayloadBytes: indexStream.DeclaredPayloadBytes,
            IndexDataStreamUsage: indexStream.DataStreamUsage,
            IndexDataStreamAccess: indexStream.DataStreamAccess,
            IndexRole: indexStream.RoleStats.PrimaryRole,
            IndexMax: maxIndex,
            IndexPairCount: indexStream.RoleStats.IndexPairCount,
            VertexMeshPayloadOffset: vertexStream.MeshPayloadOffset,
            VertexBlockIndex: vertexStream.TargetBlockIndex,
            VertexDeclaredPayloadBytes: vertexStream.DeclaredPayloadBytes,
            VertexDataStreamUsage: vertexStream.DataStreamUsage,
            VertexDataStreamAccess: vertexStream.DataStreamAccess,
            VertexRole: vertexStream.RoleStats.PrimaryRole,
            VertexCount: compatibleVertexCount,
            IndexCoverageRatio: compatibleVertexCount == 0 ? 0 : Math.Round((maxIndex + 1) / (double)compatibleVertexCount, 4),
            DataStreamMetadataScore: dataStreamMetadataScore,
            Confidence: confidence));
      }
    }

    return pairings
        .OrderByDescending(static p => p.Confidence)
        .ThenByDescending(static p => p.IndexCoverageRatio)
        .ThenByDescending(static p => p.DataStreamMetadataScore)
        .ThenBy(static p => p.IndexMeshPayloadOffset)
        .ThenBy(static p => p.VertexMeshPayloadOffset)
        .Take(16)
        .ToList();
  }

  private static List<NifMeshAttributeSetSample> FindNifMeshAttributeSets(
      string? archiveName,
      ArchiveEntrySample? entry,
      ManifestEntryBrief? manifestEntry,
      NifBlockInfo meshBlock,
      List<NifMeshBoundStreamSummary> streams)
  {
    var positions = streams
        .Where(static s => s.RoleStats.PrimaryRole.StartsWith("position-float3", StringComparison.OrdinalIgnoreCase))
        .Select(static s => (Stream: s, VertexCount: GetPrimaryRoleVertexCount(s)))
        .Where(static s => s.VertexCount is > 0)
        .ToList();
    var normals = streams
        .Where(static s => s.RoleStats.PrimaryRole.StartsWith("normal-float3", StringComparison.OrdinalIgnoreCase))
        .Select(static s => (Stream: s, VertexCount: GetPrimaryRoleVertexCount(s)))
        .Where(static s => s.VertexCount is > 0)
        .ToList();
    var uvs = streams
        .Where(static s => s.RoleStats.PrimaryRole.StartsWith("uv-float2", StringComparison.OrdinalIgnoreCase))
        .Select(static s => (Stream: s, VertexCount: GetPrimaryRoleVertexCount(s)))
        .Where(static s => s.VertexCount is > 0)
        .ToList();
    var sets = new List<NifMeshAttributeSetSample>();
    var hasBoundIndexCandidate = streams.Any(static s => s.RoleStats.PrimaryRole.StartsWith("index-", StringComparison.OrdinalIgnoreCase));

    foreach (var position in positions)
    {
      foreach (var normal in normals)
      {
        foreach (var uv in uvs)
        {
          if (position.VertexCount != normal.VertexCount || position.VertexCount != uv.VertexCount)
          {
            continue;
          }

          var confidence = Math.Min(position.Stream.RoleStats.Confidence, Math.Min(normal.Stream.RoleStats.Confidence, uv.Stream.RoleStats.Confidence));
          var dataStreamMetadataScore = GetNifDataStreamMetadataScore(position.Stream, normal.Stream, uv.Stream);
          var topology = AnalyzeNifAttributeTopology(position.VertexCount!.Value, hasBoundIndexCandidate);
          var extraStreams = FindNifAttributeSetExtraStreams(
              streams,
              position.Stream,
              normal.Stream,
              uv.Stream,
              position.VertexCount.Value,
              topology);
          sets.Add(new NifMeshAttributeSetSample(
              ArchiveName: archiveName,
              EntryIndex: entry?.Index,
              IdPrefix: entry?.IdPrefix,
              ManifestEntryIndex: manifestEntry?.Index,
              MeshBlockIndex: meshBlock.Index,
              MeshSize: meshBlock.Size,
              VertexCount: position.VertexCount!.Value,
              Confidence: confidence,
              DataStreamMetadataScore: dataStreamMetadataScore,
              Topology: topology,
              PositionMeshPayloadOffset: position.Stream.MeshPayloadOffset,
              PositionBlockIndex: position.Stream.TargetBlockIndex,
              PositionDeclaredPayloadBytes: position.Stream.DeclaredPayloadBytes,
              PositionDataStreamUsage: position.Stream.DataStreamUsage,
              PositionDataStreamAccess: position.Stream.DataStreamAccess,
              PositionRole: position.Stream.RoleStats.PrimaryRole,
              NormalMeshPayloadOffset: normal.Stream.MeshPayloadOffset,
              NormalBlockIndex: normal.Stream.TargetBlockIndex,
              NormalDeclaredPayloadBytes: normal.Stream.DeclaredPayloadBytes,
              NormalDataStreamUsage: normal.Stream.DataStreamUsage,
              NormalDataStreamAccess: normal.Stream.DataStreamAccess,
              NormalRole: normal.Stream.RoleStats.PrimaryRole,
              UvMeshPayloadOffset: uv.Stream.MeshPayloadOffset,
              UvBlockIndex: uv.Stream.TargetBlockIndex,
              UvDeclaredPayloadBytes: uv.Stream.DeclaredPayloadBytes,
              UvDataStreamUsage: uv.Stream.DataStreamUsage,
              UvDataStreamAccess: uv.Stream.DataStreamAccess,
              UvRole: uv.Stream.RoleStats.PrimaryRole,
              ExtraStreams: extraStreams));
        }
      }
    }

    return sets
        .OrderByDescending(static s => s.Confidence)
        .ThenByDescending(static s => s.DataStreamMetadataScore)
        .ThenBy(static s => s.PositionMeshPayloadOffset)
        .ThenBy(static s => s.NormalMeshPayloadOffset)
        .ThenBy(static s => s.UvMeshPayloadOffset)
        .Take(16)
        .ToList();
  }

  private static List<NifAttributeExtraStreamSample> FindNifAttributeSetExtraStreams(
      List<NifMeshBoundStreamSummary> streams,
      NifMeshBoundStreamSummary position,
      NifMeshBoundStreamSummary normal,
      NifMeshBoundStreamSummary uv,
      int vertexCount,
      NifAttributeTopologyStats topology)
  {
    return streams
        .Where(s => !IsSameNifMeshStream(s, position) && !IsSameNifMeshStream(s, normal) && !IsSameNifMeshStream(s, uv))
        .OrderBy(static s => s.MeshPayloadOffset)
        .ThenBy(static s => s.TargetBlockIndex)
        .Select(s =>
        {
          var bytesPerVertex = GetDivisibleByteRatio(s.DeclaredPayloadBytes, vertexCount);
          var bytesPerListTriangle = GetDivisibleByteRatio(s.DeclaredPayloadBytes, topology.TriangleListTriangleCount);
          var bytesPerStripOrFanTriangle = GetDivisibleByteRatio(s.DeclaredPayloadBytes, topology.TriangleStripTriangleCount);
          var bytesPerQuad = GetDivisibleByteRatio(s.DeclaredPayloadBytes, topology.QuadListQuadCount);
          var fitSummary = FormatNifAttributeExtraFit(bytesPerVertex, bytesPerListTriangle, bytesPerStripOrFanTriangle, bytesPerQuad);
          return new NifAttributeExtraStreamSample(
                  MeshPayloadOffset: s.MeshPayloadOffset,
                  BlockIndex: s.TargetBlockIndex,
                  DeclaredPayloadBytes: s.DeclaredPayloadBytes,
                  DataStreamUsage: s.DataStreamUsage,
                  DataStreamAccess: s.DataStreamAccess,
                  Role: s.RoleStats.PrimaryRole,
                  RoleConfidence: s.RoleStats.Confidence,
                  BytesPerVertex: bytesPerVertex,
                  BytesPerTriangleListTriangle: bytesPerListTriangle,
                  BytesPerStripOrFanTriangle: bytesPerStripOrFanTriangle,
                  BytesPerQuad: bytesPerQuad,
                  FitSummary: fitSummary);
        })
        .Take(16)
        .ToList();
  }

  private static bool IsSameNifMeshStream(NifMeshBoundStreamSummary left, NifMeshBoundStreamSummary right)
  {
    return left.MeshPayloadOffset == right.MeshPayloadOffset && left.TargetBlockIndex == right.TargetBlockIndex;
  }

  private static NifResidualPositionClassifierReview? BuildNifResidualPositionClassifierReview(
      int? vectorCount,
      double? finiteVectorRatio,
      double? plausibleValueRatio,
      double? nonZeroVectorRatio,
      double? maxExtent)
  {
    if (vectorCount is null &&
        finiteVectorRatio is null &&
        plausibleValueRatio is null &&
        nonZeroVectorRatio is null &&
        maxExtent is null)
    {
      return null;
    }

    const int minVectorCount = 3;
    const double minFiniteVectorRatio = 0.95;
    const double minPlausibleValueRatio = 0.95;
    const double minNonZeroVectorRatio = 0.50;
    const double minMaxExtent = 0.0001;

    static string formatValue(double? value)
    {
      return value is null ? "missing" : value.Value.ToString("0.####", CultureInfo.InvariantCulture);
    }

    var missReasons = new List<string>();
    if (vectorCount is null || vectorCount.Value < minVectorCount)
    {
      missReasons.Add($"VectorCount {vectorCount?.ToString(CultureInfo.InvariantCulture) ?? "missing"} < {minVectorCount}");
    }

    if (finiteVectorRatio is null || finiteVectorRatio.Value < minFiniteVectorRatio)
    {
      missReasons.Add($"FiniteVectorRatio {formatValue(finiteVectorRatio)} < {minFiniteVectorRatio.ToString("0.##", CultureInfo.InvariantCulture)}");
    }

    if (plausibleValueRatio is null || plausibleValueRatio.Value < minPlausibleValueRatio)
    {
      missReasons.Add($"PlausibleValueRatio {formatValue(plausibleValueRatio)} < {minPlausibleValueRatio.ToString("0.##", CultureInfo.InvariantCulture)}");
    }

    if (maxExtent is null || maxExtent.Value < minMaxExtent)
    {
      missReasons.Add($"MaxExtent {formatValue(maxExtent)} < {minMaxExtent.ToString("0.####", CultureInfo.InvariantCulture)}");
    }

    if (nonZeroVectorRatio is null || nonZeroVectorRatio.Value < minNonZeroVectorRatio)
    {
      missReasons.Add($"NonZeroVectorRatio {formatValue(nonZeroVectorRatio)} < {minNonZeroVectorRatio.ToString("0.##", CultureInfo.InvariantCulture)}");
    }

    var nonPlausibleStrictInputsPass =
        vectorCount is >= minVectorCount &&
        finiteVectorRatio is >= minFiniteVectorRatio &&
        maxExtent is >= minMaxExtent &&
        nonZeroVectorRatio is >= minNonZeroVectorRatio;
    var maxPlausibleThresholdForThisSample = nonPlausibleStrictInputsPass ? plausibleValueRatio : null;

    return new NifResidualPositionClassifierReview(
        ClassifierRole: "position-float3-ror1-lead",
        CandidateOnly: true,
        MinVectorCount: minVectorCount,
        MinFiniteVectorRatio: minFiniteVectorRatio,
        MinPlausibleValueRatio: minPlausibleValueRatio,
        MinNonZeroVectorRatio: minNonZeroVectorRatio,
        MinMaxExtent: minMaxExtent,
        VectorCount: vectorCount,
        FiniteVectorRatio: finiteVectorRatio,
        PlausibleValueRatio: plausibleValueRatio,
        NonZeroVectorRatio: nonZeroVectorRatio,
        MaxExtent: maxExtent,
        PassesStrictClassifier: missReasons.Count == 0,
        MissReasons: missReasons,
        MaxPlausibleValueRatioThresholdForThisSample: maxPlausibleThresholdForThisSample,
        CandidateGuardNote: "Candidate-only residual follow-up can rank repeated leads below the strict PlausibleValueRatio >= 0.95 role threshold; this does not promote geometry truth.");
  }

  private static bool IsNifMeshResidualStreamCandidate(uint meshSize, NifMeshBoundStreamSummary stream)
  {
    return IsNifMeshResidualTargetSize(meshSize) && !IsKnownNifMeshGeometryOrSentinelRole(stream.RoleStats.PrimaryRole);
  }

  private static bool IsNifMeshResidualTargetSize(uint meshSize)
  {
    return meshSize is 297 or 305 or 321 or 325 or 329;
  }

  private static bool IsKnownNifMeshGeometryOrSentinelRole(string role)
  {
    return role.StartsWith("index-", StringComparison.OrdinalIgnoreCase) ||
        role.StartsWith("normal-float3", StringComparison.OrdinalIgnoreCase) ||
        role.StartsWith("uv-float2", StringComparison.OrdinalIgnoreCase) ||
        role.StartsWith("position-float3", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(role, "all-zero-stream", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(role, "u32-sentinel-mask-body", StringComparison.OrdinalIgnoreCase) ||
        string.Equals(role, "sentinel-ffff-u16-body", StringComparison.OrdinalIgnoreCase);
  }

  private static int? GetDivisibleByteRatio(uint? byteCount, int? divisor)
  {
    if (byteCount is null || divisor is null || divisor.Value <= 0)
    {
      return null;
    }

    var unsignedDivisor = checked((uint)divisor.Value);
    return byteCount.Value % unsignedDivisor == 0
        ? checked((int)(byteCount.Value / unsignedDivisor))
        : null;
  }

  private static string FormatNifAttributeExtraFit(int? bytesPerVertex, int? bytesPerListTriangle, int? bytesPerStripOrFanTriangle, int? bytesPerQuad)
  {
    var parts = new List<string>();
    if (bytesPerVertex is not null)
    {
      parts.Add($"per-vertex:{bytesPerVertex.Value.ToString(CultureInfo.InvariantCulture)}");
    }

    if (bytesPerListTriangle is not null)
    {
      parts.Add($"per-triangle-list-triangle:{bytesPerListTriangle.Value.ToString(CultureInfo.InvariantCulture)}");
    }

    if (bytesPerStripOrFanTriangle is not null)
    {
      parts.Add($"per-strip-or-fan-triangle:{bytesPerStripOrFanTriangle.Value.ToString(CultureInfo.InvariantCulture)}");
    }

    if (bytesPerQuad is not null)
    {
      parts.Add($"per-quad:{bytesPerQuad.Value.ToString(CultureInfo.InvariantCulture)}");
    }

    return parts.Count == 0 ? "no-even-fit" : string.Join(",", parts);
  }

  private static NifAttributeTopologyStats AnalyzeNifAttributeTopology(int vertexCount, bool hasBoundIndexCandidate)
  {
    var evidence = new List<string> { $"vertex-count={vertexCount.ToString(CultureInfo.InvariantCulture)}" };
    if (hasBoundIndexCandidate)
    {
      evidence.Add("bound-index-candidate-present");
    }
    else
    {
      evidence.Add("no-bound-index-candidate");
    }

    var triangleListCandidate = vertexCount >= 3 && vertexCount % 3 == 0;
    int? triangleListTriangles = triangleListCandidate ? vertexCount / 3 : null;
    if (triangleListCandidate)
    {
      evidence.Add($"triangle-list-consistent:triangles={(vertexCount / 3).ToString(CultureInfo.InvariantCulture)}");
    }
    else
    {
      evidence.Add("triangle-list-rejected:vertex-count-not-divisible-by-3");
    }

    var triangleStripCandidate = vertexCount >= 3;
    int? triangleStripTriangles = triangleStripCandidate ? vertexCount - 2 : null;
    if (triangleStripCandidate)
    {
      evidence.Add($"triangle-strip-or-fan-consistent:triangles={(vertexCount - 2).ToString(CultureInfo.InvariantCulture)}");
    }
    else
    {
      evidence.Add("triangle-strip-or-fan-rejected:vertex-count-less-than-3");
    }

    var quadListCandidate = vertexCount >= 4 && vertexCount % 4 == 0;
    int? quadListQuads = quadListCandidate ? vertexCount / 4 : null;
    if (quadListCandidate)
    {
      evidence.Add($"quad-list-consistent:quads={(vertexCount / 4).ToString(CultureInfo.InvariantCulture)}");
    }
    else
    {
      evidence.Add("quad-list-rejected:vertex-count-not-divisible-by-4");
    }

    string primaryTopology;
    int confidence;
    if (hasBoundIndexCandidate)
    {
      primaryTopology = "explicit-index-candidate-present";
      confidence = 25;
    }
    else if (triangleListCandidate && quadListCandidate)
    {
      primaryTopology = "implicit-triangle-list-or-quad-candidate";
      confidence = 35;
    }
    else if (quadListCandidate)
    {
      primaryTopology = "implicit-strip-or-quad-candidate";
      confidence = 35;
    }
    else if (triangleListCandidate)
    {
      primaryTopology = "implicit-triangle-list-candidate";
      confidence = 40;
    }
    else if (triangleStripCandidate)
    {
      primaryTopology = "implicit-triangle-strip-or-fan-candidate";
      confidence = 35;
    }
    else
    {
      primaryTopology = "implicit-order-unknown";
      confidence = 0;
    }

    evidence.Add("topology-is-structural-candidate-not-export-proof");
    return new NifAttributeTopologyStats(
        PrimaryTopology: primaryTopology,
        Confidence: confidence,
        TriangleListCandidate: triangleListCandidate,
        TriangleListTriangleCount: triangleListTriangles,
        TriangleStripCandidate: triangleStripCandidate,
        TriangleStripTriangleCount: triangleStripTriangles,
        QuadListCandidate: quadListCandidate,
        QuadListQuadCount: quadListQuads,
        HasBoundIndexCandidate: hasBoundIndexCandidate,
        Evidence: evidence);
  }

  private static string FormatNifAttributeTopologySummary(NifAttributeTopologyStats topology)
  {
    return $"{topology.PrimaryTopology} c={topology.Confidence} list={topology.TriangleListTriangleCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} strip={topology.TriangleStripTriangleCount?.ToString(CultureInfo.InvariantCulture) ?? "-"} quad={topology.QuadListQuadCount?.ToString(CultureInfo.InvariantCulture) ?? "-"}";
  }

  private static int? GetPrimaryRoleVertexCount(NifMeshBoundStreamSummary stream)
  {
    var role = stream.RoleStats.PrimaryRole;
    if (role.Contains("ror1", StringComparison.OrdinalIgnoreCase))
    {
      if (role.StartsWith("uv-float2", StringComparison.OrdinalIgnoreCase))
      {
        return stream.RoleStats.RotatedFloat2Stats?.VectorCount;
      }

      if (role.StartsWith("normal-float3", StringComparison.OrdinalIgnoreCase) ||
          role.StartsWith("position-float3", StringComparison.OrdinalIgnoreCase))
      {
        return stream.RoleStats.RotatedFloat3Stats?.VectorCount;
      }
    }

    if (role.StartsWith("uv-float2", StringComparison.OrdinalIgnoreCase))
    {
      return stream.RoleStats.Float2Stats?.VectorCount;
    }

    if (role.StartsWith("normal-float3", StringComparison.OrdinalIgnoreCase) ||
        role.StartsWith("position-float3", StringComparison.OrdinalIgnoreCase))
    {
      return stream.RoleStats.Float3Stats?.VectorCount;
    }

    return null;
  }

  private static List<NifMeshPayloadRoleWindow> FindNifMeshPayloadRoleWindows(ReadOnlySpan<byte> meshPayload, List<int> vertexCounts)
  {
    var windows = new List<NifMeshPayloadRoleWindow>();
    if (meshPayload.Length == 0 || vertexCounts.Count == 0)
    {
      return windows;
    }

    foreach (var vertexCount in vertexCounts.Where(static count => count > 0).Take(8))
    {
      foreach (var components in new[] { 3, 2 })
      {
        var byteLength = checked(vertexCount * components * 4);
        if (byteLength <= 0 || byteLength > meshPayload.Length)
        {
          continue;
        }

        foreach (var transform in new[] { NifFloatByteTransform.RotateRight1, NifFloatByteTransform.LittleEndian })
        {
          for (var offset = 0; offset + byteLength <= meshPayload.Length; offset++)
          {
            var window = meshPayload.Slice(offset, byteLength);
            var stats = AnalyzeNifFloatVectors(window, components, transform);
            if (stats.FiniteVectorRatio < 0.95 || stats.PlausibleValueRatio < 0.95 || stats.NonZeroVectorRatio < 0.50)
            {
              continue;
            }

            string? role = null;
            var confidence = 0;
            if (components == 3 && stats.NearUnitVectorRatio >= 0.75)
            {
              role = $"normal-float3-{FormatNifFloatTransformSuffix(transform)}-payload-window";
              confidence = 75;
            }
            else if (components == 3 && stats.MaxExtent >= 0.0001)
            {
              role = $"position-float3-{FormatNifFloatTransformSuffix(transform)}-payload-window";
              confidence = 65;
            }
            else if (components == 2 && stats.UvRangeRatio >= 0.80)
            {
              role = $"uv-float2-{FormatNifFloatTransformSuffix(transform)}-payload-window";
              confidence = 60;
            }

            if (role is null)
            {
              continue;
            }

            windows.Add(new NifMeshPayloadRoleWindow(
                PayloadOffset: offset,
                ByteLength: byteLength,
                VertexCount: vertexCount,
                Components: components,
                Transform: transform.ToString(),
                Role: role,
                Confidence: confidence,
                First16: ToHex(window[..Math.Min(16, window.Length)]),
                Stats: stats));
          }
        }
      }
    }

    return windows
        .OrderByDescending(static w => w.Confidence)
        .ThenBy(static w => w.PayloadOffset)
        .ThenBy(static w => w.ByteLength)
        .Take(32)
        .ToList();
  }

  private static string FormatNifFloatTransformSuffix(NifFloatByteTransform transform) => transform switch
  {
    NifFloatByteTransform.RotateRight1 => "ror1",
    _ => "le"
  };

  private static string ClassifyNifIndexCandidate(NifStreamEndianStats endianStats, NifUInt16BeIndexStats indexStats)
  {
    if (indexStats.PairCount == 0)
    {
      return "empty-index-body";
    }

    if (endianStats.Classification == "big-endian-u16-lead" && indexStats.TriangleAligned)
    {
      return "uint16be-triangle-aligned-lead";
    }

    if (endianStats.Classification == "big-endian-u16-lead")
    {
      return "uint16be-index-lead";
    }

    if (endianStats.Classification == "ambiguous-small-u16" && indexStats.TriangleAligned)
    {
      return "ambiguous-u16-triangle-aligned";
    }

    if (endianStats.Classification == "little-endian-u16-lead")
    {
      return "little-endian-u16-lead";
    }

    return "not-index-ranked";
  }

  private static string ClassifyNifStreamBody(
      int byteLength,
      int nonZeroBytes,
      int floatCount,
      int finiteFloatCount,
      int plausibleFloatCount,
      int uint16Distinct,
      ushort uint16Max,
      int uint32Distinct,
      uint uint32Max,
      List<StrideCandidate> strideCandidates)
  {
    if (byteLength == 0)
    {
      return "empty-body";
    }

    if (nonZeroBytes == 0)
    {
      return "all-zero-body";
    }

    if (byteLength % 4 == 0 &&
        uint32Distinct is 1 or 2 &&
        uint32Max == uint.MaxValue)
    {
      return "u32-sentinel-mask-body";
    }

    if (byteLength % 4 == 0 &&
        uint32Distinct is 1 or 2)
    {
      return "u32-repeated-pattern-body";
    }

    if (byteLength % 4 == 0 &&
        floatCount > 0 &&
        finiteFloatCount == floatCount &&
        plausibleFloatCount >= Math.Max(1, checked((int)Math.Ceiling(floatCount * 0.85))))
    {
      return "float32-compatible-body";
    }

    if (byteLength % 2 == 0 &&
        byteLength % 6 == 0 &&
        uint16Distinct > 2 &&
        uint16Max < 65_535)
    {
      return "uint16-compatible-body";
    }

    if (byteLength % 4 == 0 &&
        uint32Distinct > 2 &&
        uint32Max < 1_000_000)
    {
      return "uint32-compatible-body";
    }

    if (strideCandidates.Count > 0)
    {
      return "strided-body";
    }

    return "mixed-body";
  }

  private static string FormatPreferredStrideSummary(IEnumerable<StrideCandidate> candidates, int max)
  {
    return string.Join(
        "/",
        candidates
            .OrderBy(static c => PreferredStrideRank(c.Stride))
            .ThenBy(static c => c.Stride)
            .Take(max)
            .Select(static c => $"{c.Stride}x{c.Count}"));
  }

  private static int PreferredStrideRank(int stride)
  {
    return stride switch
    {
      12 => 0,
      16 => 1,
      20 => 2,
      24 => 3,
      28 => 4,
      32 => 5,
      36 => 6,
      40 => 7,
      44 => 8,
      48 => 9,
      56 => 10,
      64 => 11,
      8 => 12,
      6 => 13,
      4 => 14,
      2 => 15,
      _ => 100,
    };
  }

  private static List<int> FindNifStringIndexCandidates(ReadOnlySpan<byte> payload, int stringCount)
  {
    var candidates = new List<int>();
    if (stringCount <= 0)
    {
      return candidates;
    }

    var seen = new HashSet<int>();
    for (var offset = 0; offset + 4 <= payload.Length; offset += 4)
    {
      var value = BinaryPrimitives.ReadInt32LittleEndian(payload.Slice(offset, 4));
      if (value >= 0 && value < stringCount && seen.Add(value))
      {
        candidates.Add(value);
      }
    }

    return candidates;
  }

  private static string FormatNifVersion(uint version)
  {
    return $"{(version >> 24) & 0xff}.{(version >> 16) & 0xff}.{(version >> 8) & 0xff}.{version & 0xff}";
  }

  private static string FormatBlockTypeUsage(NifBlockTypeInfo blockType)
  {
    var label = string.Equals(blockType.NormalizedName, blockType.DisplayName, StringComparison.Ordinal)
        ? blockType.DisplayName
        : $"{blockType.NormalizedName} ({blockType.DisplayName})";
    label += FormatNifDataStreamUsageAccessInline(blockType.DataStreamUsage, blockType.DataStreamAccess);

    return blockType.UsageCount > 0
        ? $"{label} x{blockType.UsageCount:N0}"
        : label;
  }

  private static string FormatNifDataStreamUsageAccessKey(string? dataStreamUsage, string? dataStreamAccess)
  {
    return $"usage={dataStreamUsage ?? "-"} access={dataStreamAccess ?? "-"}";
  }

  private static string FormatNifDataStreamUsageAccessInline(string? dataStreamUsage, string? dataStreamAccess)
  {
    return string.IsNullOrWhiteSpace(dataStreamUsage) && string.IsNullOrWhiteSpace(dataStreamAccess)
        ? string.Empty
        : $" usage={dataStreamUsage ?? "-"} access={dataStreamAccess ?? "-"}";
  }

  private static NifBlockTypeNameInfo BuildNifBlockTypeNameInfo(int index, string name)
  {
    var displayName = EscapeControlChars(name);
    var normalizedName = displayName;
    string? dataStreamUsage = null;
    string? dataStreamAccess = null;

    var parts = name.Split('\u0001');
    if (parts.Length > 1 &&
        string.Equals(parts[0], "NiDataStream", StringComparison.OrdinalIgnoreCase))
    {
      normalizedName = "NiDataStream";
      dataStreamUsage = parts.Length > 1 && parts[1].Length > 0 ? EscapeControlChars(parts[1]) : null;
      dataStreamAccess = parts.Length > 2 && parts[2].Length > 0 ? EscapeControlChars(parts[2]) : null;
    }

    return new NifBlockTypeNameInfo(
        Index: index,
        Name: name,
        DisplayName: displayName,
        NormalizedName: normalizedName,
        DataStreamUsage: dataStreamUsage,
        DataStreamAccess: dataStreamAccess);
  }

  private static string EscapeControlChars(string value)
  {
    var builder = new StringBuilder(value.Length);
    foreach (var ch in value)
    {
      if (char.IsControl(ch))
      {
        builder.Append(CultureInvariantControlEscape(ch));
        continue;
      }

      builder.Append(ch);
    }

    return builder.ToString();
  }

  private static string CultureInvariantControlEscape(char ch)
  {
    return "\\u" + ((int)ch).ToString("x4", System.Globalization.CultureInfo.InvariantCulture);
  }

  private static string DecodeNifString(ReadOnlySpan<byte> bytes)
  {
    return Encoding.UTF8.GetString(bytes).TrimEnd('\0');
  }

  private static IEnumerable<NifReferenceInfo> ExtractNifReferences(NifStringInfo stringInfo)
  {
    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

    foreach (var pattern in new[]
    {
            @"(?i)\b[A-Z]:[\\/][^\r\n<>|]+?(?=\s*>>|\s*$)",
            @"(?i)\b(?:assets?|art|textures?|models?|audio|vfx|interface)[\\/][^\s<>|""']+",
            @"(?i)\b[\w./\\:-]+\.(?:dds|nif|kf|kfm|ma|mb|xml|lua|ogg|wav|png|jpg|jpeg|tga|mesh|anim)\b"
        })
    {
      foreach (Match match in Regex.Matches(stringInfo.Value, pattern, RegexOptions.CultureInvariant))
      {
        var candidate = CleanNifReference(match.Value);
        if (candidate.Length == 0 || !seen.Add(candidate))
        {
          continue;
        }

        yield return new NifReferenceInfo(stringInfo.Index, candidate);
      }
    }
  }

  private static string CleanNifReference(string value)
  {
    return value.Trim()
        .Trim('"', '\'')
        .TrimEnd('.', ',', ';', ')', ']', '}');
  }

  private static string NormalizeNifReferenceCandidate(string value)
  {
    var normalized = NormalizeAssetName(value);
    foreach (var sourceRoot in new[] { "z:/twn/", "c:/perforce/twn/" })
    {
      if (normalized.StartsWith(sourceRoot, StringComparison.OrdinalIgnoreCase))
      {
        normalized = normalized[sourceRoot.Length..];
        break;
      }
    }

    return normalized.TrimStart('/');
  }

  private static IEnumerable<TextureCandidate> BuildTextureCandidateVariants(string reference)
  {
    var normalized = NormalizeNifReferenceCandidate(reference);
    if (!LooksLikeTextureReference(normalized))
    {
      yield break;
    }

    var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    if (seen.Add(normalized))
    {
      yield return new TextureCandidate(normalized, "normalized-reference");
    }

    var slash = normalized.LastIndexOf('/');
    if (slash >= 0 && slash + 1 < normalized.Length)
    {
      var basename = normalized[(slash + 1)..];
      if (seen.Add(basename))
      {
        yield return new TextureCandidate(basename, "basename");
      }
    }
  }

  private static bool LooksLikeTextureReference(string value)
  {
    return Regex.IsMatch(value, @"(?i)\.(?:dds|tga|png|jpg|jpeg)$", RegexOptions.CultureInvariant);
  }

  private static bool TryMatchRecoveredNameCandidate(
      ManifestLookup lookup,
      string candidate,
      out ManifestEntryBrief entry,
      out uint hash,
      out int byteLength,
      out int collisionCount)
  {
    hash = ComputeFnv1Hash(candidate);
    byteLength = Encoding.UTF8.GetByteCount(candidate);
    collisionCount = 0;
    entry = null!;

    if (!lookup.EntriesByFnv.TryGetValue(hash, out var hashMatches))
    {
      return false;
    }

    collisionCount = hashMatches.Count;
    if (hashMatches.Count != 1)
    {
      return false;
    }

    var match = hashMatches[0];
    if (match.NameLength is not null && match.NameLength.Value != byteLength)
    {
      return false;
    }

    entry = match;
    return true;
  }

  private static string TruncateForConsole(string value, int maxLength)
  {
    return value.Length <= maxLength
        ? value
        : value[..Math.Max(0, maxLength - 1)] + "…";
  }

  private static IEnumerable<string> ExtractAsciiRuns(byte[] bytes, int minLength)
  {
    var builder = new StringBuilder();
    foreach (var b in bytes)
    {
      if (b is >= 32 and <= 126)
      {
        builder.Append((char)b);
        continue;
      }

      if (builder.Length >= minLength)
      {
        yield return builder.ToString();
      }

      builder.Clear();
    }

    if (builder.Length >= minLength)
    {
      yield return builder.ToString();
    }
  }

  private static IEnumerable<string> ExtractUtf16LeRuns(byte[] bytes, int minLength)
  {
    var builder = new StringBuilder();
    for (var i = 0; i + 1 < bytes.Length; i += 2)
    {
      var value = BinaryPrimitives.ReadUInt16LittleEndian(bytes.AsSpan(i, 2));
      if (value is >= 32 and <= 126)
      {
        builder.Append((char)value);
        continue;
      }

      if (builder.Length >= minLength)
      {
        yield return builder.ToString();
      }

      builder.Clear();
    }

    if (builder.Length >= minLength)
    {
      yield return builder.ToString();
    }
  }

  private static AssetSemanticProbe BuildAssetSemanticProbe(byte[] payload, DetectedFileType detected, bool scanSemanticStrings)
  {
    var categories = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
    var nameCandidates = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
    var referenceSamples = new List<string>();
    var textSnippetSamples = new List<string>();
    var xmlTagCounts = new List<NifStringCount>();
    var xmlAttributeCounts = new List<NifStringCount>();
    XmlFamilyProbe? xmlFamily = null;

    AddDetectedTypeCategories(categories, detected);
    if (detected.Extension == "xml")
    {
      xmlFamily = BuildXmlFamilyProbe(payload);
      xmlTagCounts = xmlFamily.TagCounts;
      xmlAttributeCounts = xmlFamily.AttributeCounts;
      if (xmlTagCounts.Count > 0)
      {
        categories.Add("xml:tag-family");
      }

      if (xmlFamily.ParseWarning is not null)
      {
        categories.Add("xml-parse-warning");
      }
      else
      {
        categories.Add("xml:parse-complete");
      }
    }

    if (scanSemanticStrings && detected.Extension == "nif")
    {
      try
      {
        var header = ParseNifHeader(payload);
        foreach (var reference in header.References.Take(64))
        {
          AddReferenceSample(referenceSamples, reference.Value);
          AddNameCandidate(nameCandidates, reference.Value);
          AddSemanticCategoriesForText(categories, reference.Value);
        }

        foreach (var blockType in header.BlockTypes.OrderByDescending(static b => b.UsageCount).Take(16))
        {
          AddSemanticCategoriesForText(categories, blockType.DisplayName);
        }
      }
      catch
      {
        categories.Add("nif-parse-warning");
      }
    }

    var pathLikeRegex = PathLikeRegex();
    var scanPayload = scanSemanticStrings && ShouldScanPayloadStrings(detected) ? BuildSemanticStringScanPayload(payload) : Array.Empty<byte>();
    foreach (var run in ExtractAsciiRuns(scanPayload, minLength: 4).Take(512)
        .Concat(ExtractUtf16LeRuns(scanPayload, minLength: 4).Take(128)))
    {
      AddSemanticCategoriesForText(categories, run);
      foreach (Match match in pathLikeRegex.Matches(run))
      {
        AddNameCandidate(nameCandidates, match.Value);
        AddReferenceSample(referenceSamples, match.Value);
      }

      if (textSnippetSamples.Count < 8 && LooksSemanticallyInteresting(run))
      {
        textSnippetSamples.Add(SanitizeTextSnippet(run, maxLength: 96));
      }
    }

    return new AssetSemanticProbe(
        First4: ToHex(payload.AsSpan(0, Math.Min(payload.Length, 4))),
        First8: ToHex(payload.AsSpan(0, Math.Min(payload.Length, 8))),
        First16: ToHex(payload.AsSpan(0, Math.Min(payload.Length, 16))),
        MagicLabel: BuildMagicLabel(payload, detected),
        SemanticCategories: categories.ToList(),
        NameCandidates: nameCandidates.Take(16).ToList(),
        ReferenceSamples: referenceSamples.Distinct(StringComparer.OrdinalIgnoreCase).Take(16).ToList(),
        XmlTagCounts: xmlTagCounts,
        XmlAttributeCounts: xmlAttributeCounts,
        XmlParseStatus: xmlFamily?.ParseStatus,
        XmlParseWarning: xmlFamily?.ParseWarning,
        XmlParseLineNumber: xmlFamily?.ParseLineNumber,
        XmlParseLinePosition: xmlFamily?.ParseLinePosition,
        XmlParsedElementCount: xmlFamily?.ParsedElementCount,
        XmlParsedAttributeNameCount: xmlFamily?.ParsedAttributeNameCount,
        TextSnippetSamples: textSnippetSamples.Distinct(StringComparer.OrdinalIgnoreCase).Take(8).ToList());
  }

  private static XmlFamilyProbe BuildXmlFamilyProbe(byte[] payload)
  {
    var tagCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    var attributeCounts = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
    try
    {
      var settings = new XmlReaderSettings
      {
        DtdProcessing = DtdProcessing.Ignore,
        IgnoreComments = true,
        IgnoreProcessingInstructions = true,
        IgnoreWhitespace = true,
        XmlResolver = null
      };

      using var stream = new MemoryStream(payload, writable: false);
      using var reader = XmlReader.Create(stream, settings);
      while (reader.Read())
      {
        if (reader.NodeType != XmlNodeType.Element)
        {
          continue;
        }

        var tagName = SanitizeXmlFamilyName(string.IsNullOrWhiteSpace(reader.LocalName) ? reader.Name : reader.LocalName);
        if (!string.IsNullOrWhiteSpace(tagName))
        {
          IncrementCount(tagCounts, tagName);
        }

        if (!reader.HasAttributes)
        {
          continue;
        }

        while (reader.MoveToNextAttribute())
        {
          var attributeName = SanitizeXmlFamilyName(string.IsNullOrWhiteSpace(reader.LocalName) ? reader.Name : reader.LocalName);
          if (!string.IsNullOrWhiteSpace(attributeName))
          {
            IncrementCount(attributeCounts, attributeName);
          }
        }

        reader.MoveToElement();
      }

      return new XmlFamilyProbe(
          TagCounts: ToTopStringCounts(tagCounts, take: 32),
          AttributeCounts: ToTopStringCounts(attributeCounts, take: 32),
          ParseStatus: "complete",
          ParseWarning: null,
          ParseLineNumber: null,
          ParseLinePosition: null,
          ParsedElementCount: tagCounts.Values.Sum(),
          ParsedAttributeNameCount: attributeCounts.Values.Sum());
    }
    catch (XmlException ex)
    {
      return new XmlFamilyProbe(
          TagCounts: ToTopStringCounts(tagCounts, take: 32),
          AttributeCounts: ToTopStringCounts(attributeCounts, take: 32),
          ParseStatus: tagCounts.Count > 0 ? "partial-with-warning" : "failed",
          ParseWarning: ex.GetType().Name,
          ParseLineNumber: ex.LineNumber,
          ParseLinePosition: ex.LinePosition,
          ParsedElementCount: tagCounts.Values.Sum(),
          ParsedAttributeNameCount: attributeCounts.Values.Sum());
    }
  }

  private static string SanitizeXmlFamilyName(string value)
  {
    var builder = new StringBuilder();
    foreach (var c in value.Trim())
    {
      if (char.IsAsciiLetterOrDigit(c) || c is '_' or '-' or ':' or '.')
      {
        builder.Append(c);
      }
      else
      {
        builder.Append('_');
      }

      if (builder.Length >= 64)
      {
        break;
      }
    }

    return builder.ToString();
  }

  private static bool ShouldScanPayloadStrings(DetectedFileType detected)
  {
    return detected.Extension is "bin" or "txt" or "lua" or "xml" or "nif";
  }

  private static byte[] BuildSemanticStringScanPayload(byte[] payload)
  {
    const int maxBytes = 256 * 1024;
    if (payload.Length <= maxBytes)
    {
      return payload;
    }

    var prefixBytes = maxBytes / 2;
    var suffixBytes = maxBytes - prefixBytes;
    var scanPayload = new byte[maxBytes];
    Buffer.BlockCopy(payload, 0, scanPayload, 0, prefixBytes);
    Buffer.BlockCopy(payload, payload.Length - suffixBytes, scanPayload, prefixBytes, suffixBytes);
    return scanPayload;
  }

  private static void AddDetectedTypeCategories(SortedSet<string> categories, DetectedFileType detected)
  {
    categories.Add($"type:{detected.Extension}");
    switch (detected.Extension)
    {
      case "dds" or "png" or "jpg":
        categories.Add("asset:texture");
        break;
      case "nif":
        categories.Add("asset:model");
        break;
      case "ogg" or "riff":
        categories.Add("asset:audio");
        break;
      case "lua":
        categories.Add("asset:script-lua");
        break;
      case "xml":
        categories.Add("asset:xml");
        break;
      case "txt":
        categories.Add("asset:text");
        break;
      default:
        categories.Add("asset:unknown-binary");
        break;
    }
  }

  private static void AddReferenceSample(List<string> references, string value)
  {
    if (references.Count >= 32)
    {
      return;
    }

    var cleaned = CleanNifReference(value);
    if (cleaned.Length > 0)
    {
      references.Add(SanitizeTextSnippet(cleaned, maxLength: 128));
    }
  }

  private static void AddNameCandidate(SortedSet<string> candidates, string value)
  {
    var cleaned = CleanNifReference(value);
    if (cleaned.Length == 0)
    {
      return;
    }

    var normalized = NormalizeAssetName(cleaned);
    if (normalized.Length is >= 3 and <= 180)
    {
      candidates.Add(normalized);
    }
  }

  private static void AddSemanticCategoriesForText(SortedSet<string> categories, string text)
  {
    if (string.IsNullOrWhiteSpace(text))
    {
      return;
    }

    var lower = text.ToLowerInvariant();
    if (lower.Contains(".dds", StringComparison.Ordinal) ||
        lower.Contains(".tga", StringComparison.Ordinal) ||
        lower.Contains("texture", StringComparison.Ordinal))
    {
      categories.Add("ref:texture");
    }

    if (lower.Contains(".nif", StringComparison.Ordinal) ||
        lower.Contains(".kfm", StringComparison.Ordinal) ||
        lower.Contains(".kf", StringComparison.Ordinal) ||
        lower.Contains("model", StringComparison.Ordinal) ||
        lower.Contains("mesh", StringComparison.Ordinal))
    {
      categories.Add("ref:model");
    }

    if (lower.Contains(".ogg", StringComparison.Ordinal) ||
        lower.Contains(".wav", StringComparison.Ordinal) ||
        lower.Contains("sound", StringComparison.Ordinal) ||
        lower.Contains("audio", StringComparison.Ordinal))
    {
      categories.Add("ref:audio");
    }

    if (lower.Contains(".lua", StringComparison.Ordinal) || LooksLikeLuaText(text))
    {
      categories.Add("hint:lua");
    }

    if (lower.Contains(".xml", StringComparison.Ordinal) || LooksLikeXmlText(text))
    {
      categories.Add("hint:xml");
    }

    if (lower.Contains("interface", StringComparison.Ordinal) ||
        lower.Contains("/ui", StringComparison.Ordinal) ||
        lower.Contains("\\ui", StringComparison.Ordinal) ||
        lower.Contains("addon", StringComparison.Ordinal) ||
        lower.Contains("frame", StringComparison.Ordinal))
    {
      categories.Add("hint:ui");
    }

    if (lower.Contains("world", StringComparison.Ordinal) ||
        lower.Contains("zone", StringComparison.Ordinal) ||
        lower.Contains("terrain", StringComparison.Ordinal) ||
        lower.Contains("/map", StringComparison.Ordinal) ||
        lower.Contains("\\map", StringComparison.Ordinal) ||
        lower.Contains("map_", StringComparison.Ordinal) ||
        lower.Contains("_map", StringComparison.Ordinal) ||
        lower.Contains("bounds", StringComparison.Ordinal) ||
        lower.Contains("coordinate", StringComparison.Ordinal))
    {
      categories.Add("hint:map-zone");
    }

    if (lower.Contains("waypoint", StringComparison.Ordinal) ||
        lower.Contains("poi", StringComparison.Ordinal) ||
        lower.Contains("pointofinterest", StringComparison.Ordinal))
    {
      categories.Add("hint:waypoint-poi");
    }

    if (lower.Contains("quest", StringComparison.Ordinal) ||
        lower.Contains("objective", StringComparison.Ordinal) ||
        lower.Contains("journal", StringComparison.Ordinal))
    {
      categories.Add("hint:quest-objective");
    }

    if (lower.Contains("npc", StringComparison.Ordinal) ||
        lower.Contains("actor", StringComparison.Ordinal) ||
        lower.Contains("creature", StringComparison.Ordinal) ||
        lower.Contains("character", StringComparison.Ordinal) ||
        lower.Contains("spawn", StringComparison.Ordinal))
    {
      categories.Add("hint:actor-object");
    }
  }

  private static bool LooksSemanticallyInteresting(string text)
  {
    var categories = new SortedSet<string>(StringComparer.OrdinalIgnoreCase);
    AddSemanticCategoriesForText(categories, text);
    return categories.Any(static c => c.StartsWith("hint:", StringComparison.OrdinalIgnoreCase) || c.StartsWith("ref:", StringComparison.OrdinalIgnoreCase));
  }

  private static string BuildMagicLabel(byte[] payload, DetectedFileType detected)
  {
    if (detected.Extension == "nif")
    {
      return detected.Format ?? "Gamebryo File Format";
    }

    if (detected.Extension == "riff")
    {
      return string.IsNullOrWhiteSpace(detected.RiffType) ? "RIFF" : $"RIFF/{detected.RiffType}";
    }

    if (detected.Extension == "dds")
    {
      return string.IsNullOrWhiteSpace(detected.Format) ? "DDS" : $"DDS/{detected.Format}";
    }

    var ascii = ReadAsciiLine(payload.AsSpan(0, Math.Min(payload.Length, 32)), maxLength: 32);
    if (!string.IsNullOrWhiteSpace(ascii) && ascii.All(static c => c is >= ' ' and <= '~'))
    {
      return SanitizeTextSnippet(ascii, maxLength: 32);
    }

    return detected.Extension;
  }

  private static bool LooksLikeXmlText(string text)
  {
    var trimmed = text.TrimStart('\uFEFF', ' ', '\t', '\r', '\n');
    return trimmed.StartsWith("<?xml", StringComparison.OrdinalIgnoreCase) ||
        trimmed.StartsWith("<", StringComparison.Ordinal) &&
        (trimmed.Contains("</", StringComparison.Ordinal) || trimmed.Contains("/>", StringComparison.Ordinal));
  }

  private static bool LooksLikeLuaText(string text)
  {
    var lower = text.ToLowerInvariant();
    return lower.Contains("function ", StringComparison.Ordinal) &&
        lower.Contains(" end", StringComparison.Ordinal) ||
        lower.Contains("local ", StringComparison.Ordinal) &&
        (lower.Contains("function", StringComparison.Ordinal) || lower.Contains("return ", StringComparison.Ordinal));
  }

  private static string SanitizeTextSnippet(string value, int maxLength)
  {
    var builder = new StringBuilder();
    foreach (var c in value)
    {
      if (c is '\r' or '\n' or '\t')
      {
        builder.Append(' ');
      }
      else if (c is >= ' ' and <= '~')
      {
        builder.Append(c);
      }
    }

    var sanitized = Regex.Replace(builder.ToString(), @"\s+", " ").Trim();
    return sanitized.Length <= maxLength ? sanitized : sanitized[..Math.Max(0, maxLength - 1)] + "…";
  }

  private static List<NifStringCount> ToTopStringCounts(Dictionary<string, int> counts, int take)
  {
    return counts
        .OrderByDescending(static kvp => kvp.Value)
        .ThenBy(static kvp => kvp.Key, StringComparer.OrdinalIgnoreCase)
        .Take(take)
        .Select(static kvp => new NifStringCount(kvp.Key, kvp.Value))
        .ToList();
  }

  private static Regex PathLikeRegex() => new(
      @"(?i)\b(?:assets|art|textures|texture|models|model|audio|sound|sounds|world|ui|interface)[a-z0-9_./\\-]{2,}\.(?:dds|png|jpg|jpeg|ogg|wav|riff|mesh|xml|lua|txt|bin|model|anim|skel|mat)\b",
      RegexOptions.Compiled | RegexOptions.CultureInvariant);

  private static string FormatCounts(Dictionary<string, int> counts)
  {
    return string.Join(", ", counts.OrderBy(static kvp => kvp.Key).Select(static kvp => $"{kvp.Key}={kvp.Value}"));
  }

  private static CompressionManifestSample BuildCompressionManifestSample(string rootDirectory, string assetsDirectory, PakListingRecord pak)
  {
    var pakPath = pak.Path.Replace('/', Path.DirectorySeparatorChar).Replace('\\', Path.DirectorySeparatorChar);
    var candidates = new List<string>
        {
            Path.Combine(rootDirectory, pakPath),
            Path.Combine(assetsDirectory, pakPath)
        };

    const string assetsPrefix = "assets/";
    if (pak.Path.StartsWith(assetsPrefix, StringComparison.OrdinalIgnoreCase))
    {
      candidates.Add(Path.Combine(assetsDirectory, pak.Path[assetsPrefix.Length..].Replace('/', Path.DirectorySeparatorChar)));
    }

    var existingPath = candidates.FirstOrDefault(File.Exists);
    string? firstBytes = null;
    if (existingPath is not null)
    {
      using var stream = File.OpenRead(existingPath);
      var buffer = new byte[Math.Min(16, checked((int)Math.Min(stream.Length, 16)))];
      var read = stream.Read(buffer, 0, buffer.Length);
      firstBytes = ToHex(buffer.AsSpan(0, read));
    }

    return new CompressionManifestSample(
        PakIndex: pak.Index,
        StringOffset: pak.StringOffset,
        Path: pak.Path,
        Compression: pak.Compression,
        UncompressedSize: pak.UncompressedSize,
        CompressedSize: pak.CompressedSize,
        FileExists: existingPath is not null,
        FirstBytes: firstBytes);
  }

  private static ManifestEntryBrief ResolveTargetEntry(AppOptions options, ManifestLookup lookup)
  {
    if (!string.IsNullOrWhiteSpace(options.IdFilter))
    {
      var id = NormalizeIdPrefix(options.IdFilter);
      if (lookup.Table1ById.TryGetValue(id, out var byId))
      {
        return byId;
      }

      throw new InvalidOperationException($"No manifest entry matched ID {id}.");
    }

    if (options.ManifestIndexFilter is not null)
    {
      var byIndex = lookup.Entries.FirstOrDefault(e => e.Index == options.ManifestIndexFilter.Value);
      return byIndex ?? throw new InvalidOperationException($"No manifest entry exists at index {options.ManifestIndexFilter.Value}.");
    }

    if (options.FnvFilter is not null)
    {
      if (lookup.EntriesByFnv.TryGetValue(options.FnvFilter.Value, out var matches) && matches.Count > 0)
      {
        if (matches.Count > 1)
        {
          throw new InvalidOperationException($"FNV 0x{options.FnvFilter.Value:x8} matched {matches.Count} entries. Use --id or --manifest-index.");
        }

        return matches[0];
      }

      throw new InvalidOperationException($"No manifest entry matched FNV 0x{options.FnvFilter.Value:x8}.");
    }

    throw new InvalidOperationException("probe-binary requires --input, --id, --manifest-index, or a uniquely matching --fnv.");
  }

  private static FoundPayload? FindPayloadForId(string rootDirectory, ManifestLookup lookup, string idPrefix, AppOptions options)
  {
    var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);
    var found = FindPayloadForIdInRoot(rootDirectory, idPrefix, archiveFilter, options, sourceKind: "copied");
    if (found is not null)
    {
      return found;
    }

    if (string.IsNullOrWhiteSpace(options.LiveRoot))
    {
      return null;
    }

    var liveRoot = Path.GetFullPath(options.LiveRoot);
    var copiedAssetsDirectory = ResolveAssetsDirectory(Path.GetFullPath(rootDirectory));
    var liveAssetsDirectory = ResolveAssetsDirectory(liveRoot);
    if (PathsEqual(copiedAssetsDirectory, liveAssetsDirectory))
    {
      return null;
    }

    return FindPayloadForIdInRoot(liveRoot, idPrefix, archiveFilter, options, sourceKind: "live");
  }

  private static ArchivePayloadLookup BuildPayloadLookup(string rootDirectory, AppOptions options, IEnumerable<string> targetIds)
  {
    var targets = targetIds
        .Where(static id => !string.IsNullOrWhiteSpace(id))
        .Select(static id => id.Trim().ToLowerInvariant())
        .ToHashSet(StringComparer.OrdinalIgnoreCase);
    var lookup = new ArchivePayloadLookup();
    if (targets.Count == 0)
    {
      return lookup;
    }

    var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);
    AddPayloadLocations(lookup, Path.GetFullPath(rootDirectory), targets, archiveFilter, sourceKind: "copied");

    if (string.IsNullOrWhiteSpace(options.LiveRoot))
    {
      return lookup;
    }

    var liveRoot = Path.GetFullPath(options.LiveRoot);
    var copiedAssetsDirectory = ResolveAssetsDirectory(Path.GetFullPath(rootDirectory));
    var liveAssetsDirectory = ResolveAssetsDirectory(liveRoot);
    if (PathsEqual(copiedAssetsDirectory, liveAssetsDirectory))
    {
      return lookup;
    }

    AddPayloadLocations(lookup, liveRoot, targets, archiveFilter, sourceKind: "live");
    return lookup;
  }

  private static void AddPayloadLocations(
      ArchivePayloadLookup lookup,
      string rootDirectory,
      HashSet<string> targetIds,
      string? archiveFilter,
      string sourceKind)
  {
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      return;
    }

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (archiveFilter is not null && !string.Equals(archiveName, archiveFilter, StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      if (string.Equals(sourceKind, "live", StringComparison.OrdinalIgnoreCase))
      {
        lookup.LiveArchivesScanned++;
      }
      else
      {
        lookup.CopiedArchivesScanned++;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (entry.IsNull || !targetIds.Contains(entry.IdPrefix) || lookup.Contains(entry.IdPrefix))
        {
          continue;
        }

        lookup.Add(new ArchivePayloadLocation(
            IdPrefix: entry.IdPrefix,
            ArchivePath: archivePath,
            ArchiveName: archiveName,
            EntryIndex: entry.Index,
            Offset: entry.Offset,
            Size: entry.Size,
            Compression: entry.Compression,
            Sha1: entry.Sha1,
            SourceKind: sourceKind));
      }
    }
  }

  private static FoundPayload? FindPayloadForIdInRoot(string rootDirectory, string idPrefix, string? archiveFilter, AppOptions options, string sourceKind)
  {
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      return null;
    }

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      var archiveName = Path.GetFileName(archivePath);
      if (archiveFilter is not null && !string.Equals(archiveName, archiveFilter, StringComparison.OrdinalIgnoreCase))
      {
        continue;
      }

      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (entry.IsNull || !string.Equals(entry.IdPrefix, idPrefix, StringComparison.OrdinalIgnoreCase))
        {
          continue;
        }

        var packed = ReadArchivePayload(stream, entry, archiveName);
        var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
        return new FoundPayload(archiveName, entry.Index, payload.Bytes, sourceKind);
      }
    }

    return null;
  }

  private static bool PathsEqual(string left, string right)
  {
    return string.Equals(
        Path.GetFullPath(left).TrimEnd('\\', '/'),
        Path.GetFullPath(right).TrimEnd('\\', '/'),
        StringComparison.OrdinalIgnoreCase);
  }

  private static BinaryProbeData BuildBinaryProbe(byte[] payload)
  {
    var first4 = ToHex(payload.AsSpan(0, Math.Min(4, payload.Length)));
    var first8 = ToHex(payload.AsSpan(0, Math.Min(8, payload.Length)));
    var first16 = ToHex(payload.AsSpan(0, Math.Min(16, payload.Length)));
    var values = Math.Min(8, payload.Length / 4);
    var uints = new List<uint>(values);
    var ints = new List<int>(values);
    var floats = new List<float>(values);
    for (var i = 0; i < values; i++)
    {
      var span = payload.AsSpan(i * 4, 4);
      uints.Add(BinaryPrimitives.ReadUInt32LittleEndian(span));
      ints.Add(BinaryPrimitives.ReadInt32LittleEndian(span));
      floats.Add(BitConverter.Int32BitsToSingle(BinaryPrimitives.ReadInt32LittleEndian(span)));
    }

    var strideCandidates = new List<StrideCandidate>();
    foreach (var stride in new[] { 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 64 })
    {
      if (payload.Length >= stride && payload.Length % stride == 0)
      {
        strideCandidates.Add(new StrideCandidate(stride, payload.Length / stride));
      }
    }

    return new BinaryProbeData(first4, first8, first16, uints, ints, floats, strideCandidates);
  }

  private static string ClassifyBinaryCandidate(BinaryProbeData probe, int length)
  {
    if (probe.First8.StartsWith("57e0e05710c0c010", StringComparison.OrdinalIgnoreCase))
    {
      return "geometry-candidate";
    }

    if (probe.Float32Values.Take(4).Any(static f => Math.Abs(f - 1.0f) < 0.0001f) && length % 4 == 0)
    {
      return "animation-or-transform-candidate";
    }

    if (probe.StrideCandidates.Any(static s => s.Stride is 12 or 24 or 32 or 36 or 48))
    {
      return "structured-bin-candidate";
    }

    return $"bin.signature.{probe.First8}";
  }

  private static IEnumerable<string> ReadCandidateNames(AppOptions options)
  {
    foreach (var name in options.Names)
    {
      if (!string.IsNullOrWhiteSpace(name))
      {
        yield return name;
      }
    }

    if (string.IsNullOrWhiteSpace(options.NamesFile))
    {
      yield break;
    }

    var namesFile = Path.GetFullPath(options.NamesFile);
    if (!File.Exists(namesFile))
    {
      throw new FileNotFoundException($"Names file does not exist: {namesFile}", namesFile);
    }

    foreach (var line in File.ReadLines(namesFile, Encoding.UTF8))
    {
      var trimmed = line.Trim();
      if (trimmed.Length == 0 || trimmed.StartsWith('#'))
      {
        continue;
      }

      yield return trimmed;
    }
  }

  private static void AddNameMatches(List<NameMatchRecord> matches, ManifestLookup lookup, string normalizedName, int byteLength, string algorithm, uint hash, AppOptions options)
  {
    if (!lookup.EntriesByFnv.TryGetValue(hash, out var hashMatches))
    {
      return;
    }

    var unique = hashMatches.Count == 1;
    if (options.RequireUnique && !unique)
    {
      return;
    }

    foreach (var entry in hashMatches)
    {
      var lengthMatches = entry.NameLength is null || entry.NameLength.Value == byteLength;
      if (options.OnlyLengthMatch && !lengthMatches)
      {
        continue;
      }

      var confidence = 50 + (lengthMatches ? 30 : 0) + (unique ? 20 : 0);
      if (confidence < options.MinConfidence)
      {
        continue;
      }

      matches.Add(new NameMatchRecord(
          Name: normalizedName,
          Algorithm: algorithm,
          Hash: hash,
          Length: byteLength,
          LengthMatchesManifest: lengthMatches,
          Confidence: confidence,
          CollisionCount: hashMatches.Count,
          IsUniqueHashMatch: unique,
          IsRecovered: lengthMatches && (unique || !options.RequireUnique) && confidence >= options.MinConfidence,
          ManifestEntryIndex: entry.Index,
          IdPrefix: entry.IdPrefix,
          ManifestNameLength: entry.NameLength,
          PakIndex: entry.PakIndex,
          PakOffset: entry.PakOffset,
          CompressedSize: entry.CompressedSize,
          Size: entry.Size,
          Language: entry.Language));
    }
  }

  private static IReadOnlyDictionary<string, RecoveredNameRecord> LoadRecoveredNames(string? path, int minConfidence)
  {
    var recovered = new Dictionary<string, RecoveredNameRecord>(StringComparer.OrdinalIgnoreCase);
    if (string.IsNullOrWhiteSpace(path))
    {
      return recovered;
    }

    var fullPath = Path.GetFullPath(path);
    if (!File.Exists(fullPath))
    {
      throw new FileNotFoundException($"Recovered names file does not exist: {fullPath}", fullPath);
    }

    foreach (var line in File.ReadLines(fullPath, Encoding.UTF8))
    {
      if (string.IsNullOrWhiteSpace(line))
      {
        continue;
      }

      var record = JsonSerializer.Deserialize<RecoveredNameRecord>(line, JsonOptions());
      if (record is null || record.Confidence < minConfidence || !record.LengthMatchesManifest || !record.IsRecovered)
      {
        continue;
      }

      recovered.TryAdd(record.IdPrefix, record);
    }

    return recovered;
  }

  private static string BuildRecoveredOutputPath(string outDirectory, string recoveredName, string idPrefix, string detectedExtension)
  {
    var normalized = NormalizeAssetName(recoveredName);
    var relative = normalized.Split('/', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
    var parts = new List<string> { outDirectory, "recovered" };
    parts.AddRange(relative);
    var candidate = Path.GetFullPath(Path.Combine(parts.ToArray()));
    var root = Path.GetFullPath(Path.Combine(outDirectory, "recovered"));
    if (!candidate.StartsWith(root, StringComparison.OrdinalIgnoreCase))
    {
      candidate = Path.Combine(root, $"{idPrefix}.{detectedExtension}");
    }

    var finalPath = candidate;
    if (Path.GetExtension(finalPath).Length == 0)
    {
      finalPath += "." + detectedExtension;
    }

    if (!File.Exists(finalPath))
    {
      return finalPath;
    }

    var directory = Path.GetDirectoryName(finalPath)!;
    var name = Path.GetFileNameWithoutExtension(finalPath);
    var extension = Path.GetExtension(finalPath);
    return Path.Combine(directory, $"{name}_{idPrefix}{extension}");
  }

  private static bool RecoveredNameMatchesDetectedType(string recoveredName, string detectedExtension)
  {
    var extension = Path.GetExtension(recoveredName.Replace('/', Path.DirectorySeparatorChar)).TrimStart('.').ToLowerInvariant();
    if (extension.Length == 0)
    {
      return true;
    }

    if (extension == detectedExtension)
    {
      return true;
    }

    return extension switch
    {
      "jpeg" => detectedExtension == "jpg",
      "wav" => detectedExtension == "riff",
      _ => false
    };
  }

  private static string NormalizeAssetName(string name)
  {
    return name.Trim()
        .Replace('\\', '/')
        .TrimStart('/')
        .ToLowerInvariant();
  }

  private static uint ComputeFnv1Hash(string value)
  {
    const uint fnvOffset = 2166136261;
    const uint fnvPrime = 16777619;
    var hash = fnvOffset;
    foreach (var b in Encoding.UTF8.GetBytes(value))
    {
      hash = unchecked(hash * fnvPrime);
      hash ^= b;
    }

    return hash;
  }

  private static uint ComputeFnv1AHash(string value)
  {
    const uint fnvOffset = 2166136261;
    const uint fnvPrime = 16777619;
    var hash = fnvOffset;
    foreach (var b in Encoding.UTF8.GetBytes(value))
    {
      hash ^= b;
      hash = unchecked(hash * fnvPrime);
    }

    return hash;
  }

  private static ExtractionFilter BuildExtractionFilter(AppOptions options, ManifestLookup manifestLookup)
  {
    var targetIds = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var descriptions = new List<string>();

    if (!string.IsNullOrWhiteSpace(options.IdFilter))
    {
      var id = NormalizeIdPrefix(options.IdFilter);
      targetIds.Add(id);
      descriptions.Add($"id={id}");
    }

    if (options.FnvFilter is not null)
    {
      var matches = manifestLookup.Entries
          .Where(e => e.FilenameFnv1Hash == options.FnvFilter.Value)
          .ToArray();
      if (matches.Length == 0)
      {
        throw new InvalidOperationException($"No manifest entries matched FNV1 hash 0x{options.FnvFilter.Value:x8}.");
      }

      foreach (var match in matches)
      {
        targetIds.Add(match.IdPrefix);
      }

      descriptions.Add($"fnv=0x{options.FnvFilter.Value:x8} ({matches.Length} manifest match(es))");
    }

    if (options.ManifestIndexFilter is not null)
    {
      var match = manifestLookup.Entries.FirstOrDefault(e => e.Index == options.ManifestIndexFilter.Value);
      if (match is null)
      {
        throw new InvalidOperationException($"No manifest entry exists at index {options.ManifestIndexFilter.Value}.");
      }

      targetIds.Add(match.IdPrefix);
      descriptions.Add($"manifest-index={match.Index}");
    }

    var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);
    if (archiveFilter is not null)
    {
      descriptions.Add($"archive={archiveFilter}");
    }

    var typeFilter = NormalizeTypeFilter(options.TypeFilter);
    if (typeFilter is not null)
    {
      descriptions.Add($"type={typeFilter}");
    }

    if (options.GroupByType)
    {
      descriptions.Add("group-by-type=true");
    }

    return new ExtractionFilter(
        ArchiveName: archiveFilter,
        TargetIds: targetIds.Count > 0 ? targetIds : null,
        Type: typeFilter,
        GroupByType: options.GroupByType,
        Description: string.Join(", ", descriptions));
  }

  private static string NormalizeIdPrefix(string value)
  {
    var normalized = value.Trim();
    if (normalized.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
    {
      normalized = normalized[2..];
    }

    normalized = normalized.ToLowerInvariant();
    if (normalized.Length != 16 || normalized.Any(c => !Uri.IsHexDigit(c)))
    {
      throw new ArgumentException("--id must be a 16-hex-character asset ID prefix.");
    }

    return normalized;
  }

  private static string? NormalizeArchiveFilter(string? value)
  {
    if (string.IsNullOrWhiteSpace(value))
    {
      return null;
    }

    var normalized = value.Trim();
    if (normalized.StartsWith("assets.", StringComparison.OrdinalIgnoreCase))
    {
      return normalized.ToLowerInvariant();
    }

    if (normalized.StartsWith('.'))
    {
      normalized = normalized[1..];
    }

    if (int.TryParse(normalized, out var archiveNumber) && archiveNumber >= 0)
    {
      return $"assets.{archiveNumber:D3}";
    }

    throw new ArgumentException("--archive must look like assets.042, .042, or 42.");
  }

  private static string? NormalizeTypeFilter(string? value)
  {
    if (string.IsNullOrWhiteSpace(value))
    {
      return null;
    }

    var normalized = value.Trim().TrimStart('.').ToLowerInvariant();
    if (normalized.Length == 0 || normalized.Any(c => !(char.IsAsciiLetterOrDigit(c) || c == '_')))
    {
      throw new ArgumentException("--type must be a simple detected extension/type such as dds, riff, txt, lua, xml, bin, nif, or lzma2.");
    }

    return normalized;
  }

  private static string NormalizeSemanticCategoryFilter(string value)
  {
    var normalized = value.Trim().ToLowerInvariant();
    if (normalized.Length == 0)
    {
      throw new ArgumentException("--semantic-category cannot be blank.");
    }

    var wildcard = normalized.EndsWith('*');
    var body = wildcard ? normalized[..^1] : normalized;
    if (body.Length == 0 ||
        body.Any(static c => !(char.IsAsciiLetterOrDigit(c) || c is ':' or '-' or '_' or '.')))
    {
      throw new ArgumentException("--semantic-category must be a simple category such as hint:map-zone, ref:texture, type:xml, or hint:*.");
    }

    return normalized;
  }

  private static bool SemanticCategoryMatches(List<string> categories, List<string> filters)
  {
    if (filters.Count == 0)
    {
      return true;
    }

    foreach (var filter in filters)
    {
      if (filter.EndsWith("*", StringComparison.Ordinal))
      {
        var prefix = filter[..^1];
        if (categories.Any(c => c.StartsWith(prefix, StringComparison.OrdinalIgnoreCase)))
        {
          return true;
        }

        continue;
      }

      if (categories.Any(c => string.Equals(c, filter, StringComparison.OrdinalIgnoreCase)))
      {
        return true;
      }
    }

    return false;
  }

  private static uint ParseUInt32Flexible(string value, string optionName)
  {
    var normalized = value.Trim();
    var style = System.Globalization.NumberStyles.Integer;
    if (normalized.StartsWith("0x", StringComparison.OrdinalIgnoreCase))
    {
      normalized = normalized[2..];
      style = System.Globalization.NumberStyles.HexNumber;
    }

    if (!uint.TryParse(normalized, style, System.Globalization.CultureInfo.InvariantCulture, out var parsed))
    {
      throw new ArgumentException($"{optionName} must be a uint32 decimal or 0x-prefixed hex value.");
    }

    return parsed;
  }

  private static string ResolveManifestPath(string rootDirectory, string? manifestPath)
  {
    if (!string.IsNullOrWhiteSpace(manifestPath))
    {
      var candidate = Path.IsPathRooted(manifestPath)
          ? manifestPath
          : Path.Combine(rootDirectory, manifestPath);
      if (!File.Exists(candidate))
      {
        throw new FileNotFoundException($"Manifest file does not exist: {candidate}", candidate);
      }

      return Path.GetFullPath(candidate);
    }

    var defaultPath = Path.Combine(rootDirectory, "assets64.manifest");
    if (File.Exists(defaultPath))
    {
      return defaultPath;
    }

    var nestedDefaultPath = Path.Combine(rootDirectory, "Assets", "assets64.manifest");
    if (File.Exists(nestedDefaultPath))
    {
      return nestedDefaultPath;
    }

    var firstManifest = Directory.EnumerateFiles(rootDirectory, "*.manifest", SearchOption.TopDirectoryOnly)
        .OrderBy(static p => p)
        .FirstOrDefault();
    if (firstManifest is null)
    {
      throw new FileNotFoundException($"No *.manifest file found in {rootDirectory}");
    }

    return firstManifest;
  }

  private static string ResolveAssetsDirectory(string rootDirectory)
  {
    var nested = Path.Combine(rootDirectory, "Assets");
    if (Directory.Exists(nested))
    {
      return nested;
    }

    if (Directory.Exists(rootDirectory) &&
        Directory.EnumerateFiles(rootDirectory, "assets.*", SearchOption.TopDirectoryOnly).Any())
    {
      return rootDirectory;
    }

    return nested;
  }

  private static string ResolveOutputPath(string rootDirectory, string? outPath, string defaultFileName)
  {
    if (string.IsNullOrWhiteSpace(outPath))
    {
      return Path.GetFullPath(Path.Combine(rootDirectory, "..", "Exports", defaultFileName));
    }

    var resolved = Path.GetFullPath(outPath);
    var extension = Path.GetExtension(resolved);
    return string.IsNullOrEmpty(extension)
        ? Path.Combine(resolved, defaultFileName)
        : resolved;
  }

  private static void WriteJsonLines<T>(string path, IEnumerable<T> records, bool redactPaths = true)
  {
    var options = new JsonSerializerOptions
    {
      DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };
    if (redactPaths)
    {
      options.Converters.Add(new RedactingStringJsonConverter());
    }

    using var writer = new StreamWriter(path, append: false, Encoding.UTF8);
    foreach (var record in records)
    {
      writer.WriteLine(JsonSerializer.Serialize(record, options));
    }
  }

  private static IEnumerable<T> ReadJsonLines<T>(string path)
  {
    foreach (var line in File.ReadLines(path, Encoding.UTF8))
    {
      var trimmed = line.Trim();
      if (trimmed.Length == 0 || trimmed.StartsWith('#'))
      {
        continue;
      }

      yield return JsonSerializer.Deserialize<T>(trimmed)
          ?? throw new InvalidDataException($"Failed to parse JSONL record from {path}.");
    }
  }

  private static HashSet<string> ReadCopiedArchiveIds(string rootDirectory)
  {
    var ids = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
    var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
    if (!Directory.Exists(assetsDirectory))
    {
      return ids;
    }

    foreach (var archivePath in Directory.EnumerateFiles(assetsDirectory, "assets.*", SearchOption.TopDirectoryOnly).OrderBy(static p => p))
    {
      using var stream = new FileStream(archivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
      var entries = ReadArchiveEntryTable(stream);
      if (entries is null)
      {
        continue;
      }

      foreach (var entry in entries)
      {
        if (!entry.IsNull)
        {
          ids.Add(entry.IdPrefix);
        }
      }
    }

    return ids;
  }

  private static ManifestLookup ReadManifestLookup(string manifestPath)
  {
    var bytes = File.ReadAllBytes(manifestPath);
    if (bytes.Length < ManifestHeaderSize)
    {
      throw new InvalidDataException($"manifest is too short: {bytes.Length} bytes");
    }

    var magic = Encoding.ASCII.GetString(bytes, 0, 4);
    if (magic != "TWAM")
    {
      throw new InvalidDataException($"unexpected manifest magic '{magic}'");
    }

    var pakTable = ReadTableReference(bytes, 16);
    var entryTable = ReadTableReference(bytes, 32);
    var lookup = new ManifestLookup(Path.GetFileName(manifestPath), checked((int)pakTable.Count), checked((int)entryTable.Count));

    for (var i = 0; i < pakTable.Count; i++)
    {
      var offset = checked((int)(pakTable.Offset + i * pakTable.Stride));
      if (offset + 53 > bytes.Length)
      {
        break;
      }

      var stringOffset = ReadUInt32(bytes, offset);
      var compression = bytes[offset + 12];
      var shaA = ToHex(bytes.AsSpan(offset + 13, 20));
      var shaB = ToHex(bytes.AsSpan(offset + 33, 20));
      lookup.PakShaPrefixes.Add(shaA[..16]);
      lookup.PakShaPrefixes.Add(shaB[..16]);
      lookup.PakShas.Add(shaA);
      lookup.PakShas.Add(shaB);
      lookup.Paks.Add(new PakListingRecord(
          Index: i,
          StringOffset: stringOffset,
          Path: ReadNullTerminatedAscii(bytes, stringOffset, maxLength: 512),
          UncompressedSize: ReadUInt32(bytes, offset + 4),
          CompressedSize: ReadUInt32(bytes, offset + 8),
          Compression: compression,
          Sha1WhenUncompressed: shaA,
          Sha1WhenCompressed: shaB));
    }

    for (var i = 0; i < entryTable.Count; i++)
    {
      var offset = checked((int)(entryTable.Offset + i * entryTable.Stride));
      if (offset + entryTable.Stride > bytes.Length)
      {
        break;
      }

      var idPrefix = ToHex(bytes.AsSpan(offset, 8));
      var hash = ToHex(bytes.AsSpan(offset + 32, 20));
      lookup.Table1Hashes.Add(hash);
      var entry = new ManifestEntryBrief(
          Index: i,
          IdPrefix: idPrefix,
          FilenameFnv1Hash: ReadUInt32(bytes, offset + 8),
          PakOffset: ReadUInt32(bytes, offset + 12),
          CompressedSize: ReadUInt32(bytes, offset + 16),
          Size: ReadUInt32(bytes, offset + 20),
          PakIndex: ReadUInt16(bytes, offset + 24),
          Bitfield1: ReadUInt16(bytes, offset + 26),
          Bitfield2: ReadUInt16(bytes, offset + 28),
          UnknownByte: bytes[offset + 30],
          Language: bytes[offset + 31],
          Hash: hash,
          UnknownInt: ReadUInt32(bytes, offset + 52),
          NameLength: entryTable.Stride >= 58 ? ReadUInt16(bytes, offset + 56) : null);
      lookup.Entries.Add(entry);
      lookup.Table1ById.TryAdd(idPrefix, entry);
      if (!lookup.EntriesByFnv.TryGetValue(entry.FilenameFnv1Hash, out var hashMatches))
      {
        hashMatches = [];
        lookup.EntriesByFnv.Add(entry.FilenameFnv1Hash, hashMatches);
      }

      hashMatches.Add(entry);
    }

    return lookup;
  }

  private static ArchiveMatchResult MatchArchiveIds(string archivePath, ManifestLookup lookup)
  {
    var result = new ArchiveMatchResult();
    var bytes = File.ReadAllBytes(archivePath);
    if (bytes.Length < ArchiveHeaderSize || Encoding.ASCII.GetString(bytes, 0, 4) != "TWAD")
    {
      return result;
    }

    var tableOffset = checked((int)ReadUInt32(bytes, 8));
    var maxEntries = checked((int)Math.Min(ReadUInt32(bytes, 12), int.MaxValue));
    for (var i = 0; i < maxEntries; i++)
    {
      var entryOffset = tableOffset + i * ArchiveEntrySize;
      if (entryOffset + ArchiveEntrySize > bytes.Length)
      {
        break;
      }

      var entry = ReadArchiveEntry(bytes, entryOffset, i);
      if (entry.IsNull)
      {
        continue;
      }

      result.NonNullEntries++;
      if (lookup.Table1ById.TryGetValue(entry.IdPrefix, out var manifestEntry))
      {
        result.Table1IdMatches++;
        if (result.Samples.Count < 10)
        {
          result.Samples.Add(new ManifestArchiveMatchSample(
              ArchiveEntryIndex: i,
              IdPrefix: entry.IdPrefix,
              ManifestEntryIndex: manifestEntry.Index,
              FilenameFnv1Hash: manifestEntry.FilenameFnv1Hash,
              PakOffset: manifestEntry.PakOffset,
              CompressedSize: manifestEntry.CompressedSize,
              Size: manifestEntry.Size,
              PakIndex: manifestEntry.PakIndex,
              NameLength: manifestEntry.NameLength));
        }
      }

      if (lookup.Table1Hashes.Contains(entry.Sha1))
      {
        result.Table1ShaMatches++;
      }

      if (lookup.PakShaPrefixes.Contains(entry.IdPrefix))
      {
        result.PakShaPrefixMatches++;
      }

      if (lookup.PakShas.Contains(entry.Sha1))
      {
        result.PakShaMatches++;
      }
    }

    return result;
  }

  private static ArchiveExtractResult ExtractArchive(
      string archivePath,
      string outDirectory,
      int maxPerArchive,
      ManifestLookup? manifestLookup,
      ExtractionFilter filter,
      IReadOnlyDictionary<string, RecoveredNameRecord> recoveredNames,
      AppOptions options)
  {
    var result = new ArchiveExtractResult { ArchiveName = Path.GetFileName(archivePath) };
    var bytes = File.ReadAllBytes(archivePath);
    if (bytes.Length < ArchiveHeaderSize)
    {
      result.Failed++;
      result.Warnings.Add("Archive is shorter than the TWAD header.");
      return result;
    }

    var magic = Encoding.ASCII.GetString(bytes, 0, 4);
    if (magic != "TWAD")
    {
      result.Failed++;
      result.Warnings.Add($"Unexpected magic '{magic}'.");
      return result;
    }

    var headerSize = ReadUInt32(bytes, 8);
    var maxEntries = checked((int)Math.Min(ReadUInt32(bytes, 12), int.MaxValue));
    var tableOffset = checked((int)headerSize);
    var archiveName = Path.GetFileName(archivePath);
    var archiveOut = Path.Combine(outDirectory, archiveName);

    for (var i = 0; i < maxEntries && result.Written < maxPerArchive; i++)
    {
      var entryOffset = tableOffset + i * ArchiveEntrySize;
      if (entryOffset + ArchiveEntrySize > bytes.Length)
      {
        result.Warnings.Add($"Entry table ended early at index {i}.");
        break;
      }

      var entry = ReadArchiveEntry(bytes, entryOffset, i);
      if (entry.IsNull)
      {
        result.Skipped++;
        continue;
      }

      ManifestEntryBrief? manifestEntry = null;
      manifestLookup?.Table1ById.TryGetValue(entry.IdPrefix, out manifestEntry);
      if (!filter.EntryMatches(entry, manifestEntry))
      {
        result.Skipped++;
        continue;
      }

      if (entry.Offset + entry.Size > bytes.Length)
      {
        result.Failed++;
        result.Warnings.Add($"Entry {i} extends past EOF: offset={entry.Offset}, size={entry.Size}, file={bytes.Length}.");
        continue;
      }

      try
      {
        var packed = bytes.AsSpan(checked((int)entry.Offset), checked((int)entry.Size)).ToArray();
        var payload = DecompressPayload(entry.Compression, packed, entry.Sha1, entry.IdPrefix, options.Lzma2Mode);
        var unpacked = payload.Bytes;

        var detected = DetectFileType(unpacked);
        var extension = detected.Extension;
        if (!filter.TypeMatches(extension))
        {
          result.Skipped++;
          continue;
        }

        var fileName = manifestEntry is null
            ? $"{i:D6}_{entry.IdPrefix}.{extension}"
            : $"{i:D6}_m{manifestEntry.Index:D6}_fnv{manifestEntry.FilenameFnv1Hash:x8}_pak{manifestEntry.PakIndex:D4}_off{manifestEntry.PakOffset}_{entry.IdPrefix}.{extension}";
        var hasUsableRecoveredName = recoveredNames.TryGetValue(entry.IdPrefix, out var recoveredName)
            && RecoveredNameMatchesDetectedType(recoveredName.Name, extension);
        var outputPath = hasUsableRecoveredName
            ? BuildRecoveredOutputPath(outDirectory, recoveredName!.Name, entry.IdPrefix, extension)
            : Path.Combine(filter.GroupByType ? Path.Combine(outDirectory, extension, archiveName) : archiveOut, fileName);
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        File.WriteAllBytes(outputPath, unpacked);

        result.Written++;
        result.Samples.Add(new ExtractedPayloadSample(
            ArchiveName: archiveName,
            EntryIndex: i,
            IdPrefix: entry.IdPrefix,
            Compression: entry.Compression,
            PackedSize: entry.Size,
            UnpackedSize: unpacked.Length,
            PackedSha1: payload.PackedSha1,
            UnpackedSha1: payload.UnpackedSha1,
            RelativePath: Path.GetRelativePath(outDirectory, outputPath),
            RecoveredName: hasUsableRecoveredName ? recoveredName?.Name : null,
            DecodeStatus: payload.Status,
            Width: detected.Width,
            Height: detected.Height,
            MipMapCount: detected.MipMapCount,
            Format: detected.Format,
            RiffType: detected.RiffType,
            ManifestEntryIndex: manifestEntry?.Index,
            FilenameFnv1Hash: manifestEntry?.FilenameFnv1Hash,
            NameLength: manifestEntry?.NameLength,
            PakIndex: manifestEntry?.PakIndex,
            PakOffset: manifestEntry?.PakOffset,
            ManifestCompressedSize: manifestEntry?.CompressedSize,
            ManifestSize: manifestEntry?.Size));
      }
      catch (Exception ex)
      {
        result.Failed++;
        result.Warnings.Add($"Entry {i} failed: {ex.Message}");
      }
    }

    return result;
  }

  private static byte[] InflateZlibWithDeflateFallback(byte[] packed)
  {
    try
    {
      using var input = new MemoryStream(packed);
      using var zlib = new ZLibStream(input, CompressionMode.Decompress);
      using var output = new MemoryStream();
      zlib.CopyTo(output);
      return output.ToArray();
    }
    catch (InvalidDataException)
    {
      using var input = new MemoryStream(packed);
      using var deflate = new DeflateStream(input, CompressionMode.Decompress);
      using var output = new MemoryStream();
      deflate.CopyTo(output);
      return output.ToArray();
    }
  }

  internal static PayloadDecodeResult DecompressPayload(ushort compression, byte[] packed, string expectedPackedSha, string expectedUnpackedPrefix, string lzma2Mode)
  {
    var packedSha = ComputeSha1Hex(packed);
    if (!StringComparer.OrdinalIgnoreCase.Equals(packedSha, expectedPackedSha))
    {
      throw new InvalidDataException($"packed SHA1 mismatch. expected {expectedPackedSha}, actual {packedSha}");
    }

    byte[] unpacked;
    string status;
    switch (compression)
    {
      case 0:
        unpacked = packed;
        status = "raw";
        break;
      case 1:
        unpacked = InflateZlibWithDeflateFallback(packed);
        status = "zlib";
        break;
      case 2:
        if (string.Equals(lzma2Mode, "off", StringComparison.OrdinalIgnoreCase))
        {
          throw new NotSupportedException("lzma2-disabled");
        }

        if (HasXzMagic(packed))
        {
          unpacked = InflateXzFramedLzma2(packed);
          status = "xz-framed-lzma2";
          break;
        }

        throw new NotSupportedException("lzma2-raw-unhandled: payload is not XZ-framed; raw LZMA2 properties are not proven yet.");
      default:
        throw new NotSupportedException($"unsupported-compression-{compression}");
    }

    var unpackedSha = ComputeSha1Hex(unpacked);
    if (!string.IsNullOrWhiteSpace(expectedUnpackedPrefix) &&
        !unpackedSha.StartsWith(expectedUnpackedPrefix, StringComparison.OrdinalIgnoreCase))
    {
      throw new InvalidDataException($"unpacked SHA1 prefix mismatch. expected {expectedUnpackedPrefix}, actual {unpackedSha[..16]}");
    }

    return new PayloadDecodeResult(unpacked, packedSha, unpackedSha, status);
  }

  private static bool HasXzMagic(ReadOnlySpan<byte> bytes)
  {
    return bytes.Length >= 6
        && bytes[0] == 0xfd
        && bytes[1] == 0x37
        && bytes[2] == 0x7a
        && bytes[3] == 0x58
        && bytes[4] == 0x5a
        && bytes[5] == 0x00;
  }

  private static byte[] InflateXzFramedLzma2(byte[] packed)
  {
    using var input = new MemoryStream(packed);
    using var xz = new XZStream(input);
    using var output = new MemoryStream();
    xz.CopyTo(output);
    return output.ToArray();
  }

  private static string ComputeSha1Hex(byte[] bytes)
  {
    return Convert.ToHexString(SHA1.HashData(bytes)).ToLowerInvariant();
  }

  private static string GuessExtension(ReadOnlySpan<byte> data)
  {
    return DetectFileType(data).Extension;
  }

  private static DetectedFileType DetectFileType(ReadOnlySpan<byte> data)
  {
    if (data.Length >= 4 && data[0] == 'D' && data[1] == 'D' && data[2] == 'S' && data[3] == ' ')
    {
      var width = data.Length >= 20 ? checked((int)BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(16, 4))) : (int?)null;
      var height = data.Length >= 16 ? checked((int)BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(12, 4))) : (int?)null;
      var mipMapCount = data.Length >= 32 ? checked((int)BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(28, 4))) : (int?)null;
      var format = TryReadDdsFormat(data);
      return new DetectedFileType("dds", width, height, mipMapCount, format);
    }

    if (data.Length >= 4 && data[0] == 0x89 && data[1] == 'P' && data[2] == 'N' && data[3] == 'G')
    {
      return new DetectedFileType("png");
    }

    if (data.Length >= 3 && data[0] == 0xff && data[1] == 0xd8 && data[2] == 0xff)
    {
      return new DetectedFileType("jpg");
    }

    if (data.Length >= 4 && data[0] == 'O' && data[1] == 'g' && data[2] == 'g' && data[3] == 'S')
    {
      return new DetectedFileType("ogg");
    }

    if (data.Length >= 4 && data[0] == 'R' && data[1] == 'I' && data[2] == 'F' && data[3] == 'F')
    {
      var riffType = data.Length >= 12 ? Encoding.ASCII.GetString(data.Slice(8, 4)) : null;
      return new DetectedFileType("riff", RiffType: riffType);
    }

    if (StartsWithAscii(data, "Gamebryo File Format"))
    {
      return new DetectedFileType("nif", Format: ReadAsciiLine(data, maxLength: 128));
    }

    if (LooksText(data))
    {
      var textPrefix = Encoding.ASCII.GetString(data[..Math.Min(data.Length, 4096)]);
      if (LooksLikeXmlText(textPrefix))
      {
        return new DetectedFileType("xml");
      }

      if (LooksLikeLuaText(textPrefix))
      {
        return new DetectedFileType("lua");
      }

      return new DetectedFileType("txt");
    }

    return new DetectedFileType("bin");
  }

  private static bool StartsWithAscii(ReadOnlySpan<byte> data, string value)
  {
    if (data.Length < value.Length)
    {
      return false;
    }

    for (var i = 0; i < value.Length; i++)
    {
      if (data[i] != value[i])
      {
        return false;
      }
    }

    return true;
  }

  private static string ReadAsciiLine(ReadOnlySpan<byte> data, int maxLength)
  {
    var length = 0;
    var limit = Math.Min(data.Length, maxLength);
    while (length < limit && data[length] is not (0 or 10 or 13))
    {
      length++;
    }

    return Encoding.ASCII.GetString(data[..length]);
  }

  private static string? TryReadDdsFormat(ReadOnlySpan<byte> data)
  {
    if (data.Length < 128)
    {
      return null;
    }

    var pixelFormatFlags = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(80, 4));
    var fourCc = data.Slice(84, 4);
    if (fourCc[0] != 0 || fourCc[1] != 0 || fourCc[2] != 0 || fourCc[3] != 0)
    {
      var value = Encoding.ASCII.GetString(fourCc);
      if (value.All(static c => c >= 32 && c <= 126))
      {
        return value;
      }
    }

    return $"flags:0x{pixelFormatFlags:x8}";
  }

  private static bool LooksText(ReadOnlySpan<byte> data)
  {
    var sampleLength = Math.Min(data.Length, 256);
    if (sampleLength == 0)
    {
      return false;
    }

    var printable = 0;
    for (var i = 0; i < sampleLength; i++)
    {
      var b = data[i];
      if (b is 9 or 10 or 13 || b >= 32 && b <= 126)
      {
        printable++;
      }
    }

    return printable >= sampleLength * 9 / 10;
  }

  private static void PrintUsage()
  {
    Console.WriteLine("RiftAssetDumper");
    Console.WriteLine();
    Console.WriteLine("Usage:");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe --root <SourceFolder>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- match-ids --root <SourceFolder>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- list-paks --root <SourceFolder> --out <OutFile>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- list-entries --root <SourceFolder> --out <OutFile> --limit 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- hash-name --name <candidate/path.ext>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- match-names --root <SourceFolder> --names-file <File>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-archives --root <SourceFolder> --archive 42 --max-per-archive 20");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- scan-compression --root <SourceFolder>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- mine-strings --input <ExtractedFolder>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-asset-signatures --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- build-asset-semantic-index --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-binary-signatures --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-binary --root <SourceFolder> --id <16hex>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif --root <SourceFolder> --id <16hex>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-streams --root <SourceFolder> --id <16hex> --mesh-block <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-mesh --root <SourceFolder> --id <16hex> --mesh-block <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- decode-nif-geometry --root <SourceFolder> --id <16hex> --mesh-block <n> [--write-obj] [--experimental] [--experimental-position-source]");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-position-source --root <SourceFolder> --id <16hex> --mesh-block <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- validate-uint16-positions --root <SourceFolder> --id <16hex> --mesh-block <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-attribute-extra --root <SourceFolder> --id <16hex> --mesh-block <n> --extra-offset <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-stream-body --root <SourceFolder> --id <16hex> --stream-block <n>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-blocks --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-mesh-streams --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-mesh-bindings --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-headers --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-bodies --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-endianness --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-index-candidates --root <SourceFolder> --max-total 100");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- mine-nif-references --root <SourceFolder> --out <candidates.txt>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- link-nif-textures --root <SourceFolder>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- extract-linked-textures --root <SourceFolder> --input <links.jsonl>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- extract-nif-bundle --root <SourceFolder> --input <links.jsonl> --id <16hex>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- extract-nif-bundles --root <SourceFolder> --live-root <RiftLiveFolder> --input <links.jsonl> --limit 10");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-bundles --root <SourceFolder> --input <links.jsonl>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- plan-nif-bundle-archives --root <SourceFolder> --live-root <RiftLiveFolder> --input <links.jsonl>");
    Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- extract-archives --root <SourceFolder> --out <OutFolder> --max-per-archive 10");
    Console.WriteLine();
    Console.WriteLine("Defaults:");
    Console.WriteLine("  command: probe");
    Console.WriteLine("  root:    ./Source when it exists, otherwise current directory");
    Console.WriteLine();
    Console.WriteLine("Options:");
    Console.WriteLine("  --root <path>   Folder containing assets64.manifest and Assets/assets.###");
    Console.WriteLine("  --live-root <path>");
    Console.WriteLine("                  Live RIFT root to scan/read fallback for compression, NIF planning, or targeted bundle extraction");
    Console.WriteLine("  --input <path>  Input file/folder for mine-strings, probe-binary, probe-nif, or NIF stream probes");
    Console.WriteLine("  --manifest <path>");
    Console.WriteLine("                  Manifest to use. Defaults to assets64.manifest under --root");
    Console.WriteLine("  --out <path>    Output folder/file depending on command");
    Console.WriteLine("  --limit <n>     Maximum records for list-paks/list-entries; default is all");
    Console.WriteLine("  --archive <n|assets.nnn>");
    Console.WriteLine("                  Only process one copied archive chunk");
    Console.WriteLine("  --id <16hex>    Only extract one asset ID prefix");
    Console.WriteLine("  --mesh-block <n>");
    Console.WriteLine("  --experimental"); Console.WriteLine("                  Enable experimental geometry decode features"); Console.WriteLine("  --experimental-position-source"); Console.WriteLine("                  Use linked-stream position-source probe when no attribute sets found");
      Console.WriteLine("  --write-obj"); Console.WriteLine("                  Write decoded geometry to Wavefront OBJ file"); Console.WriteLine("                  Optional NiMesh block index filter for probe-nif-streams");
    Console.WriteLine("  --stream-block <n>");
    Console.WriteLine("                  Optional NiDataStream block index filter for probe-nif-stream-body");
    Console.WriteLine("  --extra-offset <n>");
    Console.WriteLine("                  Mesh payload offset for probe-nif-attribute-extra");
    Console.WriteLine("  --fnv <uint|0xhex>");
    Console.WriteLine("                  Only extract entries with this filename FNV1 hash");
    Console.WriteLine("  --type <kind>   Only write/inspect detected type such as dds, riff, txt, lua, xml, bin, nif, lzma2");
    Console.WriteLine("  --semantic-category <category>");
    Console.WriteLine("                  Only keep asset semantic-index/signature hits with a category, such as hint:map-zone or hint:*");
    Console.WriteLine("  --group-by-type");
    Console.WriteLine("                  Write extracted files under <out>/<type>/<archive>/...");
    Console.WriteLine("  --manifest-index <n>");
    Console.WriteLine("                  Only extract the asset at this manifest Table 1 row");
    Console.WriteLine("  --name <path>   Candidate asset path/name for hash-name or match-names");
    Console.WriteLine("  --names-file <path>");
    Console.WriteLine("                  UTF-8 candidate names file; blank/# lines ignored");
    Console.WriteLine("  --algorithm fnv1|fnv1a|both");
    Console.WriteLine("                  Name hash algorithm for match-names; default both");
    Console.WriteLine("  --only-length-match");
    Console.WriteLine("                  Only keep name matches where byte length matches manifest");
    Console.WriteLine("  --require-unique");
    Console.WriteLine("                  Only keep name matches whose hash maps to one manifest row");
    Console.WriteLine("  --min-confidence <0-100>");
    Console.WriteLine("                  Minimum match confidence; default 0 for matching, 80 for recovered extraction");
    Console.WriteLine("  --use-recovered-names <jsonl>");
    Console.WriteLine("                  Use recovered name JSONL during extraction");
    Console.WriteLine("  --lzma2-mode auto|xz-only|off");
    Console.WriteLine("                  LZMA2 behavior; raw LZMA2 remains reported as unhandled");
    Console.WriteLine("  --no-redact-paths");
    Console.WriteLine("                  Write/display full local paths instead of redacted user-profile paths");
    Console.WriteLine("  --max-total <n>");
    Console.WriteLine("                  Stop after this many total extracted files");
    Console.WriteLine("  --max-per-archive <n>");
    Console.WriteLine("                  Maximum entries to extract from each assets.### file");
    Console.WriteLine("  --no-json       Do not write probe-report.json");
    Console.WriteLine("  --help          Show this help");
  }

  private static JsonSerializerOptions JsonOptions(bool redactPaths = true)
  {
    var options = new JsonSerializerOptions
    {
      WriteIndented = true,
      DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull
    };
    if (redactPaths)
    {
      options.Converters.Add(new RedactingStringJsonConverter());
    }

    return options;
  }

  private static string DisplayPath(AppOptions options, string value) => RedactSensitivePath(value, options.RedactPaths);

  private static string RedactSensitivePath(string value, bool redactPaths)
  {
    if (!redactPaths || string.IsNullOrEmpty(value))
    {
      return value;
    }

    static string replacePathRoot(string input, string? path, string token)
    {
      if (string.IsNullOrWhiteSpace(path))
      {
        return input;
      }

      var redactedInput = input;
      foreach (var candidate in new[] { path.TrimEnd('\\', '/'), path.TrimEnd('\\', '/').Replace('\\', '/') }.Distinct(StringComparer.OrdinalIgnoreCase))
      {
        if (string.IsNullOrWhiteSpace(candidate))
        {
          continue;
        }

        var pattern = Regex.Escape(candidate) + @"(?=$|[\\/])";
        redactedInput = Regex.Replace(
            redactedInput,
            pattern,
            token,
            RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
      }

      return redactedInput;
    }

    var redacted = replacePathRoot(value, Environment.GetEnvironmentVariable("USERPROFILE"), "%USERPROFILE%");
    redacted = Regex.Replace(
        redacted,
        @"(?i)([A-Z]:[\\/]+Users[\\/]+)([^\\/:\r\n]+)(?=$|[\\/])",
        "$1%USERNAME%",
        RegexOptions.CultureInvariant);

    return redacted;
  }

  private sealed class RedactingStringJsonConverter : JsonConverter<string>
  {
    public override string? Read(ref Utf8JsonReader reader, Type typeToConvert, JsonSerializerOptions options)
    {
      return reader.GetString();
    }

    public override void Write(Utf8JsonWriter writer, string value, JsonSerializerOptions options)
    {
      writer.WriteStringValue(RedactSensitivePath(value, redactPaths: true));
    }
  }

  private sealed record AppOptions(
      string Command,
      string RootDirectory,
      bool WriteJson,
      bool ShowHelp,
      string? OutDirectory,
      string? ManifestPath,
      int MaxPerArchive,
      int Limit,
      string? ArchiveFilter,
      string? IdFilter,
      uint? FnvFilter,
      int? ManifestIndexFilter,
      int MaxTotal,
      List<string> Names,
      string? NamesFile,
      string? TypeFilter,
      List<string> SemanticCategoryFilters,
      bool GroupByType,
      string? InputPath,
      string? LiveRoot,
      string Algorithm,
      bool OnlyLengthMatch,
      bool RequireUnique,
      int MinConfidence,
      string? UseRecoveredNamesPath,
      string Lzma2Mode,
      int? MeshBlockFilter,
      int? StreamBlockFilter,
      int? ExtraOffsetFilter,
      bool RedactPaths,
      bool Experimental,
      bool ExperimentalPositionSource,
      bool ExportObj,
      bool WriteObj)
  {
    public static AppOptions Parse(string[] args)
    {
      var command = "probe";
      var root = Directory.Exists(Path.Combine(Environment.CurrentDirectory, "Source"))
          ? Path.Combine(Environment.CurrentDirectory, "Source")
          : Environment.CurrentDirectory;
      var writeJson = true;
      var showHelp = false;
      string? outDirectory = null;
      string? manifestPath = null;
      var maxPerArchive = 10;
      var limit = 0;
      string? archiveFilter = null;
      string? idFilter = null;
      uint? fnvFilter = null;
      int? manifestIndexFilter = null;
      var maxTotal = 0;
      var names = new List<string>();
      string? namesFile = null;
      string? typeFilter = null;
      var semanticCategoryFilters = new List<string>();
      var groupByType = false;
      string? inputPath = null;
      string? liveRoot = null;
      var algorithm = "both";
      var onlyLengthMatch = false;
      var requireUnique = false;
      var minConfidence = 0;
      string? useRecoveredNamesPath = null;
      var lzma2Mode = "auto";
      int? meshBlockFilter = null;
      int? streamBlockFilter = null;
      int? extraOffsetFilter = null;
      var redactPaths = true;
      var experimental = false;
      var experimentalPositionSource = false;
      var exportObj = false;
      var writeObj = false;

      for (var i = 0; i < args.Length; i++)
      {
        var arg = args[i];
        switch (arg)
        {
          case "probe":
          case "extract-archives":
          case "match-ids":
          case "list-paks":
          case "list-entries":
          case "hash-name":
          case "match-names":
          case "inventory-archives":
          case "scan-compression":
          case "mine-strings":
          case "inventory-asset-signatures":
          case "build-asset-semantic-index":
          case "inventory-binary-signatures":
          case "probe-binary":
          case "probe-nif":
          case "probe-nif-streams":
          case "probe-nif-mesh":
          case "decode-nif-geometry":
          case "probe-nif-attribute-extra":
          case "probe-nif-stream-body":
          case "inventory-nif":
          case "inventory-nif-blocks":
          case "inventory-nif-mesh-streams":
          case "inventory-nif-mesh-bindings":
          case "inventory-nif-stream-headers":
          case "inventory-nif-stream-bodies":
          case "inventory-nif-stream-endianness":
          case "inventory-nif-index-candidates":
          case "mine-nif-references":
          case "link-nif-textures":
          case "extract-linked-textures":
          case "extract-nif-bundle":
          case "extract-nif-bundles":
          case "inventory-nif-bundles":
          case "probe-nif-position-source":
          case "plan-nif-bundle-archives":
          case "validate-uint16-positions":
            command = arg;
            break;
          case "--help" or "-h" or "/?":
            showHelp = true;
            break;
          case "--no-json":
            writeJson = false;
            break;
          case "--no-redact-paths":
            redactPaths = false;
            break;
          case "--group-by-type":
            groupByType = true;
            break;
          case "--root":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--root requires a path argument.");
            }
            root = args[++i];
            break;
          case "--live-root":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--live-root requires a path argument.");
            }
            liveRoot = args[++i];
            break;
          case "--input":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--input requires a path argument.");
            }
            inputPath = args[++i];
            break;
          case "--manifest":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--manifest requires a path argument.");
            }
            manifestPath = args[++i];
            break;
          case "--out":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--out requires a path argument.");
            }
            outDirectory = args[++i];
            break;
          case "--max-per-archive":
          case "--max":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException($"{arg} requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out maxPerArchive) || maxPerArchive < 1)
            {
              throw new ArgumentException($"{arg} must be a positive integer.");
            }
            break;
          case "--limit":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--limit requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out limit) || limit < 0)
            {
              throw new ArgumentException("--limit must be a non-negative integer.");
            }
            break;
          case "--archive":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--archive requires an archive argument.");
            }
            archiveFilter = args[++i];
            break;
          case "--id":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--id requires a 16-hex-character asset ID prefix.");
            }
            idFilter = args[++i];
            break;
          case "--fnv":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--fnv requires a hash argument.");
            }
            fnvFilter = ParseUInt32Flexible(args[++i], "--fnv");
            break;
          case "--type":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--type requires a detected type argument.");
            }
            typeFilter = args[++i];
            break;
          case "--semantic-category":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--semantic-category requires a category argument.");
            }
            semanticCategoryFilters.Add(NormalizeSemanticCategoryFilter(args[++i]));
            break;
          case "--manifest-index":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--manifest-index requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out var parsedManifestIndex) || parsedManifestIndex < 0)
            {
              throw new ArgumentException("--manifest-index must be a non-negative integer.");
            }
            manifestIndexFilter = parsedManifestIndex;
            break;
          case "--name":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--name requires a candidate asset path/name.");
            }
            names.Add(args[++i]);
            break;
          case "--names-file":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--names-file requires a path argument.");
            }
            namesFile = args[++i];
            break;
          case "--algorithm":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--algorithm requires fnv1, fnv1a, or both.");
            }
            algorithm = args[++i].Trim().ToLowerInvariant();
            if (algorithm is not ("fnv1" or "fnv1a" or "both"))
            {
              throw new ArgumentException("--algorithm must be fnv1, fnv1a, or both.");
            }
            break;
          case "--only-length-match":
            onlyLengthMatch = true;
            break;
          case "--require-unique":
            requireUnique = true;
            break;
          case "--min-confidence":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--min-confidence requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out minConfidence) || minConfidence is < 0 or > 100)
            {
              throw new ArgumentException("--min-confidence must be an integer from 0 to 100.");
            }
            break;
          case "--use-recovered-names":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--use-recovered-names requires a JSONL path argument.");
            }
            useRecoveredNamesPath = args[++i];
            break;
          case "--lzma2-mode":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--lzma2-mode requires auto, xz-only, or off.");
            }
            lzma2Mode = args[++i].Trim().ToLowerInvariant();
            if (lzma2Mode is not ("auto" or "xz-only" or "off"))
            {
              throw new ArgumentException("--lzma2-mode must be auto, xz-only, or off.");
            }
            break;
          case "--experimental":
            experimental = true;
            break;
          case "--experimental-position-source":
            experimentalPositionSource = true;
            break;
          case "--export-obj":
            exportObj = true;
            break;
          case "--write-obj":
            writeObj = true;
            break;
          case "--mesh-block":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--mesh-block requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out var parsedMeshBlock) || parsedMeshBlock < 0)
            {
              throw new ArgumentException("--mesh-block must be a non-negative integer.");
            }
            meshBlockFilter = parsedMeshBlock;
            break;
          case "--stream-block":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--stream-block requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out var parsedStreamBlock) || parsedStreamBlock < 0)
            {
              throw new ArgumentException("--stream-block must be a non-negative integer.");
            }
            streamBlockFilter = parsedStreamBlock;
            break;
          case "--extra-offset":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--extra-offset requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out var parsedExtraOffset) || parsedExtraOffset < 0)
            {
              throw new ArgumentException("--extra-offset must be a non-negative integer.");
            }
            extraOffsetFilter = parsedExtraOffset;
            break;
          case "--max-total":
            if (i + 1 >= args.Length)
            {
              throw new ArgumentException("--max-total requires an integer argument.");
            }
            if (!int.TryParse(args[++i], out maxTotal) || maxTotal < 0)
            {
              throw new ArgumentException("--max-total must be a non-negative integer.");
            }
            break;
          default:
            throw new ArgumentException($"Unknown argument: {arg}");
        }
      }

      return new AppOptions(
          command,
          root,
          writeJson,
          showHelp,
          outDirectory,
          manifestPath,
          maxPerArchive,
          limit,
          archiveFilter,
          idFilter,
          fnvFilter,
          manifestIndexFilter,
          maxTotal,
          names,
          namesFile,
          typeFilter,
          semanticCategoryFilters,
          groupByType,
          inputPath,
          liveRoot,
          algorithm,
          onlyLengthMatch,
          requireUnique,
          minConfidence,
          useRecoveredNamesPath,
          lzma2Mode,
          meshBlockFilter,
          streamBlockFilter,
          extraOffsetFilter,
          redactPaths,
          experimental,
          experimentalPositionSource,
          exportObj,
          writeObj);
    }

    public int MaxTotalOrUnlimited() => MaxTotal > 0 ? MaxTotal : int.MaxValue;
  }
}

internal sealed record PayloadDecodeResult(
    byte[] Bytes,
    string PackedSha1,
    string UnpackedSha1,
    string Status);

internal sealed record CompressionScanReport(
    string RootDirectory,
    string ManifestPath,
    string AssetsDirectory,
    int ArchiveFilesScanned,
    Dictionary<string, int> ManifestPakCompressionCounts,
    Dictionary<string, int> ArchiveEntryCompressionCounts,
    int ArchiveNonNullEntries,
    List<CompressionManifestSample> ManifestSamples,
    List<CompressionArchiveSample> ArchiveSamples);

internal sealed record CompressionManifestSample(
    int PakIndex,
    uint StringOffset,
    string Path,
    byte Compression,
    uint UncompressedSize,
    uint CompressedSize,
    bool FileExists,
    string? FirstBytes);

internal sealed record CompressionArchiveSample(
    string ArchiveName,
    int EntryIndex,
    ushort Compression,
    uint Offset,
    uint PackedSize,
    string FirstBytes);

internal sealed class StringMineRecord(string candidate, int count, List<string> sampleSources)
{
  public string Candidate { get; } = candidate;
  public int Count { get; set; } = count;
  public List<string> SampleSources { get; } = sampleSources;
}

internal sealed record AssetSemanticIndexReport(
    string SchemaVersion,
    string GeneratedOutputNotice,
    string RootDirectory,
    string ManifestPath,
    List<string> SemanticCategoryFilters,
    int InspectedPayloads,
    int Failed,
    List<NifStringCount> TypeCounts,
    List<NifStringCount> SemanticCategoryCounts,
    List<AssetSignatureGroup> SignatureGroups,
    List<AssetSemanticIndexEntry> Entries);

internal sealed class AssetSignatureAccumulator(string type, string first4, string first8, string first16, string magicLabel)
{
  public string Type { get; } = type;
  public string First4 { get; } = first4;
  public string First8 { get; } = first8;
  public string First16 { get; } = first16;
  public string MagicLabel { get; } = magicLabel;
  public int Count { get; set; }
  public int MinSize { get; set; } = int.MaxValue;
  public int MaxSize { get; set; }
  public Dictionary<string, int> SemanticCategoryCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> XmlTagCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> XmlAttributeCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> XmlParseStatusCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> XmlParseWarningCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<AssetSignatureSample> Samples { get; } = [];
}

internal sealed record AssetSignatureGroup(
    string Type,
    string First4,
    string First8,
    string First16,
    string MagicLabel,
    int Count,
    int MinSize,
    int MaxSize,
    List<NifStringCount> SemanticCategoryCounts,
    List<NifStringCount> XmlTagCounts,
    List<NifStringCount> XmlAttributeCounts,
    List<NifStringCount> XmlParseStatusCounts,
    List<NifStringCount> XmlParseWarningCounts,
    List<AssetSignatureSample> Samples);

internal sealed record AssetSignatureSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int Size,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? PakIndex,
    uint? PakOffset,
    List<string> SemanticCategories,
    List<string> NameCandidates);

internal sealed record AssetSemanticIndexEntry(
    string AssetIdPrefix,
    string ArchiveName,
    int EntryIndex,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? PakIndex,
    uint? PakOffset,
    uint CompressedSize,
    int UnpackedSize,
    ushort Compression,
    string DetectedType,
    string? Format,
    string? RiffType,
    int? Width,
    int? Height,
    int? MipMapCount,
    string First4,
    string First8,
    string First16,
    string MagicLabel,
    List<string> SemanticCategories,
    List<string> NameCandidates,
    List<string> ReferenceSamples,
    List<NifStringCount> XmlTagCounts,
    List<NifStringCount> XmlAttributeCounts,
    string? XmlParseStatus,
    string? XmlParseWarning,
    int? XmlParseLineNumber,
    int? XmlParseLinePosition,
    int? XmlParsedElementCount,
    int? XmlParsedAttributeNameCount,
    List<string> TextSnippetSamples);

internal sealed record AssetSemanticProbe(
    string First4,
    string First8,
    string First16,
    string MagicLabel,
    List<string> SemanticCategories,
    List<string> NameCandidates,
    List<string> ReferenceSamples,
    List<NifStringCount> XmlTagCounts,
    List<NifStringCount> XmlAttributeCounts,
    string? XmlParseStatus,
    string? XmlParseWarning,
    int? XmlParseLineNumber,
    int? XmlParseLinePosition,
    int? XmlParsedElementCount,
    int? XmlParsedAttributeNameCount,
    List<string> TextSnippetSamples);

internal sealed record XmlFamilyProbe(
    List<NifStringCount> TagCounts,
    List<NifStringCount> AttributeCounts,
    string ParseStatus,
    string? ParseWarning,
    int? ParseLineNumber,
    int? ParseLinePosition,
    int ParsedElementCount,
    int ParsedAttributeNameCount);

internal sealed record BinarySignatureInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedBinPayloads,
    int Failed,
    List<BinarySignatureGroup> Groups);

internal sealed class BinarySignatureGroup(
    string First4,
    string First8,
    string First16,
    int Count,
    int MinSize,
    int MaxSize,
    Dictionary<string, int> SizeModuloCounts,
    List<BinarySignatureSample> Samples)
{
  public string First4 { get; } = First4;
  public string First8 { get; } = First8;
  public string First16 { get; } = First16;
  public int Count { get; set; } = Count;
  public int MinSize { get; set; } = MinSize;
  public int MaxSize { get; set; } = MaxSize;
  public Dictionary<string, int> SizeModuloCounts { get; } = SizeModuloCounts;
  public List<BinarySignatureSample> Samples { get; } = Samples;
}

internal sealed record BinarySignatureSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int Size,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? PakIndex,
    string Classification);

internal sealed record BinaryAssetSource(
    string? InputPath = null,
    string? ArchiveName = null,
    int? EntryIndex = null,
    string? IdPrefix = null,
    int? ManifestEntryIndex = null,
    uint? FilenameFnv1Hash = null,
    ushort? PakIndex = null,
    uint? PakOffset = null,
    string? SourceKind = null);

internal sealed record FoundPayload(
    string ArchiveName,
    int EntryIndex,
    byte[] Payload,
    string SourceKind);

internal sealed class ArchivePayloadLookup
{
  private readonly Dictionary<string, ArchivePayloadLocation> locations = new(StringComparer.OrdinalIgnoreCase);

  public int CopiedArchivesScanned { get; set; }

  public int LiveArchivesScanned { get; set; }

  public int IndexedPayloads => locations.Count;

  public bool Contains(string idPrefix) => locations.ContainsKey(idPrefix);

  public void Add(ArchivePayloadLocation location)
  {
    locations.TryAdd(location.IdPrefix, location);
  }

  public FoundPayload? Find(string idPrefix, string lzma2Mode)
  {
    if (!locations.TryGetValue(idPrefix, out var location))
    {
      return null;
    }

    using var stream = new FileStream(location.ArchivePath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite, bufferSize: 8192, FileOptions.RandomAccess);
    if ((long)location.Offset + location.Size > stream.Length)
    {
      throw new InvalidDataException($"Entry {location.EntryIndex} in {location.ArchiveName} extends past EOF.");
    }

    var packed = new byte[checked((int)location.Size)];
    stream.Position = location.Offset;
    stream.ReadExactly(packed);
    var payload = Program.DecompressPayload(location.Compression, packed, location.Sha1, location.IdPrefix, lzma2Mode);
    return new FoundPayload(location.ArchiveName, location.EntryIndex, payload.Bytes, location.SourceKind);
  }
}

internal sealed record ArchivePayloadLocation(
    string IdPrefix,
    string ArchivePath,
    string ArchiveName,
    int EntryIndex,
    uint Offset,
    uint Size,
    ushort Compression,
    string Sha1,
    string SourceKind);

internal sealed record BinaryProbeData(
    string First4,
    string First8,
    string First16,
    List<uint> UInt32Values,
    List<int> Int32Values,
    List<float> Float32Values,
    List<StrideCandidate> StrideCandidates);

internal sealed record StrideCandidate(int Stride, int Count);

internal sealed record BinaryProbeReport(
    BinaryAssetSource Source,
    string Type,
    int Length,
    string Classification,
    string First64,
    string First4,
    string First8,
    string First16,
    List<uint> UInt32Values,
    List<int> Int32Values,
    List<float> Float32Values,
    List<StrideCandidate> StrideCandidates);

internal sealed record NifProbeReport(
    BinaryAssetSource Source,
    int Length,
    string First64,
    NifHeaderInfo Header);

internal sealed record NifStreamProbeReport(
    BinaryAssetSource Source,
    int Length,
    string NifVersion,
    int MeshBlockCount,
    int MeshesEmitted,
    int CandidateLinks,
    List<string> HeaderWarnings,
    List<NifMeshStreamProbe> Meshes);

internal sealed record NifMeshStreamProbe(
    int MeshBlockIndex,
    uint MeshSize,
    int MeshDataOffset,
    string MeshFirst64,
    List<uint> UInt32Prefix,
    List<int> Int32Prefix,
    List<float?> Float32Prefix,
    List<string> StringSamples,
    List<NifStreamTargetProbe> StreamCandidates);

internal sealed record NifStreamTargetProbe(
    int MeshPayloadOffset,
    int TargetBlockIndex,
    string TargetTypeName,
    int TargetDataOffset,
    uint TargetSize,
    string TargetFirst64,
    List<ushort> UInt16Prefix,
    List<uint> UInt32Prefix,
    List<int> Int32Prefix,
    List<float?> Float32Prefix,
    List<StrideCandidate> WholeBlockStrideCandidates,
    List<BodyStrideCandidate> BodyStrideCandidates,
    uint? DeclaredPayloadBytes,
    int? DeclaredPayloadOffset,
    List<StrideCandidate> DeclaredPayloadStrideCandidates,
    bool MaybeStringIndex,
    string? StringValue);

internal sealed record NifMeshProbeReport(
    BinaryAssetSource Source,
    int Length,
    string NifVersion,
    int MeshBlockCount,
    int MeshesEmitted,
    int CandidateLinks,
    int Pairings,
    int AttributeSets,
    List<string> HeaderWarnings,
    List<NifMeshProbe> Meshes);

internal sealed record NifMeshProbe(
    int MeshBlockIndex,
    uint MeshSize,
    int MeshDataOffset,
    string MeshFirst64,
    List<uint> UInt32Prefix,
    List<int> Int32Prefix,
    List<float?> Float32Prefix,
    List<string> StringSamples,
    List<NifMeshBoundStreamSummary> Streams,
    List<NifMeshProbePairing> Pairings,
    List<NifMeshAttributeSetSample> AttributeSets,
    List<NifMeshPayloadRoleWindow> PayloadWindows);

internal sealed record NifMeshProbePairing(
    int IndexMeshPayloadOffset,
    int IndexBlockIndex,
    uint? IndexDeclaredPayloadBytes,
    string? IndexDataStreamUsage,
    string? IndexDataStreamAccess,
    string IndexRole,
    ushort IndexMax,
    int? IndexPairCount,
    int VertexMeshPayloadOffset,
    int VertexBlockIndex,
    uint? VertexDeclaredPayloadBytes,
    string? VertexDataStreamUsage,
    string? VertexDataStreamAccess,
    string VertexRole,
    int VertexCount,
    double IndexCoverageRatio,
    int DataStreamMetadataScore,
    int Confidence);

internal sealed record NifMeshPayloadRoleWindow(
    int PayloadOffset,
    int ByteLength,
    int VertexCount,
    int Components,
    string Transform,
    string Role,
    int Confidence,
    string First16,
    NifFloatVectorStats Stats);

internal sealed record NifAttributeExtraProbeReport(
    BinaryAssetSource Source,
    int Length,
    string NifVersion,
    int MeshBlockIndex,
    uint MeshSize,
    int MeshDataOffset,
    string MeshFirst64,
    int AttributeSets,
    int ExtraMeshPayloadOffset,
    int Matches,
    List<string> HeaderWarnings,
    List<NifAttributeExtraProbeMatch> ExtraStreams);

internal sealed record NifAttributeExtraProbeMatch(
    int AttributeSetIndex,
    int VertexCount,
    NifAttributeTopologyStats Topology,
    int PositionMeshPayloadOffset,
    int PositionBlockIndex,
    uint? PositionDeclaredPayloadBytes,
    string PositionRole,
    int NormalMeshPayloadOffset,
    int NormalBlockIndex,
    uint? NormalDeclaredPayloadBytes,
    string NormalRole,
    int UvMeshPayloadOffset,
    int UvBlockIndex,
    uint? UvDeclaredPayloadBytes,
    string UvRole,
    int ExtraMeshPayloadOffset,
    int ExtraBlockIndex,
    string ExtraTargetTypeName,
    uint? ExtraBlockSize,
    uint? ExtraDeclaredPayloadBytes,
    int? HeaderBytes,
    int? BodyOffset,
    string Role,
    int RoleConfidence,
    string FitSummary,
    string BlockFirst64,
    string BodyFirst64,
    string BodyFirst128,
    NifStreamBodyStats? BodyStats,
    List<string> RoleCandidates,
    List<string> RoleEvidence,
    List<int> VertexCountCandidates,
    ushort? IndexMax,
    int? IndexPairCount,
    NifUInt16BeIndexStats? IndexStats,
    NifAttributeExtraIndexCompatibility? IndexCompatibility,
    List<NifAttributeVertexSample> PositionVertexSamples,
    List<NifAttributeVertexSample> NormalVertexSamples,
    List<NifAttributeVertexSample> UvVertexSamples,
    List<NifAttributeExtraMappingPositionFitness> MappingPositionFitness,
    List<byte> UInt8Prefix,
    List<NifByteHistogramEntry> ByteHistogramTop,
    List<ushort> UInt16LittleEndianPrefix,
    List<ushort> UInt16BigEndianPrefix,
    List<uint> UInt32LittleEndianPrefix,
    List<uint> UInt32BigEndianPrefix,
    List<float?> Float32LittleEndianPrefix,
    List<float?> Float32BigEndianPrefix,
    List<NifRepeatedBodyPattern> Repeated2BytePatterns,
    List<NifRepeatedBodyPattern> Repeated4BytePatterns,
    List<NifAttributeExtraGroupedView> GroupedViews);

internal sealed record NifAttributeExtraIndexCompatibility(
    string CandidateTopology,
    int VertexCount,
    int PairCount,
    bool TriangleAligned,
    int TriangleCount,
    ushort MinIndex,
    ushort MaxIndex,
    int DistinctIndexCount,
    bool MaxIndexWithinVertexCount,
    double MaxIndexCoverageRatio,
    double DistinctIndexCoverageRatio,
    bool UsesZeroIndex,
    double DegenerateTriangleRatio,
    int TriangleStripWindowCount,
    int TriangleStripNonDegenerateWindowCount,
    double TriangleStripDegenerateRatio,
    bool TriangleStripLessDegenerateThanTriples,
    string IndexBaseHint,
    List<ushort> FirstIndices,
    List<NifUInt16Triple> FirstTriples,
    List<NifTriangleStripPreviewTriangle> FirstStripTriangles,
    List<NifAttributeExtraIndexMappingCandidate> MappingCandidates,
    NifTriangleStripStructureStats StripStructure,
    List<string> Evidence);

internal sealed record NifAttributeExtraIndexMappingCandidate(
    string Name,
    int IndexOffset,
    bool ValidForVertexCount,
    int OutOfRangeIndexCount,
    int ReferencedVertexCount,
    double ReferencedVertexCoverageRatio,
    int MissingVertexCount,
    List<int> MissingVertexSamples,
    int? MappedMinIndex,
    int? MappedMaxIndex,
    List<int> FirstMappedIndices,
    List<NifMappedTriangleStripPreviewTriangle> FirstMappedStripTriangles,
    List<string> Evidence);

internal sealed record NifAttributeVertexSample(
    int Index,
    string Attribute,
    string Role,
    string Transform,
    int Components,
    double? X,
    double? Y,
    double? Z,
    double? VectorLength,
    double? PreviousDistance,
    double? NextDistance);

internal sealed record NifAttributeTriangleShape(
    double Area,
    string DominantPlane,
    double DominantSignedArea);

internal sealed record NifAttributeExtraMappingPositionFitness(
    string MappingName,
    int IndexOffset,
    string RestartModeHypothesis,
    int TriangleWindowCount,
    int NonDegenerateTriangleWindowCount,
    int OutOfRangeTriangleWindowCount,
    int FiniteTriangleWindowCount,
    double? AverageMaxEdge,
    double? MedianMaxEdge,
    double? P95MaxEdge,
    double? MaxEdge,
    int SegmentCount,
    int SegmentedTriangleWindowCount,
    int DroppedDegenerateWindowCount,
    int DroppedCrossSegmentWindowCount,
    int SegmentedFiniteTriangleWindowCount,
    double? SegmentedAverageMaxEdge,
    double? SegmentedMedianMaxEdge,
    double? SegmentedP95MaxEdge,
    double? SegmentedMaxEdge,
    int SegmentedFiniteNormalTriangleWindowCount,
    double? SegmentedMedianNormalDelta,
    double? SegmentedP95NormalDelta,
    double? SegmentedMaxNormalDelta,
    int SegmentedFiniteUvTriangleWindowCount,
    double? SegmentedMedianUvDelta,
    double? SegmentedP95UvDelta,
    double? SegmentedMaxUvDelta,
    int SegmentedFiniteAreaTriangleWindowCount,
    double? SegmentedMedianTriangleArea,
    double? SegmentedMinTriangleArea,
    int SegmentedNearZeroTriangleAreaCount,
    double? ContinuousToSegmentedMedianDelta,
    List<NifAttributeExtraMappingPositionTriangleSample> WorstTriangles,
    List<NifAttributeExtraMappingPositionTriangleSample> WorstSegmentedTriangles,
    NifAttributeExtraFirstSegmentProofReview FirstSegmentProofReview,
    List<NifAttributeExtraMappingPositionTriangleSample> FirstSegmentTriangles,
    List<NifAttributeExtraMappingPositionSegmentSample> FirstSegments);

internal sealed record NifAttributeExtraFirstSegmentProofReview(
    int TriangleSampleCount,
    int NearZeroAreaCount,
    List<NifStringCount> DominantPlaneCounts,
    int PositiveDominantSignedAreaCount,
    int NegativeDominantSignedAreaCount,
    int ZeroDominantSignedAreaCount,
    int DominantPlaneSwitchCount,
    int DominantSignedAreaSignSwitchCount,
    int ContiguousWindowTransitionCount,
    int NonContiguousWindowTransitionCount,
    int NonAlternatingParityTransitionCount,
    List<string> ReviewFlags);

internal sealed record NifAttributeExtraMappingPositionTriangleSample(
    int StripWindowIndex,
    int A,
    int B,
    int C,
    double? AB,
    double? BC,
    double? CA,
    double? MaxEdge,
    double? NormalMaxDelta,
    double? UvMaxDelta,
    double? Area,
    string? DominantAreaPlane,
    double? DominantSignedArea,
    string StripWindingParity);

internal sealed record NifAttributeExtraMappingPositionSegmentSample(
    int StartWindow,
    int EndWindow,
    int TriangleWindowCount,
    int FiniteTriangleWindowCount,
    int StartA,
    int StartB,
    int EndB,
    int EndC,
    double? MedianMaxEdge,
    double? MaxEdge);

internal sealed record NifTriangleStripPreviewTriangle(
    int Index,
    ushort A,
    ushort B,
    ushort C,
    string WindingParity,
    bool Degenerate);

internal sealed record NifTriangleStripStructureStats(
    string Hint,
    int IndexCount,
    int TriangleWindowCount,
    int DegenerateWindowCount,
    int NonDegenerateWindowCount,
    int DegenerateRunCount,
    int MaxDegenerateRunLength,
    int NonDegenerateRunCount,
    int MaxNonDegenerateRunLength,
    double AverageNonDegenerateRunLength,
    int AdjacentRepeatCount,
    int MirroredAdjacentRepeatBridgeCount,
    int SentinelRestartValueCount,
    int ZeroIndexValueCount,
    List<NifTriangleStripWindowRunSample> FirstDegenerateRuns,
    List<NifTriangleStripWindowRunSample> FirstNonDegenerateRuns);

internal sealed record NifTriangleStripWindowRunSample(
    int StartWindow,
    int Length,
    int EndWindow);

internal sealed record NifMappedTriangleStripPreviewTriangle(
    int Index,
    int A,
    int B,
    int C,
    string WindingParity,
    bool Degenerate,
    bool OutOfRange);

internal sealed record NifByteHistogramEntry(int Value, string Hex, int Count, double Ratio);

internal sealed class NifRepeatedBodyPatternAccumulator(string hex, int width)
{
  public string Hex { get; } = hex;
  public int Width { get; } = width;
  public int Count { get; set; }
  public List<int> Offsets { get; } = [];
}

internal sealed record NifRepeatedBodyPattern(string Hex, int Width, int Count, List<int> Offsets);

internal sealed record NifAttributeExtraGroupedView(
    string Name,
    int SlotCount,
    int BodyBytes,
    int? BytesPerSlot,
    bool ExactFit,
    int RemainderBytes,
    List<NifAttributeExtraGroupSlot> PrefixSlots,
    string? RemainderFirst32);

internal sealed record NifAttributeExtraGroupSlot(
    int Index,
    int Offset,
    string Hex,
    List<ushort> UInt16LittleEndianPrefix,
    List<ushort> UInt16BigEndianPrefix,
    List<uint> UInt32LittleEndianPrefix,
    List<uint> UInt32BigEndianPrefix,
    List<float?> Float32LittleEndianPrefix,
    List<float?> Float32BigEndianPrefix);

internal sealed record NifStreamBodyProbeReport(
    BinaryAssetSource Source,
    int Length,
    string NifVersion,
    int DataStreamBlocks,
    int StreamBodiesEmitted,
    List<string> HeaderWarnings,
    List<NifStreamBodyProbe> StreamBodies);

internal sealed record NifStreamBodyProbe(
    int BlockIndex,
    string TypeName,
    int DataOffset,
    uint BlockSize,
    string BlockFirst64,
    uint? DeclaredPayloadBytes,
    int? HeaderBytes,
    int? BodyOffset,
    string BodyFirst128,
    NifStreamBodyStats? Stats,
    List<ushort> UInt16Prefix,
    List<ushort> UInt16BigEndianPrefix,
    List<uint> UInt32Prefix,
    List<float?> Float32Prefix,
    List<NifFloat2> Float2Prefix,
    List<NifFloat3> Float3Prefix,
    List<NifUInt16Triple> UInt16TriplesPrefix,
    List<NifUInt16Triple> UInt16BigEndianTriplesPrefix,
    NifUInt16TriplesStructure UInt16TriplesStructure,
    List<StrideCandidate> PreferredStrideCandidates);

internal sealed record NifFloat2(int Index, float? X, float? Y);

internal sealed record NifFloat3(int Index, float? X, float? Y, float? Z);

internal sealed record NifUInt16Triple(int Index, ushort A, ushort B, ushort C);

internal sealed record NifUInt16TriplesStructure(
    int TriplesCount,
    bool AlternationDetected,
    bool EvenIndexCConstant,
    List<ushort> EvenCValueSet,
    bool OddIndexAConstant,
    List<ushort> OddAValueSet,
    bool Magic43606Found,
    bool MetadataSentinelPattern,
    string StructuralFamily,
    string Interpretation);

internal sealed record BodyStrideCandidate(int HeaderBytes, int Stride, int Count);

internal sealed record NifHeaderInfo(
    string HeaderString,
    uint? Version,
    string? VersionHex,
    string VersionText,
    byte? Endian,
    bool IsLittleEndian,
    uint? UserVersion,
    uint? BlockCount,
    ushort? BlockTypeCount,
    int HeaderBytesParsed,
    int? BlockDataOffset,
    ulong? TotalBlockDataSize,
    uint? MinBlockDataSize,
    uint? MaxBlockDataSize,
    int? RemainingAfterBlockDataOffset,
    long? BlockSizePayloadDelta,
    uint? StringCount,
    uint? MaxStringLength,
    uint? GroupCount,
    List<NifBlockTypeInfo> BlockTypes,
    List<NifStringInfo> Strings,
    List<NifReferenceInfo> References,
    List<NifBlockInfo> Blocks,
    List<string> Warnings);

internal sealed record NifBlockTypeNameInfo(
    int Index,
    string Name,
    string DisplayName,
    string NormalizedName,
    string? DataStreamUsage,
    string? DataStreamAccess);

internal sealed record NifBlockTypeInfo(
    int Index,
    string Name,
    string DisplayName,
    string NormalizedName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    int UsageCount);

internal sealed record NifBlockInfo(
    int Index,
    int TypeIndex,
    string TypeName,
    string TypeDisplayName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    uint Size,
    int DataOffset,
    string First16,
    List<uint> UInt32Prefix,
    List<float?> Float32Prefix,
    List<int> StringIndexCandidates,
    List<string> StringSamples,
    List<NifBlockReferenceCandidate> DataStreamReferenceCandidates);

internal sealed record NifBlockReferenceCandidate(
    int PayloadOffset,
    int TargetBlockIndex,
    string TargetTypeName,
    string? TargetDataStreamUsage,
    string? TargetDataStreamAccess,
    uint TargetSize,
    string TargetFirst16,
    bool MaybeStringIndex,
    string? StringValue);

internal sealed record NifStringInfo(int Index, string Value);

internal sealed record NifReferenceInfo(int StringIndex, string Value);

internal sealed record TextureCandidate(string Candidate, string Kind);

internal sealed record NifInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    List<NifInventoryGroup> Groups);

internal sealed class NifInventoryGroup(
    string VersionText,
    string? VersionHex,
    string HeaderString,
    ushort? BlockTypeCount,
    List<string> BlockTypes,
    Dictionary<string, int> BlockTypeUsage,
    int Count,
    int MinSize,
    int MaxSize,
    int MinStringCount,
    int MaxStringCount,
    int ReferenceCount,
    List<NifInventorySample> Samples,
    List<NifReferenceSample> ReferenceSamples)
{
  public string VersionText { get; } = VersionText;
  public string? VersionHex { get; } = VersionHex;
  public string HeaderString { get; } = HeaderString;
  public ushort? BlockTypeCount { get; } = BlockTypeCount;
  public List<string> BlockTypes { get; } = BlockTypes;
  public Dictionary<string, int> BlockTypeUsage { get; } = BlockTypeUsage;
  public int Count { get; set; } = Count;
  public int MinSize { get; set; } = MinSize;
  public int MaxSize { get; set; } = MaxSize;
  public int MinStringCount { get; set; } = MinStringCount;
  public int MaxStringCount { get; set; } = MaxStringCount;
  public int ReferenceCount { get; set; } = ReferenceCount;
  public List<NifInventorySample> Samples { get; } = Samples;
  public List<NifReferenceSample> ReferenceSamples { get; } = ReferenceSamples;
}

internal sealed record NifInventorySample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int Size,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? PakIndex,
    uint? BlockCount,
    uint? StringCount,
    int ReferenceCount);

internal sealed class NifBlockTypeAccumulator(string typeName)
{
  public string TypeName { get; } = typeName;
  public int NifPayloadCount { get; set; }
  public int BlockCount { get; set; }
  public uint MinBlockSize { get; set; } = uint.MaxValue;
  public uint MaxBlockSize { get; set; }
  public HashSet<string> First16Values { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifBlockInventorySample> Samples { get; } = [];
}

internal sealed class NifBlockFamilyAccumulator(string typeName, uint size, string first16)
{
  public string TypeName { get; } = typeName;
  public uint Size { get; } = size;
  public string First16 { get; } = first16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public SortedSet<string> StringSamples { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifBlockInventorySample> Samples { get; } = [];
}

internal sealed record NifBlockInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int TotalBlocks,
    List<NifBlockTypeInventoryGroup> BlockTypes,
    List<NifBlockPayloadFamily> MeshFamilies,
    List<NifBlockPayloadFamily> DataStreamFamilies,
    List<NifBlockPayloadFamily> TopFamilies);

internal sealed record NifBlockTypeInventoryGroup(
    string TypeName,
    int NifPayloads,
    int BlockCount,
    uint MinBlockSize,
    uint MaxBlockSize,
    int DistinctFirst16,
    List<NifBlockInventorySample> Samples);

internal sealed record NifBlockPayloadFamily(
    string TypeName,
    uint Size,
    string First16,
    int Count,
    int NifPayloads,
    List<string> StringSamples,
    List<NifBlockInventorySample> Samples);

internal sealed record NifBlockInventorySample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int BlockIndex,
    int DataOffset,
    uint Size,
    string First16,
    List<string> StringSamples);

internal sealed class NifMeshStreamOffsetAccumulator(int payloadOffset)
{
  public int PayloadOffset { get; } = payloadOffset;
  public int Count { get; set; }
  public int AmbiguousCount { get; set; }
  public Dictionary<uint, int> TargetSizeCounts { get; } = [];
  public Dictionary<uint, int> MeshSizeCounts { get; } = [];
  public List<NifMeshStreamSample> Samples { get; } = [];
}

internal sealed class NifMeshStreamPatternAccumulator(string pattern, uint meshSize, string meshFirst16)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public string MeshFirst16 { get; } = meshFirst16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifMeshStreamSample> Samples { get; } = [];
}

internal sealed record NifMeshStreamInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int MeshBlocks,
    int MeshBlocksWithCandidates,
    int CandidateLinks,
    int AmbiguousCandidateLinks,
    List<NifMeshStreamOffsetGroup> OffsetGroups,
    List<NifMeshStreamPatternGroup> TopPatterns);

internal sealed record NifMeshStreamOffsetGroup(
    int PayloadOffset,
    int Count,
    int AmbiguousCount,
    List<NifSizeCount> TargetSizes,
    List<NifSizeCount> MeshSizes,
    List<NifMeshStreamSample> Samples);

internal sealed record NifMeshStreamPatternGroup(
    string Pattern,
    uint MeshSize,
    string MeshFirst16,
    int Count,
    int NifPayloads,
    List<NifMeshStreamSample> Samples);

internal sealed record NifSizeCount(uint Size, int Count);

internal sealed record NifMeshStreamSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    string MeshFirst16,
    int PayloadOffset,
    int TargetBlockIndex,
    string TargetTypeName,
    uint TargetSize,
    string TargetFirst16,
    bool MaybeStringIndex,
    string? StringValue);

internal sealed class NifMeshBindingRoleAccumulator(string role)
{
  public string Role { get; } = role;
  public int Count { get; set; }
  public int HighConfidenceCount { get; set; }
  public Dictionary<string, int> UsageAccessCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<uint, int> MeshSizeCounts { get; } = [];
  public Dictionary<uint, int> DeclaredPayloadSizeCounts { get; } = [];
  public List<NifMeshBindingStreamSample> Samples { get; } = [];
}

internal sealed class NifMeshBindingUsageAccessRoleAccumulator(string role, string? dataStreamUsage, string? dataStreamAccess)
{
  public string Role { get; } = role;
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public int Count { get; set; }
  public int HighConfidenceCount { get; set; }
  public Dictionary<uint, int> MeshSizeCounts { get; } = [];
  public Dictionary<uint, int> DeclaredPayloadSizeCounts { get; } = [];
  public List<NifMeshBindingStreamSample> Samples { get; } = [];
}

internal sealed class NifPositionSourceSiblingAccumulator(
    string pattern,
    string idPrefix,
    int targetBlockIndex,
    uint? declaredPayloadBytes,
    string? dataStreamUsage,
    string? dataStreamAccess,
    string role)
{
  public string Pattern { get; } = pattern;
  public string IdPrefix { get; } = idPrefix;
  public int TargetBlockIndex { get; } = targetBlockIndex;
  public uint? DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public string Role { get; } = role;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public HashSet<int> MeshBlockIndices { get; } = [];
  public HashSet<int> MeshPayloadOffsets { get; } = [];
  public Dictionary<uint, int> MeshSizeCounts { get; } = [];
  public List<NifMeshBindingStreamSample> Samples { get; } = [];
}

internal sealed class NifMeshResidualTargetAccumulator(uint meshSize)
{
  public uint MeshSize { get; } = meshSize;
  public int MeshBlockCount { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public int ResidualStreamCount { get; set; }
  public HashSet<string> ResidualPatternKeys { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifMeshBindingStreamSample> Samples { get; } = [];
}

internal sealed class NifMeshResidualStreamAccumulator(
    string pattern,
    uint meshSize,
    int meshPayloadOffset,
    uint targetSize,
    uint? declaredPayloadBytes,
    string? dataStreamUsage,
    string? dataStreamAccess,
    string role,
    int roleConfidence,
    string bodyFirst16,
    string? stringValue,
    int? rotatedFloat3VectorCount,
    double? rotatedFloat3FiniteVectorRatio,
    double? rotatedFloat3PlausibleValueRatio,
    double? rotatedFloat3NonZeroVectorRatio,
    double? rotatedFloat3MaxExtent,
    List<NifFloatVectorPrefix>? rotatedFloat3Prefix)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public int MeshPayloadOffset { get; } = meshPayloadOffset;
  public uint TargetSize { get; } = targetSize;
  public uint? DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public string Role { get; } = role;
  public int RoleConfidence { get; } = roleConfidence;
  public string BodyFirst16 { get; } = bodyFirst16;
  public string? StringValue { get; } = stringValue;
  public int? RotatedFloat3VectorCount { get; } = rotatedFloat3VectorCount;
  public double? RotatedFloat3FiniteVectorRatio { get; } = rotatedFloat3FiniteVectorRatio;
  public double? RotatedFloat3PlausibleValueRatio { get; } = rotatedFloat3PlausibleValueRatio;
  public double? RotatedFloat3NonZeroVectorRatio { get; } = rotatedFloat3NonZeroVectorRatio;
  public double? RotatedFloat3MaxExtent { get; } = rotatedFloat3MaxExtent;
  public List<NifFloatVectorPrefix>? RotatedFloat3Prefix { get; } = rotatedFloat3Prefix is null ? null : [.. rotatedFloat3Prefix];
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifMeshBindingStreamSample> Samples { get; } = [];
}

internal sealed class NifMeshBindingPatternAccumulator(string pattern, uint meshSize, string meshFirst16)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public string MeshFirst16 { get; } = meshFirst16;
  public int Count { get; set; }
  public int PairCompatibleCount { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifMeshBindingMeshSample> Samples { get; } = [];
}

internal sealed class NifMeshBindingPairingAccumulator(
    string pattern,
    uint meshSize,
    string indexRole,
    string vertexRole,
    uint? indexDeclaredPayloadBytes,
    uint? vertexDeclaredPayloadBytes,
    int? indexPairCount,
    string? indexDataStreamUsage,
    string? indexDataStreamAccess,
    string? vertexDataStreamUsage,
    string? vertexDataStreamAccess,
    int vertexCount)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public string IndexRole { get; } = indexRole;
  public string VertexRole { get; } = vertexRole;
  public uint? IndexDeclaredPayloadBytes { get; } = indexDeclaredPayloadBytes;
  public uint? VertexDeclaredPayloadBytes { get; } = vertexDeclaredPayloadBytes;
  public int? IndexPairCount { get; } = indexPairCount;
  public int? TriangleListTriangleCount { get; } = indexPairCount is int pairs && pairs % 3 == 0 ? pairs / 3 : null;
  public int? TriangleStripWindowCount { get; } = indexPairCount is int pairs && pairs >= 3 ? pairs - 2 : null;
  public string? IndexDataStreamUsage { get; } = indexDataStreamUsage;
  public string? IndexDataStreamAccess { get; } = indexDataStreamAccess;
  public string? VertexDataStreamUsage { get; } = vertexDataStreamUsage;
  public string? VertexDataStreamAccess { get; } = vertexDataStreamAccess;
  public int VertexCount { get; } = vertexCount;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public ushort MaxIndexObserved { get; set; }
  public double ConfidenceTotal { get; set; }
  public double IndexCoverageRatioTotal { get; set; }
  public List<NifMeshBindingPairingSample> Samples { get; } = [];
}

internal sealed class NifMeshAttributeSetAccumulator(
    string pattern,
    uint meshSize,
    uint? positionDeclaredPayloadBytes,
    uint? normalDeclaredPayloadBytes,
    uint? uvDeclaredPayloadBytes,
    int vertexCount,
    NifAttributeTopologyStats topology)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public uint? PositionDeclaredPayloadBytes { get; } = positionDeclaredPayloadBytes;
  public uint? NormalDeclaredPayloadBytes { get; } = normalDeclaredPayloadBytes;
  public uint? UvDeclaredPayloadBytes { get; } = uvDeclaredPayloadBytes;
  public int VertexCount { get; } = vertexCount;
  public NifAttributeTopologyStats Topology { get; } = topology;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public double ConfidenceTotal { get; set; }
  public List<NifMeshAttributeSetSample> Samples { get; } = [];
}

internal sealed class NifAttributeTopologyAccumulator(
    string topology,
    int vertexCount,
    int? triangleListTriangleCount,
    int? triangleStripTriangleCount,
    int? quadListQuadCount)
{
  public string Topology { get; } = topology;
  public int VertexCount { get; } = vertexCount;
  public int? TriangleListTriangleCount { get; } = triangleListTriangleCount;
  public int? TriangleStripTriangleCount { get; } = triangleStripTriangleCount;
  public int? QuadListQuadCount { get; } = quadListQuadCount;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public double ConfidenceTotal { get; set; }
  public List<NifMeshAttributeSetSample> Samples { get; } = [];
}

internal sealed class NifAttributeExtraStreamAccumulator(
    string topology,
    int vertexCount,
    int extraMeshPayloadOffset,
    string extraRole,
    uint? extraDeclaredPayloadBytes,
    int? bytesPerVertex,
    int? bytesPerTriangleListTriangle,
    int? bytesPerStripOrFanTriangle,
    int? bytesPerQuad,
    string fitSummary)
{
  public string Topology { get; } = topology;
  public int VertexCount { get; } = vertexCount;
  public int ExtraMeshPayloadOffset { get; } = extraMeshPayloadOffset;
  public string ExtraRole { get; } = extraRole;
  public uint? ExtraDeclaredPayloadBytes { get; } = extraDeclaredPayloadBytes;
  public int? BytesPerVertex { get; } = bytesPerVertex;
  public int? BytesPerTriangleListTriangle { get; } = bytesPerTriangleListTriangle;
  public int? BytesPerStripOrFanTriangle { get; } = bytesPerStripOrFanTriangle;
  public int? BytesPerQuad { get; } = bytesPerQuad;
  public string FitSummary { get; } = fitSummary;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifMeshAttributeSetSample> Samples { get; } = [];
}

internal sealed class NifAttributeExtraMappingFitnessAccumulator(
    string pattern,
    uint meshSize,
    string topology,
    int vertexCount,
    int extraMeshPayloadOffset,
    string extraRole,
    uint? extraDeclaredPayloadBytes)
{
  public string Pattern { get; } = pattern;
  public uint MeshSize { get; } = meshSize;
  public string Topology { get; } = topology;
  public int VertexCount { get; } = vertexCount;
  public int ExtraMeshPayloadOffset { get; } = extraMeshPayloadOffset;
  public string ExtraRole { get; } = extraRole;
  public uint? ExtraDeclaredPayloadBytes { get; } = extraDeclaredPayloadBytes;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public int RawZeroBasedPreferredCount { get; private set; }
  public int SubtractOnePreferredCount { get; private set; }
  public int TieCount { get; private set; }
  public double RawMedianMaxEdgeTotal { get; private set; }
  public int RawMedianMaxEdgeCount { get; private set; }
  public double SubtractOneMedianMaxEdgeTotal { get; private set; }
  public int SubtractOneMedianMaxEdgeCount { get; private set; }
  public double RawSegmentedMedianMaxEdgeTotal { get; private set; }
  public int RawSegmentedMedianMaxEdgeCount { get; private set; }
  public double SubtractOneSegmentedMedianMaxEdgeTotal { get; private set; }
  public int SubtractOneSegmentedMedianMaxEdgeCount { get; private set; }
  public double RawSegmentedMedianNormalDeltaTotal { get; private set; }
  public int RawSegmentedMedianNormalDeltaCount { get; private set; }
  public double SubtractOneSegmentedMedianNormalDeltaTotal { get; private set; }
  public int SubtractOneSegmentedMedianNormalDeltaCount { get; private set; }
  public double RawSegmentedMedianUvDeltaTotal { get; private set; }
  public int RawSegmentedMedianUvDeltaCount { get; private set; }
  public double SubtractOneSegmentedMedianUvDeltaTotal { get; private set; }
  public int SubtractOneSegmentedMedianUvDeltaCount { get; private set; }
  public double RawSegmentedMedianTriangleAreaTotal { get; private set; }
  public int RawSegmentedMedianTriangleAreaCount { get; private set; }
  public double SubtractOneSegmentedMedianTriangleAreaTotal { get; private set; }
  public int SubtractOneSegmentedMedianTriangleAreaCount { get; private set; }
  public double RawFirstSegmentNearZeroAreaCountTotal { get; private set; }
  public double RawFirstSegmentDominantPlaneSwitchCountTotal { get; private set; }
  public double RawFirstSegmentDominantSignedAreaSignSwitchCountTotal { get; private set; }
  public double RawFirstSegmentNonContiguousWindowTransitionCountTotal { get; private set; }
  public double RawFirstSegmentNonAlternatingParityTransitionCountTotal { get; private set; }
  public int RawFirstSegmentProofReviewCount { get; private set; }
  public double SubtractOneFirstSegmentNearZeroAreaCountTotal { get; private set; }
  public double SubtractOneFirstSegmentDominantPlaneSwitchCountTotal { get; private set; }
  public double SubtractOneFirstSegmentDominantSignedAreaSignSwitchCountTotal { get; private set; }
  public double SubtractOneFirstSegmentNonContiguousWindowTransitionCountTotal { get; private set; }
  public double SubtractOneFirstSegmentNonAlternatingParityTransitionCountTotal { get; private set; }
  public int SubtractOneFirstSegmentProofReviewCount { get; private set; }
  public double SegmentCountTotal { get; private set; }
  public double SegmentedTriangleWindowCountTotal { get; private set; }
  public double DroppedDegenerateWindowCountTotal { get; private set; }
  public double DroppedCrossSegmentWindowCountTotal { get; private set; }
  public Dictionary<string, int> StripStructureHintCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public int StripStructureCount { get; private set; }
  public double AdjacentRepeatCountTotal { get; private set; }
  public double MirroredBridgeCountTotal { get; private set; }
  public double DegenerateRunCountTotal { get; private set; }
  public double MaxDegenerateRunLengthTotal { get; private set; }
  public double NonDegenerateRunCountTotal { get; private set; }
  public double MaxNonDegenerateRunLengthTotal { get; private set; }
  public int SentinelRestartValueCountTotal { get; private set; }
  public int ZeroIndexValueCountTotal { get; private set; }
  public List<NifAttributeExtraMappingFitnessSample> Samples { get; } = [];

  public void AddFitness(
      NifAttributeExtraMappingPositionFitness? rawFitness,
      NifAttributeExtraMappingPositionFitness? subtractOneFitness,
      string preferredMapping)
  {
    if (rawFitness?.MedianMaxEdge is not null)
    {
      RawMedianMaxEdgeTotal += rawFitness.MedianMaxEdge.Value;
      RawMedianMaxEdgeCount++;
    }

    if (rawFitness?.SegmentedMedianMaxEdge is not null)
    {
      RawSegmentedMedianMaxEdgeTotal += rawFitness.SegmentedMedianMaxEdge.Value;
      RawSegmentedMedianMaxEdgeCount++;
    }

    if (rawFitness?.SegmentedMedianNormalDelta is not null)
    {
      RawSegmentedMedianNormalDeltaTotal += rawFitness.SegmentedMedianNormalDelta.Value;
      RawSegmentedMedianNormalDeltaCount++;
    }

    if (rawFitness?.SegmentedMedianUvDelta is not null)
    {
      RawSegmentedMedianUvDeltaTotal += rawFitness.SegmentedMedianUvDelta.Value;
      RawSegmentedMedianUvDeltaCount++;
    }

    if (rawFitness?.SegmentedMedianTriangleArea is not null)
    {
      RawSegmentedMedianTriangleAreaTotal += rawFitness.SegmentedMedianTriangleArea.Value;
      RawSegmentedMedianTriangleAreaCount++;
    }

    if (rawFitness is not null)
    {
      RawFirstSegmentProofReviewCount++;
      RawFirstSegmentNearZeroAreaCountTotal += rawFitness.FirstSegmentProofReview.NearZeroAreaCount;
      RawFirstSegmentDominantPlaneSwitchCountTotal += rawFitness.FirstSegmentProofReview.DominantPlaneSwitchCount;
      RawFirstSegmentDominantSignedAreaSignSwitchCountTotal += rawFitness.FirstSegmentProofReview.DominantSignedAreaSignSwitchCount;
      RawFirstSegmentNonContiguousWindowTransitionCountTotal += rawFitness.FirstSegmentProofReview.NonContiguousWindowTransitionCount;
      RawFirstSegmentNonAlternatingParityTransitionCountTotal += rawFitness.FirstSegmentProofReview.NonAlternatingParityTransitionCount;
    }

    if (subtractOneFitness?.MedianMaxEdge is not null)
    {
      SubtractOneMedianMaxEdgeTotal += subtractOneFitness.MedianMaxEdge.Value;
      SubtractOneMedianMaxEdgeCount++;
    }

    if (subtractOneFitness?.SegmentedMedianMaxEdge is not null)
    {
      SubtractOneSegmentedMedianMaxEdgeTotal += subtractOneFitness.SegmentedMedianMaxEdge.Value;
      SubtractOneSegmentedMedianMaxEdgeCount++;
    }

    if (subtractOneFitness?.SegmentedMedianNormalDelta is not null)
    {
      SubtractOneSegmentedMedianNormalDeltaTotal += subtractOneFitness.SegmentedMedianNormalDelta.Value;
      SubtractOneSegmentedMedianNormalDeltaCount++;
    }

    if (subtractOneFitness?.SegmentedMedianUvDelta is not null)
    {
      SubtractOneSegmentedMedianUvDeltaTotal += subtractOneFitness.SegmentedMedianUvDelta.Value;
      SubtractOneSegmentedMedianUvDeltaCount++;
    }

    if (subtractOneFitness?.SegmentedMedianTriangleArea is not null)
    {
      SubtractOneSegmentedMedianTriangleAreaTotal += subtractOneFitness.SegmentedMedianTriangleArea.Value;
      SubtractOneSegmentedMedianTriangleAreaCount++;
    }

    if (subtractOneFitness is not null)
    {
      SubtractOneFirstSegmentProofReviewCount++;
      SubtractOneFirstSegmentNearZeroAreaCountTotal += subtractOneFitness.FirstSegmentProofReview.NearZeroAreaCount;
      SubtractOneFirstSegmentDominantPlaneSwitchCountTotal += subtractOneFitness.FirstSegmentProofReview.DominantPlaneSwitchCount;
      SubtractOneFirstSegmentDominantSignedAreaSignSwitchCountTotal += subtractOneFitness.FirstSegmentProofReview.DominantSignedAreaSignSwitchCount;
      SubtractOneFirstSegmentNonContiguousWindowTransitionCountTotal += subtractOneFitness.FirstSegmentProofReview.NonContiguousWindowTransitionCount;
      SubtractOneFirstSegmentNonAlternatingParityTransitionCountTotal += subtractOneFitness.FirstSegmentProofReview.NonAlternatingParityTransitionCount;
    }

    var representativeFitness = rawFitness ?? subtractOneFitness;
    if (representativeFitness is not null)
    {
      SegmentCountTotal += representativeFitness.SegmentCount;
      SegmentedTriangleWindowCountTotal += representativeFitness.SegmentedTriangleWindowCount;
      DroppedDegenerateWindowCountTotal += representativeFitness.DroppedDegenerateWindowCount;
      DroppedCrossSegmentWindowCountTotal += representativeFitness.DroppedCrossSegmentWindowCount;
    }

    switch (preferredMapping)
    {
      case "raw-zero-based":
        RawZeroBasedPreferredCount++;
        break;
      case "subtract-one":
        SubtractOnePreferredCount++;
        break;
      case "tie":
        TieCount++;
        break;
    }
  }

  public void AddStripStructure(NifTriangleStripStructureStats stripStructure)
  {
    StripStructureCount++;
    StripStructureHintCounts[stripStructure.Hint] = StripStructureHintCounts.GetValueOrDefault(stripStructure.Hint) + 1;
    AdjacentRepeatCountTotal += stripStructure.AdjacentRepeatCount;
    MirroredBridgeCountTotal += stripStructure.MirroredAdjacentRepeatBridgeCount;
    DegenerateRunCountTotal += stripStructure.DegenerateRunCount;
    MaxDegenerateRunLengthTotal += stripStructure.MaxDegenerateRunLength;
    NonDegenerateRunCountTotal += stripStructure.NonDegenerateRunCount;
    MaxNonDegenerateRunLengthTotal += stripStructure.MaxNonDegenerateRunLength;
    SentinelRestartValueCountTotal += stripStructure.SentinelRestartValueCount;
    ZeroIndexValueCountTotal += stripStructure.ZeroIndexValueCount;
  }
}

internal sealed record NifMeshBindingInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int MeshBlocks,
    int MeshBlocksWithCandidates,
    int CandidateLinks,
    int ValidDeclaredStreamBodies,
    int InvalidDeclaredStreamBodies,
    int PairCompatibleMeshes,
    int PairCompatibleLinks,
    int AttributeCompatibleMeshes,
    int AttributeCompatibleSets,
    List<NifMeshBindingRoleGroup> RoleGroups,
    List<NifMeshBindingUsageAccessRoleGroup> TopUsageAccessRoles,
    List<NifPositionSourceSiblingGroup> TopPositionSourceSiblings,
    List<NifMeshResidualTargetGroup> ResidualTargetMeshSizes,
    List<NifMeshResidualStreamGroup> TopResidualStreams,
    List<NifMeshBindingPatternGroup> TopPatterns,
    List<NifMeshBindingPairingGroup> TopPairings,
    List<NifMeshAttributeSetGroup> TopAttributeSets,
    List<NifAttributeTopologyGroup> TopAttributeTopologies,
    List<NifAttributeExtraStreamGroup> TopAttributeExtraStreams,
    List<NifAttributeExtraMappingFitnessGroup> TopAttributeExtraMappingFitness);

internal sealed record NifMeshBindingRoleGroup(
    string Role,
    int Count,
    int HighConfidenceCount,
    List<NifStringCount> UsageAccessCounts,
    List<NifSizeCount> MeshSizes,
    List<NifSizeCount> DeclaredPayloadSizes,
    List<NifMeshBindingStreamSample> Samples);

internal sealed record NifMeshBindingUsageAccessRoleGroup(
    string Role,
    string? DataStreamUsage,
    string? DataStreamAccess,
    int Count,
    int HighConfidenceCount,
    List<NifSizeCount> MeshSizes,
    List<NifSizeCount> DeclaredPayloadSizes,
    List<NifMeshBindingStreamSample> Samples);

internal sealed record NifPositionSourceSiblingGroup(
    string Pattern,
    string IdPrefix,
    int TargetBlockIndex,
    uint? DeclaredPayloadBytes,
    string? DataStreamUsage,
    string? DataStreamAccess,
    string Role,
    int Count,
    int NifPayloads,
    int DistinctMeshBlocks,
    List<int> MeshBlockIndices,
    List<NifSizeCount> MeshSizes,
    List<int> MeshPayloadOffsets,
    List<NifMeshBindingStreamSample> Samples);

internal sealed record NifInlinePositionCandidate(
    int Offset,
    int Stride,
    int FloatCount,
    int VertexCount,
    string FirstFloat3);

internal sealed record NifOrphanPositionCandidate(
    int BlockIndex,
    uint BlockSize,
    int Offset,
    int Stride,
    uint DeclaredPayloadBytes,
    int FloatCount,
    int VertexCount,
    string FirstFloat3,
    string BlockTypeName);

internal sealed record NifLinkedStreamPositionCandidate(
    int MeshPayloadOffset,
    int BlockIndex,
    string PositionType,
    int Stride,
    int FloatCount,
    int VertexCount,
    string BodyFirst16,
    string? DataStreamUsage,
    string? DataStreamAccess,
    string Role,
    string FirstFloat3);

internal sealed record NifPositionSourceMeshProbe(
    int MeshBlockIndex,
    uint MeshSize,
    int MeshDataOffset,
    List<NifInlinePositionCandidate> InlinePositionCandidates,
    List<NifOrphanPositionCandidate> OrphanPositionCandidates,
    List<NifLinkedStreamPositionCandidate> LinkedStreamPositionCandidates);

internal sealed record NifPositionSourceProbeReport(
    BinaryAssetSource Source,
    int Length,
    string NifVersion,
    int MeshBlockCount,
    int MeshesEmitted,
    List<NifPositionSourceMeshProbe> Meshes);

internal sealed record NifMeshResidualTargetGroup(
    uint MeshSize,
    int MeshBlockCount,
    int NifPayloads,
    int ResidualStreamCount,
    int ResidualPatternCount,
    List<NifMeshBindingStreamSample> Samples);

internal sealed record NifMeshResidualStreamGroup(
    string Pattern,
    uint MeshSize,
    int MeshPayloadOffset,
    uint TargetSize,
    uint? DeclaredPayloadBytes,
    string? DataStreamUsage,
    string? DataStreamAccess,
    string Role,
    int RoleConfidence,
    string BodyFirst16,
    string? StringValue,
    int? RotatedFloat3VectorCount,
    double? RotatedFloat3FiniteVectorRatio,
    double? RotatedFloat3PlausibleValueRatio,
    double? RotatedFloat3NonZeroVectorRatio,
    double? RotatedFloat3MaxExtent,
    List<NifFloatVectorPrefix>? RotatedFloat3Prefix,
    NifResidualPositionClassifierReview? StrictRotatedFloat3PositionClassifierReview,
    int Count,
    int NifPayloads,
    List<NifMeshBindingStreamSample> Samples);

internal sealed record NifResidualPositionClassifierReview(
    string ClassifierRole,
    bool CandidateOnly,
    int MinVectorCount,
    double MinFiniteVectorRatio,
    double MinPlausibleValueRatio,
    double MinNonZeroVectorRatio,
    double MinMaxExtent,
    int? VectorCount,
    double? FiniteVectorRatio,
    double? PlausibleValueRatio,
    double? NonZeroVectorRatio,
    double? MaxExtent,
    bool PassesStrictClassifier,
    List<string> MissReasons,
    double? MaxPlausibleValueRatioThresholdForThisSample,
    string CandidateGuardNote);

internal sealed record NifMeshBindingPatternGroup(
    string Pattern,
    uint MeshSize,
    string MeshFirst16,
    int Count,
    int NifPayloads,
    int PairCompatibleCount,
    List<NifMeshBindingMeshSample> Samples);

internal sealed record NifMeshBindingPairingGroup(
    string Pattern,
    uint MeshSize,
    int Count,
    int NifPayloads,
    string IndexRole,
    string VertexRole,
    uint? IndexDeclaredPayloadBytes,
    uint? VertexDeclaredPayloadBytes,
    int? IndexPairCount,
    int? TriangleListTriangleCount,
    int? TriangleStripWindowCount,
    double MaxIndexCoverageRatio,
    string? IndexDataStreamUsage,
    string? IndexDataStreamAccess,
    string? VertexDataStreamUsage,
    string? VertexDataStreamAccess,
    int VertexCount,
    ushort MaxIndexObserved,
    double AverageConfidence,
    double AverageIndexCoverageRatio,
    List<NifMeshBindingPairingSample> Samples);

internal sealed record NifMeshAttributeSetGroup(
    string Pattern,
    uint MeshSize,
    int Count,
    int NifPayloads,
    uint? PositionDeclaredPayloadBytes,
    uint? NormalDeclaredPayloadBytes,
    uint? UvDeclaredPayloadBytes,
    int VertexCount,
    NifAttributeTopologyStats Topology,
    double AverageConfidence,
    List<NifMeshAttributeSetSample> Samples);

internal sealed record NifAttributeTopologyGroup(
    string Topology,
    int VertexCount,
    int Count,
    int NifPayloads,
    int? TriangleListTriangleCount,
    int? TriangleStripTriangleCount,
    int? QuadListQuadCount,
    double AverageTopologyConfidence,
    List<NifMeshAttributeSetSample> Samples);

internal sealed record NifAttributeExtraStreamGroup(
    string Topology,
    int VertexCount,
    int ExtraMeshPayloadOffset,
    string ExtraRole,
    uint? ExtraDeclaredPayloadBytes,
    int? BytesPerVertex,
    int? BytesPerTriangleListTriangle,
    int? BytesPerStripOrFanTriangle,
    int? BytesPerQuad,
    string FitSummary,
    int Count,
    int NifPayloads,
    List<NifMeshAttributeSetSample> Samples);

internal sealed record NifAttributeExtraMappingFitnessGroup(
    string Pattern,
    uint MeshSize,
    string Topology,
    int VertexCount,
    int ExtraMeshPayloadOffset,
    string ExtraRole,
    uint? ExtraDeclaredPayloadBytes,
    int Count,
    int NifPayloads,
    int RawZeroBasedPreferredCount,
    int SubtractOnePreferredCount,
    int TieCount,
    double? AverageRawMedianMaxEdge,
    double? AverageSubtractOneMedianMaxEdge,
    double? AverageMedianMaxEdgeDelta,
    double? AverageRawSegmentedMedianMaxEdge,
    double? AverageSubtractOneSegmentedMedianMaxEdge,
    double? AverageSegmentedMedianMaxEdgeDelta,
    double? AverageRawSegmentedMedianNormalDelta,
    double? AverageSubtractOneSegmentedMedianNormalDelta,
    double? AverageSegmentedMedianNormalDeltaGap,
    double? AverageRawSegmentedMedianUvDelta,
    double? AverageSubtractOneSegmentedMedianUvDelta,
    double? AverageSegmentedMedianUvDeltaGap,
    double? AverageRawSegmentedMedianTriangleArea,
    double? AverageSubtractOneSegmentedMedianTriangleArea,
    double? AverageSegmentedMedianTriangleAreaGap,
    double? AverageRawFirstSegmentNearZeroAreaCount,
    double? AverageSubtractOneFirstSegmentNearZeroAreaCount,
    double? AverageRawFirstSegmentDominantPlaneSwitchCount,
    double? AverageSubtractOneFirstSegmentDominantPlaneSwitchCount,
    double? AverageRawFirstSegmentDominantSignedAreaSignSwitchCount,
    double? AverageSubtractOneFirstSegmentDominantSignedAreaSignSwitchCount,
    double? AverageRawFirstSegmentNonContiguousWindowTransitionCount,
    double? AverageSubtractOneFirstSegmentNonContiguousWindowTransitionCount,
    double? AverageRawFirstSegmentNonAlternatingParityTransitionCount,
    double? AverageSubtractOneFirstSegmentNonAlternatingParityTransitionCount,
    double? AverageSegmentCount,
    double? AverageSegmentedTriangleWindowCount,
    double? AverageDroppedDegenerateWindowCount,
    double? AverageDroppedCrossSegmentWindowCount,
    string DominantStripStructureHint,
    double? AverageAdjacentRepeatCount,
    double? AverageMirroredBridgeCount,
    double? AverageDegenerateRunCount,
    double? AverageMaxDegenerateRunLength,
    double? AverageNonDegenerateRunCount,
    double? AverageMaxNonDegenerateRunLength,
    int SentinelRestartValueCountTotal,
    int ZeroIndexValueCountTotal,
    string PreferredMapping,
    List<NifAttributeExtraMappingFitnessSample> Samples);

internal sealed record NifAttributeExtraMappingFitnessSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    int VertexCount,
    int ExtraMeshPayloadOffset,
    int ExtraBlockIndex,
    string ExtraRole,
    double? RawMedianMaxEdge,
    double? SubtractOneMedianMaxEdge,
    double? RawSegmentedMedianMaxEdge,
    double? SubtractOneSegmentedMedianMaxEdge,
    double? RawSegmentedMedianNormalDelta,
    double? SubtractOneSegmentedMedianNormalDelta,
    double? RawSegmentedMedianUvDelta,
    double? SubtractOneSegmentedMedianUvDelta,
    double? RawSegmentedMedianTriangleArea,
    double? SubtractOneSegmentedMedianTriangleArea,
    List<string> RawFirstSegmentProofFlags,
    List<string> SubtractOneFirstSegmentProofFlags,
    int? RawFirstSegmentDominantPlaneSwitchCount,
    int? SubtractOneFirstSegmentDominantPlaneSwitchCount,
    int? RawFirstSegmentDominantSignedAreaSignSwitchCount,
    int? SubtractOneFirstSegmentDominantSignedAreaSignSwitchCount,
    int? RawFirstSegmentNonAlternatingParityTransitionCount,
    int? SubtractOneFirstSegmentNonAlternatingParityTransitionCount,
    double? RawP95MaxEdge,
    double? SubtractOneP95MaxEdge,
    int? SegmentCount,
    int? SegmentedTriangleWindowCount,
    int? DroppedDegenerateWindowCount,
    int? DroppedCrossSegmentWindowCount,
    string PreferredMapping);

internal sealed record NifMeshBindingStreamSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    NifMeshBoundStreamSummary Stream);

internal sealed record NifMeshBindingMeshSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    string MeshFirst16,
    int PairingCount,
    List<NifMeshBoundStreamSummary> Streams);

internal sealed record NifMeshBoundStreamSummary(
    int MeshPayloadOffset,
    int TargetBlockIndex,
    string TargetTypeName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    uint TargetSize,
    string TargetFirst16,
    uint? DeclaredPayloadBytes,
    int? HeaderBytes,
    string BodyFirst16,
    bool MaybeStringIndex,
    string? StringValue,
    NifMeshStreamRoleStats RoleStats);

internal sealed record NifMeshBindingPairingSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    int IndexMeshPayloadOffset,
    int IndexBlockIndex,
    uint? IndexDeclaredPayloadBytes,
    string? IndexDataStreamUsage,
    string? IndexDataStreamAccess,
    string IndexRole,
    ushort IndexMax,
    int? IndexPairCount,
    int VertexMeshPayloadOffset,
    int VertexBlockIndex,
    uint? VertexDeclaredPayloadBytes,
    string? VertexDataStreamUsage,
    string? VertexDataStreamAccess,
    string VertexRole,
    int VertexCount,
    double IndexCoverageRatio,
    int DataStreamMetadataScore,
    int Confidence);

internal sealed record NifMeshAttributeSetSample(
    string? ArchiveName,
    int? EntryIndex,
    string? IdPrefix,
    int? ManifestEntryIndex,
    int MeshBlockIndex,
    uint MeshSize,
    int VertexCount,
    int Confidence,
    int DataStreamMetadataScore,
    NifAttributeTopologyStats Topology,
    int PositionMeshPayloadOffset,
    int PositionBlockIndex,
    uint? PositionDeclaredPayloadBytes,
    string? PositionDataStreamUsage,
    string? PositionDataStreamAccess,
    string PositionRole,
    int NormalMeshPayloadOffset,
    int NormalBlockIndex,
    uint? NormalDeclaredPayloadBytes,
    string? NormalDataStreamUsage,
    string? NormalDataStreamAccess,
    string NormalRole,
    int UvMeshPayloadOffset,
    int UvBlockIndex,
    uint? UvDeclaredPayloadBytes,
    string? UvDataStreamUsage,
    string? UvDataStreamAccess,
    string UvRole,
    List<NifAttributeExtraStreamSample> ExtraStreams);

internal sealed record NifAttributeExtraStreamSample(
    int MeshPayloadOffset,
    int BlockIndex,
    uint? DeclaredPayloadBytes,
    string? DataStreamUsage,
    string? DataStreamAccess,
    string Role,
    int RoleConfidence,
    int? BytesPerVertex,
    int? BytesPerTriangleListTriangle,
    int? BytesPerStripOrFanTriangle,
    int? BytesPerQuad,
    string FitSummary);

internal sealed record NifAttributeTopologyStats(
    string PrimaryTopology,
    int Confidence,
    bool TriangleListCandidate,
    int? TriangleListTriangleCount,
    bool TriangleStripCandidate,
    int? TriangleStripTriangleCount,
    bool QuadListCandidate,
    int? QuadListQuadCount,
    bool HasBoundIndexCandidate,
    List<string> Evidence);

internal sealed record NifMeshStreamRoleStats(
    string PrimaryRole,
    int Confidence,
    List<string> RoleCandidates,
    List<string> Evidence,
    List<int> VertexCountCandidates,
    ushort? IndexMax,
    int? IndexPairCount,
    NifStreamBodyStats? BodyStats,
    NifStreamEndianStats? EndianStats,
    NifUInt16BeIndexStats? IndexStats,
    NifFloatVectorStats? Float2Stats,
    NifFloatVectorStats? Float3Stats,
    NifFloatVectorStats? RotatedFloat2Stats,
    NifFloatVectorStats? RotatedFloat3Stats)
{
  public static NifMeshStreamRoleStats Invalid(string reason) => new(
      PrimaryRole: "invalid-stream-body",
      Confidence: 0,
      RoleCandidates: ["invalid-stream-body"],
      Evidence: [reason],
      VertexCountCandidates: [],
      IndexMax: null,
      IndexPairCount: null,
      BodyStats: null,
      EndianStats: null,
      IndexStats: null,
      Float2Stats: null,
      Float3Stats: null,
      RotatedFloat2Stats: null,
      RotatedFloat3Stats: null);
}

internal enum NifFloatByteTransform
{
  LittleEndian,
  RotateRight1
}

internal sealed record NifFloatVectorStats(
    string Transform,
    int Components,
    bool Aligned,
    int VectorCount,
    int FiniteVectorCount,
    double FiniteVectorRatio,
    double PlausibleValueRatio,
    int NonZeroVectorCount,
    double NonZeroVectorRatio,
    int NearUnitVectorCount,
    double NearUnitVectorRatio,
    double UvRangeRatio,
    double? MinX,
    double? MaxX,
    double? MinY,
    double? MaxY,
    double? MinZ,
    double? MaxZ,
    double MaxExtent,
    List<NifFloatVectorPrefix> Prefix);

internal sealed record NifFloatVectorPrefix(int Index, double? X, double? Y, double? Z);

internal sealed class NifStreamHeaderAccumulator(int headerBytes)
{
  public int HeaderBytes { get; } = headerBytes;
  public int Count { get; set; }
  public Dictionary<string, int> TypeCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> UsageAccessCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<uint, int> BlockSizeCounts { get; } = [];
  public Dictionary<uint, int> DeclaredPayloadSizeCounts { get; } = [];
  public Dictionary<int, int> PayloadStrideCounts { get; } = [];
  public List<NifStreamHeaderSample> Samples { get; } = [];
}

internal sealed class NifStreamHeaderFamilyAccumulator(string typeName, string? dataStreamUsage, string? dataStreamAccess, uint blockSize, uint declaredPayloadBytes, int headerBytes, string first16, string payloadFirst16)
{
  public string TypeName { get; } = typeName;
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public uint BlockSize { get; } = blockSize;
  public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public int HeaderBytes { get; } = headerBytes;
  public string First16 { get; } = first16;
  public string PayloadFirst16 { get; } = payloadFirst16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<int, int> PayloadStrideCounts { get; } = [];
  public List<NifStreamHeaderSample> Samples { get; } = [];
}

internal sealed record NifStreamHeaderInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int DataStreamBlocks,
    int DeclaredPayloadBlocks,
    int ValidDeclaredPayloadBlocks,
    int InvalidDeclaredPayloadBlocks,
    List<NifDataStreamUsageAccessGroup> UsageAccessGroups,
    List<NifStreamHeaderGroup> HeaderGroups,
    List<NifStreamHeaderFamilyGroup> TopFamilies);

internal sealed record NifStreamHeaderGroup(
    int HeaderBytes,
    int Count,
    List<NifStringCount> TypeCounts,
    List<NifStringCount> UsageAccessCounts,
    List<NifSizeCount> BlockSizes,
    List<NifSizeCount> DeclaredPayloadSizes,
    List<NifIntCount> PayloadStrides,
    List<NifStreamHeaderSample> Samples);

internal sealed record NifStreamHeaderFamilyGroup(
    string TypeName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    uint BlockSize,
    uint DeclaredPayloadBytes,
    int HeaderBytes,
    string First16,
    string PayloadFirst16,
    int Count,
    int NifPayloads,
    List<NifIntCount> PayloadStrides,
    List<NifStreamHeaderSample> Samples);

internal sealed record NifStringCount(string Value, int Count);

internal sealed record NifIntCount(int Value, int Count);

internal sealed record NifStreamHeaderSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int BlockIndex,
    string TypeName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    int DataOffset,
    uint BlockSize,
    string First16,
    uint DeclaredPayloadBytes,
    int HeaderBytes,
    string PayloadFirst16,
    List<StrideCandidate> PayloadStrideCandidates);

internal sealed class NifDataStreamUsageAccessAccumulator(string? dataStreamUsage, string? dataStreamAccess)
{
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public int Count { get; set; }
}

internal sealed record NifDataStreamUsageAccessGroup(string? DataStreamUsage, string? DataStreamAccess, int Count);

internal sealed class NifStreamBodySizeAccumulator(uint declaredPayloadBytes)
{
  public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public int Count { get; set; }
  public int AllZeroCount { get; set; }
  public long NonZeroByteTotal { get; set; }
  public Dictionary<string, int> ClassificationCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> UsageAccessCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<uint, int> BlockSizeCounts { get; } = [];
  public Dictionary<int, int> PayloadStrideCounts { get; } = [];
  public List<NifStreamBodySample> Samples { get; } = [];
}

internal sealed class NifStreamBodySignatureAccumulator(uint declaredPayloadBytes, string? dataStreamUsage, string? dataStreamAccess, string payloadFirst16)
{
  public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public string? DataStreamUsage { get; } = dataStreamUsage;
  public string? DataStreamAccess { get; } = dataStreamAccess;
  public string PayloadFirst16 { get; } = payloadFirst16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> ClassificationCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<int, int> PayloadStrideCounts { get; } = [];
  public List<NifStreamBodySample> Samples { get; } = [];
}

internal sealed record NifStreamBodyInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int DataStreamBlocks,
    int ValidStreamBodies,
    int InvalidStreamBodies,
    List<NifDataStreamUsageAccessGroup> UsageAccessGroups,
    List<NifStreamBodySizeGroup> PayloadSizeGroups,
    List<NifStreamBodySignatureGroup> TopBodySignatures);

internal sealed record NifStreamBodySizeGroup(
    uint DeclaredPayloadBytes,
    int Count,
    int AllZeroCount,
    double AverageNonZeroBytes,
    List<NifStringCount> ClassificationCounts,
    List<NifStringCount> UsageAccessCounts,
    List<NifSizeCount> BlockSizes,
    List<NifIntCount> PayloadStrides,
    List<NifStreamBodySample> Samples);

internal sealed record NifStreamBodySignatureGroup(
    uint DeclaredPayloadBytes,
    string? DataStreamUsage,
    string? DataStreamAccess,
    string PayloadFirst16,
    int Count,
    int NifPayloads,
    List<NifStringCount> ClassificationCounts,
    List<NifIntCount> PayloadStrides,
    List<NifStreamBodySample> Samples);

internal sealed record NifStreamBodySample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int BlockIndex,
    string TypeName,
    string? DataStreamUsage,
    string? DataStreamAccess,
    uint BlockSize,
    int HeaderBytes,
    uint DeclaredPayloadBytes,
    string PayloadFirst16,
    NifStreamBodyStats Stats);

internal sealed record NifStreamBodyStats(
    int ByteLength,
    string First16,
    bool AllZero,
    int NonZeroBytes,
    int Float32Count,
    int FiniteFloat32Count,
    int PlausibleFloat32Count,
    double? Float32Min,
    double? Float32Max,
    int UInt16Count,
    int UInt16Distinct,
    ushort UInt16Max,
    int UInt32Count,
    int UInt32Distinct,
    uint UInt32Max,
    List<StrideCandidate> PayloadStrideCandidates,
    string Classification);

internal sealed class NifStreamEndianClassAccumulator(string classification)
{
  public string Classification { get; } = classification;
  public int Count { get; set; }
  public double BigEndianLowValueRatioTotal { get; set; }
  public double LittleEndianLowValueRatioTotal { get; set; }
  public Dictionary<uint, int> PayloadSizeCounts { get; } = [];
  public Dictionary<uint, int> BlockSizeCounts { get; } = [];
  public List<NifStreamEndianSample> Samples { get; } = [];
}

internal sealed class NifStreamEndianSignatureAccumulator(string classification, uint declaredPayloadBytes, string payloadFirst16)
{
  public string Classification { get; } = classification;
  public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public string PayloadFirst16 { get; } = payloadFirst16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<NifStreamEndianSample> Samples { get; } = [];
}

internal sealed record NifStreamEndiannessInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int DataStreamBlocks,
    int ValidStreamBodies,
    int EvenLengthBodies,
    int InvalidStreamBodies,
    List<NifStreamEndianClassGroup> ClassGroups,
    List<NifStreamEndianSignatureGroup> TopBigEndianSignatures,
    List<NifStreamEndianSignatureGroup> TopSignatures);

internal sealed record NifStreamEndianClassGroup(
    string Classification,
    int Count,
    double AverageBigEndianLowValueRatio,
    double AverageLittleEndianLowValueRatio,
    List<NifSizeCount> PayloadSizes,
    List<NifSizeCount> BlockSizes,
    List<NifStreamEndianSample> Samples);

internal sealed record NifStreamEndianSignatureGroup(
    string Classification,
    uint DeclaredPayloadBytes,
    string PayloadFirst16,
    int Count,
    int NifPayloads,
    List<NifStreamEndianSample> Samples);

internal sealed record NifStreamEndianSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int BlockIndex,
    string TypeName,
    uint BlockSize,
    int HeaderBytes,
    uint DeclaredPayloadBytes,
    string PayloadFirst16,
    NifStreamEndianStats Stats);

internal sealed record NifStreamEndianStats(
    int ByteLength,
    string First16,
    int PairCount,
    ushort LowValueThreshold,
    List<ushort> LittleEndianPrefix,
    List<ushort> BigEndianPrefix,
    ushort LittleEndianMax,
    ushort BigEndianMax,
    int LittleEndianDistinct,
    int BigEndianDistinct,
    int LittleEndianLowValueCount,
    int BigEndianLowValueCount,
    double LittleEndianLowValueRatio,
    double BigEndianLowValueRatio,
    int LittleEndianMultipleOf256Count,
    int BigEndianMultipleOf256Count,
    double LittleEndianMultipleOf256Ratio,
    double BigEndianMultipleOf256Ratio,
    string Classification);

internal sealed class NifIndexCandidateClassAccumulator(string classification)
{
  public string Classification { get; } = classification;
  public int Count { get; set; }
  public int TriangleAlignedCount { get; set; }
  public long MaxIndexTotal { get; set; }
  public long TriangleCountTotal { get; set; }
  public double DegenerateTriangleRatioTotal { get; set; }
  public int TriangleStripLessDegenerateThanTriplesCount { get; set; }
  public long TriangleStripWindowCountTotal { get; set; }
  public double TriangleStripDegenerateRatioTotal { get; set; }
  public Dictionary<uint, int> PayloadSizeCounts { get; } = [];
  public List<NifIndexCandidateSample> Samples { get; } = [];
}

internal sealed class NifIndexCandidateSignatureAccumulator(string classification, uint declaredPayloadBytes, string payloadFirst16)
{
  public string Classification { get; } = classification;
  public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
  public string PayloadFirst16 { get; } = payloadFirst16;
  public int Count { get; set; }
  public HashSet<string> NifIds { get; } = new(StringComparer.OrdinalIgnoreCase);
  public int TriangleAlignedCount { get; set; }
  public long TriangleCountTotal { get; set; }
  public double DegenerateTriangleRatioTotal { get; set; }
  public int TriangleStripLessDegenerateThanTriplesCount { get; set; }
  public long TriangleStripWindowCountTotal { get; set; }
  public double TriangleStripDegenerateRatioTotal { get; set; }
  public ushort MaxObservedIndex { get; set; }
  public ushort? MinObservedMaxIndex { get; set; }
  public List<NifIndexCandidateSample> Samples { get; } = [];
}

internal sealed record NifIndexCandidateInventoryReport(
    string RootDirectory,
    string ManifestPath,
    int InspectedPayloads,
    int NifPayloads,
    int Failed,
    int DataStreamBlocks,
    int ValidStreamBodies,
    int EvenLengthBodies,
    int BigEndianLeadBodies,
    int BigEndianTriangleAlignedBodies,
    int AmbiguousTriangleAlignedBodies,
    int TriangleStripLessDegenerateBodies,
    int InvalidStreamBodies,
    List<NifIndexCandidateClassGroup> ClassGroups,
    List<NifIndexCandidateSignatureGroup> TopBigEndianIndexSignatures,
    List<NifIndexCandidateSignatureGroup> TopSignatures);

internal sealed record NifIndexCandidateClassGroup(
    string Classification,
    int Count,
    int TriangleAlignedCount,
    double AverageTriangleCount,
    double AverageMaxIndex,
    double AverageDegenerateTriangleRatio,
    int TriangleStripLessDegenerateThanTriplesCount,
    double AverageTriangleStripWindowCount,
    double AverageTriangleStripDegenerateRatio,
    List<NifSizeCount> PayloadSizes,
    List<NifIndexCandidateSample> Samples);

internal sealed record NifIndexCandidateSignatureGroup(
    string Classification,
    uint DeclaredPayloadBytes,
    string PayloadFirst16,
    int Count,
    int NifPayloads,
    int TriangleAlignedCount,
    double AverageTriangleCount,
    double AverageDegenerateTriangleRatio,
    int TriangleStripLessDegenerateThanTriplesCount,
    double AverageTriangleStripWindowCount,
    double AverageTriangleStripDegenerateRatio,
    ushort MaxObservedIndex,
    ushort? MinObservedMaxIndex,
    List<NifIndexCandidateSample> Samples);

internal sealed record NifIndexCandidateSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    int BlockIndex,
    string TypeName,
    uint BlockSize,
    int HeaderBytes,
    uint DeclaredPayloadBytes,
    string PayloadFirst16,
    NifStreamEndianStats EndianStats,
    NifUInt16BeIndexStats IndexStats,
    string Classification);

internal sealed record NifUInt16BeIndexStats(
    int PairCount,
    bool TriangleAligned,
    int TriangleCount,
    ushort BigEndianMinIndex,
    ushort BigEndianMaxIndex,
    int BigEndianDistinctIndexCount,
    int DegenerateTriangles,
    double DegenerateTriangleRatio,
    int TriangleStripWindowCount,
    int TriangleStripNonDegenerateWindowCount,
    int TriangleStripDegenerateWindows,
    double TriangleStripDegenerateRatio,
    bool TriangleStripLessDegenerateThanTriples,
    List<ushort> FirstBigEndianIndices,
    List<NifUInt16Triple> FirstBigEndianTriples);

internal sealed record NifReferenceSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int StringIndex,
    string Value);

internal sealed record NifReferenceMineRecord(
    string Reference,
    string Candidate,
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? PakIndex,
    uint? PakOffset,
    int StringIndex,
    string NifVersion,
    uint? NifStringCount);

internal sealed record NifTextureLinkRecord(
    string ModelArchiveName,
    int ModelEntryIndex,
    string ModelIdPrefix,
    int? ModelManifestEntryIndex,
    uint? ModelFilenameFnv1Hash,
    ushort? ModelPakIndex,
    uint? ModelPakOffset,
    string NifVersion,
    string Reference,
    int ReferenceStringIndex,
    string Candidate,
    string CandidateKind,
    string Algorithm,
    uint Hash,
    int Length,
    int Confidence,
    int CollisionCount,
    int TextureManifestEntryIndex,
    string TextureIdPrefix,
    uint TextureFilenameFnv1Hash,
    ushort TexturePakIndex,
    uint TexturePakOffset,
    uint TextureCompressedSize,
    uint TextureSize,
    ushort? TextureNameLength);

internal sealed record LinkedTextureExtractReport(
    string RootDirectory,
    string LinksPath,
    string OutputDirectory,
    string? ModelIdFilter,
    int IndexedPayloads,
    int CopiedArchivesScanned,
    int LiveFallbackArchivesScanned,
    int UniqueTextureLinks,
    int Attempted,
    int Written,
    int WrittenFromCopiedArchives,
    int WrittenFromLiveArchives,
    int MissingFromCopiedArchives,
    int MissingFromSelectedSources,
    int TypeMismatches,
    int Failed,
    List<LinkedTextureExtractSample> Samples);

internal sealed record LinkedTextureExtractSample(
    string ModelIdPrefix,
    string TextureIdPrefix,
    string Candidate,
    string ArchiveName,
    int EntryIndex,
    string SourceKind,
    string Type,
    int? Width,
    int? Height,
    string? Format,
    string RelativePath);

internal sealed record NifBundleExtractReport(
    string RootDirectory,
    string LinksPath,
    string OutputDirectory,
    NifBundleModelSample Model,
    int IndexedPayloads,
    int CopiedArchivesScanned,
    int LiveFallbackArchivesScanned,
    int UniqueTextureLinks,
    int TextureAttempted,
    int TextureWritten,
    int TextureWrittenFromCopiedArchives,
    int TextureWrittenFromLiveArchives,
    int TextureMissingFromCopiedArchives,
    int TextureMissingFromSelectedSources,
    int TextureTypeMismatches,
    int TextureFailed,
    List<LinkedTextureExtractSample> Textures);

internal sealed record NifBundleModelSample(
    string IdPrefix,
    string ArchiveName,
    int EntryIndex,
    int ManifestEntryIndex,
    uint FilenameFnv1Hash,
    ushort PakIndex,
    uint PakOffset,
    string NifVersion,
    uint? BlockCount,
    uint? StringCount,
    string SourceKind,
    string RelativePath);

internal sealed record NifBundleBatchSelection(
    string ModelIdPrefix,
    List<NifTextureLinkRecord> Links,
    int UniqueTextureCount,
    int LinkCount);

internal sealed record NifBundleBatchExtractReport(
    string RootDirectory,
    string LinksPath,
    string OutputDirectory,
    int RequestedModelLimit,
    int SelectedModels,
    int IndexedPayloads,
    int CopiedArchivesScanned,
    int LiveFallbackArchivesScanned,
    int ModelsAttempted,
    int ModelsWritten,
    int CompleteBundles,
    int FailedBundles,
    int TotalTextureLinks,
    int TotalTexturesWritten,
    int TotalTexturesWrittenFromCopiedArchives,
    int TotalTexturesWrittenFromLiveArchives,
    int TotalTexturesMissingFromSelectedSources,
    List<NifBundleBatchExtractSample> Samples);

internal sealed record NifBundleBatchExtractSample(
    string ModelIdPrefix,
    string RelativeOutputDirectory,
    string? ModelArchiveName,
    string? ModelSourceKind,
    int UniqueTextureLinks,
    int TexturesWritten,
    int TexturesWrittenFromCopiedArchives,
    int TexturesWrittenFromLiveArchives,
    int TexturesMissingFromCopiedArchives,
    int TexturesMissingFromSelectedSources,
    int TextureTypeMismatches,
    int TextureFailures,
    bool IsComplete,
    string? Error);

internal sealed record NifBundleInventoryReport(
    string RootDirectory,
    string LinksPath,
    int CopiedAssetIds,
    int GraphLinks,
    int GraphModels,
    int ModelsPresentInCopiedArchives,
    int CompleteBundles,
    int IncompleteBundles,
    int TotalUniqueTextureRefs,
    int PresentTextureRefs,
    int MissingTextureRefs,
    List<NifBundleInventorySample> Samples);

internal sealed record NifBundleInventorySample(
    string ModelIdPrefix,
    string ModelArchiveName,
    int ModelEntryIndex,
    int? ModelManifestEntryIndex,
    ushort? ModelPakIndex,
    bool ModelPresentInCopiedArchives,
    int LinkCount,
    int UniqueTextureCount,
    int PresentTextureCount,
    int MissingTextureCount,
    bool IsComplete,
    List<string> PresentTextureSamples,
    List<string> MissingTextureSamples);

internal sealed record NifBundleArchiveModelState(
    string ModelIdPrefix,
    bool IsModelPresentInCopiedArchives,
    HashSet<string> MissingTextureIds,
    List<string> CandidateSamples);

internal sealed record NifBundleArchivePlanReport(
    string RootDirectory,
    string LinksPath,
    string LiveRoot,
    string LiveAssetsDirectory,
    int ArchivesScanned,
    int ArchiveEntriesScanned,
    int MatchingArchiveEntries,
    int CopiedAssetIds,
    int GraphLinks,
    int GraphModels,
    int ModelsPresentInCopiedArchives,
    int MissingTextureAssetIds,
    int MissingTextureAssetIdsFoundInLive,
    int MissingTextureAssetIdsNotFoundInLive,
    List<NifBundleArchiveRecommendation> ArchiveRecommendations,
    List<NifBundleArchiveGreedyStep> GreedyPlan,
    List<string> MissingTextureIdsNotFoundInLiveSamples);

internal sealed record NifBundleArchiveRecommendation(
    string ArchiveName,
    int MissingTextureAssets,
    int MissingTextureLinks,
    int AffectedModels,
    int CompletesBundlesAlone,
    List<string> SampleTextureIds,
    List<string> SampleTextureNames);

internal sealed record NifBundleArchiveGreedyStep(
    int Step,
    string ArchiveName,
    int NewTextureAssets,
    int NewlyCompletedBundles,
    int CumulativeCompletedBundles,
    int RemainingIncompleteBundles,
    List<string> SampleTextureNames);

internal sealed record ProbeReport(string RootDirectory)
{
  public List<ManifestProbe> Manifests { get; } = [];
  public List<ArchiveProbe> Archives { get; } = [];
  public List<string> Errors { get; } = [];
}

internal sealed class ArchiveExtractResult
{
  public string? ArchiveName { get; set; }
  public int Written { get; set; }
  public int Skipped { get; set; }
  public int Failed { get; set; }
  public List<ExtractedPayloadSample> Samples { get; } = [];
  public List<string> Warnings { get; } = [];
}

internal sealed record ExtractionRunReport(
    string RootDirectory,
    string OutputDirectory,
    string ManifestPath,
    List<ArchiveExtractResult> Archives);

internal sealed record ArchiveInventoryRunReport(
    string RootDirectory,
    string ManifestPath,
    int MaxPerArchive,
    string Filter,
    List<ArchiveInventoryReport> Archives);

internal sealed class ArchiveInventoryReport
{
  public string? ArchiveName { get; set; }
  public int NonNullEntries { get; set; }
  public int Inspected { get; set; }
  public int Failed { get; set; }
  public Dictionary<string, int> CompressionCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public Dictionary<string, int> TypeCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<ArchiveInventorySample> Samples { get; } = [];
  public List<string> Warnings { get; } = [];
}

internal sealed record ArchiveInventorySample(
    int EntryIndex,
    string IdPrefix,
    string Type,
    ushort Compression,
    uint PackedSize,
    int? Width,
    int? Height,
    int? MipMapCount,
    string? Format,
    string? RiffType,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? NameLength);

internal sealed record DetectedFileType(
    string Extension,
    int? Width = null,
    int? Height = null,
    int? MipMapCount = null,
    string? Format = null,
    string? RiffType = null);

internal sealed record ExtractionFilter(string? ArchiveName, HashSet<string>? TargetIds, string? Type, bool GroupByType, string Description)
{
  public bool ArchiveMatches(string archiveName)
  {
    return ArchiveName is null || string.Equals(archiveName, ArchiveName, StringComparison.OrdinalIgnoreCase);
  }

  public bool EntryMatches(ArchiveEntrySample archiveEntry, ManifestEntryBrief? manifestEntry)
  {
    return TargetIds is null || TargetIds.Contains(archiveEntry.IdPrefix);
  }

  public bool TypeMatches(string type)
  {
    return Type is null || string.Equals(type, Type, StringComparison.OrdinalIgnoreCase);
  }

  public string Describe() => Description;
}

internal sealed class ManifestLookup(string fileName, int pakCount, int entryCount)
{
  public string FileName { get; } = fileName;
  public int PakCount { get; } = pakCount;
  public int EntryCount { get; } = entryCount;
  public Dictionary<string, ManifestEntryBrief> Table1ById { get; } = new(StringComparer.OrdinalIgnoreCase);
  public HashSet<string> Table1Hashes { get; } = new(StringComparer.OrdinalIgnoreCase);
  public HashSet<string> PakShaPrefixes { get; } = new(StringComparer.OrdinalIgnoreCase);
  public HashSet<string> PakShas { get; } = new(StringComparer.OrdinalIgnoreCase);
  public List<PakListingRecord> Paks { get; } = [];
  public List<ManifestEntryBrief> Entries { get; } = [];
  public Dictionary<uint, List<ManifestEntryBrief>> EntriesByFnv { get; } = [];
}

internal sealed record ManifestEntryBrief(
    int Index,
    string IdPrefix,
    uint FilenameFnv1Hash,
    uint PakOffset,
    uint CompressedSize,
    uint Size,
    ushort PakIndex,
    ushort Bitfield1,
    ushort Bitfield2,
    byte UnknownByte,
    byte Language,
    string Hash,
    uint UnknownInt,
    ushort? NameLength);

internal sealed record PakListingRecord(
    int Index,
    uint StringOffset,
    string Path,
    uint UncompressedSize,
    uint CompressedSize,
    byte Compression,
    string Sha1WhenUncompressed,
    string Sha1WhenCompressed);

internal sealed record NameMatchRecord(
    string Name,
    string Algorithm,
    uint Hash,
    int Length,
    bool LengthMatchesManifest,
    int Confidence,
    int CollisionCount,
    bool IsUniqueHashMatch,
    bool IsRecovered,
    int ManifestEntryIndex,
    string IdPrefix,
    ushort? ManifestNameLength,
    ushort PakIndex,
    uint PakOffset,
    uint CompressedSize,
    uint Size,
    byte Language);

internal sealed record RecoveredNameRecord(
    string Name,
    string Algorithm,
    uint Hash,
    int Length,
    bool LengthMatchesManifest,
    int Confidence,
    int CollisionCount,
    bool IsUniqueHashMatch,
    bool IsRecovered,
    int ManifestEntryIndex,
    string IdPrefix,
    ushort? ManifestNameLength,
    ushort PakIndex,
    uint PakOffset,
    uint CompressedSize,
    uint Size,
    byte Language);

internal sealed class ArchiveMatchResult
{
  public int NonNullEntries { get; set; }
  public int Table1IdMatches { get; set; }
  public int Table1ShaMatches { get; set; }
  public int PakShaPrefixMatches { get; set; }
  public int PakShaMatches { get; set; }
  public List<ManifestArchiveMatchSample> Samples { get; } = [];
}

internal sealed record ManifestArchiveMatchSample(
    int ArchiveEntryIndex,
    string IdPrefix,
    int ManifestEntryIndex,
    uint FilenameFnv1Hash,
    uint PakOffset,
    uint CompressedSize,
    uint Size,
    ushort PakIndex,
    ushort? NameLength);

internal sealed record ExtractedPayloadSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    ushort Compression,
    uint PackedSize,
    int UnpackedSize,
    string PackedSha1,
    string UnpackedSha1,
    string RelativePath,
    string? RecoveredName,
    string DecodeStatus,
    int? Width,
    int? Height,
    int? MipMapCount,
    string? Format,
    string? RiffType,
    int? ManifestEntryIndex,
    uint? FilenameFnv1Hash,
    ushort? NameLength,
    ushort? PakIndex,
    uint? PakOffset,
    uint? ManifestCompressedSize,
    uint? ManifestSize);

internal sealed record ManifestProbe(
    string Path,
    string FileName,
    long Length,
    ManifestHeader Header,
    bool HeaderValid,
    List<PakListingSample> PakSamples,
    List<ManifestEntrySample> EntrySamples,
    List<string> Warnings);

internal sealed record ManifestHeader(
    string Magic,
    ushort MajorVersion,
    ushort MinorVersion,
    uint BlockTableOffset,
    uint BlockTableSize,
    TableReference Table0PakListing,
    TableReference Table1EntryTable,
    TableReference Table2Unknown);

internal sealed record TableReference(uint Offset, uint Size, uint Count, uint Stride);

internal sealed record PakListingSample(
    int Index,
    uint StringOffset,
    string Path,
    uint UncompressedSize,
    uint CompressedSize,
    byte Compression,
    string Sha1WhenUncompressed,
    string Sha1WhenCompressed);

internal sealed record ManifestEntrySample(
    int Index,
    string ContentIdPrefix,
    uint FilenameFnv1Hash,
    uint PakOffset,
    uint CompressedSize,
    uint Size,
    ushort PakIndex,
    ushort Bitfield1,
    ushort Bitfield2,
    byte UnknownByte,
    byte Language,
    string Hash,
    uint UnknownInt,
    ushort? NameLength);

internal sealed class ArchiveProbe(
    string path,
    string fileName,
    long length,
    ArchiveHeader header,
    bool headerValid,
    int nonNullEntryCount,
    long? firstDataOffset,
    List<ArchiveEntrySample> physicalEntrySamples,
    List<ArchiveEntrySample> linkedEntrySamples,
    List<string> warnings)
{
  public string Path { get; } = path;
  public string FileName { get; } = fileName;
  public long Length { get; } = length;
  public ArchiveHeader Header { get; } = header;
  public bool HeaderValid { get; } = headerValid;
  public int NonNullEntryCount { get; set; } = nonNullEntryCount;
  public long? FirstDataOffset { get; set; } = firstDataOffset;
  public List<ArchiveEntrySample> PhysicalEntrySamples { get; } = physicalEntrySamples;
  public List<ArchiveEntrySample> LinkedEntrySamples { get; } = linkedEntrySamples;
  public List<string> Warnings { get; } = warnings;
}

internal sealed record ArchiveHeader(
    string Magic,
    uint Version,
    uint HeaderSize,
    uint MaxEntryCount,
    uint FirstLinkedEntryRaw);

internal sealed record ArchiveEntrySample(
    int Index,
    string IdPrefix,
    uint Offset,
    uint Size,
    uint StreamedOrUnknown,
    ushort NextRaw,
    int? NextIndex,
    ushort Compression,
    string Sha1,
    bool IsNull);

internal sealed record UInt16ValidationFitStats(
    double Scale,
    double Translation,
    double RSquared,
    double RmsError,
    double MaxError,
    double Span,
    double OutlierThreshold,
    int OutlierCount);

internal sealed record UInt16ValidationCoordinate3D(
    double X, double Y, double Z);

internal sealed record UInt16ValidationCoordinate2D(
    double X, double Y);

internal sealed record UInt16ValidationVertex(
    int Index,
    UInt16ValidationCoordinate3D Float32,
    UInt16ValidationCoordinate2D UInt16Normalized,
    UInt16ValidationCoordinate2D Fitted,
    UInt16ValidationCoordinate2D Delta,
    bool IsOutlier);

internal sealed record UInt16ValidationOverallStats(
    int TotalOutliers,
    bool FitSuccess);

internal sealed record UInt16ValidationReport(
    string AssetId,
    int MeshBlock,
    int VertexCount,
    int AttributeSetIndex,
    int Float32BlockIndex,
    int UInt16BlockIndex,
    Dictionary<string, UInt16ValidationFitStats> FitResults,
    UInt16ValidationOverallStats Overall,
    List<UInt16ValidationVertex> Vertices);
