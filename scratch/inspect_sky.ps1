$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Sky.dll")
Write-Output "Assembly: $($asm.FullName)"
foreach ($t in $asm.GetTypes()) {
    Write-Output "Type: $($t.FullName)"
    foreach ($m in $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
        Write-Output "   $($m.Name)"
    }
}
