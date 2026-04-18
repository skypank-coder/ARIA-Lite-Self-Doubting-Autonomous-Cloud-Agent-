# Quick Command Reference

## Testing Locally (Before Deployment)

```bash
# Terminal 1: Start Backend
cd backend
source venv/bin/activate  # or: . venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 2: Start Frontend
cd frontend
npm run dev

# Browser: Open http://localhost:5174
```

## Testing Backend Directly

```bash
# Health check
curl http://localhost:8001/health

# Process ticket
curl -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "scale ec2 from 2 to 8"}'

# Destructive operation
curl -X POST http://localhost:8001/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "delete iam policy for admin"}'
```

## Testing Frontend Proxy

```bash
# Via Vite proxy (development)
curl -X POST http://localhost:5174/api/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "create s3 bucket"}'
```

## After Deployment

```bash
# Replace with your actual URLs
BACKEND_URL="https://aria-lite-backend-XXXXX.onrender.com"
FRONTEND_URL="https://aria-lite.vercel.app"

# Test backend
curl $BACKEND_URL/health

# Test backend API
curl -X POST $BACKEND_URL/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "test operation"}'

# Open frontend in browser
# Visit $FRONTEND_URL in your browser
```

## Git Commands

```bash
# Check status
git status

# Stage changes
git add .

# Commit
git commit -m "Your message"

# Push to GitHub
git push origin Version2

# View logs
git log --oneline -10
```

## Frontend Build & Test

```bash
# Build for production (same as Vercel)
cd frontend
npm run build

# Preview production build locally
npm run serve

# TypeScript check (optional)
npm run typecheck
```

## Backend Verification

```bash
# Check requirements
cat backend/requirements.txt

# Check backend main file
head -20 backend/main.py

# List backend files
ls -la backend/ | grep -E "\.py$|\.yaml$|requirements"
```

## Environment Variables

```bash
# Check Vercel env vars (after deployment):
# Go to: https://vercel.com → Project Settings → Environment Variables
# Look for: VITE_API_URL

# On Render:
# No custom env vars needed (PORT is automatic)

# Local development:
# No env vars needed (Vite proxy handles it)
```

## Debugging

```bash
# Check if ports are in use
lsof -i :5174  # Frontend
lsof -i :8001  # Backend

# Kill process on port
kill -9 PID    # Replace PID with actual process ID

# Clear browser cache (if needed)
# DevTools → Settings → Storage → Clear site data

# Check Vercel logs
# https://vercel.com → Project → Deployments → Select deployment → Logs

# Check Render logs
# https://render.com → Service → Logs
```

## Common Issues Quick Fixes

```bash
# Frontend not building
cd frontend && npm install && npm run build

# Backend not starting
cd backend && pip install -r requirements.txt

# Port already in use
kill -9 $(lsof -t -i :8001)  # Kill process on port 8001
kill -9 $(lsof -t -i :5174)  # Kill process on port 5174

# Need to restart services
# Stop current services (Ctrl+C in terminals)
# Then run commands above again
```

## Viewing Generated Files

```bash
# Frontend build output
ls -la frontend/dist/

# Backend Python files
head -50 backend/main.py

# Render config
cat backend/render.yaml

# Vercel config
cat frontend/vercel.json

# API client
cat frontend/src/lib/api.ts
```

## After Successful Deployment

```bash
# Test deployed system
curl https://aria-lite-backend-XXXXX.onrender.com/health

# Visit deployed frontend
# Copy and paste into browser:
https://aria-lite.vercel.app

# Submit test ticket
# Try: "scale ec2 from 2 to 8"
```

---

## Reference URLs

| Service | Default URL | Production URL |
|---------|------------|-----------------|
| Frontend local | http://localhost:5174 | https://aria-lite.vercel.app |
| Backend local | http://localhost:8001 | https://aria-lite-backend-XXXXX.onrender.com |
| Render dashboard | N/A | https://render.com/dashboard |
| Vercel dashboard | N/A | https://vercel.com/dashboard |

---

**Pro Tip:** Copy these commands into your terminal. Most can be run as-is with just URL replacements!
