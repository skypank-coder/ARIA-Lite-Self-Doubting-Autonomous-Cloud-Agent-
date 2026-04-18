# ARIA-Lite Frontend Deployment Config for Vercel

## Prerequisites
- Vercel account (https://vercel.com)
- GitHub repository with frontend code
- Deployed backend URL (from Render)

## Deployment Steps

### 1. Connect Repository to Vercel
- Go to https://vercel.com/dashboard
- Click "Add New..." → "Project"
- Import your GitHub repository
- Select the `frontend` folder as root directory

### 2. Configure Build & Deploy
- **Framework**: Vite
- **Build Command**: `npm run build`
- **Output Directory**: `dist`
- **Install Command**: `npm install`

### 3. Environment Variables
After backend is deployed on Render, go to **Deployment Settings**:

Add environment variable:
- **Key**: `VITE_API_URL`
- **Value**: Replace with your Render backend URL (e.g., `https://aria-lite-backend.onrender.com`)

This variable tells the frontend where the backend API is located.

### 4. After Deployment
- Vercel will provide a URL: `https://aria-lite.vercel.app`
- The frontend will automatically connect to the Render backend using the `VITE_API_URL` env var

## How It Works

**Local Development** (localhost):
- Frontend runs on http://localhost:5174
- Vite proxy intercepts `/api/*` requests → forwards to http://localhost:8001
- No environment variable needed

**Production** (Deployed):
- Frontend runs on https://aria-lite.vercel.app
- `VITE_API_URL` env var points to Render backend
- Frontend directly calls the deployed backend API
- No proxy needed (Vercel can't proxy to external services in production)

## CORS Considerations
- Backend has CORS enabled for all origins (`allow_origins=["*"]`)
- Frontend can safely call the backend from any domain
- No additional CORS configuration needed
