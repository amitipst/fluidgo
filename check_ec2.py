import subprocess, sys

result = subprocess.run(
    [
        r"C:\WINDOWS\System32\OpenSSH\ssh.exe",
        "-i", r"C:\Users\AmitSingh\.ssh\fluidgo.pem",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", "ConnectTimeout=15",
        "ubuntu@65.2.205.77",
        "cd /opt/fluidgo/app && docker compose -f docker-compose.prod.yml ps && echo '---' && curl -s http://localhost:8000/api/health && echo '---' && git log --oneline -3"
    ],
    capture_output=True, text=True, timeout=30
)
print("STDOUT:", result.stdout)
print("STDERR:", result.stderr[:300] if result.stderr else "")
print("EXIT:", result.returncode)
