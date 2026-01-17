// Simple WebSocket (Socket.IO) test script
// Usage: open in browser console or include as a small HTML with script tag

(function() {
  // Replace with your server URL and a valid JWT token
  const SERVER_URL = window.TEST_WS_SERVER_URL || 'http://localhost:5000';
  const TOKEN = window.TEST_WS_TOKEN || '';

  if (!TOKEN) {
    console.warn('TEST_WS: No token provided. Set window.TEST_WS_TOKEN to a JWT string before running.');
  }

  const socket = io(SERVER_URL, {
    auth: { token: TOKEN },
    transports: ['websocket', 'polling'],
    reconnection: true,
    timeout: 10000
  });

  function log(...args) { console.log('[TEST_WS]', ...args); }


  socket.on('connect', () => {
    log('Connected', socket.id);
    // request server to authenticate
  });

  socket.on('connected', (data) => {
    log('Authenticated as', data.user_key);
  });

  socket.on('disconnect', (reason) => log('Disconnected', reason));
  socket.on('connect_error', (err) => log('Connect error', err));

  socket.on('chat:error', (err) => log('CHAT ERROR', err));
  socket.on('chat:message', (msg) => log('CHAT MESSAGE', msg));
  socket.on('chat:message:sent', (msg) => log('CHAT SENT CONFIRM', msg));
  socket.on('chat:message:delivered', (data) => log('CHAT DELIVERED', data));
  socket.on('chat:message:read', (data) => log('CHAT READ', data));

  // helper to send message
  window.testWsSendMessage = function(conversationId, content) {
    const tempId = 'temp_' + Date.now();
    const payload = {
      conversationId: conversationId,
      content: content,
      type: 'text',
      tempId: tempId
    };
    log('Sending chat:send', payload);
    socket.emit('chat:send', payload);
  };

  window.testWsPing = function() { socket.emit('ping'); };

  window.testWs = socket;
  log('TEST_WS: ready. Use testWsSendMessage(convId, "hello")');
})();

