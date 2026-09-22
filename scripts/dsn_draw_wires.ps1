<#
Draw wires in Isis from a list of pin coordinates, then save.

This is the route that works, after the file route was measured to fail. What it needs:

* the launch notice pressed away by message (`proteus_dismiss_notice.ps1`) - until that happens
  the main window is disabled and no click is accepted;
* the screen-to-design mapping. Scale is 100 px per design inch at the default zoom; the origin is
  the window position plus (785, 440) - measured by reading the status bar's pointer coordinates,
  not guessed. The window moves between runs (0,20) one time, (12,10) another, and the canvas can
  be scrolled, so the mapping is *checked* here rather than assumed: the script hovers a known pin
  and looks for Isis's hover marker (a small ~31x16 change; a part body instead lights up ~100x60),
  stepping around until it finds it, and applies that offset to every wire;
* a click on the pin, then a click on the far pin. Both are plain clicks - Isis starts a wire from
  any mode when the pointer is on a connection point, and the cursor turns into a pencil. A click
  that misses cancels the wire, which is how earlier attempts lost every wire silently.

    powershell -File dsn_draw_wires.ps1 -Path design.DSN -WireList wires.txt

Each line of `wires.txt` is one wire: `x1,y1,x2,y2` in design inches, the two ends being pin
positions. The caller proves the result by counting objects in the saved file
(`scripts/dsn_rec_diff.py`, `_re/scratch/count_objs.py`) and by a save round trip.
#>
param(
    [Parameter(Mandatory=$true)][string]$Path,
    [Parameter(Mandatory=$true)][string]$WireList,
    [string]$Calib = "",                       # a known pin, "x,y"; defaults to the first wire's first end
    [int]$OffsetX = 0, [int]$OffsetY = 0,      # nudge if the mapping is off; see -CheckFirst
    [switch]$CheckFirst,                       # require the rubber band after the first click of each wire
    [int]$JunctionX = 30, [int]$JunctionY = 170,   # the 连接点 tool, named from the status bar
    [double]$OriginX = 785, [double]$OriginY = 440, [double]$Scale = 100,
    [string]$Exe = 'C:\Program Files (x86)\Labcenter Electronics\Proteus 7 Professional\BIN\ISIS.EXE',
    [string]$Pwsh = 'C:\Users\yangf\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe',
    [string]$Scripts = 'C:\Users\yangf\Desktop\计算机应用课程设计\_re\gh\windows-gui-vision\scripts',
    [int]$WaitSeconds = 20,
    [switch]$KeepOpen
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$sig = @'
using System;using System.Drawing;using System.Runtime.InteropServices;
public class DW {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint f);
 [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern void keybd_event(byte vk, byte scan, uint f, IntPtr e);
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, IntPtr e);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, EnumProc cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr h, System.Text.StringBuilder s, int n);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr h, System.Text.StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool IsWindowEnabled(IntPtr h);
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
 public static void Click() { mouse_event(0x0002,0,0,0,IntPtr.Zero); System.Threading.Thread.Sleep(150); mouse_event(0x0004,0,0,0,IntPtr.Zero); }
 public static void Top(IntPtr h) { keybd_event(0x12,0,0,IntPtr.Zero); keybd_event(0x12,0,2,IntPtr.Zero); SetWindowPos(h,(IntPtr)(-1),0,0,0,0,0x0003); BringWindowToTop(h); SetForegroundWindow(h); }
 public static string Text(IntPtr h) { var sb=new System.Text.StringBuilder(512); GetWindowTextW(h,sb,sb.Capacity); return sb.ToString(); }
 public static string Cls(IntPtr h) { var sb=new System.Text.StringBuilder(128); GetClassNameW(h,sb,sb.Capacity); return sb.ToString(); }
 public static IntPtr Big(uint want, int minw) {
   IntPtr best=IntPtr.Zero; int bw=0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid!=want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     int w=r.Right-r.Left;
     if (w>=minw && w>bw) { bw=w; best=h; }
     return true;
   }, IntPtr.Zero);
   return best;
 }
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
 public static int PressCancel(uint want, int maxw) {
   int done=0;
   EnumWindows(delegate(IntPtr h, IntPtr l) {
     uint pid; GetWindowThreadProcessId(h, out pid);
     if (pid!=want || !IsWindowVisible(h)) return true;
     RECT r; GetWindowRect(h, out r);
     if (r.Right-r.Left >= maxw) return true;
     EnumChildWindows(h, delegate(IntPtr c, IntPtr l2) {
       if (Cls(c) != "Button" || !IsWindowVisible(c)) return true;
       string t = Text(c);
       if (t.StartsWith("\u53d6\u6d88") || t.StartsWith("Cancel") || t.StartsWith("Close") || t.StartsWith("\u5173\u95ed")) {
         PostMessage(h, 0x0111, (IntPtr)GetDlgCtrlID(c), c);
         done++;
       }
       return true;
     }, IntPtr.Zero);
     return true;
   }, IntPtr.Zero);
   return done;
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
       if (t.StartsWith("\u786e\u5b9a") || t.StartsWith("OK")) {
         PostMessage(h, 0x0111, (IntPtr)GetDlgCtrlID(c), c);
         done++;
       }
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

$wires = @()
foreach ($line in (Get-Content -LiteralPath $WireList)) {
    $line = $line.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { continue }
    # A wire is a sequence of points, so a routed one can bend around a symbol:
    #   "x1,y1,x2,y2"                 two points
    #   "x1,y1;x2,y2;x3,y3"           a polyline, clicked point by point
    $pts = @()
    if ($line.Contains(';')) {
        foreach ($p in ($line -split ';')) {
            $p = $p.Trim()
            # a leading @ marks a point on an existing wire: place a junction there first, so the
            # new wire starts from the node - the only way to join three pins to one net
            $isTap = $p.StartsWith('@')
            if ($isTap) { $p = $p.Substring(1) }
            $v = $p -split ','
            if ($v.Count -ne 2) { Write-Error "bad point in '$line'"; exit 3 }
            $pts += ,@([double]$v[0], [double]$v[1], $isTap)
        }
    } else {
        $v = $line -split ','
        if ($v.Count -ne 4) { Write-Error "bad wire line: $line"; exit 3 }
        $pts += ,@([double]$v[0], [double]$v[1], $false)
        $pts += ,@([double]$v[2], [double]$v[3], $false)
    }
    $wires += ,$pts
}
if ($wires.Count -eq 0) { Write-Error "no wires in $WireList"; exit 3 }
if ($Calib -eq "") { $Calib = "$($wires[0][0][0]),$($wires[0][0][1])" }
$cp = $Calib -split ','

Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2
Start-Process -FilePath $Exe -ArgumentList ('"' + $Path + '"') | Out-Null
$proc = $null
for ($i = 0; $i -lt ($WaitSeconds + 20) -and -not $proc; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-Process ISIS -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne "" } |
            Sort-Object -Property MainWindowTitle | Select-Object -First 1
}
if (-not $proc) { Write-Error "Isis did not open a window for $Path"; exit 9 }
$proc.Refresh(); $main = $proc.MainWindowHandle
$pressed = [DW]::DismissNotice([uint32]$proc.Id, 700)
Write-Output "pressed $pressed OK button(s) on the launch notice"
Start-Sleep -Milliseconds 800
[DW]::Top($main); Start-Sleep -Milliseconds 1200
$rect = [DW]::RectOf($main)
$ox = $rect[0] + $OriginX
$oy = $rect[1] + $OriginY
Write-Output ("window at {0},{1}; design origin at {2},{3}, {4} px per inch" -f $rect[0], $rect[1], $ox, $oy, $Scale)

function To-Screen([double]$x, [double]$y) { @([int][Math]::Round($ox + $x*$Scale), [int][Math]::Round($oy - $y*$Scale)) }

# The one-click helper, written out as its own file so it can be run as a child process: input
# injected from this script's own process does not reach Isis, a child process's does. The file
# lives in %TEMP% so its path is ASCII (a non-ASCII path is read as ANSI by Windows PowerShell).
$Helper = Join-Path $env:TEMP 'isis_click_helper.ps1'
$member = '[DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y); [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, System.IntPtr e);'
$helperLines = @(
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
Set-Content -LiteralPath $Helper -Value $helperLines -Encoding ASCII

# No automatic calibration. A hover-marker scan was tried and it picks the part body instead of
# the pin about half the time, which silently clicks the wrong pixel. The measured origin works;
# if a run misses, -CheckFirst says so and -OffsetX/-OffsetY nudge it by hand.
[DW]::SetCursorPos(1150, 780) | Out-Null; Start-Sleep -Milliseconds 500
$adjX = $OffsetX; $adjY = $OffsetY
Write-Output ("using offset {0},{1}" -f $adjX, $adjY)

function Click-Point([int]$sx, [int]$sy) {
    # park, let the pencil come up, click. The stepped approach that was tried first did not start
    # a wire at all on this build; the plain hover-then-click is the one that reproduces the
    # hand-drawn wire.
    # The move and the click are sent from a *child* process. That is not cosmetic: input injected
    # from this script's own process did not reach Isis at all, while the same calls from a separate
    # pwsh process did - every in-process attempt produced no wire, the child-process one reproduced
    # the hand-drawn wire byte for byte.
    Invoke-ChildInput $sx $sy -Click
    Start-Sleep -Milliseconds 1000
}

function Invoke-ChildInput([int]$sx, [int]$sy, [switch]$Click) {
    $args2 = @('-File', $Helper, '-X', $sx, '-Y', $sy)
    if ($Click) { $args2 += '-Click' }
    & $Pwsh @args2 | Out-Null
}

function Clear-Dialogs([int]$procId) {
    # A stray dialog (a double-click on a part opens its properties) swallows every later click and
    # looks like "the click did nothing". Close it before it can do that, and say so.
    $left = [DW]::CountSmall([uint32]$procId, 700)
    if ($left -gt 0) {
        # press Cancel by message - the same trick as the launch notice, and Cancel rather than OK
        # so a dialog that appeared by accident cannot change the part it belongs to
        $pressed = [DW]::PressCancel([uint32]$procId, 700)
        Start-Sleep -Milliseconds 600
        if ([DW]::CountSmall([uint32]$procId, 700) -gt 0) {
            [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
            Start-Sleep -Milliseconds 600
        }
        $left2 = [DW]::CountSmall([uint32]$procId, 700)
        Write-Output ("  dialog guard: {0} small window(s), pressed cancel on {1} -> {2} left" -f $left, $pressed, $left2)
    }
}

function Count-Wires([string]$path) {
    # A wire object is the 8 byte prefix followed by 02 7f "WIRE" 00. The prefix has to be checked
    # byte by byte: the same marker text turns up inside device definitions, and a plain text match
    # counted those too (it reported ten wires where the file held eight).
    $b = [System.IO.File]::ReadAllBytes($path)
    $n = 0
    for ($i = 8; $i -lt $b.Length - 6; $i++) {
        if ($b[$i] -ne 0x02 -or $b[$i + 1] -ne 0x7f -or $b[$i + 2] -ne 0x57 -or
            $b[$i + 3] -ne 0x49 -or $b[$i + 4] -ne 0x52 -or $b[$i + 5] -ne 0x45 -or
            $b[$i + 6] -ne 0x00) { continue }
        $ok = $true
        for ($k = 0; $k -lt 8; $k++) {
            if ($b[$i - 8 + $k] -ne @(0xff, 0xff, 0xff, 0x00, 0xff, 0xff, 0xff, 0x00)[$k]) { $ok = $false; break }
        }
        if ($ok) { $n++ }
    }
    return $n
}

$n = 0
foreach ($w in $wires) {
    $n++
    $a = To-Screen $w[0][0] $w[0][1]
    $b = To-Screen $w[-1][0] $w[-1][1]
    $ax = $a[0] + $adjX; $ay = $a[1] + $adjY
    $bx = $b[0] + $adjX; $by = $b[1] + $adjY
    $txt = ($w | ForEach-Object { "({0},{1})" -f $_[0], $_[1] }) -join " "
    Write-Output ("wire {0}: {1}  screen ({2},{3}) -> ({4},{5})" -f $n, $txt, $ax, $ay, $bx, $by)
    # clear any selection first: with a part selected (it draws red) Isis does not start wires at
    # all, and a stray dialog would swallow the clicks the same way. ESC handles both.
    [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
    Start-Sleep -Milliseconds 400
    Clear-Dialogs $proc.Id
    if ($w[0][2]) {
        # The first point is on an existing wire, not on a pin. No tool has to be selected for
        # this: clicking a wire *is* the tap gesture - Isis splits the wire, leaves a node at the
        # click and starts a new wire from it. An earlier version pressed the 连接点 button first,
        # and with that mode active a click on a wire did nothing at all.
        Write-Output ("  tap: ({0},{1}) is on an existing wire, the node comes from clicking it" -f $w[0][0], $w[0][1])
    }
    Click-Point $ax $ay
    if ($CheckFirst) {
        # the baseline is taken here rather than before the loop: a capture in the middle of a wire
        # cancels it, so it is only taken when this diagnostic is asked for
        if ($null -eq $base) {
            [DW]::SetCursorPos(1200, 780) | Out-Null; Start-Sleep -Milliseconds 900
            $base = [DW]::Grab($main)
        }
        # a started wire is a thin line from the pin to wherever the pointer now is
        [DW]::SetCursorPos($ax + 40, $ay) | Out-Null; Start-Sleep -Milliseconds 500
        $shot = [DW]::Grab($main)
        $d = [DW]::Diff($shot, $base, ($ax + 40 - $rect[0]), ($ay - $rect[1]), 70)
        $shot.Dispose()
        $wd = if ($d[3] -ge $d[1]) { $d[3]-$d[1]+1 } else { 0 }
        $ht = if ($d[4] -ge $d[2]) { $d[4]-$d[2]+1 } else { 0 }
        $ok = ($d[0] -gt 25 -and $ht -le 10 -and $wd -ge 20)
        Write-Output ("  first click: diff {0} {1}x{2} -> {3}" -f $d[0], $wd, $ht, $(if ($ok) { "wire started" } else { "NO WIRE (pin missed) - stopping" }))
        if (-not $ok) {
            [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
            Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force
            exit 4
        }
        [DW]::SetCursorPos($ax, $ay) | Out-Null; Start-Sleep -Milliseconds 300
    }
    # the bends, then the far end
    for ($k = 1; $k -lt $w.Count; $k++) {
        $mid = To-Screen $w[$k][0] $w[$k][1]
        Click-Point ($mid[0] + $adjX) ($mid[1] + $adjY)
    }
    Clear-Dialogs $proc.Id
    Start-Sleep -Milliseconds 300
}
[DW]::SetCursorPos(1150, 150) | Out-Null; Start-Sleep -Milliseconds 400

$before = (Get-Item -LiteralPath $Path).Length
$wiresBefore = Count-Wires $Path
[System.Windows.Forms.SendKeys]::SendWait('^s')
Start-Sleep -Seconds 4
$after = (Get-Item -LiteralPath $Path).Length
$wiresAfter = Count-Wires $Path
$drew = $wiresAfter - $wiresBefore
Write-Output ("{0} bytes -> {1} bytes after {2} wire(s); wires in the file {3} -> {4} (drew {5})" -f $before, $after, $wires.Count, $wiresBefore, $wiresAfter, $drew)
if (($wiresAfter - $wiresBefore) -lt $wires.Count) {
    Write-Output "WARNING: fewer wires appeared than were asked for - some clicks missed their pin"
}
if (-not $KeepOpen) {
    Get-Process ISIS -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Output "closed Isis"
}
