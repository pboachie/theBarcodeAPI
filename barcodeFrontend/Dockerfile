# Use an official Node.js runtime as a parent image
FROM node:18-bullseye AS base

# Build argument for version
ARG VERSION_ARG=0.0.0-dockerfile-default
ENV NEXT_PUBLIC_APP_VERSION=${VERSION_ARG}

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# Install jq for JSON processing
RUN apt-get update && apt-get install -y jq --no-install-recommends && rm -rf /var/lib/apt/lists/*

# Install project dependencies
RUN npm install

# Update npm to the latest version
RUN npm install -g npm@latest

# Copy the rest of the application code
COPY . .

# Build the Next.js application
RUN npm run build

# Expose port 3000 (default for Next.js)
EXPOSE 3000

# Command to run the application
CMD ["npm", "start"]
