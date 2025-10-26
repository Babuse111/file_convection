export function buildCsv(data: any[]): string {
    const csvRows: string[] = [];

    // Extract headers
    const headers = Object.keys(data[0]);
    csvRows.push(headers.join(','));

    // Extract data rows
    for (const row of data) {
        const values = headers.map(header => {
            const escaped = ('' + row[header]).replace(/"/g, '\\"');
            return `"${escaped}"`;
        });
        csvRows.push(values.join(','));
    }

    return csvRows.join('\n');
}