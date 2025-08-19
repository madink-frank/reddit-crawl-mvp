// Vercel Serverless Function - System Logs
import { db } from './database.js';

export default async function handler(req, res) {
  // CORS 헤더 설정
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  
  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }
  
  try {
    if (req.method === 'GET') {
      // Get logs
      const { limit = 50 } = req.query;
      const logs = db.getLogs(parseInt(limit));
      
      res.status(200).json({
        success: true,
        data: {
          logs: logs.map(log => ({
            id: log.id,
            message: log.message,
            type: log.type,
            timestamp: log.timestamp
          })),
          count: logs.length
        },
        timestamp: new Date().toISOString()
      });
      
    } else if (req.method === 'POST') {
      // Add log
      const { message, type = 'info' } = req.body || {};
      
      if (!message) {
        return res.status(400).json({
          success: false,
          error: 'Message is required'
        });
      }
      
      const logEntry = db.addLog(message, type);
      
      res.status(200).json({
        success: true,
        data: logEntry
      });
      
    } else if (req.method === 'DELETE') {
      // Clear logs (simulate by adding a clear message)
      db.addLog('System logs cleared by user', 'info');
      
      res.status(200).json({
        success: true,
        message: 'Logs cleared successfully'
      });
      
    } else {
      res.status(405).json({ success: false, error: 'Method not allowed' });
    }
    
  } catch (error) {
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
}