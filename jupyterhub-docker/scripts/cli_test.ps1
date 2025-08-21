<#
Simple CLI test script for JELAI Admin Dashboard

Usage:
  - Set env var JELAI_TOKEN to a valid JupyterHub admin token, or paste it when prompted.
  - Optionally set ADMIN_DASHBOARD_URL (default http://localhost:8006)

Examples:
  $env:JELAI_TOKEN = '<ADMIN_TOKEN>'
  pwsh ./scripts/cli_test.ps1
#>

$token = $env:JELAI_TOKEN
if (-not $token) {
    Write-Host "JELAI_TOKEN not set. Please paste an admin token (will not be stored):"
    $secure = Read-Host -AsSecureString
    $token = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
}

$base = $env:ADMIN_DASHBOARD_URL
if (-not $base) { $base = 'http://localhost:8006' }

function Invoke-JelaiApi {
    param(
        [string]$Method = 'GET',
        [string]$Path = '/',
        $Body = $null,
        [string]$ContentType = 'application/json'
    )

    $headers = @{ Authorization = "token $token" }
    $uri = "$base/api/proxy$Path"

    Write-Host "=> $Method $uri" -ForegroundColor Cyan

    try {
        if ($Method -in @('POST','PUT') -and $ContentType -eq 'application/json') {
            $bodyJson = $Body | ConvertTo-Json -Depth 5
            return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body $bodyJson -ContentType $ContentType
        }
        elseif ($Method -in @('POST','PUT') -and $ContentType -eq 'application/x-www-form-urlencoded') {
            return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers -Body $Body -ContentType $ContentType
        }
        else {
            return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers
        }
    }
    catch {
        Write-Host "Request failed: $($_.Exception.Message)" -ForegroundColor Red
        if ($_.Exception.Response) {
            try { $_.Exception.Response | Get-Content | ConvertFrom-Json | ConvertTo-Json -Depth 5 } catch { $_.Exception.Response | Get-Content }
        }
    }
}

# 1) List courses
$courses = Invoke-JelaiApi -Method GET -Path '/courses'
Write-Host "Courses:"; $courses | ConvertTo-Json -Depth 4

# 2) Create a course
$ts = [DateTime]::UtcNow.ToString('yyyyMMddHHmmss')
$newTitle = "CLI-Test-Course-$ts"
$createBody = @{ title = $newTitle; description = "Created by CLI test at $ts" }
$created = Invoke-JelaiApi -Method POST -Path '/courses' -Body $createBody -ContentType 'application/json'
Write-Host "Created:"; $created | ConvertTo-Json -Depth 5

if ($created -and $created.id) {
    $id = $created.id
    # 3) Assign teacher (form)
    $form = @{ teacher = $env:USERNAME -or 'cli_admin' }
    $assign = Invoke-JelaiApi -Method POST -Path "/courses/$id/assign-teacher" -Body $form -ContentType 'application/x-www-form-urlencoded'
    Write-Host "Assign response:"; $assign | ConvertTo-Json -Depth 5

    # 4) Enroll a student (form)
    $form2 = @{ student = "cli_student_$ts" }
    $enroll = Invoke-JelaiApi -Method POST -Path "/courses/$id/enroll" -Body $form2 -ContentType 'application/x-www-form-urlencoded'
    Write-Host "Enroll response:"; $enroll | ConvertTo-Json -Depth 5

    # 5) Confirm course
    $confirm = Invoke-JelaiApi -Method GET -Path "/courses/$id"
    Write-Host "Course state:"; $confirm | ConvertTo-Json -Depth 6
}
else {
    Write-Host "Course creation failed; aborting assign/enroll tests." -ForegroundColor Yellow
}
