<#
Find a device's pins by trying to draw from them, and letting the saved file say which attempts
produced a wire.

The hover-marker scan was unreliable: it picks up the part body and pin-name text as well as pins.
A wire, on the other hand, can only start on a connection point, so the *outcome* is the test: for
each point of a grid over the symbol, click there and then click a point to the right, and at the
end save the design and read the wires back. Every wire's first endpoint is a pin.

This works with the same input rules as dsn_draw_wires.ps1: notice pressed by message, mapping =
window + (785,440) at 100 px/inch, child-process clicks, and no window capture between the two
clicks of one attempt.

    powershell -File dsn_probe_pins.ps1 -Path design.DSN -Center "-3.976,-1.5" -HalfW 0.8 -HalfH 0.5

The design is modified and saved; run it on a copy. The probe wires are left in place, which is
also how the pin list is proved.
#>
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Center,
    [double]$HalfW = 0.8, [double]$HalfH = 0.5, [double]$Step = 0.1,
    [double]$ProbeDX = 0.15, [switch]$ProbeDY,          # probe to the right, or down, of the point
    [double]$OriginX = 785, [double]$OriginY = 440, [double]$Scale = 100,
    [string]$Exe = 'C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE',
    [string]$Pwsh = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe',
    [int]$WaitSeconds = 20,
    [switch]$KeepOpen
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$sig = @'
using System;using System.Drawing;using System.Runtime.InteropServices;using System.Text;
public class PP {
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
 public delegate bool EnumProc(IntPtr h, IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
 public static int[] RectOf(IntPtr h) { RECT r; GetWindowRect(h,out r); return new int[]{r.Left,r.Top}; }
 public static string Text(IntPtr h) { var sb=new StringBuilder(512); GetWindowTextW(h,sb,sb.Capacity); return sb.ToString(); }
 public static string Cls(IntPtr h) { var sb=new StringBuilder(128); GetClassNameW(h,sb,sb.Capacity); return sb.ToString(); }
 public static void Top(IntPtr h) { keybd_event(0x12,0,0,IntPtr.Zero); keybd_event(0x12,0,2,IntPtr.Zero); SetWindowPos(h,(IntPtr)(-1),0,0,0,0,0x0003); BringWindowToTop(h); SetForegroundWindow(h); }
 public static int DismissNotice(uint want, int maxw) {
   return PressOk(want, maxw);
 }
 public static int CountSmall(uint want, int maxw) {
   int n=0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid!=want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     if (r.Right-r.Left < maxw) n++;
     return true;
   }, IntPtr.Zero);
   return n;
 }
 public static int PressOk(uint want, int maxw) {
   int done=0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid!=want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     if (r.Right-r.Left >= maxw) return true;
     EnumChildWindows(h, delegate(IntPtr c, IntPtr l2) {
       if (Cls(c) != "Button" || !IsWindowVisible(c)) return true;
       string t = Text(c);
       if (t.StartsWith("\u786e\u5b9a") || t.StartsWith("OK")) { PostMessage(h, 0x0111, (IntPtr)GetDlgCtrlID(c), c); done++; }
       return true;
     }, IntPtr.Zero);
     return true;
   }, IntPtr.Zero);
   return done;
 }
}
'@
$refs = @()
foreach ($n in 'System.Drawing.Common','System.Drawing.Primitives','System.Private.Windows.GdiPlus') {
    try { $a=[System.Reflection.Assembly]::Load($n); if ($a.Location -and (Test-Path -LiteralPath $a.Location)) { $refs += $a.Location } } catch { }
}
if ($refs.Count -gt 0) { Add-Type -TypeDefinition $sig -ReferencedAssemblies $refs } else { Add-Type -TypeDefinition $sig -ReferencedAssemblies 'System.Drawing' }

# one-click helper as its own file: input from a child process is the only kind Isis accepts
$Helper = Join-Path $env:TEMP 'isis_click_helper.ps1'
$member = '[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y); [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, System.IntPtr e);'
Set-Content -LiteralPath $Helper -Encoding ASCII -Value @(
    'param([int]$X, [int]$Y, [switch]$Click)',
    ("Add-Type -Namespace Inp -Name M -MemberDefinition '" + $member + "'"),
    '[Inp.M]::SetCursorPos($X, $Y) | Out-Null',
    'Start-Sleep -Milliseconds 1200',
    'if ($Click) {',
    '    [Inp.M]::mouse_event(2,0,0,0,[IntPtr]::Zero)',
    '    Start-Sleep -Milliseconds 150',
    '    [Inp.M]::mouse_event(4,0,0,0,[IntPtr]::Zero)',
    '}'
)

Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process -FilePath $Exe -ArgumentList ('"' + $Path + '"') | Out-Null
$proc = $null
for ($i = 0; $i -lt ($WaitSeconds + 20) -and -not $proc; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-Process ISIS -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } |
            Sort-Object -Property MainWindowTitle | Select-Object -First 1
}
if (-not $proc) { Write-Error "Isis did not open $Path"; exit 9 }
$proc.Refresh(); $main = $proc.MainWindowHandle
$pressed = [PP]::DismissNotice([uint32]$proc.Id, 700)
Start-Sleep -Milliseconds 800
[PP]::Top($main); Start-Sleep -Milliseconds 1200
$rect = [PP]::RectOf($main)
$ox = $rect[0] + $OriginX; $oy = $rect[1] + $OriginY
$c = $Center -split ','
$cxD = [double]$c[0]; $cyD = [double]$c[1]
Write-Output ("notice {0}; window {1},{2}; origin {3},{4}" -f $pressed, $rect[0], $rect[1], $ox, $oy)

function To-Screen([double]$x, [double]$y) { @([int][Math]::Round($ox + $x*$Scale), [int][Math]::Round($oy - $y*$Scale)) }

$tried = 0
for ($dy = -$HalfH; $dy -le $HalfH + 1e-9; $dy += $Step) {
    for ($dx = -$HalfW; $dx -le $HalfW + 1e-9; $dx += $Step) {
        $x = $cxD + $dx; $y = $cyD + $dy
        $p = To-Screen $x $y
        $q = if ($ProbeDY) { To-Screen $x ($y - $ProbeDX) } else { To-Screen ($x + $ProbeDX) $y }
        # a selected part (it draws red) refuses to start wires, and a probe that landed on the body
        # leaves one selected - so clear the selection before every attempt
        [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
        Start-Sleep -Milliseconds 400
        & $Pwsh -File $Helper -X $p[0] -Y $p[1] -Click | Out-Null
        # keep the gap well past the double-click time: two quick clicks on the same part open its
        # properties dialog, and everything after that goes into the dialog, not the canvas
        Start-Sleep -Milliseconds 1200
        & $Pwsh -File $Helper -X $q[0] -Y $q[1] -Click | Out-Null
        Start-Sleep -Milliseconds 600
        # a dialog that did open is cleared before the next probe, and reported
        $small = [PP]::CountSmall([uint32]$proc.Id, 700)
        if ($small -gt 0) {
            [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
            Start-Sleep -Milliseconds 600
            Write-Output ("  probe {0}: {1} dialog(s) open - pressed ESC" -f ($tried + 1), $small)
        }
        $tried++
        if ($tried % 10 -eq 0) { Write-Output ("  {0} probes" -f $tried) }
    }
}
Write-Output ("{0} probes done; saving" -f $tried)
[System.Windows.Forms.SendKeys]::SendWait('^s')
Start-Sleep -Seconds 4
if (-not $KeepOpen) { Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force }
Write-Output "now read the file back (dsn_walk.py / count_objs.py): every wire's first endpoint is a pin"
