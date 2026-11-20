$ProgressPreference='SilentlyContinue'
$node = 'D:\app\DeepseekHarness\resources\runtime\primary-runtime\dependencies\node\bin\node.exe'
$entry = 'D:\app\DeepseekHarness\resources\app.asar\dsh\node_modules\@deepseek-ai\dsh-desktop-host\lib\cli.js'
$exe = 'D:\app\DeepseekHarness\DeepSeek Harness.exe'
$env:ELECTRON_RUN_AS_NODE = '1'
$env:DSH_HOME = 'C:\Users\Lenovo\.dsh'
$log = 'D:\Projects\kog\_desk_verify.log'

# desktop profile 真实注入测试：--from-default-profile 不行（会覆盖），改用 DSH_PROFILE 无关；
# 这里通过 --patch 把 desktop 的 package.json 依赖上下文带上，并用 cwd 指到 desktop 目录
$args = @(
  '--expose-internals', $entry,
  '--profile', 'desktop',
  '--dump-config'
)
$p = Start-Process -FilePath $node -ArgumentList $args -RedirectStandardOutput $log -RedirectStandardError "$log.err" -PassThru -WindowStyle Hidden -WorkingDirectory 'C:\Users\Lenovo\.dsh\profiles\desktop'
Start-Sleep -Seconds 12
"pid=$($p.Id) exited=$($p.HasExited)"
"== stdout head =="
Get-Content $log -ErrorAction SilentlyContinue | Select-Object -First 5 | Out-String
"== stderr =="
Get-Content "$log.err" -ErrorAction SilentlyContinue | Select-Object -First 8 | Out-String
if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
