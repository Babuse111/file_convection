import { Request, Response } from 'express';
import fs from 'fs/promises';
import path from 'path';
import { convertBufferToCsv } from '../services/pdfToCsvService';

export default class UploadController {
  public async handleUpload(req: Request, res: Response) {
    try {
      if (!req.file) {
        return res.status(400).json({ error: 'No file uploaded. Use form field name "file".' });
      }

      const uploadedPath = req.file.path;
      const buffer = await fs.readFile(uploadedPath);
      const csv = await convertBufferToCsv(buffer);

      // cleanup uploaded file
      try { await fs.unlink(uploadedPath); } catch { /* ignore */ }

      const base = path.parse(req.file.originalname).name || 'output';
      res.setHeader('Content-Type', 'text/csv; charset=utf-8');
      res.setHeader('Content-Disposition', `attachment; filename="${base}.csv"`);
      res.send(csv);
    } catch (err) {
      console.error('Conversion error:', err);
      res.status(500).json({ error: 'Conversion failed', detail: String(err) });
    }
  }
}