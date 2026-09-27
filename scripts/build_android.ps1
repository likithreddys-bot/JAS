# Builds the JAS Android app and, if a phone is plugged in with USB debugging on, installs it.
#
# The toolchain lives in C:\jas-tools deliberately: the Android SDK's own .bat scripts do not quote
# JAVA_HOME, so a space anywhere in the path ("jaya lakshmi") makes sdkmanager and friends fail with
# "'C:\Users\jaya' is not recognized". None of that is in git - it is 1.3 GB of machine-specific tools.

$ErrorActionPreference = 'Stop'

$tools = 'C:\jas-tools'
$env:JAVA_HOME = Join-Path $tools 'jdk\jdk-17.0.20.1+1'
$env:ANDROID_HOME = Join-Path $tools 'sdk'
$gradle = Join-Path $tools 'gradle\gradle-8.7\bin\gradle.bat'
$project = Join-Path $PSScriptRoot '..\android' | Resolve-Path
$apk = Join-Path $project 'app\build\outputs\apk\debug\app-debug.apk'

if (-not (Test-Path $env:JAVA_HOME)) { throw "No JDK at $env:JAVA_HOME" }
if (-not (Test-Path $gradle)) { throw "No Gradle at $gradle" }

& $gradle -p $project assembleDebug --console=plain
if ($LASTEXITCODE -ne 0) { throw 'The build failed - see above.' }

'{0:N1} MB  {1}' -f ((Get-Item $apk).Length / 1MB), $apk

# Install straight onto the phone when one is attached; otherwise copy the APK across yourself.
$adb = Join-Path $env:ANDROID_HOME 'platform-tools\adb.exe'
if (Test-Path $adb) {
    $devices = & $adb devices | Select-String -Pattern '\tdevice$'
    if ($devices) {
        'installing on the phone...'
        & $adb install -r $apk
    } else {
        'No phone attached. Copy the APK above onto the phone and open it there.'
    }
}
