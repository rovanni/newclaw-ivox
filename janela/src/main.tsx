import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
// Fontes no próprio build (licença OFL): nada é buscado em servidor de terceiros.
import '@fontsource/exo-2/400.css';
import '@fontsource/exo-2/500.css';
import '@fontsource/exo-2/600.css';
import '@fontsource/exo-2/700.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import './estilo.css';
import { App } from './App';

createRoot(document.getElementById('raiz')!).render(<StrictMode><App /></StrictMode>);
