# Deployment Guide - CEO's Scenes Media Pipeline

## ✅ Deployment Readiness Checklist

Your application is **READY** for cloud deployment! Here's what's in place:

- ✅ Production-optimized Dockerfile with multi-stage build
- ✅ Health check endpoint (`/api/health`)
- ✅ Environment variables configured
- ✅ Static file serving (React build)
- ✅ Docker Compose for local testing
- ✅ .gitignore to prevent junk files
- ✅ All dependencies declared (Node.js, Python, FFmpeg)
- ✅ Persistent volume mounts for media files

---

## 🚀 Deployment Options

### Option 1: Railway (Recommended - Easiest)

**Why Railway?**
- Free tier available ($5 credit/month)
- Automatic deployments from GitHub
- Built-in domain & HTTPS
- Easy environment variables
- Good for prototypes and demos

**Steps:**

1. **Prepare Repository**
```bash
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video
git init
git add .
git commit -m "Initial commit - Media Pipeline"
```

2. **Push to GitHub**
```bash
# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/media-pipeline.git
git branch -M main
git push -u origin main
```

3. **Deploy on Railway**
- Go to [railway.app](https://railway.app)
- Click "New Project" → "Deploy from GitHub repo"
- Select your repository
- Railway will auto-detect the Dockerfile
- Click "Deploy"

4. **Configure**
- Railway will automatically set `PORT` environment variable
- Your app will be live at `https://your-app.railway.app`

**Cost:** FREE up to 500 hours/month (~$5 credit)

---

### Option 2: Render (Good Alternative)

**Why Render?**
- Free tier with 750 hours/month
- Auto-scaling
- Custom domains
- Good uptime

**Steps:**

1. **Push code to GitHub** (same as Railway step 1-2)

2. **Deploy on Render**
- Go to [render.com](https://render.com)
- Click "New +" → "Web Service"
- Connect your GitHub repository
- Configure:
  - **Name:** media-pipeline
  - **Environment:** Docker
  - **Region:** Choose nearest to you
  - **Instance Type:** Free (or Starter for $7/mo)

3. **Environment Variables** (optional)
```
PORT=5000
NODE_ENV=production
```

4. **Deploy**
- Click "Create Web Service"
- Render will build and deploy
- Live at `https://media-pipeline.onrender.com`

**Cost:** FREE (with spin-down after inactivity) or $7/mo for always-on

---

### Option 3: Google Cloud Run (Scalable)

**Why Cloud Run?**
- Pay only for what you use
- Auto-scales to zero
- Can handle production traffic
- $0 for low traffic

**Steps:**

1. **Install Google Cloud SDK**
```bash
# macOS
brew install google-cloud-sdk

# Initialize
gcloud init
```

2. **Build and Push Docker Image**
```bash
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video

# Set project ID
export PROJECT_ID=your-gcp-project-id
export IMAGE_NAME=media-pipeline

# Build
docker build -t gcr.io/$PROJECT_ID/$IMAGE_NAME .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/$IMAGE_NAME
```

3. **Deploy to Cloud Run**
```bash
gcloud run deploy media-pipeline \
  --image gcr.io/$PROJECT_ID/$IMAGE_NAME \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --port 5000
```

4. **Access**
- Cloud Run will provide a URL: `https://media-pipeline-xxx.run.app`

**Cost:** 
- First 2 million requests/month: FREE
- ~$0.05 per hour of usage
- Great for sporadic usage

---

### Option 4: AWS Elastic Beanstalk

**Why Elastic Beanstalk?**
- Managed AWS infrastructure
- Easy to scale
- Integrates with other AWS services

**Steps:**

1. **Install EB CLI**
```bash
pip install awsebcli
```

2. **Initialize**
```bash
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video
eb init -p docker media-pipeline --region us-east-1
```

3. **Create Environment**
```bash
eb create production-env
```

4. **Deploy Updates**
```bash
eb deploy
```

5. **Access**
```bash
eb open
```

**Cost:** Starts at ~$10-20/month (t2.micro instance)

---

### Option 5: DigitalOcean App Platform

**Why DigitalOcean?**
- Simple interface
- Predictable pricing
- Good documentation

**Steps:**

1. **Push to GitHub** (same as Railway)

2. **Create App**
- Go to [digitalocean.com/products/app-platform](https://www.digitalocean.com/products/app-platform)
- Click "Create App"
- Connect GitHub repository
- DigitalOcean will detect Dockerfile

3. **Configure**
- Select instance size (Basic $5/mo or Pro $12/mo)
- Set environment variables if needed
- Click "Launch App"

**Cost:** $5-12/month

---

### Option 6: Heroku (Classic Choice)

**Why Heroku?**
- Developer-friendly
- Easy deploys with Git
- Good for MVPs

**Steps:**

1. **Install Heroku CLI**
```bash
brew tap heroku/brew && brew install heroku
```

2. **Login and Create App**
```bash
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video
heroku login
heroku create media-pipeline
```

3. **Set Stack to Container**
```bash
heroku stack:set container -a media-pipeline
```

4. **Deploy**
```bash
git push heroku main
```

5. **Open**
```bash
heroku open
```

**Cost:** 
- Free tier discontinued
- Basic: $7/month
- Standard: $25/month

---

## 🧪 Testing Locally with Docker

Before deploying, test locally:

```bash
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video

# Build the image
docker build -t media-pipeline .

# Run with docker-compose
docker-compose up

# Or run manually
docker run -p 5000:5000 \
  -v $(pwd)/input_images:/app/input_images \
  -v $(pwd)/output_images:/app/output_images \
  media-pipeline

# Test
open http://localhost:5000
```

---

## 🔐 Environment Variables (Optional)

For production, you may want to add:

```bash
# Node environment
NODE_ENV=production

# Port (usually set by platform)
PORT=5000

# Optional: API keys for future integrations
# GOOGLE_DRIVE_API_KEY=xxx
# AWS_ACCESS_KEY=xxx
```

---

## 📊 Recommended: Railway (For You)

**Best choice for your use case:**

1. **Easy Setup** - Just connect GitHub and deploy
2. **Free Tier** - Start for free, $5/month credit
3. **Auto-deploys** - Push to GitHub = auto-deploy
4. **Built-in HTTPS** - Secure by default
5. **No DevOps** - Focus on features, not infrastructure

### Quick Start with Railway:

```bash
# 1. Push to GitHub
cd /Users/piyush.s_int/Documents/CEO\'s\ Scenes/image-to-video
git init
git add .
git commit -m "Initial commit"
gh repo create media-pipeline --public
git push -u origin main

# 2. Go to railway.app
# 3. "New Project" → "Deploy from GitHub"
# 4. Select your repo
# 5. DONE! ✅
```

---

## 🛠️ Post-Deployment

After deploying:

1. **Test the app** - Navigate to your deployment URL
2. **Upload a test image** - Verify processing works
3. **Check logs** - Ensure no errors
4. **Monitor usage** - Watch resource consumption
5. **Set up monitoring** - Most platforms have built-in metrics

---

## 💰 Cost Comparison

| Platform | Free Tier | Paid Tier | Best For |
|----------|-----------|-----------|----------|
| Railway | $5 credit/mo | $5-20/mo | Getting started |
| Render | 750 hrs/mo | $7/mo | Hobby projects |
| Cloud Run | 2M requests | Pay-per-use | Scalability |
| DigitalOcean | No | $5/mo | Simplicity |
| AWS EB | 1 yr free tier | $10-20/mo | Enterprise |
| Heroku | No | $7/mo | Classic |

---

## 🚨 Important Notes

1. **FFmpeg is included** in the Dockerfile - no manual setup needed
2. **Volumes are configured** for persistent file storage
3. **Health checks** ensure your app stays running
4. **Auto-restart** on crashes (depending on platform)
5. **HTTPS is automatic** on most platforms

---

## 🎯 Next Steps

1. Choose a deployment platform (Railway recommended)
2. Push code to GitHub
3. Deploy (takes 5-10 minutes)
4. Test your live app
5. Share the URL! 🎉

Need help? Check the platform-specific docs or run:
```bash
# Railway
railway login && railway init

# Render
render help

# Cloud Run
gcloud run deploy --help
```

---

## 🔄 CI/CD (Optional)

For automatic deployments on every Git push, most platforms support:
- **Railway** - Auto-deploy on push (built-in)
- **Render** - Auto-deploy on push (built-in)
- **Others** - Set up GitHub Actions

---

**Your app is production-ready! 🚀**

