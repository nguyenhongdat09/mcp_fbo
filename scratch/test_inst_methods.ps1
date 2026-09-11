$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
$inst = [Activator]::CreateInstance($t, $true)

$byteMethods = @('DWV4AYanPS', 'MS44m6pGbj', 'Lhp48lqIlZ', 'OdZ4YaNkaN', 'KTo4jJrSlY', 'ysh4WJ0sLe', 'xfQ4bPPhtS', 'XY24cNRYEb', 'Wni4pFjJkI', 'ofu4onNqxU')
foreach ($name in $byteMethods) {
    $m = $t.GetMethod($name, [Reflection.BindingFlags]'Public,NonPublic,Instance')
    if ($m) {
        try {
            $bytes = $m.Invoke($inst, @())
            Write-Output "$name -> Length: $($bytes.Length), Base64: $([Convert]::ToBase64String($bytes)), Hex: $([BitConverter]::ToString($bytes))"
        } catch {
            Write-Output "$name -> Error: $_"
        }
    }
}
