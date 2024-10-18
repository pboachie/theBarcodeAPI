//src/slices/barcodeSlice.js

import { createSlice } from '@reduxjs/toolkit';

const initialState = {
  barcodeType: 'code128',
  barcodeText: 'Change Me!',
  barcodeWidth: 200,
  barcodeHeight: 100,
  showText: true,
  barcodeUrl: '',
  isLoading: false,
  apiCallUrl: '',
  imageFormat: 'PNG',
  dpi: 300,
  error: null,
  rateLimit: {
    requests: 0,
    remaining: 0,
    reset: 0,
  },
  isLimitExceeded: false,
};

export const barcodeSlice = createSlice({
  name: 'barcode',
  initialState,
  reducers: {
    setBarcodeType: (state, action) => {
      state.barcodeType = action.payload;
    },
    setBarcodeText: (state, action) => {
      state.barcodeText = action.payload;
    },
    setBarcodeWidth: (state, action) => {
      state.barcodeWidth = action.payload;
    },
    setBarcodeHeight: (state, action) => {
      state.barcodeHeight = action.payload;
    },
    setShowText: (state, action) => {
      state.showText = action.payload;
    },
    setBarcodeUrl: (state, action) => {
      state.barcodeUrl = action.payload;
    },
    setIsLoading: (state, action) => {
      state.isLoading = action.payload;
    },
    setApiCallUrl: (state, action) => {
      state.apiCallUrl = action.payload;
    },
    setImageFormat: (state, action) => {
      state.imageFormat = action.payload;
    },
    setDpi: (state, action) => {
      state.dpi = action.payload;
    },
    setError: (state, action) => {
      state.error = action.payload;
    },
    setRateLimit: (state, action) => {
      state.rateLimit = action.payload;
    },
    setIsLimitExceeded: (state, action) => {
      state.isLimitExceeded = action.payload;
    },
  },
});

export const {
  setBarcodeType,
  setBarcodeText,
  setBarcodeWidth,
  setBarcodeHeight,
  setShowText,
  setBarcodeUrl,
  setIsLoading,
  setApiCallUrl,
  setImageFormat,
  setDpi,
  setError,
  setRateLimit,
  setIsLimitExceeded,
} = barcodeSlice.actions;

export default barcodeSlice.reducer;
