using System.Buffers.Binary;
using System.Globalization;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;
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

            if (options.Command == "probe-nif-stream-body")
            {
                return ProbeNifStreamBody(options);
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
                UInt16TriplesPrefix: ReadUInt16TriplesPrefix(body, maxValues: 16),
                UInt16BigEndianTriplesPrefix: ReadUInt16BigEndianTriplesPrefix(body, maxValues: 16),
                PreferredStrideCandidates: stats is null
                    ? []
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
                        var sample = new NifStreamHeaderSample(
                            ArchiveName: archiveName,
                            EntryIndex: entry.Index,
                            IdPrefix: entry.IdPrefix,
                            ManifestEntryIndex: manifestEntry?.Index,
                            BlockIndex: block.Index,
                            TypeName: block.TypeName,
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

                        var familyKey = $"{block.TypeName}|size={block.Size}|payload={declaredPayloadBytes}|header={headerBytes}|first16={block.First16}";
                        if (!familyGroups.TryGetValue(familyKey, out var familyGroup))
                        {
                            familyGroup = new NifStreamHeaderFamilyAccumulator(block.TypeName, block.Size, declaredPayloadBytes, headerBytes, block.First16, sample.PayloadFirst16);
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
                BlockSizes: topSizeCounts(group.BlockSizeCounts),
                DeclaredPayloadSizes: topSizeCounts(group.DeclaredPayloadSizeCounts),
                PayloadStrides: topIntCounts(group.PayloadStrideCounts),
                Samples: group.Samples);
        }

        static NifStreamHeaderFamilyGroup toFamilyRecord(NifStreamHeaderFamilyAccumulator family)
        {
            return new NifStreamHeaderFamilyGroup(
                TypeName: family.TypeName,
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
        Console.WriteLine($"Top header byte counts: {string.Join(", ", report.HeaderGroups.Take(8).Select(static g => $"{g.HeaderBytes}={g.Count:N0}"))}");
        Console.WriteLine($"Top stream families: {string.Join(" | ", report.TopFamilies.Take(5).Select(static f => $"size={f.BlockSize}/payload={f.DeclaredPayloadBytes}/header={f.HeaderBytes} count={f.Count:N0}"))}");
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
                        validStreamBodies++;

                        var sample = new NifStreamBodySample(
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

                        if (!sizeGroups.TryGetValue(declaredPayloadBytes, out var sizeGroup))
                        {
                            sizeGroup = new NifStreamBodySizeAccumulator(declaredPayloadBytes);
                            sizeGroups.Add(declaredPayloadBytes, sizeGroup);
                        }

                        sizeGroup.Count++;
                        sizeGroup.ClassificationCounts[stats.Classification] = sizeGroup.ClassificationCounts.GetValueOrDefault(stats.Classification) + 1;
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

                        var signatureKey = $"{declaredPayloadBytes}|{stats.First16}";
                        if (!signatureGroups.TryGetValue(signatureKey, out var signatureGroup))
                        {
                            signatureGroup = new NifStreamBodySignatureAccumulator(declaredPayloadBytes, stats.First16);
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
                BlockSizes: topSizeCounts(group.BlockSizeCounts),
                PayloadStrides: topIntCounts(group.PayloadStrideCounts),
                Samples: group.Samples);
        }

        static NifStreamBodySignatureGroup toSignatureRecord(NifStreamBodySignatureAccumulator group)
        {
            return new NifStreamBodySignatureGroup(
                DeclaredPayloadBytes: group.DeclaredPayloadBytes,
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
        Console.WriteLine($"Top payload sizes: {string.Join(", ", report.PayloadSizeGroups.Take(8).Select(static g => $"{g.DeclaredPayloadBytes}={g.Count:N0}"))}");
        Console.WriteLine($"Top body signatures: {string.Join(" | ", report.TopBodySignatures.Take(5).Select(static g => $"payload={g.DeclaredPayloadBytes} first16={g.PayloadFirst16} count={g.Count:N0}"))}");
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

        var blockTypeNames = new List<(int Index, string Name, string DisplayName)>(blockTypeCount);
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
            blockTypeNames.Add((i, name, EscapeControlChars(name)));
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
            .Select(t => new NifBlockTypeInfo(t.Index, t.Name, t.DisplayName, t.Index < usageCounts.Length ? usageCounts[t.Index] : 0))
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
        List<(int Index, string Name, string DisplayName)> blockTypeNames,
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
            var typeName = typeIndex >= 0 && typeIndex < blockTypeNames.Count
                ? blockTypeNames[typeIndex].DisplayName
                : $"type-index-{typeIndex}";
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
        List<(int Index, string Name, string DisplayName)> blockTypeNames,
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
            var targetTypeName = targetTypeIndex >= 0 && targetTypeIndex < blockTypeNames.Count
                ? blockTypeNames[targetTypeIndex].DisplayName
                : $"type-index-{targetTypeIndex}";
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

    private static List<NifUInt16Triple> ReadUInt16TriplesPrefix(ReadOnlySpan<byte> payload, int maxValues)
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

    private static List<NifUInt16Triple> ReadUInt16BigEndianTriplesPrefix(ReadOnlySpan<byte> payload, int maxValues)
    {
        var count = Math.Min(maxValues, payload.Length / 6);
        var values = new List<NifUInt16Triple>(count);
        for (var i = 0; i < count; i++)
        {
            var offset = i * 6;
            values.Add(new NifUInt16Triple(
                Index: i,
                A: BinaryPrimitives.ReadUInt16BigEndian(payload.Slice(offset, 2)),
                B: BinaryPrimitives.ReadUInt16BigEndian(payload.Slice(offset + 2, 2)),
                C: BinaryPrimitives.ReadUInt16BigEndian(payload.Slice(offset + 4, 2))));
        }

        return values;
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
            var value = BinaryPrimitives.ReadUInt16LittleEndian(body.Slice(i * 2, 2));
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
        return blockType.UsageCount > 0
            ? $"{blockType.DisplayName} x{blockType.UsageCount:N0}"
            : blockType.DisplayName;
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
            throw new ArgumentException("--type must be a simple detected extension/type such as dds, riff, txt, bin, or lzma2.");
        }

        return normalized;
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
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-binary-signatures --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-binary --root <SourceFolder> --id <16hex>");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif --root <SourceFolder> --id <16hex>");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-streams --root <SourceFolder> --id <16hex> --mesh-block <n>");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- probe-nif-stream-body --root <SourceFolder> --id <16hex> --stream-block <n>");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-blocks --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-mesh-streams --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-headers --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-bodies --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif-stream-endianness --root <SourceFolder> --max-total 100");
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
        Console.WriteLine("                  Optional NiMesh block index filter for probe-nif-streams");
        Console.WriteLine("  --stream-block <n>");
        Console.WriteLine("                  Optional NiDataStream block index filter for probe-nif-stream-body");
        Console.WriteLine("  --fnv <uint|0xhex>");
        Console.WriteLine("                  Only extract entries with this filename FNV1 hash");
        Console.WriteLine("  --type <kind>   Only write/inspect detected type such as dds, riff, txt, bin, nif, lzma2");
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
        bool RedactPaths)
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
            var redactPaths = true;

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
                    case "inventory-binary-signatures":
                    case "probe-binary":
                    case "probe-nif":
                    case "probe-nif-streams":
                    case "probe-nif-stream-body":
                    case "inventory-nif":
                    case "inventory-nif-blocks":
                    case "inventory-nif-mesh-streams":
                    case "inventory-nif-stream-headers":
                    case "inventory-nif-stream-bodies":
                    case "inventory-nif-stream-endianness":
                    case "mine-nif-references":
                    case "link-nif-textures":
                    case "extract-linked-textures":
                    case "extract-nif-bundle":
                    case "extract-nif-bundles":
                    case "inventory-nif-bundles":
                    case "plan-nif-bundle-archives":
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
                redactPaths);
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
    List<StrideCandidate> PreferredStrideCandidates);

internal sealed record NifFloat2(int Index, float? X, float? Y);

internal sealed record NifFloat3(int Index, float? X, float? Y, float? Z);

internal sealed record NifUInt16Triple(int Index, ushort A, ushort B, ushort C);

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

internal sealed record NifBlockTypeInfo(int Index, string Name, string DisplayName, int UsageCount);

internal sealed record NifBlockInfo(
    int Index,
    int TypeIndex,
    string TypeName,
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

internal sealed class NifStreamHeaderAccumulator(int headerBytes)
{
    public int HeaderBytes { get; } = headerBytes;
    public int Count { get; set; }
    public Dictionary<string, int> TypeCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<uint, int> BlockSizeCounts { get; } = [];
    public Dictionary<uint, int> DeclaredPayloadSizeCounts { get; } = [];
    public Dictionary<int, int> PayloadStrideCounts { get; } = [];
    public List<NifStreamHeaderSample> Samples { get; } = [];
}

internal sealed class NifStreamHeaderFamilyAccumulator(string typeName, uint blockSize, uint declaredPayloadBytes, int headerBytes, string first16, string payloadFirst16)
{
    public string TypeName { get; } = typeName;
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
    List<NifStreamHeaderGroup> HeaderGroups,
    List<NifStreamHeaderFamilyGroup> TopFamilies);

internal sealed record NifStreamHeaderGroup(
    int HeaderBytes,
    int Count,
    List<NifStringCount> TypeCounts,
    List<NifSizeCount> BlockSizes,
    List<NifSizeCount> DeclaredPayloadSizes,
    List<NifIntCount> PayloadStrides,
    List<NifStreamHeaderSample> Samples);

internal sealed record NifStreamHeaderFamilyGroup(
    string TypeName,
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
    int DataOffset,
    uint BlockSize,
    string First16,
    uint DeclaredPayloadBytes,
    int HeaderBytes,
    string PayloadFirst16,
    List<StrideCandidate> PayloadStrideCandidates);

internal sealed class NifStreamBodySizeAccumulator(uint declaredPayloadBytes)
{
    public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
    public int Count { get; set; }
    public int AllZeroCount { get; set; }
    public long NonZeroByteTotal { get; set; }
    public Dictionary<string, int> ClassificationCounts { get; } = new(StringComparer.OrdinalIgnoreCase);
    public Dictionary<uint, int> BlockSizeCounts { get; } = [];
    public Dictionary<int, int> PayloadStrideCounts { get; } = [];
    public List<NifStreamBodySample> Samples { get; } = [];
}

internal sealed class NifStreamBodySignatureAccumulator(uint declaredPayloadBytes, string payloadFirst16)
{
    public uint DeclaredPayloadBytes { get; } = declaredPayloadBytes;
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
    List<NifStreamBodySizeGroup> PayloadSizeGroups,
    List<NifStreamBodySignatureGroup> TopBodySignatures);

internal sealed record NifStreamBodySizeGroup(
    uint DeclaredPayloadBytes,
    int Count,
    int AllZeroCount,
    double AverageNonZeroBytes,
    List<NifStringCount> ClassificationCounts,
    List<NifSizeCount> BlockSizes,
    List<NifIntCount> PayloadStrides,
    List<NifStreamBodySample> Samples);

internal sealed record NifStreamBodySignatureGroup(
    uint DeclaredPayloadBytes,
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
