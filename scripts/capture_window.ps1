param(
    [Parameter(Mandatory=$true)][string]$OutPath,
    [string]$TitlePattern = "*",
    [int]$ProcessId = 0,
    [int]$WaitMs = 400,
    [switch]$ClientOnly
)

Add-Type -AssemblyName System.Drawing

$sig = @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public class WinCap {
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr hwnd, IntPtr hdcBlt, uint nFlags);

    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool GetClientRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder text, int count);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left; public int Top; public int Right; public int Bottom; }
}
'@

if (-not ("WinCap" -as [type])) {
    Add-Type -TypeDefinition $sig -ReferencedAssemblies System.Drawing
}

function Get-CandidateWindows {
    $list = New-Object System.Collections.ArrayList
    $callback = [WinCap+EnumWindowsProc]{
        param($hWnd, $lParam)
        if ([WinCap]::IsWindowVisible($hWnd)) {
            $sb = New-Object System.Text.StringBuilder 512
            [void][WinCap]::GetWindowText($hWnd, $sb, $sb.Capacity)
            $title = $sb.ToString()
            $pid2 = 0
            [void][WinCap]::GetWindowThreadProcessId($hWnd, [ref]$pid2)
            if ($title) {
                [void]$list.Add([pscustomobject]@{ Handle = $hWnd; Title = $title; Pid = $pid2 })
            }
        }
        return $true
    }
    [void][WinCap]::EnumWindows($callback, [IntPtr]::Zero)
    return $list
}

$windows = Get-CandidateWindows
$match = $null
if ($ProcessId -gt 0) {
    $match = $windows | Where-Object { $_.Pid -eq $ProcessId } |
        Sort-Object { $_.Title.Length } -Descending | Select-Object -First 1
}
if (-not $match) {
    $match = $windows | Where-Object { $_.Title -like $TitlePattern } |
        Sort-Object { $_.Title.Length } -Descending | Select-Object -First 1
}
if (-not $match) {
    Write-Error "No window matched. Available windows:"
    $windows | Sort-Object Title | ForEach-Object { Write-Error ("  [{0}] {1}" -f $_.Pid, $_.Title) }
    exit 2
}

[void][WinCap]::SetForegroundWindow($match.Handle)
Start-Sleep -Milliseconds $WaitMs

$rect = New-Object WinCap+RECT
if ($ClientOnly) {
    [void][WinCap]::GetClientRect($match.Handle, [ref]$rect)
} else {
    [void][WinCap]::GetWindowRect($match.Handle, [ref]$rect)
}
$width = $rect.Right - $rect.Left
$height = $rect.Bottom - $rect.Top
if ($width -le 0 -or $height -le 0) {
    Write-Error "Bad window size ${width}x${height} for '$($match.Title)'"
    exit 3
}

$bmp = New-Object System.Drawing.Bitmap $width, $height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $gfx.GetHdc()
$ok = [WinCap]::PrintWindow($match.Handle, $hdc, 2)
$gfx.ReleaseHdc($hdc)
$gfx.Dispose()

$dir = Split-Path -Parent $OutPath
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

Write-Output ("OK pid={0} size={1}x{2} title='{3}' -> {4}" -f $match.Pid, $width, $height, $match.Title, $OutPath)
