import subprocess, sys, time
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SSH = [
    r"C:\WINDOWS\System32\OpenSSH\ssh.exe",
    "-i", r"C:\Users\AmitSingh\.ssh\fluidgo.pem",
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=20",
    "-o", "ServerAliveInterval=30",
    "ubuntu@65.2.205.77"
]

def run(cmd, desc="", timeout=120):
    print(f"\n--- {desc or cmd[:60]} ---")
    result = subprocess.run(SSH + [cmd], capture_output=True, text=True,
                            timeout=timeout, encoding='utf-8', errors='replace')
    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0 and result.stderr.strip():
        print(f"STDERR: {result.stderr.strip()[:400]}")
    return result.returncode, result.stdout

# 1. Check container status
rc, out = run(
    "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml ps --format 'table {{.Name}}\t{{.Status}}'",
    "Container status"
)

# 2. API health
rc, out = run("curl -s http://localhost:8000/api/health", "API health check")

# 3. Pull latest code
rc, out = run(
    "cd /opt/fluidgo/app && git fetch origin main && git reset --hard origin/main",
    "Pull latest code from GitHub"
)

# 4. Run migration for audit_logs (migration 0007)
rc, out = run(
    "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml exec -T backend alembic upgrade head",
    "Run DB migrations (0007 audit_logs)",
    timeout=60
)

# 5. Rebuild backend only (faster than full rebuild)
rc, out = run(
    "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml build backend 2>&1 | tail -5",
    "Rebuild backend image",
    timeout=180
)

# 6. Restart backend with new image
rc, out = run(
    "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml up -d backend",
    "Restart backend",
    timeout=60
)

time.sleep(15)

# 7. Final health check
rc, out = run("curl -s http://localhost:8000/api/health", "Final health check")

# 8. Check ollama model status
rc, out = run(
    "docker exec $(docker ps -qf name=ollama | head -1) ollama list 2>/dev/null || echo 'Ollama: checking...'",
    "Ollama model status"
)

# 9. Smoke test
rc, out = run(
    "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml exec -T backend python smoke_test.py --base http://localhost:8000 2>&1 | tail -20",
    "Smoke test (last 20 lines)",
    timeout=90
)

print("\n✅ EC2 update complete")
