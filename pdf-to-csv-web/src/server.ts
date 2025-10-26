import express from 'express';
import cors from 'cors';
import path from 'path';
import { setRoutes } from './routes/index';

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// serve a static test page if you add public/index.html
app.use(express.static(path.join(__dirname, '..', 'public')));

setRoutes(app);

const PORT = process.env.PORT || 3000;
app.listen(Number(PORT), () => {
  console.log(`Server listening on http://localhost:${PORT}`);
});