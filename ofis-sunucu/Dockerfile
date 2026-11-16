FROM node:22-slim
WORKDIR /app
COPY server.js ./
COPY public ./public
ENV PORT=3000
EXPOSE 3000
USER node
CMD ["node", "server.js"]
