$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
$m = $t.GetMethod('DWV4AYanPS', [Reflection.BindingFlags]'Public,NonPublic,Static')
$res = $m.Invoke($null, @())
Write-Output "Type of res: $($res.GetType().FullName)"
Write-Output "Length: $($res.Length)"
Write-Output "Hex: $([BitConverter]::ToString($res))"
