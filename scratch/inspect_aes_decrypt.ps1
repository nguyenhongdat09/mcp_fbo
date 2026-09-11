$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll")
$t = $asm.GetType("Crypto")
$m = $t.GetMethod("AESDecrypt", [type[]]@([string], [string]))
$body = $m.GetMethodBody()
$il = $body.GetILAsByteArray()
Write-Output "AESDecrypt IL Length: $($il.Length)"

# Let's inspect fields of Crypto
Write-Output "=== Fields of Crypto ==="
foreach ($f in $t.GetFields([Reflection.BindingFlags]'Public,NonPublic,Static,Instance')) {
    Write-Output "Field: $($f.FieldType.Name) $($f.Name)"
}
