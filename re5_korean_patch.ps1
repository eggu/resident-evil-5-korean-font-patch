# Resident Evil 5 Korean patch for the current Steam build (Windows PowerShell 5.1+ / PowerShell 7).
# Same behaviour as re5_korean_patch.py: replaces only the Korean font and English-slot message
# entries inside the game's own archives and keeps every other resource as shipped.
#   powershell -ExecutionPolicy Bypass -File re5_korean_patch.ps1 [GAME_FOLDER]
#   powershell -ExecutionPolicy Bypass -File re5_korean_patch.ps1 -Restore [GAME_FOLDER]
param([switch]$Restore, [string]$GameFolder, [ValidateSet('malgun', 'nanum', 'kyeon')][string]$Font)

$ErrorActionPreference = 'Stop'
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$PatchPath = Join-Path (Join-Path $Here 'data') 'ko_patch.arc'
$Targets = @('CoreResource.arc', 'MsgResource_e.arc', 'Msg2Resource_e.arc')
$ArchiveDir = [IO.Path]::Combine('nativePC_MT', 'Image', 'Archive')
$BackupSuffix = '.orig'
# Present in the current Steam build only; the old full CoreResource.arc replacement drops it.
$CurrentBuildMarker = 'etc\message\font00_ch'
$EntrySize = 80
$SizeMask = 0x1FFFFFFF

function Get-EntryName([byte[]]$NameBytes) {
    $end = [Array]::IndexOf($NameBytes, [byte]0)
    if ($end -lt 0) { $end = $NameBytes.Length }
    [Text.Encoding]::GetEncoding(28591).GetString($NameBytes, 0, $end)
}

function Read-Arc([byte[]]$Data, [string]$Label) {
    if ($Data.Length -lt 8) { throw ("${Label}: file too small") }
    $magic = [Text.Encoding]::ASCII.GetString($Data, 0, 4)
    $version = [BitConverter]::ToUInt16($Data, 4)
    if ($magic -ne "ARC`0" -or $version -ne 7) { throw ("${Label}: not an RE5 archive (version $version)") }
    $count = [BitConverter]::ToUInt16($Data, 6)
    if (8 + $count * $EntrySize -gt $Data.Length) { throw ("${Label}: entry table is truncated") }
    $entries = New-Object System.Collections.ArrayList
    $start = [long]::MaxValue
    for ($i = 0; $i -lt $count; $i++) {
        $at = 8 + $i * $EntrySize
        $name = New-Object byte[] 64
        [Array]::Copy($Data, $at, $name, 0, 64)
        $csize = [BitConverter]::ToUInt32($Data, $at + 68)
        $offset = [BitConverter]::ToUInt32($Data, $at + 76)
        if ($offset + $csize -gt $Data.Length) { throw ("${Label}: entry $i points past the end of the file") }
        $blob = New-Object byte[] $csize
        [Array]::Copy($Data, $offset, $blob, 0, $csize)
        [void]$entries.Add([pscustomobject]@{
            Name = $name; Text = Get-EntryName $name
            Type = [BitConverter]::ToUInt32($Data, $at + 64)
            DSize = [BitConverter]::ToUInt32($Data, $at + 72); Blob = $blob
        })
        if ($offset -lt $start) { $start = $offset }
    }
    if ($count -eq 0) { $start = 8 }
    [pscustomobject]@{ Start = [long]$start; Entries = $entries }
}

function Build-Arc($Arc) {
    $count = $Arc.Entries.Count
    $start = [Math]::Max($Arc.Start, 8 + $count * $EntrySize)
    $out = New-Object IO.MemoryStream
    $w = [IO.BinaryWriter]::new($out)
    $w.Write([Text.Encoding]::ASCII.GetBytes("ARC`0")); $w.Write([uint16]7); $w.Write([uint16]$count)
    $offset = [uint32]$start
    foreach ($e in $Arc.Entries) {
        $w.Write($e.Name); $w.Write([uint32]$e.Type); $w.Write([uint32]$e.Blob.Length)
        $w.Write([uint32]$e.DSize); $w.Write([uint32]$offset)
        $offset += $e.Blob.Length
    }
    while ($out.Length -lt $start) { $w.Write([byte]0) }
    foreach ($e in $Arc.Entries) { $w.Write($e.Blob) }
    $w.Flush(); $out.ToArray()
}

function Get-Key($Entry) { '{0}|{1}' -f $Entry.Text, $Entry.Type }

function Test-SameBytes([byte[]]$A, [byte[]]$B) {
    $A.Length -eq $B.Length -and [Linq.Enumerable]::SequenceEqual($A, $B)
}

function Get-InflatedLength([byte[]]$Blob) {
    # zlib stream: skip the 2-byte header, DeflateStream reads the raw deflate data.
    $src = [IO.MemoryStream]::new($Blob, 2, $Blob.Length - 2)
    $inflate = [IO.Compression.DeflateStream]::new($src, [IO.Compression.CompressionMode]::Decompress)
    $sink = New-Object IO.MemoryStream
    $inflate.CopyTo($sink); $inflate.Dispose()
    $sink.Length
}

function Get-PatchedCopy([byte[]]$Data, [string]$Label, $Patch) {
    $arc = Read-Arc $Data $Label
    $swapped = 0; $already = 0
    foreach ($e in $arc.Entries) {
        $donor = $Patch[(Get-Key $e)]
        if ($null -eq $donor) { continue }
        if ($e.DSize -eq $donor.DSize -and (Test-SameBytes $e.Blob $donor.Blob)) { $already++ }
        else { $e.DSize = $donor.DSize; $e.Blob = $donor.Blob; $swapped++ }
    }
    [pscustomobject]@{ Bytes = (Build-Arc $arc); Swapped = $swapped; Already = $already }
}

function Assert-Written([byte[]]$New, [string]$Label, $Patch, [byte[]]$Original) {
    $after = (Read-Arc $New $Label).Entries
    $before = (Read-Arc $Original $Label).Entries
    if ($after.Count -ne $before.Count) { throw ("${Label}: entry list changed while writing") }
    for ($i = 0; $i -lt $after.Count; $i++) {
        $a = $after[$i]; $b = $before[$i]
        if ((Get-Key $a) -ne (Get-Key $b)) { throw ("${Label}: entry list changed while writing") }
        $expected = $Patch[(Get-Key $a)]
        if ($null -eq $expected) { $expected = $b }
        if ($a.DSize -ne $expected.DSize -or -not (Test-SameBytes $a.Blob $expected.Blob)) {
            throw ("${Label}: entry $($a.Text) was not written correctly")
        }
        if ($Patch.ContainsKey((Get-Key $a)) -and (Get-InflatedLength $a.Blob) -ne ($a.DSize -band $SizeMask)) {
            throw ("${Label}: patched entry failed to decompress")
        }
    }
}

function Test-ArchiveFolder([string]$Folder) {
    foreach ($t in $Targets) { if (-not (Test-Path -LiteralPath (Join-Path $Folder $t) -PathType Leaf)) { return $false } }
    $true
}

function Find-ArchiveFolder([string]$Arg) {
    if ($Arg) { $candidates = @($Arg) } else { $candidates = @($Here, (Get-Location).Path, (Split-Path -Parent $Here)) }
    foreach ($base in $candidates) {
        foreach ($folder in @((Join-Path $base $ArchiveDir), $base)) {
            if (Test-ArchiveFolder $folder) { return (Resolve-Path -LiteralPath $folder).Path }
        }
    }
    if ($Arg) { throw ("Cannot find $ArchiveDir with $($Targets -join ', ') under: $Arg") }
    $entered = (Read-Host 'Drag the Resident Evil 5 folder (with re5dx9.exe) here and press Enter').Trim().Trim('"', "'")
    if (-not $entered) { throw ('No game folder given.') }
    Find-ArchiveFolder $entered
}

function Write-FileAtomic([string]$Path, [byte[]]$Data) {
    $temp = "$Path.tmp"
    [IO.File]::WriteAllBytes($temp, $Data)
    Move-Item -LiteralPath $temp -Destination $Path -Force
}

function Invoke-Apply([string]$Folder) {
    $patch = @{}
    foreach ($e in (Read-Arc ([IO.File]::ReadAllBytes($PatchPath)) 'ko_patch.arc').Entries) { $patch[(Get-Key $e)] = $e }
    if ($Font -ne 'nanum') {
        $fontPath = Join-Path (Join-Path (Join-Path $Here 'data') 'fonts') ($Font + '.arc')
        $fonts = (Read-Arc ([IO.File]::ReadAllBytes($fontPath)) $Font).Entries
        if ($fonts.Count -ne 1 -or $fonts[0].Text -ne 'etc\message\font00_j') { throw 'Invalid font archive' }
        $patch[(Get-Key $fonts[0])] = $fonts[0]
    }
    $core = (Read-Arc ([IO.File]::ReadAllBytes((Join-Path $Folder 'CoreResource.arc'))) 'CoreResource.arc').Entries
    if (-not ($core | Where-Object { $_.Text -eq $CurrentBuildMarker })) {
        throw ("CoreResource.arc is the old full replacement from the previous Korean patch.`n" +
            'Restore the game files first (Steam: Properties > Installed Files > Verify integrity), then run this again.')
    }
    $planned = @()
    foreach ($name in $Targets) {
        $path = Join-Path $Folder $name
        $original = [IO.File]::ReadAllBytes($path)
        $result = Get-PatchedCopy $original $name $patch
        if ($result.Swapped + $result.Already -eq 0) { throw ("${name}: none of the Korean entries exist in this archive") }
        Assert-Written $result.Bytes $name $patch $original
        $planned += [pscustomobject]@{ Path = $path; Name = $name; Original = $original; Result = $result }
    }
    foreach ($p in $planned) {
        if ($p.Result.Swapped -eq 0) { Write-Host "$($p.Name): already patched"; continue }
        $backup = $p.Path + $BackupSuffix
        if (-not (Test-Path -LiteralPath $backup)) { [IO.File]::WriteAllBytes($backup, $p.Original) }
        Write-FileAtomic $p.Path $p.Result.Bytes
        Write-Host "$($p.Name): replaced $($p.Result.Swapped) entries (backup: $(Split-Path -Leaf $backup))"
    }
}

function Invoke-Restore([string]$Folder) {
    $restored = 0
    foreach ($name in $Targets) {
        $backup = Join-Path $Folder ($name + $BackupSuffix)
        if (Test-Path -LiteralPath $backup) {
            Write-FileAtomic (Join-Path $Folder $name) ([IO.File]::ReadAllBytes($backup))
            Remove-Item -LiteralPath $backup
            $restored++
            Write-Host "${name}: restored"
        }
    }
    if ($restored -eq 0) { throw ('No backups found. Use Steam "Verify integrity of game files" instead.') }
}

$code = 0
try {
    $folder = Find-ArchiveFolder $GameFolder
    Write-Host "Game archives: $folder"
    if ($Restore) { Invoke-Restore $folder } else {
        if (-not $Font) {
            $Font = 'malgun'
            if ($env:RE5_PATCH_NO_PAUSE -ne '1') {
                Write-Host '1. 맑은고딕체 (기본값)  2. 나눔명조체  3. 견명조체'
                $choice = Read-Host 'Font [1/2/3, Enter=1]'
                switch ($choice) {
                    '1' { $Font = 'malgun' }
                    '2' { $Font = 'nanum' }
                    '' { $Font = 'malgun' }
                    '3' { $Font = 'kyeon' }
                    default { throw 'Choose 1, 2 or 3.' }
                }
            }
        }
        Write-Host "Font: $Font"
        Invoke-Apply $folder
    }
    Write-Host 'Done.'
} catch {
    [Console]::Error.WriteLine("Error: $($_.Exception.Message)")
    $code = 1
}
if (-not $GameFolder -and $env:RE5_PATCH_NO_PAUSE -ne '1') { Read-Host 'Press Enter to close' | Out-Null }
exit $code
