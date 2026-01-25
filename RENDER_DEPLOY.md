# Render Deployment Guide (Demo)

Quick deployment for 3-week demo. Total time: ~30 minutes.

## Prerequisites

- GitHub repo pushed with latest code
- Neo4j AuraDB credentials (you have these)
- Google API key for Gemini (you have this)

## Step 1: Deploy Backend (15 min)

1. Go to [render.com](https://render.com) → Sign up/Login with GitHub

2. Click **New** → **Web Service**

3. Connect your GitHub repo: `Document-Graph-Representation`

4. Configure:
   | Setting | Value |
   |---------|-------|
   | Name | `taxlaw-backend` |
   | Region | `Singapore` |
   | Branch | `feat/add-frontend-and-docs` (or `main`) |
   | Runtime | `Python 3` |
   | Build Command | `pip install -r requirements-api.txt` |
   | Start Command | `gunicorn api.main:app --bind 0.0.0.0:$PORT --workers 2 --worker-class uvicorn.workers.UvicornWorker --timeout 300` |
   | Plan | `Free` (or Starter $7/mo for faster) |

5. Add **Environment Variables** (click "Advanced"):
   ```
   NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
   NEO4J_CLIENT_ID=your_client_id
   NEO4J_CLIENT_SECRET=your_client_secret
   GOOGLE_API_KEY=your_gemini_key
   JWT_SECRET=any-random-string-for-demo
   HF_HUB_DISABLE_SYMLINKS=1
   CORS_ORIGINS=https://taxlaw-frontend.onrender.com
   ```

6. Click **Create Web Service**

7. Wait for build (~10-15 min first time due to PyTorch/sentence-transformers)

8. Note your backend URL: `https://taxlaw-backend.onrender.com`

## Step 2: Deploy Frontend (10 min)

1. Click **New** → **Static Site**

2. Connect same repo

3. Configure:
   | Setting | Value |
   |---------|-------|
   | Name | `taxlaw-frontend` |
   | Branch | `feat/add-frontend-and-docs` |
   | Build Command | `cd frontend && npm ci && npm run build` |
   | Publish Directory | `frontend/dist` |

4. Add **Environment Variables**:
   ```
   VITE_API_URL=https://taxlaw-backend.onrender.com
   VITE_ENABLE_GRAPH_VIEW=true
   VITE_ENABLE_ANNOTATIONS=true
   ```

5. Click **Create Static Site**

6. Add **Rewrite Rule** (in Settings → Redirects/Rewrites):
   | Source | Destination | Action |
   |--------|-------------|--------|
   | `/*` | `/index.html` | Rewrite |

## Step 3: Update CORS (2 min)

1. Go to backend service → Environment

2. Update `CORS_ORIGINS` with your actual frontend URL:
   ```
   CORS_ORIGINS=https://taxlaw-frontend.onrender.com
   ```

3. Click **Save Changes** (auto-redeploys)

## Step 4: Test

```bash
# Health check
curl https://taxlaw-backend.onrender.com/api/health

# Open frontend
open https://taxlaw-frontend.onrender.com
```

## Environment Variables Reference

### Backend (Required)
| Variable | Description | Example |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j AuraDB connection string | `neo4j+s://xxx.databases.neo4j.io` |
| `NEO4J_CLIENT_ID` | Neo4j OAuth client ID | `xxxxxxxx` |
| `NEO4J_CLIENT_SECRET` | Neo4j OAuth client secret | `xxxxxxxx` |
| `GOOGLE_API_KEY` | Gemini API key | `AIza...` |
| `JWT_SECRET` | Any random string | `demo-secret-key-123` |
| `CORS_ORIGINS` | Frontend URL(s), comma-separated | `https://taxlaw-frontend.onrender.com` |

### Backend (Optional)
| Variable | Description | Default |
|----------|-------------|---------|
| `HF_HUB_DISABLE_SYMLINKS` | Fix for HuggingFace on some systems | `1` |

### Frontend (Build-time)
| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `https://taxlaw-backend.onrender.com` |
| `VITE_ENABLE_GRAPH_VIEW` | Show graph visualization | `true` |
| `VITE_ENABLE_ANNOTATIONS` | Enable annotations feature | `true` |

## Demo Day Tips

1. **Wake up the backend** 5 minutes before demo (free tier sleeps after 15 min inactivity)
   ```bash
   curl https://taxlaw-backend.onrender.com/api/health
   ```

2. **Pre-upload documents** the day before if using upload feature

3. **Test the full flow** morning of demo:
   - Open frontend
   - Ask a question
   - View graph
   - Toggle between vector/graph retrieval

## Troubleshooting

### Build fails on sentence-transformers
Add to environment:
```
PYTHON_VERSION=3.11.0
```

### CORS errors
Check `CORS_ORIGINS` matches your frontend URL exactly (including https://)

### 502 Bad Gateway on first request
Free tier cold starts take 30-60 seconds. Wait and retry.

### Frontend routes return 404
Ensure rewrite rule `/* → /index.html` is configured.

## Cost

| Service | Plan | Cost |
|---------|------|------|
| Backend | Free | $0 (sleeps after 15min) |
| Backend | Starter | $7/mo (always on) |
| Frontend | Static | Free |

**For demo: Free tier is fine.** Just wake it up before presenting.
