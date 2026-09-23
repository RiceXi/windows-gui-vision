# Hover each candidate button in the ISIS left icon column and capture the whole window,
# so the status bar text for each hover can be read out afterwards.
#
#   powershell -File probe_toolbar.ps1 -TargetPid 1234 -X 13 -Ys "100,121,143" -OutDir out
param(
    [Parameter(Mandatory=$true)][int]$TargetPid,
    [int]$X = 13,
    [string]$Ys = "100,121,143,165,187,209,231,253,275,297,319,341",
    [Parameter(Mandatory=$true)][string]$OutDir
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;
using System.Runtime.InteropServices;
public class TBProbe {
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L, T, R, B; }
  public static IntPtr main = IntPtr.Zero;
  public static int mw = 0;
  public static void Scan(uint want) {
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

[TBProbe]::Scan([uint32]$TargetPid)
if ([TBProbe]::main -eq [IntPtr]::Zero) { Write-Output "no visible window for pid $TargetPid"; exit 1 }

$r = New-Object TBProbe+RECT
[void][TBProbe]::GetWindowRect([TBProbe]::main, [ref]$r)
$w = $r.R - $r.L
$h = $r.B - $r.T
Write-Output ("window left={0} top={1} {2}x{3}" -f $r.L, $r.T, $w, $h)

[void][TBProbe]::SetForegroundWindow([TBProbe]::main)
Start-Sleep -Milliseconds 800

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
foreach ($y in ($Ys -split ',')) {
    $yy = [int]$y
    [void][TBProbe]::SetCursorPos($X, $yy)
    Start-Sleep -Milliseconds 800
    $bmp = New-Object System.Drawing.Bitmap $w, $h
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $hdc = $g.GetHdc()
    [void][TBProbe]::PrintWindow([TBProbe]::main, $hdc, 0)
    $g.ReleaseHdc($hdc)
    $g.Dispose()
    $out = Join-Path $OutDir ("y{0}.png" -f $yy)
    $bmp.Save($out, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output ("saved {0}" -f $out)
}
