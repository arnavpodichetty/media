$ErrorActionPreference = "Stop"

# Cross-Media Recommendation Engine launcher (PowerShell, double-click friendly)
# - Opens a PowerShell window for llama.cpp llama-server on :8080 (if available)
# - Opens a PowerShell window for FastAPI (uvicorn) on :8001
# - Opens the browser to the UI

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$venvPy = Join-Path $backend ".venv\Scripts\python.exe"

# Optional overrides (set in your environment before launching):
#   $env:LLAMA_SERVER_EXE = "C:\path\to\llama-server.exe"
#   $env:LLAMA_MODEL      = "C:\path\to\model.gguf"
#   $env:LLAMA_CTX        = "8192"
$llamaServer = if ($env:LLAMA_SERVER_EXE) { $env:LLAMA_SERVER_EXE } else { "llama-server.exe" }
$llamaModel  = if ($env:LLAMA_MODEL) { $env:LLAMA_MODEL } else { (Join-Path $backend "models\Qwen3.5-4B-Q5_K_M.gguf") }
$llamaCtx    = if ($env:LLAMA_CTX) { $env:LLAMA_CTX } else { "8192" }

if (-not (Test-Path $venvPy)) {
  throw "Python venv not found at '$venvPy'. Create it under backend\.venv first."
}

function Resolve-LlamaServer([string]$candidate) {
  if (Test-Path $candidate) { return $candidate }
  $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  return $null
}

$llamaServerResolved = Resolve-LlamaServer $llamaServer
if ($llamaServerResolved -and (Test-Path $llamaModel)) {
  $llamaArgs = @(
    "-NoExit",
    "-Command",
    "& `"$llamaServerResolved`" -m `"$llamaModel`" --host 127.0.0.1 --port 8080 -c $llamaCtx"
  )
  Start-Process -FilePath "powershell.exe" -ArgumentList $llamaArgs -WorkingDirectory $root -WindowStyle Normal
} else {
  Write-Warning "Skipping llama-server startup."
  if (-not $llamaServerResolved) { Write-Warning "Could not find llama-server ('$llamaServer'). Set `$env:LLAMA_SERVER_EXE or put it on PATH." }
  if (-not (Test-Path $llamaModel)) { Write-Warning "Model not found at '$llamaModel'. Set `$env:LLAMA_MODEL if needed." }
}

$uvicornArgs = @(
  "-NoExit",
  "-Command",
  "Set-Location -LiteralPath `"$backend`"; & `"$venvPy`" -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload"
)
Start-Process -FilePath "powershell.exe" -ArgumentList $uvicornArgs -WorkingDirectory $root -WindowStyle Normal

Start-Sleep -Milliseconds 500
Start-Process "http://127.0.0.1:8001/"

