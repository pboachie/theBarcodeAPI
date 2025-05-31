# Use an official Node.js runtime as a parent image
FROM node:18-alpine AS base

# Build argument for version
ARG VERSION_ARG=0.0.0-dockerfile-default
ENV NEXT_PUBLIC_APP_VERSION=${VERSION_ARG}

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json (or yarn.lock if used)
COPY package.json package-lock.json ./

# Install project dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the Next.js application
RUN npm run build

# Expose port 3000 (default for Next.js)
EXPOSE 3000

# Command to run the application
CMD ["npm", "start"]
