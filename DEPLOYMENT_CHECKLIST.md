# Quick Deployment Checklist

## Prerequisites
- [ ] GitHub repository with code pushed
- [ ] Render account created (https://render.com)
- [ ] Vercel account created (https://vercel.com)

## Backend Deployment (Render)

- [ ] Navigate to https://render.com/dashboard
- [ ] Create new Web Service → Connect GitHub
- [ ] Configure:
  - Root Directory: `backend`
  - Runtime: Python 3.11
  - Build: `pip install -r requirements.txt`
  - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- [ ] Deploy
- [ ] Copy deployed URL in format: `https://aria-lite-backend-XXXXX.onrender.com`
- [ ] Test health endpoint: `/health`
- [ ] Test API: `/process_ticket` POST endpoint

## Frontend Deployment (Vercel)

- [ ] Navigate to https://vercel.com/dashboard
- [ ] Create new Project → Import GitHub repo
- [ ] Configure:
  - Root Directory: `frontend`
  - Framework: Vite
  - Build: `npm run build`
  - Output: `dist`
- [ ] Before deploying, set Environment Variables:
  - Key: `VITE_API_URL`
  - Value: Your Render backend URL
  - Scope: Production
- [ ] Deploy
- [ ] Copy frontend URL: `https://aria-lite.vercel.app`

## Post-Deployment Testing

- [ ] Backend health check works
- [ ] Backend API responds to POST requests
- [ ] Frontend loads at Vercel URL
- [ ] Frontend connects to Render backend
- [ ] Submit test ticket in frontend
- [ ] Verify response returns gate decision

## Files to Review

Backend:
- `backend/render.yaml` - Render configuration
- `backend/RENDER_DEPLOYMENT.md` - Detailed steps
- `backend/requirements.txt` - Python dependencies

Frontend:
- `frontend/vercel.json` - Vercel configuration
- `frontend/VERCEL_DEPLOYMENT.md` - Detailed steps
- `frontend/src/lib/api.ts` - API client with env var support
- `frontend/vite.config.ts` - Vite config

Root:
- `DEPLOYMENT_GUIDE.md` - Complete guide with troubleshooting

## Environment Variables

Frontend needs:
- `VITE_API_URL`: Your Render backend URL (set in Vercel)

Backend:
- No custom env vars (PORT is set by Render automatically)

## Support

If you encounter issues:
1. Check Render logs: Service → Logs tab
2. Check Vercel logs: Deployments → Click deployment
3. Review browser DevTools (Network tab) for failed requests
4. Verify environment variables are set correctly
5. Test endpoints with curl before going to frontend
