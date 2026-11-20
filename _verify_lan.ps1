$ProgressPreference='SilentlyContinue'
$ip = '192.168.43.170'
$out = 'D:\Projects\kog\dshgo-lan.ps1result.txt'
$lines = @()
$lines += "target=http://$ip`:3081"
# 1) 拿 launch token 后走一次根导航，看是否能 303 拿 cookie
$cookie = New-Object System.Net.CookieContainer
try {
  $r1 = Invoke-WebRequest -Uri "http://$ip`:3081/" -Headers @{Accept='text/html'} -UseBasicParsing -MaximumRedirection 0 -TimeoutSec 15 -ErrorAction Stop
  $lines += "GET / status=$($r1.StatusCode) location=$($r1.Headers['Location']) setcookie=$($r1.Headers['Set-Cookie'])"
} catch {
  $resp = $_.Exception.Response
  $lines += "GET / (redirect) status=$([int]$resp.StatusCode) location=$($resp.Headers['Location']) setcookie=$($resp.Headers['Set-Cookie'])"
  if ($resp.Headers['Set-Cookie']) {
    $parts = ($resp.Headers['Set-Cookie'] -split ';')[0] -split '='
    $cookie.Add([System.Net.Cookie]::new($parts[0], $parts[1], '/', $ip))
  }
}
# 2) 用 cookie 访问 /api/ping
try {
  $r2 = Invoke-WebRequest -Uri "http://$ip`:3081/api/ping" -UseBasicParsing -WebSession ([Microsoft.PowerShell.Commands.WebRequestSession]::new()) -TimeoutSec 10 -ErrorAction Stop
  $lines += "api/ping status=$($r2.StatusCode)"
} catch {
  $lines += "api/ping 无会话 status=$($_.Exception.Response.StatusCode.Value__)"
}
if ($cookie.Count -gt 0) {
  try {
    $h = @{ Cookie = "$($cookie.GetCookies([uri]"http://$ip`:3081")[0].Name)=$($cookie.GetCookies([uri]"http://$ip`:3081")[0].Value)" }
    $r3 = Invoke-WebRequest -Uri "http://$ip`:3081/api/ping" -Headers $h -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    $lines += "api/ping 带cookie status=$($r3.StatusCode)"
  } catch { $lines += "api/ping 带cookie status=$($_.Exception.Response.StatusCode.Value__)" }
} else { $lines += "未取到会话 cookie（根导航未下发）" }
$lines | Set-Content -Encoding utf8 $out
