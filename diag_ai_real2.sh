#!/bin/bash
cd /opt/fluidgo/app

echo "=== Ollama reachable from INSIDE the backend container (how the app calls it) ==="
echo "--- model list ---"
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import httpx
r = httpx.get('http://ollama:11434/api/tags', timeout=10)
print(r.status_code, r.text[:300])
"

echo ""
echo "=== REAL timing: generate a full-sized prompt from inside the container, timed ==="
docker compose -f docker-compose.prod.yml exec -T backend python -c "
import httpx, time
prompt = '''Sales Rep Activity (last 20 working days):
Total Calls: 36 | Visits: 1 | Follow-ups: 14 | New Leads: 6
Average Rigor Score: 56/100
Analyse this FluidPro field sales rep performance. Give:
1. Rigor assessment 2. Top 2 deal priorities 3. Critical gaps 4. One coaching observation'''
t = time.time()
try:
    r = httpx.post('http://ollama:11434/api/generate',
        json={'model':'phi3:mini','prompt':prompt,'stream':False,'keep_alive':'30m','options':{'num_predict':350}},
        timeout=400)
    elapsed = time.time() - t
    data = r.json()
    print(f'HTTP {r.status_code} | took {elapsed:.1f}s')
    print('response length:', len(data.get('response','')))
    print('eval_count (tokens generated):', data.get('eval_count'))
    print('---first 200 chars---')
    print(data.get('response','')[:200])
except Exception as e:
    print(f'FAILED after {time.time()-t:.1f}s: {type(e).__name__}: {e}')
"
