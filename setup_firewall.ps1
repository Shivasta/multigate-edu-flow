# MEF Portal - Firewall Setup Script
# Run this as Administrator to allow mobile connections

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "MEF Portal - Firewall Configuration" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    Write-Host "Then run this script again." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "Adding firewall rule for Flask on port 5000..." -ForegroundColor Green

try {
    # Remove existing rule if it exists
    Remove-NetFirewallRule -DisplayName "Flask MEF Portal Port 5000" -ErrorAction SilentlyContinue
    
    # Add new firewall rule
    New-NetFirewallRule -DisplayName "Flask MEF Portal Port 5000" `
        -Direction Inbound `
        -LocalPort 5000 `
        -Protocol TCP `
        -Action Allow `
        -Profile Any `
        -Description "Allow incoming connections to MEF Portal Flask app on port 5000"
    
    Write-Host ""
    Write-Host "SUCCESS! Firewall rule added." -ForegroundColor Green
    Write-Host ""
    Write-Host "You can now access the portal from your mobile device!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Run: python run_mobile.py" -ForegroundColor White
    Write-Host "2. Connect your phone to the same WiFi" -ForegroundColor White
    Write-Host "3. Use the IP address shown in the terminal" -ForegroundColor White
    Write-Host ""
    
} catch {
    Write-Host "ERROR: Failed to add firewall rule" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host ""
    pause
    exit 1
}

pause
