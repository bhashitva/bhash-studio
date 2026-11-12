[CmdletBinding()]
param(
    [string]$InstallRoot = "$env:LOCALAPPDATA\Programs\Bhash Yantra",
    [switch]$NoShortcut,
    [switch]$SkipDebugTools,
    [switch]$InstallAndroidPackages
)

$ErrorActionPreference = 'Stop'
$payload = Join-Path $PSScriptRoot 'payload'
$lock = Get-Content (Join-Path $PSScriptRoot 'payload.json') -Raw | ConvertFrom-Json
function Confirm-File($name) {
    $file = Join-Path $payload $name
    if ((Get-FileHash -LiteralPath $file).Hash -ne $lock.$name) {
        throw "Invalid payload checksum: $name"
    }
    $file
}
function Find-Tool($candidates, $check) {
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if ((Test-Path -LiteralPath $candidate -PathType Leaf) -and (& $check $candidate)) {
            return $candidate
        }
    }
}
function Python-Version($path) {
    try {
        $result = & $path -I -c 'import sys,struct,tkinter; t=tkinter.Tcl(); print(sys.version_info.minor if sys.version_info.major==3 and struct.calcsize(chr(80))==8 else 0)' 2>$null
        if ($LASTEXITCODE -eq 0 -and "$result" -match '^(11|12|13|14)$' -and
            (Test-Path -LiteralPath (Join-Path (Split-Path $path) 'pythonw.exe'))) { return "$result" }
    } catch {}
}
function Java21($path) {
    if (!(Test-Path -LiteralPath (Join-Path (Split-Path $path) 'javac.exe'))) { return $false }
    try {
        $ErrorActionPreference = 'Continue'
        $result = & $path -version 2>&1
        return $LASTEXITCODE -eq 0 -and ($result -join ' ') -match 'version "21(?:[.+"]|$)'
    } catch {
        return $false
    }
}
function Install-Zip($zip, $target, $marker) {
    if (Test-Path -LiteralPath (Join-Path $target $marker) -PathType Leaf) { return }
    $stage = Join-Path (Split-Path $target) ([guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $stage -Force | Out-Null
    & tar.exe -xf $zip -C $stage
    if ($LASTEXITCODE) { throw "Could not extract $zip. Staging folder: $stage" }
    $folder = Get-ChildItem -LiteralPath $stage -Directory | Select-Object -First 1
    if (!$folder -or !(Test-Path -LiteralPath (Join-Path $folder.FullName $marker) -PathType Leaf)) {
        throw "Unexpected archive layout: $zip"
    }
    if (Test-Path -LiteralPath $target) { throw "Incomplete installation at $target" }
    Move-Item -LiteralPath $folder.FullName -Destination $target
    Remove-Item -LiteralPath $stage
}

if ([Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString() -ne 'X64') {
    throw 'This preview installer requires Windows x64.'
}
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
$managed = Join-Path $InstallRoot 'tools'
New-Item -ItemType Directory -Path $managed -Force | Out-Null

$pythonCandidates = @()
$launcher = Get-Command py.exe -ErrorAction SilentlyContinue
if ($launcher) {
    $pythonCandidates += & $launcher.Source -0p | ForEach-Object {
        if ($_ -match '([A-Za-z]:\\.*\\python\.exe)\s*$') { $Matches[1] }
    }
}
foreach ($hive in @('HKCU:', 'HKLM:')) {
    foreach ($minor in 11..14) {
        $key = Get-Item -LiteralPath "$hive\Software\Python\PythonCore\3.$minor\InstallPath" -ErrorAction SilentlyContinue
        if ($key) { $pythonCandidates += $key.GetValue('ExecutablePath') }
    }
}
$privatePython = Join-Path $managed 'python-3.13.12'
$python = Find-Tool ($pythonCandidates + @((Get-Command python.exe -All -ErrorAction SilentlyContinue).Source |
    Where-Object { $_ -notlike '*\Microsoft\WindowsApps\*' }) + @("$privatePython\python.exe")) {
    param($path) [bool](Python-Version $path)
}
if (!$python) {
    $installer = Confirm-File 'python.exe'
    $process = Start-Process -FilePath $installer -WindowStyle Hidden -Wait -PassThru -ArgumentList @(
        '/quiet', 'InstallAllUsers=0', "TargetDir=`"$privatePython`"", 'Include_launcher=0',
        'Include_tcltk=1', 'Include_pip=0', 'Include_test=0', 'Include_doc=0',
        'Shortcuts=0', 'AssociateFiles=0', 'PrependPath=0'
    )
    if ($process.ExitCode -ne 0) { throw "Python setup returned $($process.ExitCode)." }
    $python = "$privatePython\python.exe"
    if (!(Python-Version $python)) { throw 'Installed Python did not pass the Tk check.' }
    Write-Host "Installed Python: $python"
} else { Write-Host "Reusing Python: $python" }
$minor = Python-Version $python

$jdk = Join-Path $managed 'temurin-21.0.10'
$java = Find-Tool (@(
    $(if ($env:JAVA_HOME) { "$env:JAVA_HOME\bin\java.exe" }),
    "$env:ProgramFiles\Android\Android Studio\jbr\bin\java.exe",
    "$jdk\bin\java.exe"
) + @((Get-Command java.exe -All -ErrorAction SilentlyContinue).Source) +
    @(Get-ChildItem "$env:USERPROFILE\.jdks\*\bin\java.exe","$env:ProgramFiles\Eclipse Adoptium\*\bin\java.exe" -ErrorAction SilentlyContinue |
      ForEach-Object FullName)) { param($path) Java21 $path }
if (!$java) {
    Install-Zip (Confirm-File 'java.zip') $jdk 'bin\java.exe'
    $java = "$jdk\bin\java.exe"
    if (!(Java21 $java)) { throw 'Installed JDK did not pass the Java 21 check.' }
    Write-Host "Installed Java: $java"
} else { Write-Host "Reusing Java: $java" }

$llvm = Join-Path $managed 'llvm-mingw-20240619'
$clang = Find-Tool @((Get-Command clang.exe -ErrorAction SilentlyContinue).Source, "$llvm\bin\clang.exe") {
    param($path)
    try { (& $path --version 2>$null | Out-String) -match '(?m)^Target: x86_64-.*-windows-gnu' -and
        (Test-Path -LiteralPath (Join-Path (Split-Path $path) 'ld.lld.exe')) } catch { $false }
}
$debugger = Find-Tool @($env:BHASH_LLDB_DAP, (Get-Command lldb-dap.exe -ErrorAction SilentlyContinue).Source,
    "$llvm\bin\lldb-dap.exe") {
    param($path)
    try { $null = & $path --help 2>$null; $LASTEXITCODE -eq 0 } catch { $false }
}
if (!$SkipDebugTools -and (!$clang -or !$debugger)) {
    try {
        $archive = Join-Path $managed 'llvm-mingw-download.zip'
        $url = 'https://github.com/mstorsjo/llvm-mingw/releases/download/20240619/llvm-mingw-20240619-ucrt-x86_64.zip'
        if (!(Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive).Hash -ne $lock.llvm) {
            & curl.exe -fLSs --max-time 300 $url -o $archive
            if ($LASTEXITCODE -or (Get-FileHash -LiteralPath $archive).Hash -ne $lock.llvm) {
                throw 'LLVM-MinGW download failed verification.'
            }
        }
        Install-Zip $archive $llvm 'bin\lldb-dap.exe'
        if (!$clang) { $clang = "$llvm\bin\clang.exe" }
        if (!$debugger) { $debugger = "$llvm\bin\lldb-dap.exe" }
        Remove-Item -LiteralPath $archive
    } catch { Write-Warning "Native debug setup incomplete: $_" }
}
if ($clang) { Write-Host "Using Clang: $clang" }
if ($debugger) { Write-Host "Using LLDB: $debugger" }

$app = Join-Path $InstallRoot "app-$($lock.app)-cp3$minor"
New-Item -ItemType Directory -Path $app -Force | Out-Null
$archives = @((Confirm-File 'app.zip'))
$reusedDependencies = $false
try {
    & $python -c 'from send2trash.win.modern import send2trash' 2>$null
    $reusedDependencies = $LASTEXITCODE -eq 0
} catch {}
if (!$reusedDependencies) {
    $archives += Confirm-File 'send2trash-2.1.0-py3-none-any.whl'
    $archives += Confirm-File "pywin32-312-cp3$minor-cp3$minor-win_amd64.whl"
}
foreach ($archive in $archives) {
    & $python -I -m zipfile -e $archive $app
    if ($LASTEXITCODE) { throw "Could not install $archive." }
}
$compiler = Find-Tool @($env:BHASH_COMPILER_JAR, (Join-Path $managed 'bhash-compiler-0.25.0.jar')) {
    param($path) (Get-FileHash -LiteralPath $path).Hash -eq $lock.'compiler.jar'
}
if (!$compiler) { $compiler = Join-Path $managed 'bhash-compiler-0.25.0.jar' }
if (!(Test-Path -LiteralPath $compiler) -or (Get-FileHash -LiteralPath $compiler).Hash -ne $lock.'compiler.jar') {
    Copy-Item -LiteralPath (Confirm-File 'compiler.jar') -Destination $compiler -Force
} else { Write-Host "Reusing Bhash compiler: $compiler" }

$sdk = @($env:ANDROID_HOME, $env:ANDROID_SDK_ROOT, "$env:LOCALAPPDATA\Android\Sdk") |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Container) } | Select-Object -First 1
$androidPackages = [ordered]@{
    'platform-tools' = 'platform-tools\adb.exe'
    'platforms;android-36' = 'platforms\android-36\android.jar'
    'build-tools;35.0.0' = 'build-tools\35.0.0\aapt2.exe'
    'ndk;28.2.13676358' = 'ndk\28.2.13676358\source.properties'
}
$missing = @($androidPackages.Keys | Where-Object {
    !$sdk -or !(Test-Path -LiteralPath (Join-Path $sdk $androidPackages[$_]) -PathType Leaf)
})
if ($missing.Count -and $InstallAndroidPackages -and $sdk) {
    $sdkmanager = Get-ChildItem "$sdk\cmdline-tools\*\bin\sdkmanager.bat" -ErrorAction SilentlyContinue |
        Sort-Object { $_.FullName -notlike '*\latest\*' } | Select-Object -First 1
    if ($sdkmanager) {
        $env:JAVA_HOME = Split-Path (Split-Path $java)
        & $sdkmanager.FullName "--sdk_root=$sdk" --install @missing
        if ($LASTEXITCODE -ne 0) { Write-Warning "Google sdkmanager returned $LASTEXITCODE." }
        $missing = @($missing | Where-Object {
            !(Test-Path -LiteralPath (Join-Path $sdk $androidPackages[$_]) -PathType Leaf)
        })
    }
}
if ($missing.Count) {
    Write-Warning "Android tools missing: $($missing -join ', '). Install from https://developer.android.com/studio"
} else { Write-Host "Reusing Android SDK: $sdk" }

$config = @{
    python = $python
    compiler = $compiler; java = $java; sdk = [string]$sdk; debugger = [string]$debugger
    clangBin = $(if ($clang) { Split-Path $clang } else { '' })
} | ConvertTo-Json
[IO.File]::WriteAllText((Join-Path $app 'installed-tools.json'), $config, [Text.UTF8Encoding]::new($false))
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.txt') -Destination $InstallRoot -Force
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
$arguments = '"' + (Join-Path $app 'Launch.py') + '"'
if (!$NoShortcut) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Programs')) 'Bhash Yantra.lnk'))
    $link.TargetPath = $pythonw
    $link.Arguments = $arguments
    $link.WorkingDirectory = $app
    $link.Save()
}
Write-Host "Bhash Yantra installed. Launch: `"$pythonw`" $arguments"
