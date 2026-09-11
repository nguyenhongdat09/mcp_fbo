$dllPath = "z:\FBI\NHM_FBI\FBISP2422\bin\BouncyCastle.Crypto.dll"
if (-not (Test-Path $dllPath)) {
    Write-Output "DLL not found: $dllPath"
    exit
}

$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("crypto.Security")
$method = $type.GetMethod("Decrypt", [type[]]@([string]))

$filePath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($filePath)

$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$matches = $regex.Matches($content)
Write-Output "Total matches: $($matches.Count)"

$i = 1
foreach ($m in $matches) {
    $enc = $m.Groups[1].Value.Trim()
    Write-Output "================ Block $i ================"
    Write-Output "Encrypted length: $($enc.Length)"
    try {
        $dec = $method.Invoke($null, @($enc))
        Write-Output "Decrypted successfully! Length: $($dec.Length)"
        Write-Output "--- Content preview ---"
        Write-Output $dec
    } catch {
        Write-Output "Failed to decrypt: $_"
    }
    $i++
}
