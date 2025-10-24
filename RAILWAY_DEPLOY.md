# Railway Deployment Guide 🚂

## ✅ Pre-Deployment Checklist

All these files are ready:
- ✅ `Dockerfile` - Updated with proper COPY paths
- ✅ `.dockerignore` - Optimized to exclude only unnecessary files
- ✅ `railway.json` - Railway-specific configuration
- ✅ `backend/package.json` - Backend dependencies
- ✅ `frontend/package.json` - Frontend dependencies
- ✅ Health check endpoint at `/api/health`

---

## 🚀 Deploy to Railway (3 Steps)

### Step 1: Push to GitHub

```bash
cd "/Users/piyush.s_int/Documents/CEO's Scenes/image-to-video"

# Initialize git if not already done
git init

# Add all files
git add .

# Commit
git commit -m "Production-ready: Media pipeline with Docker and Railway config"

# Create GitHub repo and push
# Option A: Using GitHub CLI
gh repo create media-pipeline --public --source=. --push

# Option B: Manually
# 1. Go to github.com
# 2. Create new repository "media-pipeline"
# 3. Copy the commands and run:
git remote add origin https://github.com/YOUR_USERNAME/media-pipeline.git
git branch -M main
git push -u origin main
```

---

### Step 2: Deploy on Railway

1. **Go to [railway.app](https://railway.app)**
2. **Sign in** with your GitHub account
3. **Click "New Project"**
4. **Select "Deploy from GitHub repo"**
5. **Choose** your `media-pipeline` repository
6. **Railway will automatically:**
   - Detect the Dockerfile
   - Read railway.json configuration
   - Build the Docker image
   - Deploy your application
   - Assign a URL

---

### Step 3: Test Your Deployment

Once deployed (takes 5-10 minutes):

1. **Open the URL** Railway provides (looks like: `https://media-pipeline-production-xxxx.up.railway.app`)

2. **Test the dashboard:**
   - Should see the sidebar with Download/Images/Videos tabs
   - Toggle dark mode 🌙
   - Try uploading a test image

3. **Check health:**
   ```
   https://your-app.railway.app/api/health
   ```
   Should return:
   ```json
   {"status":"ok","timestamp":"2024-10-24T..."}
   ```

---

## 🔧 Configuration (Optional)

Railway automatically sets:
- `PORT` - Dynamic port assigned by Railway
- `NODE_ENV=production` - Set by our Dockerfile

No additional environment variables needed!

---

## 📊 Monitoring

**Railway Dashboard shows:**
- Build logs
- Deployment status
- Resource usage (CPU, Memory)
- Request logs
- Health check status

**Access logs:**
1. Click on your deployment
2. Go to "Deployments" tab
3. Click on active deployment
4. View real-time logs

---

## 💰 Cost

**Free Tier:**
- $5 credit per month
- ~500 hours of usage
- Perfect for testing and demos

**Pricing after free tier:**
- $0.000231/GB-sec for memory
- $0.000463/vCPU-sec for CPU
- Usually $5-20/month for moderate usage

---

## 🐛 Troubleshooting

### Build fails with "package.json not found"
- **Solution:** Already fixed! Updated `.dockerignore` and `Dockerfile`

### Build succeeds but app doesn't start
- Check Railway logs for errors
- Verify health check is working
- Ensure PORT environment variable is used

### App starts but can't process videos
- FFmpeg is included in the Docker image
- Check logs for Python errors
- Verify `requirements.txt` is correct

### Out of memory
- Upgrade to a larger instance in Railway settings
- Currently using 512MB RAM by default

---

## 🔄 Updates & Redeployment

**Every time you push to GitHub:**
1. Railway automatically detects the push
2. Rebuilds the Docker image
3. Redeploys your application
4. Zero downtime deployment

```bash
# Make changes to your code
# Then:
git add .
git commit -m "Your update message"
git push

# Railway will auto-deploy! 🚀
```

---

## 📱 Custom Domain (Optional)

1. In Railway dashboard, click "Settings"
2. Go to "Domains"
3. Click "Add Custom Domain"
4. Enter your domain (e.g., `media.yoursite.com`)
5. Add CNAME record to your DNS:
   ```
   CNAME media -> your-app.railway.app
   ```

---

## ✅ Success Indicators

Your deployment is successful when:
- ✅ Build completes without errors
- ✅ Health check returns 200 OK
- ✅ Dashboard loads at your Railway URL
- ✅ Can toggle dark mode
- ✅ Can upload test files
- ✅ Processing works (try a small image)

---

## 🎯 Next Steps After Deployment

1. **Share the URL** with your team
2. **Test all features:**
   - Download media from URLs
   - Upload files via drag & drop
   - Process images (3:4 ratio)
   - Process videos (10MB limit)
   - Search processed files
3. **Monitor usage** in Railway dashboard
4. **Set up backups** (download processed files periodically)
5. **Consider upgrading** if you need more resources

---

## 📞 Need Help?

- **Railway Docs:** https://docs.railway.app
- **Railway Discord:** https://discord.gg/railway
- **Check build logs** in Railway dashboard
- **Verify files:** Make sure all files committed to GitHub

---

**Your app is ready to deploy! Follow the 3 steps above.** 🚀

