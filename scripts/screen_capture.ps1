param(
    [Parameter(Mandatory=$true)][string]$OutPath,
    [int]$X = 0,
    [int]$Y = 0,
    [int]$Width = 0,
    [int]$Height = 0,
    [int]$DelayMs = 300
)

Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms

Start-Sleep -Milliseconds $DelayMs

$bounds = [System.Windows.Forms.SystemInformation]::VirtualScreen
if ($Width -le 0)  { $Width  = $bounds.Width }
if ($Height -le 0) { $Height = $bounds.Height }
if ($X -lt 0) { $X = 0 }
if ($Y -lt 0) { $Y = 0 }

$bmp = New-Object System.Drawing.Bitmap $Width, $Height
$gfx = [System.Drawing.Graphics]::FromImage($bmp)
$gfx.CopyFromScreen($bounds.X + $X, $bounds.Y + $Y, 0, 0, (New-Object System.Drawing.Size $Width, $Height))
$gfx.Dispose()

$dir = Split-Path -Parent $OutPath
if ($dir -and -not (Test-Path -LiteralPath $dir)) {
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
}
$bmp.Save($OutPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()

Write-Output ("OK screen {0}x{1} at ({2},{3}) -> {4}" -f $Width, $Height, $X, $Y, $OutPath)
