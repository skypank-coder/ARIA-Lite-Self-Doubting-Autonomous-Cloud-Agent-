# ARIA-Lite Backend Deployment Config for Render

## Prerequisites
- Render account (https://render.com)
- GitHub repository with backend code

## Deployment Steps

### 1. Create Web Service on Render
- Go to https://render.com/dashboard
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Select the repository
- Choose `backend` folder as the root directory

### 2. Configure Service
- **Name**: aria-lite-backend
- **Runtime**: Python 3.11
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Region**: Choose closest to users
- **Instance Type**: Free tier is sufficient for development

### 3. Environment Variables
No additional env vars needed - Render automatically sets `PORT`

### 4. After Deployment
- Render will provide a URL: `https://aria-lite-backend.onrender.com`
- Copy this URL for frontend configuration

## Notes
- Free tier has cold starts (30 seconds) when inactive
- No custom domain required unless desired
- CORS is already enabled in FastAPI app
