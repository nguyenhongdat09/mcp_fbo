$asm = [System.Reflection.Assembly]::LoadFrom('z:\FBO\VLOTUS\SP228\bin\View.dll')
$t = $asm.GetType('yxta9tQKhaZD3X4rhj.GrBjqThgnwfVJs9RZZ')
$ctors = $t.GetConstructors([Reflection.BindingFlags]'Public,NonPublic,Instance')
foreach ($c in $ctors) {
    $p = ($c.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Output "Constructor: .ctor($p)"
}
