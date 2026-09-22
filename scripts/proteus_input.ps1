<#
Put input into a Proteus window, and get the notice windows out of the way first.

Two things make this necessary. ISIS opens a small notice window titled the same as the main
window, roughly 300x140, parked in the middle of the canvas; every click aimed at the drawing
area lands on that window instead, and nothing happens. And on this install the window-scoped
click and key calls of the automation layer did not reach ISIS at all - SetCursorPos plus
mouse_event and SendKeys did. Both were measured, not assumed.

    powershell -File proteus_input.ps1 -TargetPid 1234 -CloseNotices
    powershell -File proteus_input.ps1 -TargetPid 1234 -Click 750,362
    powershell -File proteus_input.ps1 -TargetPid 1234 -MoveX 860 -MoveY 480 -ClickX 860 -ClickY 480
    powershell -File proteus_input.ps1 -TargetPid 1234 -Keys "^s"

-CloseNotices closes every visible window of that process narrower than -NoticeWidth, and
reports what it closed. -Click moves the pointer, then presses and releases the left button.
Coordinates are screen pixels.

To find where a design coordinate is on screen, hover over the canvas and read the pointer
position out of the coordinate display at the bottom right of the window. Two readings give
the scale and the origin; on a 1440x900 screen with the window maximized at (12,10) the scale
was exactly 100 px per inch. See references/coords.md.
#>
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [int]$NoticeWidth = 700,
    [switch]$CloseNotices,
    [int]$MoveX = -1,
    [int]$MoveY = -1,
    [int]$ClickX = -1,
    [int]$ClickY = -1,
    [string]$Keys = "",
    [switch]$Focus
)

$sig = @'
using System;using System.Runtime.InteropServices;using System.Text;
public class PIn {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 public static IntPtr main = IntPtr.Zero;
 public static string log = "";
 public static void Scan(uint want, int maxw, bool closeSmall) {
   main = IntPtr.Zero; log = "";
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w = r.Right - r.Left, ht = r.Bottom - r.Top;
     var sb = new StringBuilder(256); GetWindowTextW(h, sb, sb.Capacity);
     if (w > maxw) { main = h; log += "main " + h + " '" + sb + "' " + w + "x" + ht + "\n"; }
     else if (closeSmall) { PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero); log += "closed " + h + " '" + sb + "' " + w + "x" + ht + "\n"; }
     else { log += "small " + h + " '" + sb + "' " + w + "x" + ht + "\n"; }
     return true;
   }, IntPtr.Zero);
 }
 public static void Click(int x, int y) { SetCursorPos(x, y); System.Threading.Thread.Sleep(320); mouse_event(0x0002,0,0,0,IntPtr.Zero); System.Threading.Thread.Sleep(110); mouse_event(0x0004,0,0,0,IntPtr.Zero); }
}
'@
Add-Type -TypeDefinition $sig
Add-Type -AssemblyName System.Windows.Forms

[PIn]::Scan([uint32]$TargetPid, $NoticeWidth, [bool]$CloseNotices)
Write-Output ([PIn]::log.Trim())

if ($Focus -and [PIn]::main -ne [IntPtr]::Zero) {
    [void][PIn]::SetForegroundWindow([PIn]::main)
    Start-Sleep -Seconds 1
}
if ($MoveX -ge 0 -and $MoveY -ge 0) { [void][PIn]::SetCursorPos($MoveX, $MoveY); Start-Sleep -Milliseconds 300 }
if ($ClickX -ge 0 -and $ClickY -ge 0) { [PIn]::Click($ClickX, $ClickY); Start-Sleep -Milliseconds 300 }
if ($Keys -ne "") { [System.Windows.Forms.SendKeys]::SendWait($Keys); Write-Output "sent keys: $Keys" }
