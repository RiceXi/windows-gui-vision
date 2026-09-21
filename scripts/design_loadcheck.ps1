<#
Open a design in ISIS and report whether it actually loaded.

An application that rejects a file often does it silently, and the result is indistinguishable
from a slow load or an empty new document. ISIS 7 tells you in the window title: a design that
loaded puts its file name before "- ISIS Professional". A crashed one leaves the title bare and
puts the complaint in a small dialog of its own.

    powershell -File scripts/design_loadcheck.ps1 -Path C:\work\design.DSN
    powershell -File scripts/design_loadcheck.ps1 -Path C:\work\design.DSN -KeepOpen

Exit code 0 means the design loaded, 1 means it did not load and said nothing, and 2 means it
did not load and put a dialog on screen - that last one is the crash shape. Run this on a copy:
the point is to find out whether the file loads, not to edit it.
#>
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Exe = 'C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE',
    [int]$WaitSeconds = 25,
    [switch]$KeepOpen
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class WinEnum {
    public delegate bool EnumProc(IntPtr hWnd, IntPtr lParam);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr lParam);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, StringBuilder s, int max);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }

    public static List<string> ForProcess(uint want) {
        var found = new List<string>();
        EnumWindows(delegate(IntPtr h, IntPtr l) {
            uint pid; GetWindowThreadProcessId(h, out pid);
            if (pid != want || !IsWindowVisible(h)) return true;
            var sb = new StringBuilder(512);
            GetWindowTextW(h, sb, sb.Capacity);
            RECT r; GetWindowRect(h, out r);
            found.Add(string.Format("{0}|{1}|{2}x{3}", h, sb.ToString(), r.Right - r.Left, r.Bottom - r.Top));
            return true;
        }, IntPtr.Zero);
        return found;
    }
}
'@
Add-Type -TypeDefinition $sig

if (-not (Test-Path -LiteralPath $Path)) { Write-Error "no such file: $Path"; exit 3 }

$proc = Start-Process -FilePath $Exe -ArgumentList "`"$Path`"" -PassThru
Start-Sleep -Seconds $WaitSeconds

$proc.Refresh()
$windows = [WinEnum]::ForProcess([uint32]$proc.Id)
$rows = @()
foreach ($w in $windows) {
    $parts = $w.Split('|')
    $rows += [pscustomobject]@{
        Handle = $parts[0]
        Title  = $parts[1]
        Size   = $parts[2]
        Wide   = [int]($parts[2].Split('x')[0])
    }
}

$stem = [System.IO.Path]::GetFileNameWithoutExtension($Path)
$main = $rows | Sort-Object Wide -Descending | Select-Object -First 1
$dialogs = $rows | Where-Object { $_ -ne $main -and $_.Wide -lt 700 }

Write-Output "pid $($proc.Id)  responding=$($proc.Responding)"
foreach ($r in $rows) { Write-Output ("  {0,-10} {1,-22} {2}" -f $r.Handle, $r.Size, $r.Title) }

if ($main -and $main.Title -like "*$stem*") {
    Write-Output "LOADED: the title names $stem."
    if ($dialogs) {
        Write-Output "Something is open over it as well - ISIS 7 shows a hint window on most"
        Write-Output "launches. Capture and OCR it if it does not look like that."
    }
    $code = 0
} else {
    if ($dialogs) {
        Write-Output "NOT LOADED, and a dialog is up: the crash shape. Capture the small window"
        Write-Output "and OCR it - it usually says access violation in module VGDVCDLL."
        $code = 2
    } else {
        Write-Output "NOT LOADED, and nothing was said: the silent shape. Waiting longer does"
        Write-Output "not help; the file was rejected."
        $code = 1
    }
}

if (-not $KeepOpen) {
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Write-Output "closed it again; pass -KeepOpen to leave it on screen"
}
exit $code
