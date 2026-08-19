
# pgPlanAdvisor

**pgPlanAdvisor** is a PostgreSQL execution-plan advisor for DBAs.

A DBA can paste output from:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT ...;
```

Then click **Explain Plan** to get:

- Bottleneck summary
- DBA checklist
- Expensive node table
- Findings with evidence
- Recommendations
- A beautiful plan-tree visualizer tab
- Raw normalized JSON tab

---

## 1. Recommended PostgreSQL Command

For best analysis, use:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT ...
```

Why this format?

- `ANALYZE` gives real runtime and row counts.
- `BUFFERS` shows I/O behavior.
- `VERBOSE` adds more object details.
- `FORMAT JSON` gives accurate structured data for visualization.

Text EXPLAIN is accepted, but JSON format is strongly recommended.

---

## 2. Deploy with Docker Compose

### Step 1: Unzip

```bash
unzip pgplanadvisor.zip
cd pgplanadvisor
```

### Step 2: Build and start

```bash
sudo docker compose up --build
```

### Step 3: Open the UI

If running locally:

```text
http://localhost:5173
```

If running on a remote server through SSH tunnel:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 your_user@your_server
```

Then open on your laptop:

```text
http://localhost:5173
```

Backend API docs:

```text
http://localhost:8000/docs
```

---

## 3. Verify Services

Check containers:

```bash
sudo docker compose ps
```

Check backend health:

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"status":"ok","app":"pgPlanAdvisor"}
```

---

## 4. Use the App

1. Open the UI.
2. Paste SQL or notes in the first box.
3. Paste EXPLAIN output in the second box.
4. Click **Explain Plan**.
5. Review the **Advisor** tab.
6. Open **Tree Visualizer** to inspect the execution plan tree.
7. Open **Raw JSON** if you need normalized plan details.

---

## 5. Run Backend Locally Without Docker

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 6. Run Frontend Locally Without Docker

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

---

## 7. Test Backend

```bash
cd backend
pip install -r requirements.txt
pytest
```

---

## 8. Troubleshooting

### Docker Compose YAML error

Make sure you are using the latest project package.

Check file size:

```bash
ls -lh docker-compose.yml
cat docker-compose.yml
```

It should contain `backend` and `frontend` services.

### Browser opens but analysis fails

Check backend is reachable:

```bash
curl http://localhost:8000/health
```

If using SSH tunnel, create both tunnels:

```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 your_user@your_server
```

### Port already used

Change ports in `docker-compose.yml`, or stop old containers:

```bash
sudo docker compose down
sudo docker ps
```

---

## 9. Roadmap

Planned improvements:

- Richer text EXPLAIN parser
- Plan comparison before/after tuning
- Index recommendation simulation
- Export Markdown/PDF report
- Saved plan history
- Authentication
- `pg_stat_statements` integration
- Kubernetes manifests

---

## Persistent Logging

This version writes logs in two places:

1. Docker's own rotated JSON logs
2. Project-mounted files under `./logs`

Log files on the server:

```bash
logs/backend/backend.log
logs/frontend/frontend.log
```

Start in background:

```bash
sudo docker compose up -d --build
```

Check status:

```bash
sudo docker compose ps
```

Follow Docker logs:

```bash
sudo docker compose logs -f
```

Follow backend app log file:

```bash
tail -f logs/backend/backend.log
```

Follow frontend app log file:

```bash
tail -f logs/frontend/frontend.log
```

Use helper script:

```bash
./scripts/logs.sh all
./scripts/logs.sh backend
./scripts/logs.sh frontend
```

Stop:

```bash
sudo docker compose down
```

Restart:

```bash
sudo docker compose restart
```

The containers use:

```yaml
restart: unless-stopped
```

So they continue after SSH disconnect and restart after server reboot unless you explicitly stop them.

Docker log rotation is configured:

```yaml
logging:
  driver: json-file
  options:
    max-size: "20m"
    max-file: "5"
```

This prevents Docker logs from growing without limit.


---

## Complex Text EXPLAIN Support

This version improves text EXPLAIN parsing. It extracts:

- Relation/table name
- Alias
- Index name
- Index condition
- Filter
- Join condition
- Sort method
- Sort disk usage
- Buffers
- I/O timings
- Hash batches and memory
- Row-estimation errors

A complex sample is included:

```bash
samples/complex-text-explain.txt
```

For best results, still prefer:

```sql
EXPLAIN (ANALYZE, BUFFERS, VERBOSE, FORMAT JSON)
SELECT ...
```
