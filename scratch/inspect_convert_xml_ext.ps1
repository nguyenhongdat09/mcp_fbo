$dllPath = "z:\FBO\VLOTUS\SP228\bin\ConvertXmlExtender.dll"
$asm = [Reflection.Assembly]::LoadFrom($dllPath)
Write-Output "Assembly: $($asm.FullName)"
foreach ($t in $asm.GetTypes()) {
    Write-Output "Type: $($t.FullName)"
    foreach ($m in $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
        Write-Output "   $($m.Name)"
    }
}
