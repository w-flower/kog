#requires -Version 5
param(
  [Parameter(Mandatory=$true)][string]$Asar,
  [Parameter(Mandatory=$true)][string]$InnerPath,   # e.g. /dsh/node_modules/@deepseek-ai/dsh-official-bundles/package.json
  [Parameter(Mandatory=$true)][string]$OutFile,
  [switch]$List
)
$fs = [System.IO.File]::OpenRead($Asar)
try {
  $br = New-Object System.IO.BinaryReader($fs)
  $null = $br.ReadInt32(); $null = $br.ReadInt32(); $null = $br.ReadInt32()
  $strLen = $br.ReadInt32()
  $json = [System.Text.Encoding]::UTF8.GetString($br.ReadBytes($strLen))
  $base = 8 + 4 + $strLen
  $hdr = $json | ConvertFrom-Json
  $node = $hdr
  $parts = $InnerPath.Trim('/').Split('/')
  foreach ($p in $parts) {
    if ($null -eq $node.files) { throw "not a dir: $p" }
    $node = $node.files.$p
    if ($null -eq $node) { throw "not found: $p" }
  }
  if ($List) {
    $node.files.PSObject.Properties.Name
    return
  }
  if ($null -eq $node.offset) {
    # directory: list recursive
    $out = New-Object System.Collections.Generic.List[string]
    function Walk($n, $prefix) {
      foreach ($prop in $n.files.PSObject.Properties) {
        $v = $prop.Value
        if ($null -ne $v.offset) { $script:out.Add("$prefix$($prop.Name)") } else { Walk $v "$prefix$($prop.Name)/" }
      }
    }
    Walk $node ""
    $out | Set-Content -Encoding utf8 $OutFile
    return
  }
  $size = [int64]$node.size
  $fs.Position = $base + [int64]$node.offset
  $buf = New-Object byte[] $size
  $read = 0
  while ($read -lt $size) { $read += $fs.Read($buf, $read, $size - $read) }
  [System.IO.File]::WriteAllBytes($OutFile, $buf)
  "ok $size"
} finally { $fs.Close() }
