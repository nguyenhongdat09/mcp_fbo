$dlls = @("ExternalScript.dll", "Fields.dll", "Voucher.dll", "ViewPanel.dll")
foreach ($d in $dlls) {
    Write-Output "=== $d ==="
    $asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\$d")
    foreach ($t in $asm.GetTypes()) {
        Write-Output "Type: $($t.FullName)"
        foreach ($m in $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance,DeclaredOnly')) {
            if ($m.Name -notmatch 'get_|set_') {
                Write-Output "   $($m.ReturnType.Name) $($m.Name)"
            }
        }
    }
}
