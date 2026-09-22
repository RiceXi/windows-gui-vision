<#
Press OK on the notice Isis opens on launch, without needing the window to be on top.

The notice is a modal dialog (`#32770`, about 294x136, titled like the main window) owned by the
main window, and while it is up the main window is disabled - the coordinate readout stops
tracking the pointer and every click aimed at the canvas is discarded.

Two things made this hard to get rid of, and both are worth knowing before trying again:

* the dialog is often *behind another application's window*. A click at the button's own screen
  coordinates then lands in that other window - in the session this was measured in, on a Chrome
  window - and nothing happens. `WindowFromPoint` at the button's centre is how to see that;
* its OK button is a real child control, so it can be pressed by message instead of by pointer:
  post `WM_COMMAND` with the button's control id and handle. That works with the dialog behind
  everything and with the owning process in the background.

    powershell -File scripts/proteus_dismiss_notice.ps1 -ProcId 1234
    powershell -File scripts/proteus_dismiss_notice.ps1 -ProcId 1234 -NoMore

Exit 0 when no notice is left and the main window is enabled, 1 when one survived. `-NoMore`
also ticks the "do not show this again" control (it is hidden, so `BM_CLICK` on it, not a click),
which is a lasting change to that installation - use it only if that is wanted.
#>
param(
    [Parameter(Mandatory=$true)][int]$ProcId,
    [int]$NoticeWidth = 700,
    [switch]$NoMore,
    [int]$TimeoutSeconds = 20
)

$sig = @'
using System;using System.Collections.Generic;using System.Runtime.InteropServices;using System.Text;
public class DN {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 public static string Text(IntPtr h) { var sb = new StringBuilder(512); GetWindowTextW(h, sb, sb.Capacity); return sb.ToString(); }
 public static string Cls(IntPtr h) { var sb = new StringBuilder(256); GetClassNameW(h, sb, sb.Capacity); return sb.ToString(); }
 public static List<IntPtr> Small(uint want, int maxw) {
   var found = new List<IntPtr>();
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     if (r.Right - r.Left < maxw) found.Add(h);
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
     if (r.Right - r.Left >= maxw && r.Right - r.Left > bestw) { bestw = r.Right - r.Left; best = h; }
     return true;
   }, IntPtr.Zero);
   return best;
 }
 public static List<IntPtr> Children(IntPtr parent, string cls, bool visibleOnly) {
   var found = new List<IntPtr>();
   EnumChildWindows(parent, delegate(IntPtr h, IntPtr l) {
     if (cls != "" && Cls(h) != cls) return true;
     if (visibleOnly && !IsWindowVisible(h)) return true;
     found.Add(h);
     return true;
   }, IntPtr.Zero);
   return found;
 }
}
'@
Add-Type -TypeDefinition $sig

function Get-Notice { [DN]::Small([uint32]$ProcId, $NoticeWidth) }

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$notices = Get-Notice
while ($notices.Count -eq 0 -and (Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 500
    $notices = Get-Notice
}
if ($notices.Count -eq 0) {
    $main = [DN]::Main([uint32]$ProcId, $NoticeWidth)
    Write-Output "no notice window; main=$main enabled=$([DN]::IsWindowEnabled($main))"
    exit 0
}

foreach ($h in $notices) {
    $rect = New-Object DN+RECT
    [void][DN]::GetWindowRect($h, [ref]$rect)
    Write-Output ("notice {0} '{1}' at {2},{3} {4}x{5}" -f $h, [DN]::Text($h), $rect.Left, $rect.Top,
                  ($rect.Right - $rect.Left), ($rect.Bottom - $rect.Top))

    if ($NoMore) {
        foreach ($c in [DN]::Children($h, "Button", $false)) {
            $t = [DN]::Text($c)
            if ($t -match '不再显示|Do not show|don.t show') {
                [void][DN]::SendMessage($c, 0x00F5, [IntPtr]::Zero, [IntPtr]::Zero)   # BM_CLICK
                Write-Output ("  ticked the do-not-show control {0}" -f $c)
                Start-Sleep -Milliseconds 400
            }
        }
    }

    $ok = [IntPtr]::Zero
    foreach ($c in [DN]::Children($h, "Button", $true)) {
        if ([DN]::Text($c) -match '确定|OK') { $ok = $c; break }
    }
    if ($ok -eq [IntPtr]::Zero) {
        foreach ($c in [DN]::Children($h, "Button", $true)) { $ok = $c; break }
    }
    if ($ok -eq [IntPtr]::Zero) { Write-Output "  no button to press"; continue }
    $id = [DN]::GetDlgCtrlID($ok)
    Write-Output ("  pressing button {0} id={1} '{2}' by WM_COMMAND" -f $ok, $id, [DN]::Text($ok))
    [void][DN]::PostMessage($h, 0x0111, [IntPtr]$id, $ok)
    Start-Sleep -Milliseconds 1200
}

$left = Get-Notice
$main = [DN]::Main([uint32]$ProcId, $NoticeWidth)
Write-Output ("after: notices={0} main={1} enabled={2}" -f $left.Count, $main, [DN]::IsWindowEnabled($main))
if ($left.Count -eq 0 -and [DN]::IsWindowEnabled($main)) { Write-Output "notice dismissed"; exit 0 }
Write-Output "notice survived"; exit 1
