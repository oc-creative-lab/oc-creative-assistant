$base = "http://127.0.0.1:9000/api"

$session = Invoke-RestMethod -Method Post -Uri "$base/sessions" `
  -ContentType "application/json" `
  -Body '{"project_id":"default-project","title":"Phase 6 端到端"}'
Write-Host "session.id = $($session.id)"

$r1 = Invoke-RestMethod -Method Post -Uri "$base/chat" `
  -ContentType "application/json" `
  -Body (@{ session_id = $session.id; user_message = "项目里有哪些角色?"; selected_node_ids = @() } | ConvertTo-Json)
Write-Host "=== Test 1 (期望 research) ==="
Write-Host "intent = $($r1.intent)"
Write-Host "reply  = $($r1.reply_text)"

$r2 = Invoke-RestMethod -Method Post -Uri "$base/chat" `
  -ContentType "application/json" `
  -Body (@{ session_id = $session.id; user_message = "帮我新建一个反派角色, 叫黑斯廷"; selected_node_ids = @() } | ConvertTo-Json)
Write-Host "=== Test 2 (期望 structure) ==="
Write-Host "intent  = $($r2.intent)"
Write-Host "reply   = $($r2.reply_text)"
Write-Host "staging = $($r2.staging_count) 条变更进 staging"