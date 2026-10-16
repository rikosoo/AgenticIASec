<#
Instala o adaptador PromptShield para o Claude Code NO SEU USUÁRIO do Windows (sem administrador, sem tocar na política da máquina).
Status: NÃO EXECUTADO em Windows real. É um modelo para o teste do roteiro (docs/teste-windows.md); anote o que falhar.

  .\install-user.ps1 -ApiUrl http://localhost:8000 [-ApiKey ps_...] [-Department Pessoal] [-FailMode open|closed] [-DryRun]
  .\install-user.ps1 -Uninstall

O que faz: instala o pacote com pip, grava %USERPROFILE%\.promptshield\hook.json (legível só por você), settings.json com os 3 hooks
e o atalho claude-ps.cmd, que roda `claude --settings ...` com a configuração certa. Não altera ~\.claude\settings.json.
O hook envia o que você digita e as ações do agente: use só com o seu consentimento e em um tenant de teste.
#>
param(
  [string]$ApiUrl = "http://localhost:8000",
  [string]$ApiKey = "",
  [string]$Department = "",
  [ValidateSet("open", "closed")][string]$FailMode = "open",
  [string]$Dir = (Join-Path $env:USERPROFILE ".promptshield"),
  [switch]$DryRun,
  [switch]$Uninstall
)
$ErrorActionPreference = "Stop"
$pkg = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($Uninstall) {
  if (Test-Path $Dir) { Remove-Item -Recurse -Force $Dir; Write-Host "Removido: $Dir" }
  python -m pip uninstall -y promptshield-claude-hook 2>$null | Out-Null
  Write-Host "Desinstalado. Revogue a chave no console do PromptShield."
  return
}

$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "python não encontrado no PATH (precisa do Python 3.9 ou mais novo)." }
if ($ApiUrl -notmatch '^https?://') { throw "ApiUrl precisa começar com http:// ou https://" }
if (-not $ApiKey) {
  $sec = Read-Host "Chave da API (ps_...)" -AsSecureString
  $ApiKey = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
}
if ($ApiKey -notmatch '^ps_') { throw "A chave deve começar com ps_" }

$cfg = [ordered]@{ api_url = $ApiUrl.TrimEnd('/'); api_key = $ApiKey; fail_mode = $FailMode; timeout_seconds = 3; integration_status = "partial" }
if ($Department) { $cfg.department = $Department }
$pyJson = $py.Replace('\', '\\')
$hook = '{ "type": "command", "command": "' + $pyJson + '", "args": ["-m", "promptshield_claude_hook"], "timeout": 10 }'
$settings = @"
{
  "hooks": {
    "UserPromptSubmit": [ { "hooks": [ $hook ] } ],
    "PreToolUse":  [ { "matcher": "*", "hooks": [ $hook ] } ],
    "PostToolUse": [ { "matcher": "*", "hooks": [ $hook ] } ]
  }
}
"@
$launcher = "@echo off`r`nset PROMPTSHIELD_HOOK_CONFIG=$Dir\hook.json`r`nclaude --settings `"$Dir\settings.json`" %*`r`n"

if ($DryRun) {
  Write-Host "SIMULAÇÃO. Faria:`n  pip install -e $pkg`n  gravar $Dir\hook.json (chave oculta), settings.json e claude-ps.cmd"
  Write-Host $settings
  return
}

python -m pip install -e $pkg
New-Item -ItemType Directory -Force $Dir | Out-Null
($cfg | ConvertTo-Json) | Set-Content -Encoding UTF8 (Join-Path $Dir "hook.json")
icacls (Join-Path $Dir "hook.json") /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null   # só você lê a chave
$settings | Set-Content -Encoding UTF8 (Join-Path $Dir "settings.json")
$launcher | Set-Content -Encoding ASCII (Join-Path $Dir "claude-ps.cmd")

$env:PROMPTSHIELD_HOOK_CONFIG = Join-Path $Dir "hook.json"
python -m promptshield_claude_hook check
Write-Host "`nPronto. Abra o Claude Code com:  $Dir\claude-ps.cmd"
Write-Host "Importar histórico (simulação primeiro):  python -m promptshield_claude_hook import --preview 5"
