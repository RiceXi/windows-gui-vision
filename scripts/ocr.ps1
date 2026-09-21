param(
    [Parameter(Mandatory=$true)][string]$Path,
    [string]$Lang = "zh-Hans-CN",
    [switch]$NoBoxes
)

Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.IRandomAccessStream, Windows.Storage, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics, ContentType=WindowsRuntime] | Out-Null
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    [void]$netTask.Wait(-1)
    $netTask.Result
}

$resolved = (Resolve-Path -LiteralPath $Path).Path
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($resolved)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])

$language = New-Object Windows.Globalization.Language $Lang
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($language)
if (-not $engine) { $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages() }
if (-not $engine) { Write-Error "No OCR engine"; exit 4 }

$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
Write-Output ("IMAGE {0} ({1}x{2})" -f $resolved, $bitmap.PixelWidth, $bitmap.PixelHeight)
foreach ($line in $result.Lines) {
    $text = ($line.Words | ForEach-Object { $_.Text }) -join ''
    if (-not $text) { continue }
    if ($NoBoxes) {
        Write-Output $text
        continue
    }
    try {
        $first = @($line.Words)[0]
        $last = @($line.Words)[@($line.Words).Count - 1]
        $x = [int][math]::Round([double]$first.BoundingRect.X)
        $y = [int][math]::Round([double]$first.BoundingRect.Y)
        $x2 = [int][math]::Round([double]$last.BoundingRect.X + [double]$last.BoundingRect.Width)
        $y2 = [int][math]::Round([double]$last.BoundingRect.Y + [double]$last.BoundingRect.Height)
        Write-Output ("[{0},{1}-{2},{3}] {4}" -f $x, $y, $x2, $y2, $text)
    } catch {
        Write-Output ("[?,?] {0}" -f $text)
    }
}
