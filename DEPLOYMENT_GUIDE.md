# Complete Deployment Guide: ARIA-Lite++ on Render + Vercel

This guide covers deploying both backend (Render) and frontend (Vercel) with everything you need.

## Architecture Overview

```
PRODUCTION (After Deployment):
════════════════════════════════════════════════════════════════

  User Browser
        ↓
  https://aria-lite.vercel.app (Frontend)
        ↓ fetch with VITE_API_URL
        ↓
  https://aria-lite-backend-XXXXX.onrender.com (Backend)
        ↓
  Analysis Engine (trust_engine_v3)
        ↓
  JSON Response → Frontend → User
```

## Files Modified/Created

### Backend
- `backend/render.yaml` - Render deployment config (NEW)
- `backend/requirements.txt` - Already correct
- `backend/main.py` - Already has CORS enabled

### Frontend
- `frontend/vercel.json` - Vercel deployment config (NEW)
- `frontend/src/lib/api.ts` - Smart API client (NEW)
- `frontend/src/App.tsx` - Updated to use new API client
- `frontend/vite.config.ts` - Already fixed for production

## Deployment Timeline

```
Step 1: Deploy Backend (2-3 minutes)
├─ Push code to GitHub
├─ Create Render web service
├─ Wait for build and deployment
└─ Get backend URL: https://aria-lite-backend-XXXXX.onrender.com

Step 2: Deploy Frontend (1-2 minutes)
├─ Set VITE_API_URL environment variable in Vercel
├─ Import project to Vercel
├─ Set output directory to dist/public
├─ Deploy
└─ Get frontend URL: https://aria-lite.vercel.app

Step 3: Test (2-3 minutes)
├─ Open frontend URL
├─ Submit test ticket
└─ Verify response from backend
```

## Quick Start (5 Minutes)

### 1. Deploy Backend to Render

```bash
# Ensure latest code is on GitHub
git push origin main

# Go to https://render.com
# Click "New +" → "Web Service"
# Connect GitHub repository
# Set Root Directory: backend
# Set Build Command: pip install -r requirements.txt
# Set Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
# Click Deploy
# Wait 2-3 minutes
# Copy the URL shown, e.g., https://aria-lite-backend-XXXXX.onrender.com
```

For detailed instructions, see: [backend/RENDER_DEPLOYMENT.md](../backend/RENDER_DEPLOYMENT.md)

### 2. Deploy Frontend to Vercel

```bash
# Go to https://vercel.com
# Click "Add New" → "Project"
# Select your GitHub repository
# Set Root Directory: frontend
# Set Output Directory: dist/public

# Add Environment Variable:
# Key: VITE_API_URL
# Value: https://aria-lite-backend-XXXXX.onrender.com (the URL from step 1)

# Click Deploy
# Wait 1-2 minutes
# Access frontend at: https://aria-lite.vercel.app
```

For detailed instructions, see: [frontend/VERCEL_DEPLOYMENT.md](../frontend/VERCEL_DEPLOYMENT.md)

### 3. Test

```bash
# Open in browser
https://aria-lite.vercel.app

# Try submitting: "scale ec2 from 2 to 8"
# Should see analysis within a few seconds
```

## How It Works

### Development (Local)

```typescript
// frontend/src/lib/api.ts detects we're in development
fetch("/api/process_ticket")
  ↓
// Vite proxy intercepts /api/* requests and rewrites them
// Path: /api/process_ticket → /process_ticket
// Target: http://localhost:8001
  ↓
// Backend receives request
```

### Production (Deployed)

```typescript
// frontend/src/lib/api.ts detects we're in production
fetch(VITE_API_URL + "/api/process_ticket")
// Where VITE_API_URL = https://aria-lite-backend-XXXXX.onrender.com
  ↓
// Direct HTTPS request to Render backend
  ↓
// Backend receives request
```

## Environment Variables

### Vercel

Only one environment variable needed:

| Key | Value | Example |
|-----|-------|---------|
| `VITE_API_URL` | Your backend URL | `https://aria-lite-backend-abc123.onrender.com` |

Set in: **Project Settings → Environment Variables**

### Render

No custom environment variables needed. Render automatically provides:
- `PORT` - The port to listen on (we use it in start command)

## Troubleshooting

### "Failed to fetch" error

**Problem**: Frontend can't reach backend

**Solution**:
1. Check backend URL in Vercel env vars
2. Verify backend is "Live" on Render dashboard
3. Test directly: `curl https://your-backend-url/health`

### Slow responses (20-30 seconds)

**Problem**: Free tier Render cold starts

**Expected**: First request after idle takes 20-30 seconds
**Solution**: This is normal for free tier, not an error

### "Backend unreachable" in UI

**Problem**: Frontend deployed but showing error

**Solution**:
1. Vercel: Check Project Settings → Environment Variables
2. Ensure `VITE_API_URL` is set to your Render URL
3. Redeploy frontend: Deployments → Redeploy

### Build fails on Vercel

**Problem**: Build logs show errors

**Solution**: Check Vercel build logs
```
Deployments → [Click failed deployment] → Logs
```

Common fixes:
- Check output directory is `dist/public`
- Verify TypeScript errors are resolved
- Ensure all dependencies are in package.json

## Local Development

You can mix local + deployed:

```bash
# Option 1: Both local
cd backend && uvicorn main:app --port 8001
cd frontend && npm run dev  # Uses Vite proxy

# Option 2: Local frontend + deployed backend
VITE_API_URL=https://aria-lite-backend-XXXXX.onrender.com npm run dev
# Open http://localhost:5174

# Option 3: Both deployed
# Just open https://aria-lite.vercel.app
```

## Performance Expectations

| Scenario | Response Time | Notes |
|----------|---------------|-------|
| Local → Local | <100ms | No network latency |
| Browser → Deployed | 2-5s | Render cold start, network |
| Subsequent requests | <1s | Render warm instance |

## Monitoring

### Check Backend Status

```bash
curl https://aria-lite-backend-XXXXX.onrender.com/health
```

Returns:
```json
{"status":"ok","service":"ARIA-LITE++","version":"5.0.0"}
```

### View Logs

**Render**: Dashboard → Services → [Your service] → Logs
**Vercel**: Dashboard → Deployments → [Your deployment] → Logs

## Next Steps

1. **Immediate**: Deploy both services (5 minutes)
2. **Testing**: Submit test tickets and verify
3. **Optimization**: Monitor performance, adjust if needed
4. **Custom Domain**: Add custom domain to Vercel (optional)

## Support Resources

- Render Docs: https://render.com/docs
- Vercel Docs: https://vercel.com/docs
- FastAPI Docs: https://fastapi.tiangolo.com
- React Docs: https://react.dev

## Quick Commands Reference

```bash
# Test backend health
curl https://aria-lite-backend-XXXXX.onrender.com/health

# Test backend API
curl -X POST https://aria-lite-backend-XXXXX.onrender.com/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "scale ec2 from 2 to 8"}'

# Test frontend (just open in browser)
https://aria-lite.vercel.app

# Redeploy frontend
# (In Vercel dashboard: Deployments → Redeploy latest)

# View frontend logs
# (In Vercel dashboard: Deployments → [latest] → Logs)
```

---

**Ready to deploy?** Start with [backend/RENDER_DEPLOYMENT.md](../backend/RENDER_DEPLOYMENT.md)
