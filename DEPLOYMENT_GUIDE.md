# ARIA-Lite Deployment Guide

Complete guide to deploy ARIA-Lite++ with backend on Render and frontend on Vercel.

## Overview

```
┌─────────────────────────────────┐
│   Vercel Frontend (React)       │
│   https://aria-lite.vercel.app  │
└──────────────┬──────────────────┘
               │ HTTPS API Calls
               │ (VITE_API_URL env var)
               ▼
┌─────────────────────────────────┐
│   Render Backend (FastAPI)      │
│   https://aria-lite-backend...  │
│   (API Endpoint on port $PORT)  │
└─────────────────────────────────┘
```

## Step 1: Deploy Backend on Render

### 1.1 Prepare Backend
The `render.yaml` file is already configured. Verify requirements.txt exists:
```bash
cat backend/requirements.txt
```

### 1.2 Push to GitHub
```bash
git add backend/
git commit -m "Prepare backend for Render deployment"
git push origin main
```

### 1.3 Deploy on Render
1. Go to https://render.com
2. Sign in with GitHub
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub account and select repository
5. Configure:
   - **Root Directory**: `backend`
   - **Runtime**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Click **"Deploy"**

### 1.4 Get Backend URL
After deployment completes, Render shows your service URL:
```
https://aria-lite-backend-XXXXX.onrender.com
```

**Save this URL** - you'll need it for frontend configuration.

---

## Step 2: Deploy Frontend on Vercel

### 2.1 Prepare Frontend
Verify `vercel.json` and API configuration exist:
```bash
cat frontend/vercel.json
cat frontend/src/lib/api.ts
```

### 2.2 Push to GitHub
```bash
git add frontend/
git commit -m "Prepare frontend for Vercel deployment"
git push origin main
```

### 2.3 Deploy on Vercel
1. Go to https://vercel.com/dashboard
2. Click **"Add New..."** → **"Project"**
3. Import your GitHub repository
4. Configure:
   - **Framework**: Vite
   - **Root Directory** (if needed): `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. Before clicking **Deploy**, go to **"Environment Variables"**

### 2.4 Add Render Backend URL as Environment Variable
In Vercel's Environment Variables section:
- **Key**: `VITE_API_URL`
- **Value**: Paste your Render backend URL
  ```
  https://aria-lite-backend-XXXXX.onrender.com
  ```
- **Environments**: Select `Production`
- Click **"Add"**

Then click **"Deploy"**

### 2.5 Get Frontend URL
After deployment, Vercel provides:
```
https://aria-lite.vercel.app
```

---

## Step 3: Test End-to-End Connection

### 3.1 Test Backend Health
```bash
curl https://aria-lite-backend-XXXXX.onrender.com/health
```

Expected response:
```json
{"status": "ok", "service": "ARIA-LITE++", "version": "5.0.0"}
```

### 3.2 Test Backend API
```bash
curl -X POST https://aria-lite-backend-XXXXX.onrender.com/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "scale ec2 from 2 to 8"}'
```

### 3.3 Test Frontend in Browser
1. Open https://aria-lite.vercel.app
2. Enter a test ticket: "scale ec2 from 2 to 8"
3. Submit and verify:
   - ✅ Page loads
   - ✅ Analysis completes
   - ✅ Returns gate decision (AUTO/APPROVE/BLOCK)

---

## Troubleshooting

### Backend shows "Internal Server Error" (500)
- Check Render logs: Dashboard → Service → Logs
- Verify `main.py` starts correctly
- Test health endpoint: `/health`

### Frontend shows "Backend unreachable"
- Verify `VITE_API_URL` environment variable is set in Vercel
- Check browser DevTools Network tab to see actual request URL
- Ensure Render backend URL is correct (with https://)
- Wait ~30 seconds for Render cold start (free tier)

### CORS errors
- Backend already has CORS enabled
- No additional configuration needed

### Build fails on Vercel
- Ensure `npm run build` works locally:
  ```bash
  cd frontend && npm run build
  ```
- Check dist folder is created
- Verify `vite.config.ts` has correct output directory

---

## How API Requests Work

**During Local Development:**
- Frontend: http://localhost:5174
- Request to `/api/process_ticket` 
- Vite proxy intercepts → forwards to http://localhost:8001
- No environment variable needed

**In Production (Deployed):**
- Frontend: https://aria-lite.vercel.app
- Request to `https://aria-lite-backend-XXXXX.onrender.com/process_ticket`
- Uses `VITE_API_URL` environment variable
- Direct HTTPS call (no proxy)

---

## Cost Considerations

- **Render**: Free tier includes:
  - One web service
  - Shared CPU
  - 0.5GB RAM
  - Cold starts after 15 min inactivity
  
- **Vercel**: Free tier includes:
  - Unlimited deployments
  - Fast build times
  - Automatic HTTPS
  - Generous bandwidth

---

## Next Steps

After successful deployment:
1. Monitor Render logs for errors
2. Set up Render notifications for deployments
3. Configure custom domain (optional)
4. Enable environment variable protection (optional)
5. Set up automatic deploys on GitHub push
