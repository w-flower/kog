$ProgressPreference='SilentlyContinue'
$exe = 'D:\app\DeepseekHarness\DeepSeek Harness.exe'
$entry = 'D:\app\DeepseekHarness\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-desktop-host\lib\cli.js'
$env:ELECTRON_RUN_AS_NODE = '1'
$env:DSH_HOME = 'C:\Users\Lenovo\.dsh'
$log = 'D:\Projects\kog\_desk_verify.log'
$p = Start-Process -FilePath $exe -ArgumentList @('--expose-internals', $entry, '--profile', 'desktop', '--dump-config') `
  -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru -WindowStyle Hidden -WorkingDirectory 'C:\Users\Lenovo\.dsh\profiles\desktop'
Start-Sleep -Seconds 15
"pid=$($p.Id) exited=$($p.HasExited)"
"== stdout =="
Get-Content $log -ErrorAction SilentlyContinue | Select-Object -First 4 | Out-String
"== stderr =="
Get-Content "$log.err" -ErrorAction SilentlyContinue | Select-Object -First 6 | Out-String
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
