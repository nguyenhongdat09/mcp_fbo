$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll")
foreach ($t in $asm.GetTypes()) {
    Write-Output "Type: $($t.FullName)"
    $methods = $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly') | Where-Object { $_.Name -notmatch '^[a-zA-Z0-9]{15,}' }
    foreach ($m in $methods) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Output "   $($m.ReturnType.Name) $($m.Name)($p)"
    }
}
