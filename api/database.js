// Simple JSON-based database for Vercel deployment
import fs from 'fs';
import path from 'path';

const DATA_DIR = '/tmp';
const DB_FILE = path.join(DATA_DIR, 'reddit_data.json');

// Initialize database structure
const initDB = () => {
  const defaultData = {
    posts: [],
    stats: {
      total_posts: 0,
      ai_processed: 0,
      published: 0,
      collected_today: 0,
      success_rate: 0,
      last_updated: new Date().toISOString()
    },
    jobs: [],
    logs: []
  };
  
  try {
    if (!fs.existsSync(DB_FILE)) {
      fs.writeFileSync(DB_FILE, JSON.stringify(defaultData, null, 2));
    }
    return defaultData;
  } catch (error) {
    console.log('Using in-memory database (filesystem not writable)');
    return defaultData;
  }
};

// Read database
const readDB = () => {
  try {
    if (fs.existsSync(DB_FILE)) {
      const data = fs.readFileSync(DB_FILE, 'utf8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.log('Error reading database, using default data');
  }
  return initDB();
};

// Write database
const writeDB = (data) => {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(data, null, 2));
    return true;
  } catch (error) {
    console.log('Error writing database:', error.message);
    return false;
  }
};

// Database operations
export const db = {
  // Get all stats
  getStats: () => {
    const data = readDB();
    return data.stats;
  },
  
  // Update stats
  updateStats: (newStats) => {
    const data = readDB();
    data.stats = { ...data.stats, ...newStats, last_updated: new Date().toISOString() };
    writeDB(data);
    return data.stats;
  },
  
  // Add post
  addPost: (post) => {
    const data = readDB();
    const newPost = {
      id: `post_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      ...post,
      created_at: new Date().toISOString(),
      processed: false,
      published: false
    };
    
    data.posts.push(newPost);
    data.stats.total_posts = data.posts.length;
    data.stats.last_updated = new Date().toISOString();
    
    writeDB(data);
    return newPost;
  },
  
  // Get posts
  getPosts: (limit = 10) => {
    const data = readDB();
    return data.posts.slice(-limit).reverse();
  },
  
  // Update post
  updatePost: (postId, updates) => {
    const data = readDB();
    const postIndex = data.posts.findIndex(p => p.id === postId);
    
    if (postIndex !== -1) {
      data.posts[postIndex] = { ...data.posts[postIndex], ...updates };
      
      // Recalculate stats
      const processedCount = data.posts.filter(p => p.processed).length;
      const publishedCount = data.posts.filter(p => p.published).length;
      
      data.stats.ai_processed = processedCount;
      data.stats.published = publishedCount;
      data.stats.success_rate = data.stats.total_posts > 0 ? 
        Math.round((publishedCount / data.stats.total_posts) * 100) : 0;
      data.stats.last_updated = new Date().toISOString();
      
      writeDB(data);
      return data.posts[postIndex];
    }
    return null;
  },
  
  // Add job
  addJob: (job) => {
    const data = readDB();
    const newJob = {
      id: `job_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      ...job,
      created_at: new Date().toISOString(),
      status: 'pending'
    };
    
    data.jobs.push(newJob);
    writeDB(data);
    return newJob;
  },
  
  // Get jobs
  getJobs: (status = null) => {
    const data = readDB();
    if (status) {
      return data.jobs.filter(j => j.status === status);
    }
    return data.jobs;
  },
  
  // Update job
  updateJob: (jobId, updates) => {
    const data = readDB();
    const jobIndex = data.jobs.findIndex(j => j.id === jobId);
    
    if (jobIndex !== -1) {
      data.jobs[jobIndex] = { ...data.jobs[jobIndex], ...updates };
      writeDB(data);
      return data.jobs[jobIndex];
    }
    return null;
  },
  
  // Add log
  addLog: (message, type = 'info') => {
    const data = readDB();
    const logEntry = {
      id: `log_${Date.now()}`,
      message,
      type,
      timestamp: new Date().toISOString()
    };
    
    data.logs.push(logEntry);
    
    // Keep only last 100 logs
    if (data.logs.length > 100) {
      data.logs = data.logs.slice(-100);
    }
    
    writeDB(data);
    return logEntry;
  },
  
  // Get logs
  getLogs: (limit = 50) => {
    const data = readDB();
    return data.logs.slice(-limit).reverse();
  },
  
  // Initialize with sample data
  initSampleData: () => {
    const data = readDB();
    
    if (data.posts.length === 0) {
      // Add some sample posts
      const samplePosts = [
        {
          title: 'Apple accidentally leaked its own top secret hardware in software code',
          subreddit: 'technology',
          score: 1250,
          comments: 234,
          url: 'https://reddit.com/r/technology/sample1',
          content: 'Apple has accidentally revealed details about upcoming hardware...'
        },
        {
          title: 'Volkswagen locks horsepower behind paid subscription',
          subreddit: 'cars',
          score: 890,
          comments: 156,
          url: 'https://reddit.com/r/cars/sample2',
          content: 'Volkswagen is now offering performance upgrades through subscriptions...'
        },
        {
          title: 'AI experts return from China stunned: The U.S. grid is so weak',
          subreddit: 'artificial',
          score: 2100,
          comments: 445,
          url: 'https://reddit.com/r/artificial/sample3',
          content: 'AI researchers visiting China report significant infrastructure gaps...'
        }
      ];
      
      samplePosts.forEach(post => {
        const newPost = db.addPost(post);
        
        // Simulate some processing
        if (Math.random() > 0.5) {
          db.updatePost(newPost.id, { 
            processed: true, 
            ai_summary: `AI-generated summary for: ${post.title}` 
          });
          
          if (Math.random() > 0.3) {
            db.updatePost(newPost.id, { 
              published: true, 
              ghost_url: `https://american-trends.ghost.io/sample-${newPost.id}` 
            });
          }
        }
      });
      
      db.addLog('Sample data initialized', 'success');
    }
    
    return data;
  }
};

// Initialize database on import
initDB();