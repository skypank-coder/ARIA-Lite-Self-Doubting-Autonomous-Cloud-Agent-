# Deploy Frontend to Vercel

This guide walks you through deploying ARIA-Lite++ frontend to Vercel.

## Prerequisites

- GitHub account (with repository pushed)
- Vercel account (free tier available at vercel.com)
- Backend already deployed on Render (get the URL first!)

## Step-by-Step Deployment

### 1. Ensure Code is Pushed to GitHub

```bash
cd /path/to/ARIA-Lite-Self-Doubting-Autonomous-Cloud-Agent-
git add -A
git commit -m "Add Vercel deployment config"
git push origin main
```

### 2. Create Vercel Account & Login

1. Go to [vercel.com](https://vercel.com)
2. Sign up with GitHub (recommended)
3. Authorize Vercel to access your repositories

### 3. Import Project on Vercel

1. Click **"Add New..."** in top right
2. Select **"Project"**
3. Select your GitHub repository
4. Continue

### 4. Configure Project

**Root Directory:**
- Set to `frontend`

**Build Command:**
- Leave as default (Vercel auto-detects Vite)

**Output Directory:**
- Set to `dist/public` (matches our build output)

**Environment Variables:**
- **Key:** `VITE_API_URL`
- **Value:** `https://aria-lite-backend-XXXXX.onrender.com` (from Render deployment)
  - Replace `XXXXX` with YOUR backend service ID

### 5. Deploy

1. Click **"Deploy"**
2. Wait 1-2 minutes for build and deployment

Your frontend will be available at:
```
https://aria-lite.vercel.app
```

(or a custom domain you configure)

## After Deployment

### Test the Connection

1. Open https://aria-lite.vercel.app
2. Enter a test ticket: "scale ec2 from 2 to 8"
3. Click Submit
4. You should see analysis results within a few seconds

### If Connection Fails

**Check backend URL is correct:**
1. Go to Vercel Project Settings
2. Go to **Environment Variables**
3. Verify `VITE_API_URL` value matches your Render backend URL
4. Redeploy: Click **Deployments** → **Redeploy** on latest

**Test backend directly:**
```bash
curl https://aria-lite-backend-XXXXX.onrender.com/health
```

Should return:
```json
{"status":"ok","service":"ARIA-LITE++","version":"5.0.0","engine":"trust_engine_v3"}
```

## Important Notes

- **API URL must be set**: Frontend won't work without `VITE_API_URL`
- **CORS enabled**: Backend already allows all origins
- **No build secrets needed**: Our app is stateless
- **Cold starts**: First request to Render backend takes 20-30 seconds

## Troubleshooting

### "Backend unreachable" error in app

**Solution 1**: Check environment variable
```bash
# In Vercel Project Settings → Environment Variables
# VITE_API_URL should be: https://aria-lite-backend-XXXXX.onrender.com
```

**Solution 2**: Redeploy frontend
```bash
# Go to Vercel dashboard → Deployments → Click latest → Redeploy
```

**Solution 3**: Verify backend is running
```bash
curl https://your-backend-url/health
```

### Build fails

**Solution**: Check Vercel build logs
```
Deployments → [Click failed] → Logs
```

Common issues:
- Wrong output directory
- Missing dependencies in package.json
- TypeScript errors

## Continuous Deployment

After initial setup, deployments are automatic:
1. Push code to GitHub
2. Vercel auto-detects and builds
3. Frontend updates (takes ~1-2 minutes)

No manual deployment needed!

## Local Testing Before Production

Test with deployed backend locally:

```bash
# In frontend directory
VITE_API_URL=https://aria-lite-backend-XXXXX.onrender.com npm run dev
```

Then open http://localhost:5174

## Quick Reference

| Item | Value |
|------|-------|
| Framework | React + TypeScript (Vite) |
| Root Directory | frontend |
| Build Command | `npm run build` (auto-detected) |
| Output Directory | `dist/public` |
| Environment Variable | `VITE_API_URL` |

## Support

For issues, check:
- Vercel documentation: https://vercel.com/docs
- Build logs in Vercel dashboard
- GitHub Issues in your repository
- API client code: `frontend/src/lib/api.ts`
