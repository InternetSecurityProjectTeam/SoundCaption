# SoundCaption 시연용 설치 + 실행 (PowerShell 5.1 기본 내장만 사용)
# 1) 이미 풀려 있으면 바로 실행
# 2) 아니면 zip 2개(또는 release_parts 조각)를 합쳐 SoundCaption 폴더로 풀고 실행
param([string]$Root)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$Root = (Resolve-Path $Root).Path
$dest = Join-Path $Root 'SoundCaption'
$py   = Join-Path $dest 'runtime\pythonw.exe'
$boot = Join-Path $dest 'launcher\boot.py'
$mark = Join-Path $dest 'models\home\panns_data\Cnn14_mAP=0.431.pth'

function Get-Zip([string]$name) {
    $z = Join-Path $Root $name
    if (Test-Path $z) { return @($z, $false) }
    $partDir = Join-Path $Root 'release_parts'
    $parts = @(Get-ChildItem -LiteralPath $partDir -Filter "$name.part*" -ErrorAction SilentlyContinue | Sort-Object Name)
    if ($parts.Count -eq 0) { throw "$name 또는 release_parts\$name.part* 를 찾지 못했어요." }
    Write-Host "  조각 $($parts.Count)개 합치는 중..."
    $tmp = Join-Path $Root ($name + '.joining')
    $out = [System.IO.File]::Create($tmp)
    try { foreach ($p in $parts) { $in = [System.IO.File]::OpenRead($p.FullName); try { $in.CopyTo($out) } finally { $in.Close() } } }
    finally { $out.Close() }
    return @($tmp, $true)
}

function Expand-ZipSafe([string]$zip) {
    $za = [System.IO.Compression.ZipFile]::OpenRead($zip)
    $n = 0; $skip = 0; $total = $za.Entries.Count
    try {
        foreach ($e in $za.Entries) {
            $n++
            if ($n % 2000 -eq 0) { Write-Host ("  {0} / {1}" -f $n, $total) }
            if ($e.FullName -like '*/PySide6/qml/*') { continue }      # 이 앱은 안 씀 (경로가 길어서 제외)
            $target = Join-Path $Root ($e.FullName -replace '/', '\')
            if ($e.FullName.EndsWith('/')) { [void][System.IO.Directory]::CreateDirectory($target); continue }
            try {
                [void][System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($target))
                [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, $target, $true)
            } catch { $skip++; Write-Host "  (건너뜀) $($e.FullName): $($_.Exception.Message)" }
        }
    } finally { $za.Dispose() }
    if ($skip -gt 0) { Write-Host "  건너뛴 파일 $skip 개 (폴더 경로가 너무 길면 생겨요. 바탕화면처럼 짧은 곳에서 다시 해 보세요)" }
}

if (-not ((Test-Path $py) -and (Test-Path $mark))) {
    Write-Host '처음 실행이라 프로그램을 준비해요. (몇 분 걸려요, 창을 닫지 마세요)'
    foreach ($name in 'SoundCaption_1_program.zip', 'SoundCaption_2_models.zip') {
        Write-Host "[$name]"
        $r = Get-Zip $name
        try { Expand-ZipSafe $r[0] } finally { if ($r[1]) { Remove-Item -LiteralPath $r[0] -Force -ErrorAction SilentlyContinue } }
    }
    if (-not ((Test-Path $py) -and (Test-Path $mark))) { throw '풀기가 끝났는데 실행 파일이나 모델이 없어요. 압축 파일이 다 받아졌는지 확인해 주세요.' }
    Write-Host '준비 완료!'
}
Write-Host 'SoundCaption 을 켜요. (모델을 올리느라 20초~1분 걸려요)'
Start-Process -FilePath $py -ArgumentList ('"' + $boot + '"') -WorkingDirectory $dest
