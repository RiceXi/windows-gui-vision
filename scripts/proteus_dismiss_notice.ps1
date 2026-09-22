<#
Get rid of the modal notice Isis opens on launch, the way a person does.

The notice is a second top-level window of the Isis process: 294x136, titled like the main
window, and it makes the main window modal-disabled for as long as it is up - the coordinate
display stops tracking the pointer and every click is discarded. See
references/proteus-modal-notice.md.

Two things make it awkward:

* it may sit *behind* the main window, so clicking at its rectangle hits the disabled main
  window instead. It has to be brought to the front first;
* closing it with WM_CLOSE (what `proteus_input.ps1 -CloseNotices` does) makes it disappear from
  the window list while leaving the main window disabled, which is worse than leaving it alone.

So: find it, bring it forward, press ENTER, and if that does not take, click along its bottom
edge until it is gone. Then confirm - and the caller should confirm for itself that the
coordinate display reads a real design coordinate on the next hover.

    powershell -File scripts/proteus_dismiss_notice.ps1 -TargetPid 1234

Exit 0 if no small window is left, 1 if one survived.
#>
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [int]$NoticeWidth = 700,
    [string]$Pwsh = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe',
    [string]$InputScript = "$PSScriptRoot\proteus_input.ps1"
)

Add-Type -AssemblyName System.Windows.Forms
$sig = @'
using System;using System.Collections.Generic;using System.Runtime.InteropServices;using System.Text;
public class Nw {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int cmd);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
 [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 public static List<string> Small(uint want, int maxw) {
   var found = new List<string>();
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w = r.Right - r.Left;
     if (w < maxw) found.Add(h + "|" + r.Left + "|" + r.Top + "|" + w + "|" + (r.Bottom - r.Top));
     return true;
   }, IntPtr.Zero);
   return found;
 }
 public static IntPtr Main(uint want, int maxw) {
   IntPtr best = IntPtr.Zero; int bestw = 0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w = r.Right - r.Left;
     if (w >= maxw && w > bestw) { bestw = w; best = h; }
     return true;
   }, IntPtr.Zero);
   return best;
 }
 public static string MainInfo(uint want, int maxw) {
   IntPtr h = Main(want, maxw);
   if (h == IntPtr.Zero) return "none";
   return h + " enabled=" + IsWindowEnabled(h);
 }
}
'@
Add-Type -TypeDefinition $sig

$small = [Nw]::Small([uint32]$TargetPid, $NoticeWidth)
if ($small.Count -eq 0) { Write-Output "no small window to dismiss"; exit 0 }

foreach ($row in $small) {
    $p = $row.Split('|')
    $h = [IntPtr][int64]$p[0]
    $l = [int]$p[1]; $t = [int]$p[2]; $w = [int]$p[3]; $ht = [int]$p[4]
    Write-Output ("dismissing window at $l,$t ${w}x${ht}")
    [void][Nw]::ShowWindow($h, 5)          # SW_SHOW
    # SetForegroundWindow is refused to a background process, and a window that is *behind* the
    # disabled main window never sees a click. Raising it does not need foreground rights.
    [void][Nw]::SetWindowPos($h, [IntPtr](-1), 0, 0, 0, 0, 0x0003)   # HWND_TOPMOST, NOMOVE|NOSIZE
    [void][Nw]::BringWindowToTop($h)
    [void][Nw]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 600
    [System.Windows.Forms.SendKeys]::SendWait("{ENTER}")
    Start-Sleep -Milliseconds 800
    if ([Nw]::Small([uint32]$TargetPid, $NoticeWidth).Count -eq 0) { break }
    # click along the bottom edge, where a dialog button sits
    for ($x = $l + 20; $x -lt $l + $w - 10; $x += 24) {
        & $InputScript -TargetPid $TargetPid -ClickX $x -ClickY ($t + $ht - 22) | Out-Null
        Start-Sleep -Milliseconds 250
        if ([Nw]::Small([uint32]$TargetPid, $NoticeWidth).Count -eq 0) { break }
    }
    if ([Nw]::Small([uint32]$TargetPid, $NoticeWidth).Count -eq 0) { break }
}

Start-Sleep -Seconds 1
$left = [Nw]::Small([uint32]$TargetPid, $NoticeWidth)
Write-Output ("main window: " + [Nw]::MainInfo([uint32]$TargetPid, $NoticeWidth))
if ($left.Count -eq 0) { Write-Output "notice dismissed"; exit 0 }
Write-Output ("still open: " + ($left -join ", ")); exit 1
