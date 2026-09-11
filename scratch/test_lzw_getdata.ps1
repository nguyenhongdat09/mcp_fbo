$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\Decompress.dll")
$t = $asm.GetType("Decompress.LZW")
$inst = [System.Activator]::CreateInstance($t)
$m = $t.GetMethod("GetData", [type[]]@([string]))

$fPath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($fPath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$matches = $regex.Matches($content)

$i = 1
foreach ($match in $matches) {
    $enc = $match.Groups[1].Value.Trim()
    Write-Output "--- Block $i ---"
    try {
        $res = $m.Invoke($inst, @($enc))
        Write-Output "Result: $res"
    } catch {
        Write-Output "Error: $_"
    }
    $i++
}
