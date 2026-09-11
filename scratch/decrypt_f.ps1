$dllPath = "z:\FBO\VLOTUS\SP228\bin\FastBusiness.Data.Query.dll"
if (-not (Test-Path $dllPath)) {
    $dllPath = "z:\FBI\NHM_FBI\FBISP2422\bin\FastBusiness.Data.Query.dll"
}
Write-Output "Using DLL: $dllPath"

$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("FastBusiness.Data.Query.Report.Query")
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
        Write-Output "Content preview:"
        Write-Output $dec
    } catch {
        Write-Output "Failed to decrypt: $_"
    }
    $i++
}
