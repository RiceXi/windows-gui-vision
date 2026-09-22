<#
Wait until Isis has finished loading a design before sending it any clicks.

Isis 7 accepts a design, puts its name in the title bar and *then* spends a long time loading:
the status bar reads `正在加载设计 'name'.` ("loading design name") while the canvas ignores every
click. Every click sent during that window is silently dropped, which looks exactly like a broken
script - a probe that draws nothing, a placement that never happens, a wire that will not commit.
Twenty-five seconds was not enough on this machine; a probe sequence sent after that wait still
went nowhere.

This polls the status bar (capture, crop the hint area, OCR) and returns when the text no longer
says it is loading. It needs Windows PowerShell 5.1 for the OCR - the WinRT OCR types do not load
in PowerShell 7.

    powershell -File scripts/proteus_wait_ready.ps1 -TargetPid 1234

Exit 0 means ready (or the poll could not OCR and the timeout expired - read the output), 1 means
the timeout ran out while still loading.
#>
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [int]$TimeoutSeconds = 240,
    [int]$PollSeconds = 3,
    [string]$Scripts = $PSScriptRoot,
    [string]$Pwsh = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe',
    [string]$Py = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$Ps5 = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'
)

$tmp = Join-Path $env:TEMP ("waitready_" + $TargetPid)
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$shot = Join-Path $tmp 'w.png'
$crops = Join-Path $tmp 'crops'

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$last = ''
while ((Get-Date) -lt $deadline) {
    & $Pwsh -File "$Scripts\capture_window.ps1" -OutPath $shot -ProcessId $TargetPid | Out-Null
    if (Test-Path $shot) {
        & $Py "$Scripts\crop.py" $shot $crops --box 0,784,700,830 --prefix w --scale 2 | Out-Null
        $crop = Join-Path $crops 'w00.png'
        if (Test-Path $crop) {
            $txt = (& $Ps5 -NoProfile -ExecutionPolicy Bypass -File "$Scripts\ocr.ps1" -Path $crop 2>&1 | Out-String)
            $line = ($txt -replace '\s+', ' ').Trim()
            if ($line -ne $last) { Write-Output ("status: " + $line); $last = $line }
            if ($line -notmatch '加载|Loading|loading') {
                Write-Output "READY"
                exit 0
            }
        }
    }
    Start-Sleep -Seconds $PollSeconds
}
Write-Output "TIMEOUT while still loading"
exit 1
