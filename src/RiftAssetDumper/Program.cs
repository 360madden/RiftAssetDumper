using System.Buffers.Binary;
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

            if (options.Command == "inventory-nif")
            {
                return InventoryNif(options);
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
            ?? throw new InvalidOperationException($"target asset {target.IdPrefix} was not found in copied archives.");

        return (found.Payload, new BinaryAssetSource(
            ArchiveName: found.ArchiveName,
            EntryIndex: found.EntryIndex,
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
                for (var i = 0; i < blockCountInt; i++)
                {
                    var typeIndex = BinaryPrimitives.ReadUInt16LittleEndian(data.Slice(offset + (i * 2), 2));
                    if (typeIndex >= usageCounts.Length)
                    {
                        allIndicesValid = false;
                        warnings.Add($"Block {i} references out-of-range block type index {typeIndex}.");
                        break;
                    }

                    usageCounts[typeIndex]++;
                }

                offset += indexBytes;
                if (!allIndicesValid)
                {
                    usageCounts = new int[blockTypeNames.Count];
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
                for (var i = 0; i < blockCountInt; i++)
                {
                    var blockSize = BinaryPrimitives.ReadUInt32LittleEndian(data.Slice(offset + (i * 4), 4));
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
            Warnings: warnings);
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
        var assetsDirectory = ResolveAssetsDirectory(rootDirectory);
        var archiveFilter = NormalizeArchiveFilter(options.ArchiveFilter);
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
                return new FoundPayload(archiveName, entry.Index, payload.Bytes);
            }
        }

        return null;
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

    private static PayloadDecodeResult DecompressPayload(ushort compression, byte[] packed, string expectedPackedSha, string expectedUnpackedPrefix, string lzma2Mode)
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
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- inventory-nif --root <SourceFolder> --max-total 100");
        Console.WriteLine("  dotnet run --project src/RiftAssetDumper -- extract-archives --root <SourceFolder> --out <OutFolder> --max-per-archive 10");
        Console.WriteLine();
        Console.WriteLine("Defaults:");
        Console.WriteLine("  command: probe");
        Console.WriteLine("  root:    ./Source when it exists, otherwise current directory");
        Console.WriteLine();
        Console.WriteLine("Options:");
        Console.WriteLine("  --root <path>   Folder containing assets64.manifest and Assets/assets.###");
        Console.WriteLine("  --live-root <path>");
        Console.WriteLine("                  Live RIFT root to scan read-only for scan-compression");
        Console.WriteLine("  --input <path>  Input file/folder for mine-strings, probe-binary, or probe-nif");
        Console.WriteLine("  --manifest <path>");
        Console.WriteLine("                  Manifest to use. Defaults to assets64.manifest under --root");
        Console.WriteLine("  --out <path>    Output folder/file depending on command");
        Console.WriteLine("  --limit <n>     Maximum records for list-paks/list-entries; default is all");
        Console.WriteLine("  --archive <n|assets.nnn>");
        Console.WriteLine("                  Only process one copied archive chunk");
        Console.WriteLine("  --id <16hex>    Only extract one asset ID prefix");
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
                    case "inventory-nif":
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
    uint? PakOffset = null);

internal sealed record FoundPayload(
    string ArchiveName,
    int EntryIndex,
    byte[] Payload);

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
    List<string> Warnings);

internal sealed record NifBlockTypeInfo(int Index, string Name, string DisplayName, int UsageCount);

internal sealed record NifStringInfo(int Index, string Value);

internal sealed record NifReferenceInfo(int StringIndex, string Value);

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

internal sealed record NifReferenceSample(
    string ArchiveName,
    int EntryIndex,
    string IdPrefix,
    int StringIndex,
    string Value);

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
