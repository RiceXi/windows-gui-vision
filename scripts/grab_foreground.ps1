<#
Screen-region capture of a window after raising it. Use when PrintWindow returns black
(GPU-composited clients: Qt Quick, WebEngine, modern Electron/Qt canvases).

    powershell -File grab_foreground.ps1 -OutPath shot.png -TitlePattern *Instruments*
    powershell -File grab_foreground.ps1 -OutPath shot.png -ProcessId 1234 [-ClientOnly]

Because this reads the composited desktop, whatever sits on top of the window is captured
too, and the mouse cursor may appear. Park the cursor somewhere harmless first.
#>
param(
    [Parameter(Mandatory=$true)][string]$OutPath,
    [string]$TitlePattern = "*",
    [int]$ProcessId = 0,
    [int]$WaitMs = 900,
    [switch]$ClientOnly
)
Add-Type -AssemblyName System.Drawing
$sig = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WgvFore {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    public delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h, ref POINT p);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
    [StructLayout(LayoutKind.Sequential)] public struct POINT { public int X, Y; }
}
'@
if (-not ("WgvFore" -as [type])) { Add-Type -TypeDefinition $sig -ReferencedAssemblies System.Drawing }

$found = New-Object System.Collections.ArrayList
$cb = [WgvFore+EnumProc]{
    param($h, $p)
    if ([WgvFore]::IsWindowVisible($h)) {
        $sb = New-Object System.Text.StringBuilder 512
        [void][WgvFore]::GetWindowText($h, $sb, 512)
        $t = $sb.ToString()
        if ($t) {
            $procId = 0
            [void][WgvFore]::GetWindowThreadProcessId($h, [ref]$procId)
            [void]$found.Add([pscustomobject]@{ h = $h; t = $t; pid = $procId })
        }
    }
    return $true
}
[void][WgvFore]::EnumWindows($cb, [IntPtr]::Zero)

if ($ProcessId -gt 0) {
    $pick = $found | Where-Object { $_.pid -eq $ProcessId } | Sort-Object { $_.t.Length } -Descending | Select-Object -First 1
} else {
    $pick = $found | Where-Object { $_.t -like $TitlePattern } | Sort-Object { $_.t.Length } -Descending | Select-Object -First 1
}
if (-not $pick) {
    Write-Error "No window matched. Available:"
    $found | Sort-Object t | ForEach-Object { Write-Error ("  [{0}] {1}" -f $_.pid, $_.t) }
    exit 2
}

[void][WgvFore]::ShowWindow($pick.h, 9)          # SW_RESTORE
[void][WgvFore]::SetForegroundWindow($pick.h)
Start-Sleep -Milliseconds $WaitMs

if ($ClientOnly) {
    $cr = New-Object WgvFore+RECT
    [void][WgvFore]::GetClientRect($pick.h, [ref]$cr)
    $pt = New-Object WgvFore+POINT
    [void][WgvFore]::ClientToScreen($pick.h, [ref]$pt)
    $x = $pt.X; $y = $pt.Y; $w = $cr.R - $cr.L; $h2 = $cr.B - $cr.T
} else {
    $r = New-Object WgvFore+RECT
    [void][WgvFore]::GetWindowRect($pick.h, [ref]$r)
    $x = $r.L; $y = $r.T; $w = $r.R - $r.L; $h2 = $r.B - $r.T
}
if ($w -le 0 -or $h2 -le 0) { Write-Error "Bad window size ${w}x${h2}"; exit 3 }

$bmp = New-Object System.Drawing.Bitmap $w, $h2
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.CopyFromScreen($x, $y, 0, 0, (New-Object System.Drawing.Size $w, $h2))
$g.Dispose()
$dir = Split-Path -Parent $OutPath
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output ("OK screen {0} {1}x{2} at ({3},{4}) <- '{5}'" -f $OutPath, $w, $h2, $x, $y, $pick.t)
