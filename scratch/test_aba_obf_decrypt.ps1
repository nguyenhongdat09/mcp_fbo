$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
if ($null -eq $t) {
    Write-Output "Type not found!"
    exit
}
$m = $t.GetMethod('LTp4ewuY2v', [System.Reflection.BindingFlags]'Public,NonPublic,Static')
if ($null -eq $m) {
    Write-Output "Method not found!"
    exit
}

$fPath = "z:\FBO\VLOTUS\SP228\App_Data\Controllers\Filter\AccountBalanceAdjustment.f"
$content = [System.IO.File]::ReadAllText($fPath)
$regex = [regex]'<Encrypted>([\s\S]*?)</Encrypted>'
$matches = $regex.Matches($content)
Write-Output "Matches found: $($matches.Count)"

$idx = 1
foreach ($match in $matches) {
    $enc = $match.Groups[1].Value.Trim()
    Write-Output "--- Block $idx (length $($enc.Length)) ---"
    try {
        $rawBytes = [System.Convert]::FromBase64String($enc)
        $res = $m.Invoke($null, @(,$rawBytes))
        if ($null -eq $res) {
            Write-Output "Result is null"
        } else {
            $text = [System.Text.Encoding]::UTF8.GetString($res)
            Write-Output "SUCCESS! Length: $($text.Length)"
            Write-Output $text
        }
    } catch {
        Write-Output "Error: $_"
    }
    $idx++
}
