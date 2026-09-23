# Hover a list of points over a window and save one capture per point.
#
# Isis marks a connection point when the pointer rests on one, and the marker is much smaller
# than the highlight it draws for a part body, so the difference between two captures is enough
# to tell "this is a pin" from "this is the body" - without asking what the cursor looks like,
# which a PrintWindow capture never contains.
#
#   powershell -File hover_scan.ps1 -TargetPid 1234 -Points "1119,375 1119,380" -OutDir out
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [Parameter(Mandatory=$true)][string]$Points,   # "x,y x,y ..." in screen pixels
    [Parameter(Mandatory=$true)][string]$OutDir,
    [int]$SettleMs = 500
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;using System.Runtime.InteropServices;
public class HScan {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
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

[HScan]::Find([uint32]$TargetPid)
if ([HScan]::main -eq [IntPtr]::Zero) { Write-Output "no window"; exit 1 }
$r = New-Object HScan+RECT
[void][HScan]::GetWindowRect([HScan]::main, [ref]$r)
$w = $r.R - $r.L; $h = $r.B - $r.T
[void][HScan]::SetForegroundWindow([HScan]::main)
Start-Sleep -Milliseconds 600
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$i = 0
foreach ($p in ($Points -split '\s+')) {
    if ($p -notmatch '^\s*(\d+)\s*,\s*(\d+)\s*$') { continue }
    $i++
    $px = [int]$Matches[1]; $py = [int]$Matches[2]
    [void][HScan]::SetCursorPos($px, $py)
    Start-Sleep -Milliseconds $SettleMs
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    [void][HScan]::PrintWindow([HScan]::main, $hdc, 0)
    $g.ReleaseHdc($hdc); $g.Dispose()
    $out = Join-Path $OutDir ("h{0}_{1}_{2}.png" -f $i, $px, $py)
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output "hovered $px,$py -> $out"
}
