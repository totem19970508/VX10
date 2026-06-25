$IP = "10.0.1.182"

# Base64 of: admin:Simpson!712
$code = "YWRtaW46U2ltcHNvbiE3MTI="

$headers = New-Object "System.Collections.Generic.Dictionary[[String],[String]]"
$headers.Add("Authorization", "Basic $code")
$headers.Add("Content-Type", "application/json")

$body = @"
{
    "serial": {
        "enabled": 1,
        "baudrate": 19200,
        "protocol": "RS-232"
    },
    "tcp": {
        "enabled": 1,
        "port": 6000
    },
    "udp": {
        "enabled": 1,
        "port": 6001
    }
}
"@

try {
    $response = Invoke-RestMethod "http://$IP/api/supcon.json" `
        -Method PUT `
        -Headers $headers `
        -Body $body

    Write-Host "Success:"
    $response | ConvertTo-Json
}
catch {
    Write-Host "Error:"
    Write-Host $_.Exception.Message

    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $responseBody = $reader.ReadToEnd()
        Write-Host "Response Body:"
        Write-Host $responseBody
    }
}