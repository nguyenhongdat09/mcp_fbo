$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')

$fPath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($fPath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$m = $regex.Match($content)
$enc = $m.Groups[1].Value.Trim()
$rawBytes = [System.Convert]::FromBase64String($enc)

Write-Output "--- Testing methods taking String ---"
$methods = $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static')
foreach ($method in $methods) {
    $p = $method.GetParameters()
    if ($p.Length -eq 1 -and $p[0].ParameterType -eq [string]) {
        try {
            $res = $method.Invoke($null, @($enc))
            if ($null -ne $res) {
                Write-Output "Method $($method.Name)(String) succeeded: $($res.ToString().Substring(0, [Math]::Min(100, $res.ToString().Length)))"
            }
        } catch {
            Write-Output "Method $($method.Name)(String) failed: $($_.Exception.InnerException.Message)"
        }
    }
}

Write-Output "--- Testing methods taking Byte[] ---"
foreach ($method in $methods) {
    $p = $method.GetParameters()
    if ($p.Length -eq 1 -and $p[0].ParameterType -eq [byte[]]) {
        try {
            $res = $method.Invoke($null, @(,$rawBytes))
            if ($null -ne $res) {
                $decText = [System.Text.Encoding]::UTF8.GetString($res)
                Write-Output "Method $($method.Name)(Byte[]) succeeded: $($decText.Substring(0, [Math]::Min(100, $decText.Length)))"
            }
        } catch {
            Write-Output "Method $($method.Name)(Byte[]) failed: $($_.Exception.InnerException.Message)"
        }
    }
}
