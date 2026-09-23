<#
Place a device from ISIS's object selector at a chosen design coordinate.

The object selector lists the devices the design already contains, and placing one takes three
clicks: the row in the list, a point near the target so the preview follows you, then the target
itself. This does exactly that, converting design inches to screen pixels with the same mapping
as proteus_input.ps1, and closes the notice window first.

It will only place a device that is already in the list - which is the same constraint the file
route has: a design can render and wire a part type it already holds. Use ISIS to add a new type
to the list (Pick Devices) once, then place as many instances as you like from here.

    powershell -File proteus_place.ps1 -TargetPid 1234 -Row 0 -AtX 2.0 -AtY 1.0

Afterwards, verify. Two independent checks are cheap: capture the window and subtract it from a
capture of the design without the part (the symbol outline is a few hundred pixels of ink), and
parse the saved design to see the new record at the coordinate you asked for.
#>
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][double]$AtX,
    [Parameter(Mandatory=$true)][double]$AtY,
    [int]$Row = 0,
    [double]$ListX = 72,
    [double]$FirstRowY = 220,
    [double]$RowPitch = 13,
    [double]$OriginX = 790,
    [double]$OriginY = 450,
    [double]$Scale = 100,
    [double]$AnchorDX = -0.308,
    [double]$AnchorDY = 0.208,
    [int]$ClickGapMs = 1000,
    [string]$Keys = "",
    [int]$NoticeWidth = 700,
    [int]$ModeButtonX = 37,
    [int]$ModeButtonY = 133
)

$sig = @'
using System;using System.Runtime.InteropServices;
public class Pg {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 public static void Click(int x, int y) { SetCursorPos(x, y); System.Threading.Thread.Sleep(280); mouse_event(0x0002,0,0,0,IntPtr.Zero); System.Threading.Thread.Sleep(90); mouse_event(0x0004,0,0,0,IntPtr.Zero); }
}
'@
Add-Type -TypeDefinition $sig
Add-Type -AssemblyName System.Windows.Forms

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$input = Join-Path $here 'proteus_input.ps1'
& $input -TargetPid $TargetPid -CloseNotices -Focus -NoticeWidth $NoticeWidth
Start-Sleep -Milliseconds 800

# Placement only works in Component mode, and Isis remembers the mode between sessions. Left in
# Selection mode, a session silently swallows every canvas click and the placement looks like a
# broken script - which is what it looked like for a long time. ModeButton* is the Component Mode
# icon at screen coordinates for a window at (12,10) with the default (1416x832) size.
& $input -TargetPid $TargetPid -Focus -ClickX $ModeButtonX -ClickY $ModeButtonY | Out-Null
Start-Sleep -Milliseconds 700

$rowY = [int][Math]::Round($FirstRowY + $Row * $RowPitch)
Write-Output ("selecting list row {0} at window y {1}" -f $Row, $rowY)
# Each click goes through proteus_input.ps1 in its own process. Batched clicks from one process
# did not register with ISIS, and this sequence is the one that was measured to work.
& $input -TargetPid $TargetPid -ClickX ([int]$ListX) -ClickY $rowY
Start-Sleep -Milliseconds 1000

function To-Screen([double]$x, [double]$y) {
    @([int][Math]::Round($OriginX + $x * $Scale), [int][Math]::Round($OriginY - $y * $Scale))
}
# The point clicked and the coordinate ISIS stores are not the same point: measured on this
# build, the record lands 0.308 inch left and 0.208 inch above where the click was. Ask for the
# coordinate you want and click at the compensating point.
$clickX = $AtX - $AnchorDX
$clickY = $AtY - $AnchorDY
$dst = To-Screen $clickX $clickY
Write-Output ("placing at design ({0}, {1}): clicking ({2}, {3}) -> screen ({4}, {5})" -f $AtX, $AtY, $clickX, $clickY, $dst[0], $dst[1])
# Clicks go to whatever window is under the pointer, so the target has to be brought back to the
# front before every one of them. With two ISIS windows open - a second one opened on a copy to
# run a comparison, say - an unfocused click silently lands in the other design, and the run
# looks like a placement that did nothing. Measured both ways.
#
# Three clicks are needed, not two: the first arms the placement, the second one places the
# part, and a run that stops at two leaves a part hanging on the pointer (its ink follows the
# cursor and no record is written). Verified against the saved file, which is the only thing
# that settles it.
& $input -TargetPid $TargetPid -Focus -ClickX $dst[0] -ClickY $dst[1]
Start-Sleep -Milliseconds $ClickGapMs
& $input -TargetPid $TargetPid -Focus -ClickX $dst[0] -ClickY $dst[1]
Start-Sleep -Milliseconds $ClickGapMs
& $input -TargetPid $TargetPid -Focus -ClickX $dst[0] -ClickY $dst[1]
Start-Sleep -Milliseconds $ClickGapMs
& $input -TargetPid $TargetPid -Focus -MoveX 1150 -MoveY 150
Start-Sleep -Milliseconds 400

if ($Keys -ne "") {
    [System.Windows.Forms.SendKeys]::SendWait($Keys)
    Write-Output "sent keys: $Keys"
}
