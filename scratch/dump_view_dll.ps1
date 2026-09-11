$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
Write-Output "--- Types in View.dll ---"
foreach ($t in $asm.GetTypes()) {
    Write-Output "Type: $($t.FullName)"
    foreach ($m in $t.GetMethods([System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Output "   $($m.ReturnType.Name) $($m.Name)($p)"
    }
}
