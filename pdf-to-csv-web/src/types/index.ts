export interface FileUpload {
    filename: string;
    mimetype: string;
    size: number;
}

export interface ConversionResult {
    success: boolean;
    message: string;
    data?: string; // CSV data as a string
}