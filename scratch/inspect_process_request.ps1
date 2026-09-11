$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$p = $asm.GetType('View.View.Process')
$m = $p.GetMethod('ProcessRequest', [Reflection.BindingFlags]'Public,NonPublic,Instance')
if ($m) {
    $body = $m.GetMethodBody()
    if ($body) {
        $il = $body.GetILAsByteArray()
        Write-Output "View.View.Process.ProcessRequest IL bytes: $($il.Length)"
    } else {
        Write-Output "No body found (native/PInvoke?)"
    }
}

$h = $asm.GetType('View.View.Handler')
$mH = $h.GetMethod('ProcessRequest', [Reflection.BindingFlags]'Public,NonPublic,Instance')
if ($mH) {
    $body = $mH.GetMethodBody()
    if ($body) {
        $il = $body.GetILAsByteArray()
        Write-Output "View.View.Handler.ProcessRequest IL bytes: $($il.Length)"
    } else {
        Write-Output "No body found (native/PInvoke?)"
    }
}
