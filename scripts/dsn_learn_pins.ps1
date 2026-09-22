<#
Learn a device's pin positions by hovering over its symbol and watching for the hover marker.

Why this exists: a generated design can place parts and draw wires, but only if the pin positions
are known, and they are not in any readable field - they come from the symbol drawing. What *is*
observable is Isis's own feedback: hovering a connection point draws a small marker (measured about
31x16 px at the default zoom), while hovering the body of a part lights up the whole symbol (about
100x64). The two are told apart by the size of the change, so a grid of hovers over the symbol
maps its pins.

The output is the marker's own bounding-box centre, not the pointer position: the marker is drawn
at the pin, which makes it a better estimate than where the mouse happened to be.

    powershell -File dsn_learn_pins.ps1 -Path design.DSN -Center "-3.976,-1.5" -HalfW 0.8 -HalfH 0.5 -Out pins.json

Verify the result: draw a probe wire to each learned pin (scripts/dsn_draw_wires.ps1), save, and
read the wire endpoints back out of the file (`dsn_walk.py`). The file is the ground truth.
#>
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$Center,          # design inches, the instance's own anchor
    [double]$HalfW = 0.8, [double]$HalfH = 0.5,
    [double]$Step = 0.1, [double]$FineStep = 0.04, [double]$FineReach = 0.06,
    [int]$MinDiff = 12, [int]$MaxDiff = 400, [int]$MaxW = 44, [int]$MaxH = 30,
    [string]$Out = "",
    [double]$OriginX = 785, [double]$OriginY = 440, [double]$Scale = 100,
    [string]$Exe = 'C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE',
    [string]$Pwsh = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe',
    [int]$WaitSeconds = 20,
    [switch]$KeepOpen
)

Add-Type -AssemblyName System.Drawing
$sig = @'
using System;using System.Drawing;using System.Runtime.InteropServices;using System.Text;
public class LP {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
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
 public static Bitmap Grab(IntPtr h) {
   RECT r; GetWindowRect(h, out r); int w=r.Right-r.Left, ht=r.Bottom-r.Top;
   if (w<=0||ht<=0) return null;
   var bmp=new Bitmap(w,ht);
   using (var g=Graphics.FromImage(bmp)) { IntPtr hdc=g.GetHdc(); PrintWindow(h,hdc,2); g.ReleaseHdc(hdc); }
   return bmp;
 }
 public static int[] RectOf(IntPtr h) { RECT r; GetWindowRect(h,out r); return new int[]{r.Left,r.Top,r.Right-r.Left,r.Bottom-r.Top}; }
 public static int[] Diff(Bitmap a, Bitmap b, int cx, int cy, int rad) {
   int n=0,x0=int.MaxValue,y0=int.MaxValue,x1=-1,y1=-1;
   for (int y=Math.Max(0,cy-rad); y<=Math.Min(Math.Min(a.Height,b.Height)-1,cy+rad); y++)
     for (int x=Math.Max(0,cx-rad); x<=Math.Min(Math.Min(a.Width,b.Width)-1,cx+rad); x++) {
       Color p=a.GetPixel(x,y), q=b.GetPixel(x,y);
       if (p.R!=q.R||p.G!=q.G||p.B!=q.B) { n++; if(x<x0)x0=x; if(y<y0)y0=y; if(x>x1)x1=x; if(y>y1)y1=y; }
     }
   return new int[]{n,x0,y0,x1,y1};
 }
 public static void Top(IntPtr h) { keybd_event(0x12,0,0,IntPtr.Zero); keybd_event(0x12,0,2,IntPtr.Zero); SetWindowPos(h,(IntPtr)(-1),0,0,0,0,0x0003); BringWindowToTop(h); SetForegroundWindow(h); }
 public static string Text(IntPtr h) { var sb=new StringBuilder(512); GetWindowTextW(h,sb,sb.Capacity); return sb.ToString(); }
 public static string Cls(IntPtr h) { var sb=new StringBuilder(128); GetClassNameW(h,sb,sb.Capacity); return sb.ToString(); }
 public static int DismissNotice(uint want, int maxw) {
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
$pressed = [LP]::DismissNotice([uint32]$proc.Id, 700)
Start-Sleep -Milliseconds 800
[LP]::Top($main); Start-Sleep -Milliseconds 1200
$rect = [LP]::RectOf($main)
$ox = $rect[0] + $OriginX; $oy = $rect[1] + $OriginY
$c = $Center -split ','
$cxD = [double]$c[0]; $cyD = [double]$c[1]
Write-Output ("notice buttons pressed: {0}; window {1},{2}; origin {3},{4}; centre ({5},{6})" -f $pressed, $rect[0], $rect[1], $ox, $oy, $cxD, $cyD)

function To-Screen([double]$x, [double]$y) { @([int][Math]::Round($ox + $x*$Scale), [int][Math]::Round($oy - $y*$Scale)) }

[LP]::SetCursorPos(1200, 780) | Out-Null; Start-Sleep -Milliseconds 500
$base = [LP]::Grab($main)
if ($base -eq $null) { Write-Error "no bitmap"; exit 9 }

$markers = @()
$nScanned = 0
for ($dy = -$HalfH; $dy -le $HalfH + 1e-9; $dy += $Step) {
    for ($dx = -$HalfW; $dx -le $HalfW + 1e-9; $dx += $Step) {
        $sx = [int](To-Screen ($cxD + $dx) ($cyD + $dy))[0]
        $sy = [int](To-Screen ($cxD + $dx) ($cyD + $dy))[1]
        [LP]::SetCursorPos($sx, $sy) | Out-Null
        Start-Sleep -Milliseconds 260
        $shot = [LP]::Grab($main)
        if ($shot -eq $null) { continue }
        # a generous window, so the whole marker is inside the measurement
        $d = [LP]::Diff($shot, $base, ($sx - $rect[0]), ($sy - $rect[1]), 20)
        $shot.Dispose()
        $nScanned++
        if ($d[0] -lt $MinDiff -or $d[0] -gt $MaxDiff) { continue }
        $w = if ($d[3] -ge $d[1]) { $d[3]-$d[1]+1 } else { 0 }
        $h = if ($d[4] -ge $d[2]) { $d[4]-$d[2]+1 } else { 0 }
        if ($w -gt $MaxW -or $h -gt $MaxH) { continue }
        # the marker is drawn at the pin, so its centre - not the pointer - is the estimate
        $mx = ($d[1] + $d[3]) / 2.0 + $rect[0]
        $my = ($d[2] + $d[4]) / 2.0 + $rect[1]
        $markers += [pscustomobject]@{
            X = [Math]::Round(($mx - $ox) / $Scale, 3)
            Y = [Math]::Round(($oy - $my) / $Scale, 3)
            Diff = $d[0]; W = $w; H = $h
        }
    }
}
Write-Output ("scanned {0} points, {1} marker responses" -f $nScanned, $markers.Count)
$base.Dispose()

# cluster neighbouring responses: the same pin answers for a few pixel offsets
$clusters = @()
foreach ($m in ($markers | Sort-Object -Property Diff -Descending)) {
    $placed = $false
    foreach ($c in $clusters) {
        if ([Math]::Abs($m.X - $c.X) -le 0.06 -and [Math]::Abs($m.Y - $c.Y) -le 0.06) {
            $c.Members += $m; $placed = $true; break
        }
    }
    if (-not $placed) { $clusters += [pscustomobject]@{ X = $m.X; Y = $m.Y; Members = @($m) } }
}

$pins = @()
foreach ($c in $clusters) {
    $sx = 0.0; $sy = 0.0
    foreach ($m in $c.Members) { $sx += $m.X; $sy += $m.Y }
    $pins += [pscustomobject]@{
        x = [Math]::Round($sx / $c.Members.Count, 3)
        y = [Math]::Round($sy / $c.Members.Count, 3)
        hits = $c.Members.Count
        strongest = ($c.Members | Sort-Object -Property Diff -Descending | Select-Object -First 1).Diff
    }
}
$pins = $pins | Sort-Object -Property y, x

Write-Output "candidate pins (design inches, from the marker centre):"
foreach ($p in $pins) {
    Write-Output ("  ({0,7},{1,7})   {2,3} responses, strongest {3}" -f $p.x, $p.y, $p.hits, $p.strongest)
}
if ($Out -ne "") {
    $obj = [pscustomobject]@{ design = (Split-Path -Leaf $Path); center = $Center; pins = $pins }
    $obj | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Out -Encoding UTF8
    Write-Output "wrote $Out"
}
if (-not $KeepOpen) { Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force; Write-Output "closed Isis" }
