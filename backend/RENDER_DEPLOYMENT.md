# Deploy Backend to Render

This guide walks you through deploying ARIA-Lite++ backend to Render.

## Prerequisites

- GitHub account (with repository pushed)
- Render account (free tier available at render.com)

## Step-by-Step Deployment

### 1. Push Code to GitHub

```bash
cd /path/to/ARIA-Lite-Self-Doubting-Autonomous-Cloud-Agent-
git add -A
git commit -m "Add Render and Vercel deployment config"
git push origin main
```

### 2. Create Render Account & Login

1. Go to [render.com](https://render.com)
2. Sign up with GitHub (easier for CI/CD)
3. Authorize Render to access your repositories

### 3. Create New Web Service on Render

1. Click **"New +"** in top right
2. Select **"Web Service"**
3. Connect your GitHub repository
4. Choose the repository containing ARIA-Lite++

### 4. Configure Service

Fill in these settings:

| Setting | Value |
|---------|-------|
| **Name** | `aria-lite-backend` |
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Root Directory** | `backend` |

### 5. Finalize & Deploy

1. Click **"Create Native Environment Variable"** (optional for now)
2. Click **"Deploy"**
3. Wait 2-3 minutes for build & deployment

### 6. Get Your Backend URL

Once deployed, you'll see:
```
https://aria-lite-backend-XXXXX.onrender.com
```

Copy this URL - you'll need it for the frontend!

## Important Notes

- **First request is slow**: Free tier cold starts take 20-30 seconds
- **CORS enabled**: Already configured in main.py
- **No database**: No external services required
- **Environment variables**: Not needed for basic setup

## Troubleshooting

### Build fails with "Module not found"

**Solution**: Ensure `requirements.txt` is in `/backend` directory
```bash
# Verify
cat requirements.txt
```

### Service won't start

**Solution**: Check logs in Render dashboard
```
Logs → "Building" or "Deploying" tab
```

Common issues:
- Wrong start command
- Missing dependencies in requirements.txt
- Port binding error (should use `$PORT`)

### Backend not responding

**Solution**: 
1. Check Render deployment status (should be "Live")
2. Test health endpoint:
```bash
curl https://aria-lite-backend-XXXXX.onrender.com/health
```

## Next Steps

After backend is deployed:
1. Copy the backend URL
2. Follow [VERCEL_DEPLOYMENT.md](../frontend/VERCEL_DEPLOYMENT.md) to deploy frontend
3. Set `VITE_API_URL` environment variable in Vercel to your backend URL

## Quick Reference

| Item | Value |
|------|-------|
| Service Name | aria-lite-backend |
| Runtime | Python 3.11 |
| Root Dir | backend |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |

## Support

For issues, check:
- Render documentation: https://render.com/docs
- Backend logs in Render dashboard
- GitHub Issues in your repository
