const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const multer = require('multer');

const app = express();
app.use(cors());
app.use(bodyParser.json());

const projectRoot = path.join(__dirname, '..');
const inputImagesDir = path.join(projectRoot, 'input_images');
const inputVideosDir = path.join(projectRoot, 'input_videos');

for (const dir of [inputImagesDir, inputVideosDir]) {
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
}

function runPython(args, res) {
  const proc = spawn('python3', args, { cwd: projectRoot });
  let stdout = '';
  let stderr = '';
  proc.stdout.on('data', data => { stdout += data.toString(); });
  proc.stderr.on('data', data => { stderr += data.toString(); });
  proc.on('close', code => {
    res.json({ code, stdout, stderr });
  });
}

function runScript(cmd, args, res) {
  const proc = spawn(cmd, args, { cwd: projectRoot });
  let stdout = '';
  let stderr = '';
  proc.stdout.on('data', data => { stdout += data.toString(); });
  proc.stderr.on('data', data => { stderr += data.toString(); });
  proc.on('close', code => {
    res.json({ code, stdout, stderr });
  });
}

function runScriptWithCallback(cmd, args, onComplete) {
  const proc = spawn(cmd, args, { cwd: projectRoot });
  let stdout = '';
  let stderr = '';
  proc.stdout.on('data', data => { stdout += data.toString(); });
  proc.stderr.on('data', data => { stderr += data.toString(); });
  proc.on('close', code => {
    onComplete(code, stdout, stderr);
  });
}

function runDownload(type, urls = [], res) {
  const args = ['download.py'];
  const flag = type === 'image' ? '--image-url' : '--video-url';
  urls.forEach(url => {
    args.push(flag, url);
  });
  runScript('python3', args, res);
}

function runDownloadProcess(type, url, res) {
  const flag = type === 'image' ? '--image-url' : '--video-url';
  const args = ['download.py', flag, url];
  runScriptWithCallback('python3', args, (code, stdout, stderr) => {
    if (code !== 0) {
      res.status(500).json({ code, stdout, stderr });
      return;
    }
    const processArgs = type === 'image'
      ? ['image.py']
      : ['video.py', '--bulk'];
    runScriptWithCallback('python3', processArgs, (processCode, processStdout, processStderr) => {
      res.json({
        code: processCode,
        stdout: stdout + processStdout,
        stderr: stderr + processStderr,
      });
    });
  });
}

function runDownloadBulk(type, urls, autoProcess, res) {
  if (!Array.isArray(urls) || urls.length === 0) {
    res.status(400).json({ error: 'urls array is required' });
    return;
  }
  const args = ['download.py'];
  const flag = type === 'image' ? '--image-url' : '--video-url';
  urls.forEach(url => {
    args.push(flag, url);
  });
  runScriptWithCallback('python3', args, (code, stdout, stderr) => {
    if (code !== 0) {
      res.status(500).json({ code, stdout, stderr });
      return;
    }
    if (!autoProcess) {
      res.json({ code, stdout, stderr });
      return;
    }
    const processArgs = type === 'image'
      ? ['image.py']
      : ['video.py', '--bulk'];
    runScriptWithCallback('python3', processArgs, (processCode, processStdout, processStderr) => {
      res.json({
        code: processCode,
        stdout: stdout + processStdout,
        stderr: stderr + processStderr,
      });
    });
  });
}

function autodetectLatestFiles(type) {
  const directory = type === 'image' ? inputImagesDir : inputVideosDir;
  if (!fs.existsSync(directory)) return [];
  const files = fs.readdirSync(directory)
    .filter(file => !file.startsWith('.'))
    .sort((a, b) => fs.statSync(path.join(directory, b)).mtimeMs - fs.statSync(path.join(directory, a)).mtimeMs);
  return files.length ? files.slice(0, 1) : [];
}

function processAllImages(res) {
  runScriptWithCallback('python3', ['image.py'], (code, stdout, stderr) => {
    res.json({ code, stdout, stderr });
  });
}

function processAllVideos(res) {
  runScriptWithCallback('python3', ['video.py', '--bulk'], (code, stdout, stderr) => {
    res.json({ code, stdout, stderr });
  });
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const targetDir = file.mimetype.startsWith('video') ? inputVideosDir : inputImagesDir;
    cb(null, targetDir);
  },
  filename: (req, file, cb) => {
    const sanitized = file.originalname.replace(/[^a-zA-Z0-9._-]/g, '_');
    cb(null, sanitized);
  },
});

const upload = multer({ storage });

// Trigger full download for images and videos
app.post('/api/download', (req, res) => {
  runScript('python3', ['download.py'], res);
});

// Download specific image URLs
app.post('/api/download-image', (req, res) => {
  const { url } = req.body || {};
  if (!url) {
    res.status(400).json({ error: 'url is required' });
    return;
  }
  runDownloadProcess('image', url, res);
});

app.post('/api/download-image-noauto', (req, res) => {
  const { url } = req.body || {};
  if (!url) {
    res.status(400).json({ error: 'url is required' });
    return;
  }
  runDownload('image', [url], res);
});

// Download specific video URLs
app.post('/api/download-video', (req, res) => {
  const { url } = req.body || {};
  if (!url) {
    res.status(400).json({ error: 'url is required' });
    return;
  }
  runDownloadProcess('video', url, res);
});

app.post('/api/download-video-noauto', (req, res) => {
  const { url } = req.body || {};
  if (!url) {
    res.status(400).json({ error: 'url is required' });
    return;
  }
  runDownload('video', [url], res);
});

app.post('/api/download-images-bulk', (req, res) => {
  const { urls = [], autoProcess = false } = req.body || {};
  runDownloadBulk('image', urls, autoProcess, res);
});

app.post('/api/download-videos-bulk', (req, res) => {
  const { urls = [], autoProcess = false } = req.body || {};
  runDownloadBulk('video', urls, autoProcess, res);
});

// Upload images/videos
app.post('/api/upload-media', upload.array('files', 100), (req, res) => {
  const uploaded = (req.files || []).map(file => ({
    originalName: file.originalname,
    filename: file.filename,
    mimetype: file.mimetype,
    size: file.size,
    destination: path.relative(projectRoot, file.destination),
  }));
  res.json({ uploaded });
});

// Trigger image processing pipeline
app.post('/api/process-images', (req, res) => {
  runScript('python3', ['image.py'], res);
});

// Trigger video processing pipeline; accept optional 'bulk' flag in request body
app.post('/api/process-videos', (req, res) => {
  const args = ['video.py'];
  if (req.body.bulk) args.push('--bulk');
  if (req.body.jobs) { args.push('--jobs', String(req.body.jobs)); }
  runScript('python3', args, res);
});

// Process all staged media (images and videos)
app.post('/api/process-all', (req, res) => {
  runScriptWithCallback('python3', ['image.py'], (imageCode, imageStdout, imageStderr) => {
    runScriptWithCallback('python3', ['video.py', '--bulk'], (videoCode, videoStdout, videoStderr) => {
      res.json({
        image: { code: imageCode, stdout: imageStdout, stderr: imageStderr },
        video: { code: videoCode, stdout: videoStdout, stderr: videoStderr },
      });
    });
  });
});

// List available input videos
app.get('/api/input-videos', (req, res) => {
  const proc = spawn('python3', ['video.py', '--list-json'], { cwd: projectRoot });
  let stdout = '';
  let stderr = '';
  proc.stdout.on('data', data => { stdout += data.toString(); });
  proc.stderr.on('data', data => { stderr += data.toString(); });
  proc.on('close', code => {
    if (code === 0) {
      try {
        const parsed = JSON.parse(stdout || '[]');
        res.json(parsed);
      } catch (error) {
        res.status(500).json({ error: 'Failed to parse video list', details: error.message, raw: stdout });
      }
    } else {
      res.status(500).json({ error: 'Failed to list videos', stderr });
    }
  });
});

// Process a specific selection of videos using video.py
app.post('/api/process-videos-selection', (req, res) => {
  const { filenames = [], jobs, bulk } = req.body || {};
  if (bulk) {
    const args = ['video.py', '--bulk'];
    if (jobs) args.push('--jobs', String(jobs));
    runPython(args, res);
    return;
  }
  if (!Array.isArray(filenames) || filenames.length === 0) {
    res.status(400).json({ error: 'filenames array is required' });
    return;
  }
  const args = ['video.py', '--files-json', JSON.stringify(filenames)];
  if (jobs) args.push('--jobs', String(jobs));
  runPython(args, res);
});

// Serve processed output folders for download
app.use('/output_images', express.static(path.join(projectRoot, 'output_images')));
app.use('/output_videos', express.static(path.join(projectRoot, 'output_videos')));

// Endpoint to list processed images
app.get('/api/output-images', (req, res) => {
  const dir = path.join(projectRoot, 'output_images');
  fs.readdir(dir, (err, files) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(files.filter(f => !f.startsWith('.')));
  });
});

// Endpoint to list processed videos
app.get('/api/output-videos', (req, res) => {
  const dir = path.join(projectRoot, 'output_videos');
  fs.readdir(dir, (err, files) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(files.filter(f => !f.startsWith('.')));
  });
});

// Serve React build in production
if (process.env.NODE_ENV === 'production') {
  const reactBuildPath = path.join(projectRoot, 'frontend', 'build');
  app.use(express.static(reactBuildPath));
  app.get('*', (req, res) => {
    res.sendFile(path.join(reactBuildPath, 'index.html'));
  });
}

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() });
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Backend server listening on port ${PORT}`));