<#
List targetable top-level windows: handle, pid, title, rect (logical px), maximized flag.

    powershell -File wins.ps1 [-Filter *ISIS*]

Windows whose client area lives on another desktop/session are not listed.
The rect is what you need to turn "a point inside a capture" into an input coordinate.
#>
param([string]$Filter = "*")

$sig = @'
using System;
using System.Runtime.InteropServices;
using System.Text;
public class WgvWins {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr p);
    public delegate bool EnumProc(IntPtr h, IntPtr p);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern bool IsZoomed(IntPtr h);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
}
'@
if (-not ("WgvWins" -as [type])) { Add-Type -TypeDefinition $sig }

$rows = New-Object System.Collections.ArrayList
$cb = [WgvWins+EnumProc]{
    param($h, $p)
    if ([WgvWins]::IsWindowVisible($h)) {
        $sb = New-Object System.Text.StringBuilder 512
        [void][WgvWins]::GetWindowText($h, $sb, 512)
        $title = $sb.ToString()
        if ($title -and $title -like $Filter) {
            $procId = 0
            [void][WgvWins]::GetWindowThreadProcessId($h, [ref]$procId)
            $r = New-Object WgvWins+RECT
            [void][WgvWins]::GetWindowRect($h, [ref]$r)
            [void]$rows.Add([pscustomobject]@{
                handle = $h
                pid    = $procId
                zoomed = [WgvWins]::IsZoomed($h)
                left   = $r.L
                top    = $r.T
                width  = ($r.R - $r.L)
                height = ($r.B - $r.T)
                title  = $title
            })
        }
    }
    return $true
}
[void][WgvWins]::EnumWindows($cb, [IntPtr]::Zero)

Add-Type -AssemblyName System.Windows.Forms -ErrorAction SilentlyContinue
$vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
Write-Output ("virtual-screen {0},{1} {2}x{3}" -f $vs.X, $vs.Y, $vs.Width, $vs.Height)
$rows | Sort-Object pid | Format-Table -AutoSize -Wrap
