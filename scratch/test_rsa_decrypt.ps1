$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll")
$t = $asm.GetType("Crypto")
$inst = [Activator]::CreateInstance($t)

$fPath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($fPath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$matches = $regex.Matches($content)

$mRSA1 = $t.GetMethod("RSADecrypt", [type[]]@([string]))
$idx = 1
foreach ($match in $matches) {
    $enc = $match.Groups[1].Value.Trim()
    Write-Output "--- Block $idx (len $($enc.Length)) ---"
    try {
        $res = $mRSA1.Invoke($inst, @($enc))
        Write-Output "RSADecrypt result: $res"
    } catch {
        Write-Output "RSADecrypt failed: $_"
    }
    $idx++
}
