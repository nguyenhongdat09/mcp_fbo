$dllPath = "z:\FBO\VLOTUS\SP228\bin\FastBusiness.Data.Query.dll"
$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("FastBusiness.Data.Query.Report.Query")
$methods = $type.GetMethods([Reflection.BindingFlags]"Public,NonPublic,Static,Instance") | Where-Object { $_.Name -like "*Decrypt*" -or $_.Name -like "*Crypt*" -or $_.Name -like "*Cipher*" }
foreach ($m in $methods) {
    Write-Output "$($m.ReturnType.Name) $($m.Name)($([string]::Join(', ', ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }))))"
}

# Also let's inspect all types and methods with Decrypt in bin DLLs
Write-Output "--- Other types in FastBusiness.Data.Query.dll ---"
foreach ($t in $asm.GetTypes()) {
    $ms = $t.GetMethods([Reflection.BindingFlags]"Public,NonPublic,Static,Instance") | Where-Object { $_.Name -like "*Decrypt*" }
    if ($ms) {
        Write-Output "Type: $($t.FullName)"
        foreach ($m in $ms) {
            Write-Output "   $($m.Name)"
        }
    }
}
