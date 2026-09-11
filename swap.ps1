param([string]$v)
$proj = "H:\z_thesis\codebase\projects\mlkem_bench"
$pq   = "$proj\pqclean"
$src  = "H:\z_thesis\codebase\PQClean\crypto_kem\ml-kem-$v\clean"
$keep = @("fips202.c","fips202.h","randombytes.c","randombytes.h","compat.h","crypto_declassify.h")
Get-ChildItem $pq -Include *.c,*.h -Recurse | Where-Object { $keep -notcontains $_.Name } | Remove-Item -Force
Copy-Item "$src\*.c" $pq
Copy-Item "$src\*.h" $pq
(Get-Content "$proj\hello_world.c") -replace 'MLKEM\d+',"MLKEM$v" | Set-Content "$proj\hello_world.c"
Write-Host "Swapped to ML-KEM-$v"
