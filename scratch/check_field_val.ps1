$asm = [Reflection.Assembly]::LoadFrom("z:\FBO\VLOTUS\SP228\bin\FastBusiness.Crypto.dll")
$t = $asm.GetType("Crypto")
$inst = [Activator]::CreateInstance($t)
$f = $t.GetField("bSyNsLxAu", [Reflection.BindingFlags]'Public,NonPublic,Instance,Static')
$val = $f.GetValue($inst)
Write-Output "bSyNsLxAu: '$val'"
