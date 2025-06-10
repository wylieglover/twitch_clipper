# frontend/Dockerfile
FROM cirrusci/flutter:stable AS build

WORKDIR /app
COPY . .

RUN flutter pub get
RUN flutter build web

# Use a simple web server (like nginx) to serve the built site
FROM nginx:alpine
COPY --from=build /app/build/web /usr/share/nginx/html
