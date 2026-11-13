Write-Host "Starting CRM server on port 8001..."
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python victim_app/mcp_servers/crm_server.py"
Start-Sleep -Seconds 2

Write-Host "Starting Email server on port 8002..."
Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run python victim_app/mcp_servers/email_server.py"
Start-Sleep -Seconds 2

Write-Host "Both servers are running! You can now run the agent or baseline in a NEW terminal tab."