import { Router } from 'express';
import multer from 'multer';
import UploadController from '../controllers/uploadController';

const router = Router();
const uploadController = new UploadController();

// store uploads in ./uploads
const upload = multer({ dest: 'uploads/' });

export function setRoutes(app) {
    // POST /upload — accepts multipart form field "file" and returns CSV download
    app.post('/upload', upload.single('file'), uploadController.handleUpload.bind(uploadController));

    // POST /convert — alternate endpoint (same behavior)
    app.post('/convert', upload.single('file'), uploadController.handleUpload.bind(uploadController));
}