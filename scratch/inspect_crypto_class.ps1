$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll")
$t = $asm.GetType("Crypto")
Write-Output "=== Methods of Crypto ==="
foreach ($m in $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
    $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Output "$($m.ReturnType.Name) $($m.Name)($p)"
}
