import pdf from 'pdf-parse';

/**
 * Simple CSV builder that escapes quotes and wraps fields when needed.
 */
function escapeCell(cell: string): string {
  const needsQuote = /[,"\r\n]/.test(cell);
  const escaped = cell.replace(/"/g, '""');
  return needsQuote ? `"${escaped}"` : escaped;
}

function getSegmentStarts(line: string): number[] {
  const starts: number[] = [];
  for (let i = 0; i < line.length; i++) {
    if (line[i] !== ' ' && (i === 0 || line[i - 1] === ' ')) {
      starts.push(i);
    }
  }
  return starts;
}

/**
 * Build coarse column boundaries by clustering segment starts across all lines.
 */
function detectColumnBoundaries(lines: string[], clusterTolerance = 6): number[] {
  const allStarts: number[] = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    const starts = getSegmentStarts(line);
    for (const s of starts) allStarts.push(s);
  }
  if (allStarts.length === 0) return [];

  const unique = Array.from(new Set(allStarts)).sort((a, b) => a - b);
  const clusters: number[] = [];
  let cluster: number[] = [unique[0]];

  for (let i = 1; i < unique.length; i++) {
    const s = unique[i];
    if (s - cluster[cluster.length - 1] <= clusterTolerance) {
      cluster.push(s);
    } else {
      clusters.push(Math.min(...cluster));
      cluster = [s];
    }
  }
  clusters.push(Math.min(...cluster));
  return clusters;
}

export async function convertBufferToCsv(buffer: Buffer): Promise<string> {
  const data = await pdf(buffer);
  const text = data.text || '';

  // Preserve leading spaces (they can indicate column offsets); normalize non-breaking spaces & tabs
  const lines = text.split(/\r?\n/).map(l => l.replace(/\u00A0/g, ' ').replace(/\t/g, ' ').replace(/\u2007/g, ' ').replace(/\u202F/g, ' ').replace(/\u00A0/g, ' '));

  // detect column boundaries from text layout
  const boundaries = detectColumnBoundaries(lines);

  let rows: string[][];
  if (boundaries.length >= 2) {
    // slice each line by detected boundaries, trim cell text
    rows = lines
      .map(line => {
        if (!line.trim()) return [];
        const cols: string[] = [];
        for (let i = 0; i < boundaries.length; i++) {
          const start = boundaries[i];
          const end = i + 1 < boundaries.length ? boundaries[i + 1] : line.length;
          const raw = (start < line.length) ? line.substring(start, Math.min(end, line.length)) : '';
          cols.push(raw.trim());
        }
        // if line has extra text after last boundary, append as last column
        if (line.length > (boundaries[boundaries.length - 1] || 0)) {
          // already included in last slice via end=line.length
        }
        return cols;
      })
      .filter(c => c.length > 0);
  } else {
    // fallback to splitting on 2+ spaces (useful for simple PDFs)
    rows = lines
      .filter(l => l.trim().length > 0)
      .map(line => line.split(/\s{2,}/).map(c => c.trim()));
  }

  // ensure rows have equal number of columns by padding empties
  const maxCols = rows.reduce((m, r) => Math.max(m, r.length), 0);
  const padded = rows.map(r => {
    const copy = r.slice();
    while (copy.length < maxCols) copy.push('');
    return copy;
  });

  // build CSV string (CRLF)
  const csvLines = padded.map(cols => cols.map(escapeCell).join(','));
  return csvLines.join('\r\n') + '\r\n';
}