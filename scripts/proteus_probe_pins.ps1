<#
Find a part's pins by asking ISIS, one grid point at a time.

A wire can only start on a connection point, and can only finish on one. So: click a candidate
point, click a pin you already know, press Escape. If the candidate was a pin, ISIS commits a
wire whose endpoints are both exact pin coordinates; if it was not, nothing is created and the
Escape clears the half-started wire. Save afterwards and read the file: the endpoints that
appeared are the pins.

That makes pin-hunting a file-verified operation with no vision in the loop, which matters
because the offsets a part answers to depend on the record's orientation and cannot be guessed
from the part's name.

    powershell -File proteus_probe_pins.ps1 -TargetPid 1234 -FromX 0.7 -FromY 0.8 `
        -CentreX 2.0 -CentreY 1.0 -SpanX 1.4 -SpanY 1.2 -Step 0.1 -Keys "^s"

Coordinates are design inches; they are converted with the same mapping as
proteus_input.ps1. Escape is sent after every candidate, and the file is saved at the end if
-Keys is given.
#>
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][double]$FromX,
    [Parameter(Mandatory=$true)][double]$FromY,
    [Parameter(Mandatory=$true)][double]$CentreX,
    [Parameter(Mandatory=$true)][double]$CentreY,
    [double]$SpanX = 1.2,
    [double]$SpanY = 1.0,
    [double]$Step = 0.1,
    [double]$OriginX = 790,
    [double]$OriginY = 450,
    [double]$Scale = 100,
    [string]$Keys = "",
    [int]$NoticeWidth = 700
)

$sig = @'
using System;using System.Runtime.InteropServices;using System.Text;
public class Pp {
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 public static IntPtr main = IntPtr.Zero;
 public static void Scan(uint want, int maxw) {
   main = IntPtr.Zero;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid != want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     if (r.Right - r.Left > maxw) main = h; else PostMessage(h, 0x0010, IntPtr.Zero, IntPtr.Zero);
     return true;
   }, IntPtr.Zero);
 }
 public static void Click(int x, int y) { SetCursorPos(x, y); System.Threading.Thread.Sleep(220); mouse_event(0x0002,0,0,0,IntPtr.Zero); System.Threading.Thread.Sleep(70); mouse_event(0x0004,0,0,0,IntPtr.Zero); }
}
'@
Add-Type -TypeDefinition $sig
Add-Type -AssemblyName System.Windows.Forms

[Pp]::Scan([uint32]$TargetPid, $NoticeWidth)
Start-Sleep -Seconds 1
[void][Pp]::SetForegroundWindow([Pp]::main)
Start-Sleep -Seconds 1

function To-Screen([double]$x, [double]$y) {
    @([int][Math]::Round($OriginX + $x * $Scale), [int][Math]::Round($OriginY - $y * $Scale))
}

$fx, $fy = To-Screen $FromX $FromY
$n = 0
for ($dy = -$SpanY / 2; $dy -le $SpanY / 2 + 1e-9; $dy += $Step) {
    for ($dx = -$SpanX / 2; $dx -le $SpanX / 2 + 1e-9; $dx += $Step) {
        $x = [Math]::Round($CentreX + $dx, 3)
        $y = [Math]::Round($CentreY + $dy, 3)
        $cx, $cy = To-Screen $x $y
        [Pp]::Click($cx, $cy)
        Start-Sleep -Milliseconds 260
        [Pp]::Click($fx, $fy)
        Start-Sleep -Milliseconds 260
        [System.Windows.Forms.SendKeys]::SendWait("{ESC}")
        Start-Sleep -Milliseconds 180
        $n++
    }
}
Write-Output ("probed $n candidates around ($CentreX, $CentreY)")
if ($Keys -ne "") {
    [void][Pp]::SetCursorPos(1150, 150)
    Start-Sleep -Milliseconds 300
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Write-Output "sent keys: $Keys"
}
