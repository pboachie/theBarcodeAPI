//src/App.js

import React from 'react';
import { Provider } from 'react-redux';
import { store } from './app/store';
import BarcodeDemo from './components/BarcodeDemo';

const App = () => {
  return (
    <Provider store={store}>
      <div className="p-4 md:p-8 max-w-6xl mx-auto bg-cream text-slate-800">
        <h1 className="text-3xl font-bold mb-6 text-center">The Barcode Api</h1>
        <BarcodeDemo />
      </div>
    </Provider>
  );
};

export default App;
