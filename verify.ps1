$baseUrl = "http://127.0.0.1:8000"

$testUsername = $env:VERIFY_USERNAME
$testPassword = $env:VERIFY_PASSWORD

if (-not $testUsername -or -not $testPassword) {
    Write-Host "ERROR: VERIFY_USERNAME and VERIFY_PASSWORD environment variables are required." -ForegroundColor Red
    exit 1
}

Write-Host "`n[1/2] Authenticating $testUsername..." -ForegroundColor Cyan

$custBody = @{
    username = $testUsername
    password = $testPassword
} | ConvertTo-Json

$custAuth = Invoke-RestMethod `
    -Uri "$baseUrl/api/v1/token/" `
    -Method Post `
    -Body $custBody `
    -ContentType "application/json"

$custHeaders = @{
    "Authorization" = "Bearer $($custAuth.access)"
    "Accept" = "application/json"
}

Write-Host "[2/2] Fetching Customer Notifications..." -ForegroundColor Cyan

$notifications = Invoke-RestMethod `
    -Uri "$baseUrl/api/v1/services/notifications/" `
    -Method Get `
    -Headers $custHeaders

Write-Host "--- Notifications API Payload ---" -ForegroundColor Green

$notifications | ConvertTo-Json -Depth 10 | Write-Output