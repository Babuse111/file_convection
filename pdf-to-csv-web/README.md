# PDF to CSV Web Application

This project is a web application that allows users to upload PDF files and convert them to CSV format without any additional columns. The application is built using TypeScript and Express.

## Features

- Upload PDF files
- Convert PDF files to CSV format
- No additional columns added during conversion

## Project Structure

```
pdf-to-csv-web
├── src
│   ├── server.ts               # Entry point of the application
│   ├── routes
│   │   └── index.ts            # Defines application routes
│   ├── controllers
│   │   └── uploadController.ts  # Handles file uploads and conversions
│   ├── services
│   │   └── pdfToCsvService.ts   # Logic for converting PDF to CSV
│   ├── utils
│   │   └── csvBuilder.ts        # Utility for building CSV strings
│   └── types
│       └── index.ts            # Type definitions
├── public
│   ├── index.html              # Main HTML file
│   ├── app.js                  # Client-side JavaScript
│   └── styles.css              # Styles for the web application
├── tests
│   └── pdfToCsv.test.ts        # Unit tests for the conversion service
├── package.json                 # npm configuration
├── tsconfig.json               # TypeScript configuration
├── .gitignore                  # Git ignore file
└── README.md                   # Project documentation
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   ```

2. Navigate to the project directory:
   ```
   cd pdf-to-csv-web
   ```

3. Install the dependencies:
   ```
   npm install
   ```

4. Start the server:
   ```
   npm start
   ```

5. Open your browser and go to `http://localhost:3000` to access the application.

## Usage

- Use the provided form on the main page to upload a PDF file.
- After uploading, the application will convert the PDF to CSV format.
- The resulting CSV file will be available for download.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.