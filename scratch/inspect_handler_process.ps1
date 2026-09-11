$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
Write-Output "--- Handler Methods ---"
$h = $asm.GetType('View.View.Handler')
if ($h) {
    foreach ($m in $h.GetMethods([System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
        $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Output "$($m.ReturnType.Name) $($m.Name)($p)"
    }
}
Write-Output "--- Process Methods ---"
$p = $asm.GetType('View.View.Process')
if ($p) {
    foreach ($m in $p.GetMethods([System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
        $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
        Write-Output "$($m.ReturnType.Name) $($m.Name)($params)"
    }
}
