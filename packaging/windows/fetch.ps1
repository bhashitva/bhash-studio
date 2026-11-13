param([Parameter(Mandatory)][string]$Directory)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $Directory -Force | Out-Null
$temurin = 'https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.10%2B7'
$files = @{
    'python.exe' = 'https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe'
    'compiler.jar' = 'https://github.com/bhashitva/bhash/releases/download/bhash-0.25.0/bhash-compiler-0.25.0.jar'
    'java.zip' = "$temurin/OpenJDK21U-jdk_x64_windows_hotspot_21.0.10_7.zip"
    'java-source.tar.gz' = "$temurin/OpenJDK21U-jdk-sources_21.0.10_7.tar.gz"
}
foreach ($package in @(@('Send2Trash', '2.1.0'), @('pywin32', '312'))) {
    $metadata = & curl.exe -fsSL "https://pypi.org/pypi/$($package[0])/$($package[1])/json"
    if ($LASTEXITCODE) { throw "Could not resolve $($package[0])." }
    foreach ($file in (($metadata | ConvertFrom-Json).urls |
        Where-Object filename -Match '(none-any|cp31[1234]-cp31[1234]-win_amd64)\.whl$')) {
        $files[$file.filename] = $file.url
    }
}
foreach ($name in $files.Keys) {
    & curl.exe -fLSs --retry 2 $files[$name] -o (Join-Path $Directory $name)
    if ($LASTEXITCODE) { throw "Download failed: $name" }
}
