import { PdfToCsvService } from '../src/services/pdfToCsvService';

describe('PdfToCsvService', () => {
    let pdfToCsvService: PdfToCsvService;

    beforeEach(() => {
        pdfToCsvService = new PdfToCsvService();
    });

    it('should convert a simple PDF to CSV correctly', async () => {
        const pdfInput = 'path/to/simple.pdf'; // Replace with actual PDF path
        const expectedCsvOutput = 'column1,column2,column3\nvalue1,value2,value3'; // Expected CSV output

        const result = await pdfToCsvService.convertPdfToCsv(pdfInput);
        
        expect(result).toEqual(expectedCsvOutput);
    });

    it('should handle empty PDF files', async () => {
        const pdfInput = 'path/to/empty.pdf'; // Replace with actual PDF path
        const expectedCsvOutput = ''; // Expected output for empty PDF

        const result = await pdfToCsvService.convertPdfToCsv(pdfInput);
        
        expect(result).toEqual(expectedCsvOutput);
    });

    it('should throw an error for invalid PDF files', async () => {
        const pdfInput = 'path/to/invalid.pdf'; // Replace with actual PDF path

        await expect(pdfToCsvService.convertPdfToCsv(pdfInput)).rejects.toThrow('Invalid PDF file');
    });
});