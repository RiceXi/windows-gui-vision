# A sequence of screen clicks aimed at one window, all from a single process.
#
# Why one process: Windows refuses SetForegroundWindow when the user is interacting with
# something else, and the refusal is silent. A batch of clicks split across processes can
# therefore land in the *other* window half way through, which looks like "the script did half
# of it". This re-asserts the foreground before every click and reports whether it stuck, so a
# failed run is visible instead of being mistaken for a placement that did not take.
#
#   powershell -File proteus_click.ps1 -TargetPid 1234 -Clicks 25,143 72,232 1372,221
#   powershell -File proteus_click.ps1 -TargetPid 1234 -Clicks 1372,221 -Repeat 3
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][string]$Clicks,      # "x,y x,y ..." in screen pixels
    [int]$Repeat = 1,                                  # how often to repeat the last point
    [int]$GapMs = 800,
    [int]$PressMs = 45,
    [int]$Approach = 6,                                # mouse moves before each click
    [switch]$AbortOnLostFocus                          # stop instead of clicking into another window
)

$sig = @'
using System;using System.Runtime.InteropServices;using System.Text;
public class Clicker {
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint a, uint b, bool attach);
 [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
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
 public static bool Force() {
   if (main == IntPtr.Zero) return false;
   uint fgPid; uint fg = GetWindowThreadProcessId(GetForegroundWindow(), out fgPid);
   uint me = GetCurrentThreadId();
   AttachThreadInput(me, fg, true);
   BringWindowToTop(main);
   bool ok = SetForegroundWindow(main);
   AttachThreadInput(me, fg, false);
   return ok;
 }
 public static bool Focused() { return GetForegroundWindow() == main; }
 public static void Click(int x, int y, int press) {
   SetCursorPos(x, y);
   System.Threading.Thread.Sleep(120);
   mouse_event(0x0002, 0, 0, 0, IntPtr.Zero);
   System.Threading.Thread.Sleep(press);
   mouse_event(0x0004, 0, 0, 0, IntPtr.Zero);
 }
 // A click without a preceding *motion* is not the same event to the application: Isis decides
 // whether the pointer is on a connection point from its own mouse-move bookkeeping, so a jump
 // straight to the target and a press never starts a wire. Walking there in steps does.
 public static void ApproachClick(int x, int y, int press, int steps) {
   for (int i = 1; i <= steps; i++) {
     SetCursorPos(x - (steps - i) * 3, y - (steps - i) * 2);
     System.Threading.Thread.Sleep(40);
   }
   SetCursorPos(x, y);
   System.Threading.Thread.Sleep(150);
   mouse_event(0x0002, 0, 0, 0, IntPtr.Zero);
   System.Threading.Thread.Sleep(press);
   mouse_event(0x0004, 0, 0, 0, IntPtr.Zero);
 }
}
'@
Add-Type -TypeDefinition $sig

[Clicker]::Find([uint32]$TargetPid)
if ([Clicker]::main -eq [IntPtr]::Zero) { Write-Output "no visible window for pid $TargetPid"; exit 1 }

$points = @()
foreach ($p in ($Clicks -split '\s+')) {
    if ($p -match '^\s*(\d+)\s*,\s*(\d+)\s*$') {
        $points += ,@([int]$Matches[1], [int]$Matches[2])
    }
}
if ($points.Count -eq 0) { Write-Output "no points parsed from '$Clicks'"; exit 1 }
$last = $points[$points.Count - 1]
for ($i = 1; $i -lt $Repeat; $i++) { $points += ,$last }

$n = 0
foreach ($pt in $points) {
    $n++
    [void][Clicker]::Force()
    Start-Sleep -Milliseconds 150
    $focused = [Clicker]::Focused()
    # Half a placement, or half a wire, is worse than none: the leftover has to be found and
    # deleted by hand. Stopping here leaves the design in a state the file can describe exactly.
    if ($AbortOnLostFocus -and -not $focused) {
        Write-Output ("ABORT before click {0}/{1}: {2},{3} is not foreground" -f $n, $points.Count, $pt[0], $pt[1])
        exit 2
    }
    [Clicker]::ApproachClick($pt[0], $pt[1], $PressMs, $Approach)
    Write-Output ("click {0}/{1} at {2},{3} foreground={4}" -f $n, $points.Count, $pt[0], $pt[1], $focused)
    Start-Sleep -Milliseconds $GapMs
}
