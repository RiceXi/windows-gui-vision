# One process, one or two presses at a place - the shape ISIS needs to see a real
# double click, and the only way to send a right click at all.
#
#   powershell -File mouse.ps1 -TargetPid 1234 -X 648 -Y 210 -Button right
#   powershell -File mouse.ps1 -TargetPid 1234 -X 648 -Y 210 -Count 2
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][int]$X,
    [Parameter(Mandatory=$true)][int]$Y,
    [ValidateSet("left", "right")][string]$Button = "left",
    [ValidateRange(1, 3)][int]$Count = 1,
    [int]$GapMs = 80
)

$sig = @'
using System;using System.Runtime.InteropServices;
public class Mz {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 public static void Press(int down, int up) {
   mouse_event((uint)down,0,0,0,IntPtr.Zero); System.Threading.Thread.Sleep(45);
   mouse_event((uint)up,0,0,0,IntPtr.Zero);
 }
}
'@
Add-Type -TypeDefinition $sig

$down = 0x0002
$up = 0x0004
if ($Button -eq "right") { $down = 0x0008; $up = 0x0010 }

[void][Mz]::SetCursorPos($X, $Y)
Start-Sleep -Milliseconds 300
for ($i = 0; $i -lt $Count; $i++) {
    [Mz]::Press($down, $up)
    if ($i -lt $Count - 1) { Start-Sleep -Milliseconds $GapMs }
}
Write-Output "$Button x$Count at $X,$Y"
