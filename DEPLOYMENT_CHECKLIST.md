# Deployment Checklist

Use this checklist while deploying. Check off each step as you complete it.

## Before Deployment

- [ ] Latest code pushed to GitHub main or Version2 branch
- [ ] Verified `requirements.txt` exists in `backend/`
- [ ] Verified `package.json` exists in `frontend/`
- [ ] Have Render account ready (render.com)
- [ ] Have Vercel account ready (vercel.com)

## Backend Deployment (Render)

```
RENDER DASHBOARD: https://render.com/dashboard
```

### Create Service

- [ ] Click "New +" button
- [ ] Select "Web Service"
- [ ] Connect GitHub (authorize if needed)
- [ ] Select your ARIA-Lite repo

### Configure Service

- [ ] **Name**: `aria-lite-backend`
- [ ] **Environment**: Python 3
- [ ] **Build Command**: `pip install -r requirements.txt`
- [ ] **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] **Root Directory**: `backend`

### Deploy

- [ ] Click "Create Web Service"
- [ ] Wait for "Build in progress..." → "Deploying..." → "Live"
- [ ] ⏱️ Wait 2-3 minutes total
- [ ] **Save this URL** (you'll need it next): `https://aria-lite-backend-XXXXX.onrender.com`

### Verify Backend

- [ ] Open browser and test: `https://aria-lite-backend-XXXXX.onrender.com/health`
- [ ] Should see JSON response with `"status":"ok"`

## Frontend Deployment (Vercel)

```
VERCEL DASHBOARD: https://vercel.com/dashboard
```

### Import Project

- [ ] Click "Add New"
- [ ] Select "Project"
- [ ] Select your ARIA-Lite repo from GitHub
- [ ] Click "Import"

### Configure Project

- [ ] **Root Directory**: Set to `frontend`
- [ ] **Build Command**: Leave as default (auto-detected)
- [ ] **Output Directory**: Set to `dist/public`

### Add Environment Variables

**IMPORTANT**: Set these BEFORE deploying

- [ ] Click "Environment Variables"
- [ ] Add new variable:
  - **Key**: `VITE_API_URL`
  - **Value**: `https://aria-lite-backend-XXXXX.onrender.com` (from backend step)
  - Click "Add"

### Deploy

- [ ] Click "Deploy"
- [ ] Check build status: "Building..." → "Ready"
- [ ] ⏱️ Wait 1-2 minutes
- [ ] **Save this URL**: `https://aria-lite.vercel.app` (or your custom domain)

## Testing

### Test Backend Directly

```bash
# In terminal, test your backend URL
curl https://aria-lite-backend-XXXXX.onrender.com/health

# Should return:
# {"status":"ok","service":"ARIA-LITE++","version":"5.0.0"}
```

- [ ] Backend health endpoint responds
- [ ] Status is "ok"

### Test Frontend

- [ ] Open `https://aria-lite.vercel.app` in browser
- [ ] Page loads (might take 10-15 seconds)
- [ ] Submit test ticket: `"scale ec2 from 2 to 8"`
- [ ] See loading indicator
- [ ] See analysis results (might take 20-30 seconds on first try)

### Test Full Flow

- [ ] Try different tickets:
  - [ ] `"create s3 bucket"`
  - [ ] `"delete iam policy"`
  - [ ] `"update rds parameter"`
- [ ] All return analysis results
- [ ] No "Backend unreachable" errors

## Post-Deployment

- [ ] Bookmark both URLs
- [ ] Share frontend URL with others: `https://aria-lite.vercel.app`
- [ ] Keep backend URL private/secure
- [ ] Monitor first few days for errors

### Optional: Custom Domain

- [ ] In Vercel dashboard → Project Settings → Domains
- [ ] Add custom domain (verify DNS)
- [ ] Update browser bookmarks

## Troubleshooting Quick Fixes

### "Backend unreachable" error?

- [ ] Check Vercel env var `VITE_API_URL` is correct
- [ ] Redeploy frontend: Vercel Dashboard → Deployments → Redeploy
- [ ] Wait 1-2 minutes for redeployment

### Backend not responding?

- [ ] Check Render status: Should be "Live" (green)
- [ ] Check Render logs for errors
- [ ] Test manually: `curl https://aria-lite-backend-XXXXX.onrender.com/health`

### First request is slow?

- [ ] This is expected (Render free tier cold start is 20-30 seconds)
- [ ] Not an error, just normal behavior
- [ ] Second and subsequent requests will be faster

### Build failed error?

- [ ] Check build logs in dashboard
- [ ] Verify output directory is `dist/public`
- [ ] Ensure all dependencies are correct

## Traffic & Monitoring

### Check Live Status

**Render:**
- [ ] Dashboard shows "Live" (green)
- [ ] View logs if needed

**Vercel:**
- [ ] Dashboard shows latest deployment is live
- [ ] View logs if needed

### Monitor Usage

**For free tier limits:**
- Render: ~750 hours/month free
- Vercel: ~100 invocations/day on hobby tier (abundant for personal use)

### Performance Tips

- [ ] First request to backend will be slow (expected)
- [ ] Keep frontend URL public, keep backend private
- [ ] No additional configuration needed for basic usage

## Success Indicators

You'll know deployment is successful when:

✅ Frontend URL loads in browser
✅ Can submit ticket and get response
✅ Analysis displays correctly
✅ No "Backend unreachable" errors
✅ Response time < 5 seconds (after first request)

## Done!

- [ ] All checks complete
- [ ] Both services deployed and working
- [ ] Frontend accessible to users
- [ ] Backend processing requests

**Congratulations! Your ARIA-Lite++ is now live!** 🚀
