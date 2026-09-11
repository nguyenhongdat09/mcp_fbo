$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
$methods = $t.GetMethods([Reflection.BindingFlags]'Public,NonPublic,Static,Instance')
foreach ($m in $methods) {
    if ($m.ReturnType -eq [byte[]]) {
        Write-Output "Byte[] method: $($m.Name), params: $($m.GetParameters().Count)"
    }
}
