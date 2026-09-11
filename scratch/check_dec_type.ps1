$dllPath = "z:\FBO\VLOTUS\SP228\bin\FastBusiness.Data.Query.dll"
$asm = [Reflection.Assembly]::LoadFrom($dllPath)
$type = $asm.GetType("FastBusiness.Data.Query.Report.Query")
$method = $type.GetMethod("Decrypt", [type[]]@([string]))

$filePath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($filePath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$m = $regex.Match($content)
$enc = $m.Groups[1].Value.Trim()
$res = $method.Invoke($null, @($enc))
Write-Output "Result is null: $($null -eq $res)"
if ($null -ne $res) {
    Write-Output "Result Type: $($res.GetType().FullName)"
    Write-Output "Result string: $res"
}
