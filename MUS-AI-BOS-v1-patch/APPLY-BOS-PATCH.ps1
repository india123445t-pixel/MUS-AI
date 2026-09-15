param(
  [Parameter(Mandatory=$true)][string]$RepoPath,
  [switch]$AllowDirty
)
$ErrorActionPreference='Stop'
$PatchRoot=Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo=(Resolve-Path $RepoPath).Path
if(-not (Test-Path (Join-Path $Repo '.git'))){throw "RepoPath is not a Git repository: $Repo"}
Push-Location $Repo
try {
  $remote=(git remote get-url origin 2>$null)
  if($remote -notmatch 'india123445t-pixel/MUS-AI'){throw "Unexpected repository remote: $remote"}
  $dirty=(git status --porcelain)
  if($dirty -and -not $AllowDirty){throw 'Repository has uncommitted changes. Commit/stash them or rerun with -AllowDirty after review.'}
  $branch='mus-bos-v1'
  $exists=(git branch --list $branch)
  if($exists){git switch $branch | Out-Host}else{git switch -c $branch | Out-Host}

  $paths=@(
    'package.json',
    'lib/mus/constants.js','lib/mus/security.js','lib/mus/persona.js','lib/mus/domain-protocols.js','lib/mus/providers.js','lib/mus/kernel.js',
    'lib/mus/tool-registry.js','lib/mus/authority.js','lib/mus/state-machines.js','lib/mus/context.js','lib/mus/receipts.js','lib/mus/response-governor.js',
    'app/api/chat/route.js','app/api/internal/bos-status/route.js',
    'tests/mus-kernel.test.mjs','tests/security-regression.test.mjs','tests/authority-contract.test.mjs','tests/response-governor.test.mjs','tests/persona-contract.test.mjs',
    'docs/MUS_BOS_v1_IMPLEMENTATION.md','supabase/migrations/20260915_mus_bos_v1.sql'
  )
  foreach($rel in $paths){
    $src=Join-Path $PatchRoot $rel
    if(-not (Test-Path $src)){throw "Patch file missing: $rel"}
    $dst=Join-Path $Repo $rel
    $dir=Split-Path -Parent $dst
    if(-not (Test-Path $dir)){New-Item -ItemType Directory -Force -Path $dir | Out-Null}
    Copy-Item -Force $src $dst
  }
  Write-Host 'BOS patch copied to branch mus-bos-v1.' -ForegroundColor Green
  npm run bos:check
  npm run bos:test
  npm run build
  Write-Host 'Local checks complete. Review git diff before committing/pushing.' -ForegroundColor Green
  Write-Host 'Supabase migration is NOT auto-applied.' -ForegroundColor Yellow
} finally { Pop-Location }
