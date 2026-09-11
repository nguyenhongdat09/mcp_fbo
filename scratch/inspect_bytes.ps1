$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')

$fPath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($fPath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$m = $regex.Match($content)
$enc = $m.Groups[1].Value.Trim()
$rawBytes = [System.Convert]::FromBase64String($enc)

$m1 = $t.GetMethod('c3sfBwuYu', [Reflection.BindingFlags]'Public,NonPublic,Static')
$res1 = $m1.Invoke($null, @(,$rawBytes))
Write-Output "c3sfBwuYu length: $($res1.Length)"
Write-Output "Hex: $([BitConverter]::ToString($res1).Substring(0, [Math]::Min(100, $res1.Length * 3 - 1)))"

$m2 = $t.GetMethod('NngNFrBjq', [Reflection.BindingFlags]'Public,NonPublic,Static')
$res2 = $m2.Invoke($null, @(,$rawBytes))
Write-Output "NngNFrBjq length: $($res2.Length)"
Write-Output "Hex: $([BitConverter]::ToString($res2).Substring(0, [Math]::Min(100, $res2.Length * 3 - 1)))"
