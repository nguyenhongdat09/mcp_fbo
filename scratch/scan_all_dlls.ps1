$dllPath = "z:\FBO\VLOTUS\SP228\bin\FastBusiness.Data.Query.dll"
$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("FastBusiness.Data.Query.Report.Query")
$method = $type.GetMethod("Decrypt", [Reflection.BindingFlags]"Public,NonPublic,Static,Instance")
$body = $method.GetMethodBody()
$bytes = $body.GetILAsByteArray()
Write-Output "IL byte count: $($bytes.Length)"

# Also let's check what other Decrypt methods exist across ALL DLLs in bin!
$binDir = "z:\FBO\VLOTUS\SP228\bin"
Get-ChildItem -Path $binDir -Filter "*.dll" | ForEach-Object {
    try {
        $a = [Reflection.Assembly]::LoadFrom($_.FullName)
        foreach ($t in $a.GetTypes()) {
            foreach ($m in $t.GetMethods([Reflection.BindingFlags]"Public,NonPublic,Static,Instance,DeclaredOnly")) {
                if ($m.Name -match "(?i)decrypt|decode|unprotect") {
                    Write-Output "$($_.Name) -> $($t.FullName).$($m.Name)"
                }
            }
        }
    } catch {}
}
