$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\Decompress.dll")
$t = $asm.GetType("Decompress.LZW")
Write-Output "Methods of Decompress.LZW:"
foreach ($m in $t.GetMethods([System.Reflection.BindingFlags]'Public,NonPublic,Static,Instance')) {
    $p = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Output "$($m.ReturnType.Name) $($m.Name)($p)"
}
