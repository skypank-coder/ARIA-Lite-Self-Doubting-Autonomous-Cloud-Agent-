# Quick Deployment Commands

Copy-paste ready commands for fast deployment. See [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) for detailed steps.

## 1. Push Code to GitHub

```bash
cd /path/to/ARIA-Lite-Self-Doubting-Autonomous-Cloud-Agent-
git add -A
git commit -m "Prepare for Render + Vercel deployment"
git push origin main
```

## 2. Backend: Render Configuration

After creating web service on Render, use these exact values:

```
Name:           aria-lite-backend
Environment:    Python 3
Runtime:        Python 3.11
Root Directory: backend

Build Command:  pip install -r requirements.txt
Start Command:  uvicorn main:app --host 0.0.0.0 --port $PORT
```

No environment variables needed.

## 3. Test Backend Health

Once deployed, test with:

```bash
# Replace XXXXX with your Render service ID
curl https://aria-lite-backend-XXXXX.onrender.com/health

# Should return:
# {"status":"ok","service":"ARIA-LITE++","version":"5.0.0","engine":"trust_engine_v3"}
```

## 4. Test Backend API

```bash
# Replace XXXXX with your Render service ID
curl -X POST https://aria-lite-backend-XXXXX.onrender.com/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "scale ec2 from 2 to 8"}'

# Should return analysis JSON with gate decision
```

## 5. Frontend: Vercel Configuration

During project import on Vercel, use these exact values:

```
Root Directory:    frontend
Build Command:     (leave auto-detected)
Output Directory:  dist/public

Environment Variables:
  Key:   VITE_API_URL
  Value: https://aria-lite-backend-XXXXX.onrender.com
```

**CRITICAL**: The environment variable VITE_API_URL must match your backend URL exactly!

## 6. Environment Variable in Vercel (Copy-Paste Ready)

In Vercel dashboard: **Project Settings → Environment Variables**

Create new variable:
```
Key:   VITE_API_URL
Value: https://aria-lite-backend-XXXXX.onrender.com
```

(Replace XXXXX with YOUR Render service ID)

## 7. Test Frontend

After Vercel deployment completes:

```bash
# Open in browser (takes 10-15 seconds to load initially)
https://aria-lite.vercel.app

# Or with custom domain:
https://your-custom-domain.com
```

## 8. Verify Full Connection

In the deployed application:
1. Enter ticket: "scale ec2 from 2 to 8"
2. Click Submit
3. Wait 2-5 seconds
4. Should see analysis with decision gate

## Issues? Quick Fixes

### Backend not found:

```bash
# Verify backend URL works
curl -v https://aria-lite-backend-XXXXX.onrender.com/health

# Check Render logs for errors
# (Render Dashboard → Services → [Your service] → Logs)
```

### Frontend shows "Backend unreachable":

```bash
# In Vercel, check environment variables
# Project Settings → Environment Variables
# Should have: VITE_API_URL = https://aria-lite-backend-XXXXX.onrender.com

# Then redeploy
# Deployments → [Latest] → Redeploy
```

### Slow response (20-30 seconds):

This is normal for Render free tier first request.
Subsequent requests will be faster (~1-2 seconds).

## Local Testing with Deployed Backend

To test frontend locally against deployed backend:

```bash
cd frontend

# Set backend URL and start dev server
VITE_API_URL=https://aria-lite-backend-XXXXX.onrender.com npm run dev

# Open http://localhost:5174 in browser
```

## Verify All Systems

```bash
# 1. Test backend
echo "Testing backend..."
curl -s https://aria-lite-backend-XXXXX.onrender.com/health | jq .

# 2. Test API
echo "Testing backend API..."
curl -s -X POST https://aria-lite-backend-XXXXX.onrender.com/process_ticket \
  -H "Content-Type: application/json" \
  -d '{"ticket": "test"}' | jq '.gate'

# 3. Test frontend (just check status)
echo "Testing frontend..."
curl -s -I https://aria-lite.vercel.app | head -1

# All should succeed
```

## URLs Summary

After deployment, you'll have:

```
Frontend:  https://aria-lite.vercel.app
Backend:   https://aria-lite-backend-XXXXX.onrender.com

(Replace XXXXX with your unique Render service ID)
```

## Deployment Status Tracking

```bash
# Check both services are live
echo "=== Frontend ==="
curl -s -o /dev/null -w "Status: %{http_code}\n" https://aria-lite.vercel.app

echo "=== Backend ==="
curl -s -o /dev/null -w "Status: %{http_code}\n" https://aria-lite-backend-XXXXX.onrender.com/health

# Both should return 200
```

## Support Resources

| Issue | Resource |
|-------|----------|
| Render deployment | https://render.com/docs |
| Vercel deployment | https://vercel.com/docs |
| Backend/API issues | Check Render logs |
| Frontend/build issues | Check Vercel logs |
| API client code | `frontend/src/lib/api.ts` |

## Next: Production Optimization

Once deployed and working:

1. Monitor error logs for 24 hours
2. Test with real users
3. Consider domain upgrade
4. Set up monitoring/alerting (if needed)
5. Update backups/disaster recovery

For full details, see [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md)
