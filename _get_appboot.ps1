$ProgressPreference='SilentlyContinue'
$asar = 'D:\app\DeepseekHarness\resources\app.asar'
$f = [System.IO.File]::OpenRead($asar)
$br = New-Object System.IO.BinaryReader($f)
$null = $br.ReadInt32(); $null = $br.ReadInt32(); $null = $br.ReadInt32()
$strLen = $br.ReadInt32()
$json = [System.Text.Encoding]::UTF8.GetString($br.ReadBytes($strLen))
$f.Close()
$base = 8 + 4 + $strLen
$hdr = $json | ConvertFrom-Json
$libEntry = $hdr.files.dsh.files.'node_modules'.files.'@deepseek-ai'.files.'dsh-app-boot'.files.lib.files.'index.js'
$fs2 = [System.IO.File]::OpenRead($asar)
$fs2.Position = $base + [int64]$libEntry.offset
$buf = New-Object byte[] $libEntry.size
$read = 0
while ($read -lt $libEntry.size) { $read += $fs2.Read($buf, $read, $libEntry.size - $read) }
$fs2.Close()
[System.IO.File]::WriteAllBytes('D:\Projects\kog\_appboot_index.js', $buf)
"size=$($libEntry.size)"
