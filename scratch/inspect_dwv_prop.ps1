$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
$m = $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance') | Where-Object { $_.Name -eq 'DWV4AYanPS' }
Write-Output "DeclaringType: $($m.DeclaringType.FullName)"
Write-Output "IsStatic: $($m.IsStatic)"
Write-Output "IsPrivate: $($m.IsPrivate)"
Write-Output "IsPublic: $($m.IsPublic)"
