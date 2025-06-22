# 🎨 barcodeFrontend

This is the frontend for the Barcode Generation platform, built with Next.js, TypeScript, and Tailwind CSS.

## ✨ Features

- **Modern UI**: Sleek and responsive user interface.
- **Real-time Previews**: See barcode changes as you type.
- **Multiple Format Support**: User-friendly selection of barcode types.
- **Customization**: Options for size, color, and other parameters.

## 🛠️ Technology Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Radix UI Components (or shadcn/ui if that's the case)
- **State Management**: React Hooks / Context API
- **API Communication**: Fetch API / React Query / SWR (as appropriate)

## 🚀 Getting Started

### Prerequisites

- Node.js (version specified in `package.json` or latest LTS, e.g., 18.x or 20.x)
- npm or yarn

### Local Development

1.  **Navigate to frontend directory:**
    ```bash
    cd barcodeFrontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```

3.  **Run the development server:**
    ```bash
    npm run dev
    # or
    # yarn dev
    ```
    The application will typically be available at `http://localhost:3000`.

### Building for Production

To create a production build:

```bash
npm run build
# or
# yarn build
```
This will generate an optimized build in the `.next` folder. To run this build:
```bash
npm start
# or
# yarn start
```

## 📁 Project Structure

```
barcodeFrontend/
├── app/                # Next.js App Router (pages, layouts)
├── components/         # Reusable UI components
├── lib/                # Utility functions, hooks, config
├── public/             # Static assets (images, fonts)
├── styles/             # Global styles (if any beyond Tailwind)
├── package.json        # Project dependencies and scripts
├── next.config.js      # Next.js configuration
├── tsconfig.json       # TypeScript configuration
└── tailwind.config.ts  # Tailwind CSS configuration
```

## Versioning

The application version is displayed in the footer and is sourced from the `NEXT_PUBLIC_APP_VERSION` environment variable. This variable is set during the Docker build process, originating from the `PROJECT_VERSION` defined in the root `.env` file and passed via Docker Compose.

## 🔗 API Connection

The frontend connects to the `barcodeApi` service. The API URL is typically configured via an environment variable `NEXT_PUBLIC_API_URL`. When running via Docker Compose, this is set to `http://barcodeApi:8000` (or the configured API port). For local development outside Docker, ensure the backend API is running and accessible.
