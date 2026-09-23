# Put a window on top of every other window, or take it back off.
#
# Why this exists: input goes to the window under the pointer, and Windows refuses
# SetForegroundWindow from a process the user is not interacting with. With a second ISIS
# window (a copy, opened to run a comparison) behind the user's own, every click lands in the
# user's design and the run looks like "the script did nothing".
#
#   powershell -File wintop.ps1 -TargetPid 1234 -On
#   powershell -File wintop.ps1 -TargetPid 1234 -Off
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [switch]$On,
    [switch]$Off
)

$sig = @'
using System;using System.Runtime.InteropServices;using System.Text;
public class TopMost {
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
 public static IntPtr main = IntPtr.Zero;
 public static int mw = 0;
 public static void Find(uint want) {
   main = IntPtr.Zero; mw = 0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w = r.R - r.L;
     if (w > mw) { mw = w; main = h; }
     return true;
   }, IntPtr.Zero);
 }
}
'@
Add-Type -TypeDefinition $sig

[TopMost]::Find([uint32]$TargetPid)
if ([TopMost]::main -eq [IntPtr]::Zero) { Write-Output "no visible window for pid $TargetPid"; exit 1 }

$HWND_TOPMOST = [IntPtr](-1)
$HWND_NOTOPMOST = [IntPtr](-2)
$SWP_NOMOVE = 0x0002
$SWP_NOSIZE = 0x0001
$flags = $SWP_NOMOVE -bor $SWP_NOSIZE

$after = $HWND_NOTOPMOST
$what = "not topmost"
if ($On) { $after = $HWND_TOPMOST; $what = "topmost" }

[void][TopMost]::SetWindowPos([TopMost]::main, $after, 0, 0, 0, 0, $flags)
Write-Output ("pid {0} handle {1} -> {2}" -f $TargetPid, [TopMost]::main, $what)
