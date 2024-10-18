// src/app/store.js

import { configureStore } from '@reduxjs/toolkit';
import barcodeReducer from '../slices/barcodeSlice';

export const store = configureStore({
  reducer: {
    barcode: barcodeReducer,
  },
});
