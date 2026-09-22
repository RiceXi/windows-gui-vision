<#
Open a design in Isis, save it from inside the application, and report what survives.

design_loadcheck.ps1 answers "did Isis accept this file". That is not the same question as "did
it read all of it". A design whose object area is damaged part way through can load *partially*:
the title still names the file, the load check says yes, and the objects after the damage are
simply missing. Saving from inside the application then writes that reduced design back out,
which is what gives it away.

So the acceptance test for anything a script writes is: open it, save it from the app, close it,
and compare the objects before and after. This does the first half and reports the sizes and the
reference designators it finds on both sides.

    powershell -File scripts/dsn_savecheck.ps1 -Path C:\work\built.DSN

Run it on a copy. A clean design comes back the same size and with the same list of designators;
one that only partly loaded comes back smaller with objects missing.
#>
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Exe = 'C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE',
    [int]$WaitSeconds = 25,
    [string]$InputScript = "$PSScriptRoot\proteus_input.ps1"
)

function Get-Objects([string]$file) {
    $bytes = [System.IO.File]::ReadAllBytes($file)
    $text = [System.Text.Encoding]::GetEncoding(28591).GetString($bytes)
    $refs = [regex]::Matches($text, 'U[0-9]+(:[A-D])?') | ForEach-Object { $_.Value } |
            Sort-Object -Unique
    $wires = [regex]::Matches($text, [char]2 + [char]127 + 'WIRE' + [char]0).Count
    [pscustomobject]@{ Bytes = $bytes.Length; Refs = ($refs -join ' '); Wires = $wires }
}

if (-not (Test-Path -LiteralPath $Path)) { Write-Error "no such file: $Path"; exit 3 }
$before = Get-Objects $Path
Write-Output "before: $($before.Bytes) bytes, $($before.Wires) wire markers, refs: $($before.Refs)"

$proc = Start-Process -FilePath $Exe -ArgumentList "`"$Path`"" -PassThru
Start-Sleep -Seconds $WaitSeconds
& $InputScript -TargetPid $proc.Id -CloseNotices -Focus | Out-Null
Start-Sleep -Seconds 2
& $InputScript -TargetPid $proc.Id -Keys "^s"
Start-Sleep -Seconds 4
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue

$after = Get-Objects $Path
Write-Output "after:  $($after.Bytes) bytes, $($after.Wires) wire markers, refs: $($after.Refs)"
if ($after.Bytes -eq $before.Bytes -and $after.Refs -eq $before.Refs) {
    Write-Output "SAME: the design survived a save from inside Isis, so it loaded whole."
    exit 0
}
Write-Output "CHANGED: the design Isis saved is not the one it was given. Either it only partly"
Write-Output "loaded (objects after the damaged one are gone) or the save normalised it - compare"
Write-Output "the reference designators and the wire count, those do not change on a normal save."
exit 2
