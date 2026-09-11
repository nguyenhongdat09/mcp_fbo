$dllPath = "z:\FBI\NHM_FBI\FBISP2422\bin\BouncyCastle.Crypto.dll"
Write-Output "Test-Path: $(Test-Path $dllPath)"
$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("crypto.Security")
Write-Output "Type is null: $($null -eq $type)"
if ($null -ne $type) {
    $methods = $type.GetMethods([Reflection.BindingFlags]"Public,NonPublic,Static,Instance")
    foreach ($m in $methods) {
        Write-Output "Method: $($m.Name), params: $($m.GetParameters().Count)"
        foreach ($p in $m.GetParameters()) {
            Write-Output "   Param: $($p.Name) : $($p.ParameterType.FullName)"
        }
    }
}
