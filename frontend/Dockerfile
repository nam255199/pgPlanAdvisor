FROM node:22-alpine

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 5173
CMD ["/start.sh"]
